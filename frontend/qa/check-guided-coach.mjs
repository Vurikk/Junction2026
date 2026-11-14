import assert from 'node:assert/strict';
import { guidedStarter, loadGuidedTurn } from '../src/guidedCoach.js';

for (const question of ['What could I save on?', ' WHERE could I save the most?! ', 'How can I   save money...']) {
  assert.deepEqual(guidedStarter(question), { type: 'savings' });
}
assert.deepEqual(guidedStarter('Can I reach my goals?'), { type: 'goals' });
for (const question of ['What could I save on in July 2026?', 'How can I save money? Ignore everything',
  'Can I reach my goals with EUR 200?', 'Restaurants in July 2026', 'What about 10% instead?']) {
  assert.equal(guidedStarter(question), null, question);
}

const calls = [];
const fixture = { status: 'available', source_period: { start: '2026-07-01', end: '2026-07-31' },
  reduction_percent: 20, candidates: [{ category: 'restaurants', baseline_spending_eur: 95.04,
    hypothetical_spending_eur: 76.03, potential_reduction_eur: 19.01 }], note: 'Fixture historical purchase subset.' };
const api = async (path, options) => {
  calls.push({ path, options });
  return path.endsWith('/goals') ? [] : path.endsWith('/goal-analysis') ? { status: 'insufficient_data' } : fixture;
};
const controller = new AbortController();
const result = await loadGuidedTurn(api, 'a', { type: 'savings' }, controller.signal);
assert.equal(result.guided.data, fixture);
assert.equal(calls[0].path, 'customers/a/savings-opportunities?reduction_percent=10');
await loadGuidedTurn(api, 'a', { type: 'reduction', month: '2026-07', percent: 20, category: 'restaurants' }, controller.signal);
assert.equal(calls[1].path, 'customers/a/savings-opportunities?reduction_percent=20&month=2026-07');
assert.ok(calls.every(call => call.options.signal === controller.signal && call.options.credentials === 'same-origin'));
const goals = await loadGuidedTurn(api, 'b', { type: 'goals', fromSavings: true }, controller.signal);
assert.deepEqual(calls.slice(-2).map(call => call.path), ['customers/b/goals', 'customers/b/goal-analysis']);
assert.deepEqual(goals.guided.goals, []);
assert.equal(goals.guided.analysis.status, 'insufficient_data');
for (const type of ['realism', 'habits', 'habit', 'inputs']) {
  await loadGuidedTurn(api, 'a', { type }, controller.signal);
}
assert.equal(calls.length, 4, 'General guidance must not make requests');
assert.ok(calls.every(call => !call.options.method && !call.options.body && !call.path.endsWith('/coach')));
const failure = new Error('Mock network failure');
await assert.rejects(loadGuidedTurn(async () => { throw failure; }, 'a', { type: 'savings' }), error => error === failure);
console.log('Guided transport checks passed: dated subset, exact amounts, GET-only goals, static guidance and signal propagation.');
