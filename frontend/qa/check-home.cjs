// Uses the existing Vite/esbuild installation. No browser or added dependencies.
const assert = require('node:assert/strict');
const path = require('node:path');
const Module = require('node:module');
const { buildSync } = require('esbuild');
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');

const root = path.resolve(__dirname, '..');
const compiled = buildSync({
  entryPoints: [path.join(root, 'src/HomeSummary.jsx')], bundle: true,
  platform: 'node', format: 'cjs', write: false, external: ['react', 'recharts'],
});
const component = new Module(path.join(root, 'home-check.cjs'));
component.filename = path.join(root, 'home-check.cjs');
component.paths = Module._nodeModulePaths(root);
component._compile(compiled.outputFiles[0].text, component.filename);
const HomeSummary = component.exports.default;
const money = value => value == null ? 'Not available' : `EUR ${Number(value).toFixed(2)}`;
const render = data => renderToStaticMarkup(React.createElement(HomeSummary, {
  data, money, openCoach() {}, onSpending() {}, onPlan() {},
}));

const unknown = render({});
assert.match(unknown, /Not available/);
assert.doesNotMatch(unknown, /EUR 0.00/);
assert.match(unknown, /comparison is unavailable/);
assert.doesNotMatch(unknown, /role="progressbar"|aria-valuenow/);

const zero = render({
  'recorded-balances': { simultaneous_total_eur: 0, total_recorded_at: '2026-09-30T12:00:00' },
  budget: { daily_eur: '0', weekly_eur: '0', status: 'estimated', assumptions: { horizon_days: 30 } },
});
assert.equal((zero.match(/EUR 0.00/g) || []).length, 1);
assert.match(zero, /2026-09-30/);
assert.doesNotMatch(zero, /allowance-track|Usage tracking unavailable/);

const separate = render({ 'recorded-balances': {
  simultaneous_total_eur: null,
  accounts: [
    { account_id: 'test-a', balance_eur: 10, recorded_at: '2026-09-29T12:00:00' },
    { account_id: 'test-b', balance_eur: null, recorded_at: null },
  ],
} });
assert.match(separate, /Account 1/);
assert.match(separate, /Account 2/);
assert.match(separate, /EUR 10.00/);
assert.match(separate, /Date unavailable/);
assert.match(separate, /Not available/);

for (const status of ['above', 'below', 'equal']) {
  const html = render({ 'spending-comparison': {
    status, comparison: { start: '2026-08-01', end: '2026-08-31', spending_eur: 0 },
    baseline: { average_spending_eur: 0, period_count: 2 }, difference_eur: 0,
  } });
  assert.match(html, /2026-08-01/);
  assert.match(html, /EUR 0.00 spent/);
  assert.doesNotMatch(html, /on track|doing well|saved progress/);
}
console.log('Home contract rendering checks passed: null, zero, separate accounts, comparisons and neutral track.');
const goals = render({ goals: [{ id: 'fixture', name: 'Fixture goal', amount_eur: 10, priority: 'critical' }] });
for (const text of ['Current goals', 'Add goal', 'Fixture goal', 'EUR 10.00', 'critical']) assert.ok(goals.includes(text));
assert.match(render({ goals: [] }), /No goals yet/);
assert.doesNotMatch(render({ goals: [] }), /Fixture goal/);
const targetHistory = { period: 'week', periods: [{ start: '2026-08-24', end: '2026-08-30', spending_eur: 10 }],
  historical_average_eur: 15, budget_target_eur: 0 };
const autoTarget = render({ 'spending-history': { ...targetHistory, target_source: 'automatic_historical' } });
assert.match(autoTarget, /Estimated plan target EUR 0.00/);
const manualTarget = render({ 'spending-history': { ...targetHistory, target_source: 'manual' } });
assert.match(manualTarget, /Target EUR 0.00/);
assert.doesNotMatch(manualTarget, /Estimated plan target/);
assert.match(render({ 'spending-history': { ...targetHistory, budget_target_eur: null } }), /Set spending target/);
console.log('PASS: automatic provenance, manual zero and unavailable chart target.');
