import assert from 'node:assert/strict';
import { categoriesFor, eligibleMonths, preferredCategory, validReduction } from '../src/reductionOptions.js';

assert.deepEqual(categoriesFor({ categories: { unknown: 1, Uncategorized: 2, Groceries: 0 } }), ['Groceries']);
assert.equal(preferredCategory({ categories: { Groceries: 1, Restaurants: 2 } }), 'Restaurants');
assert.equal(preferredCategory({ categories: { Groceries: 1 } }), 'Groceries');
assert.deepEqual(eligibleMonths({ periods: [
  { start: '2026-01-01', end: '2026-01-31', partial: true, categories: { Food: 1 } },
  { start: '2026-02-01', end: '2026-02-28', partial: false, categories: {} },
  { start: '2026-03-01', end: '2026-03-31', partial: false, categories: { Food: 1 } },
] }, '2026-03-20'), []);
for (const value of ['0', '100', '20', '0.25']) assert.ok(validReduction(value));
for (const value of ['', '-1', '101', '20.123', 'NaN']) assert.ok(!validReduction(value));

const base = process.env.QA_API || 'http://127.0.0.1:8018/api';
async function get(path) {
  const response = await fetch(`${base}/${path}`);
  assert.equal(response.status, 200);
  return response.json();
}
async function post(id, body) {
  return fetch(`${base}/customers/${id}/category-reduction`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  });
}
const customers = await get('customers');
const before = {};
for (const { customer_id: id } of customers) {
  before[id] = await Promise.all(['goals', 'assumptions', 'budget'].map(route => get(`customers/${id}/${route}`)));
}
for (const { customer_id: id } of customers) {
  const history = await get(`customers/${id}/spending-history?period=month`);
  const month = eligibleMonths(history)[0];
  assert.ok(month, `${id} has a recorded complete month`);
  const body = { category: preferredCategory(month), period: 'month', period_start: month.start, reduction_percent: '20' };
  const response = await post(id, body);
  assert.equal(response.status, 200);
  const result = await response.json();
  assert.equal(result.customer_id, id);
  assert.equal(result.source_period.start, month.start);
  assert.equal(result.goal_impact, null);
  assert.equal(result.read_only, true);
  assert.deepEqual(await (await post(id, body)).json(), result, 'repeated previews return the same result');
  const zero = await (await post(id, { ...body, reduction_percent: '0' })).json();
  assert.equal(zero.potential_reduction_eur, 0);
  assert.equal(zero.hypothetical_spending_eur, zero.baseline_spending_eur);
  const all = await (await post(id, { ...body, reduction_percent: '100' })).json();
  assert.equal(all.hypothetical_spending_eur, 0);
  assert.equal(all.potential_reduction_eur, all.baseline_spending_eur);
  assert.equal((await post(id, { ...body, reduction_percent: '101' })).status, 422);
  assert.equal((await post(id, { ...body, category: 'QA absent category' })).status, 404);
  const partial = history.periods.find(item => item.partial);
  if (partial) assert.equal((await post(id, { ...body, period_start: partial.start })).status, 422);
  console.log(`${id}: ${body.category}, ${month.start}; exact API result ${JSON.stringify(result)}`);
}
for (const { customer_id: id } of customers) {
  const after = await Promise.all(['goals', 'assumptions', 'budget'].map(route => get(`customers/${id}/${route}`)));
  assert.deepEqual(after, before[id], `${id} goals, assumptions and budget unchanged`);
}
console.log('PASS: option selection, validation, both profiles, 0/20/100%, 404/422, repeatability and non-mutation.');
