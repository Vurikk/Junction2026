const assert = require('node:assert/strict');
const path = require('node:path');
const Module = require('node:module');
const { buildSync } = require('esbuild');
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');
const root = path.resolve(__dirname, '..');
const compiled = buildSync({ entryPoints: [path.join(root, 'src/CoachResult.jsx')], bundle: true,
  platform: 'node', format: 'cjs', write: false, external: ['react'] });
const component = new Module(path.join(root, 'coach-cards-check.cjs'));
component.filename = path.join(root, 'coach-cards-check.cjs');
component.paths = Module._nodeModulePaths(root);
component._compile(compiled.outputFiles[0].text, component.filename);
const render = card => renderToStaticMarkup(React.createElement(component.exports.default, {
  card, money: value => value == null ? 'Not available' : `EUR ${Number(value).toFixed(2)}`,
}));
const dates = { start: '2026-07-01', end: '2026-07-31' };
const ranking = render({ type: 'category_spending', data: { category: 'all', source_period: dates,
  spending_eur: 25, categories: [{ category: 'housing', spending_eur: 20 }], other_spending_eur: 5 } });
for (const text of ['Where your money went', '2026-07-01', 'housing', 'EUR 25.00', 'EUR 20.00', 'EUR 5.00']) {
  assert.ok(ranking.includes(text), text);
}
const reduction = render({ type: 'category_reduction', data: { source_period: dates, category: 'restaurants',
  reduction_percent: 100, baseline_spending_eur: 95.04, hypothetical_spending_eur: 0, potential_reduction_eur: 95.04 } });
assert.match(reduction, /EUR 0.00/);
assert.match(reduction, /not money already saved/);
const unknown = render({ type: 'spending_comparison', data: { status: 'insufficient_data',
  comparison: null, baseline: null, difference_eur: null } });
assert.match(unknown, /Not available/);
assert.doesNotMatch(unknown, /EUR 0.00/);
const comparison = render({ type: 'spending_comparison', data: { status: 'above', comparison: { ...dates, spending_eur: 20 },
  baseline: { start: '2026-01-01', end: '2026-06-30', average_spending_eur: 10 }, difference_eur: 10 } });
for (const text of ['2026-07-01', '2026-07-31', '2026-01-01', '2026-06-30', 'EUR 10.00']) assert.ok(comparison.includes(text));
console.log('Coach card rendering checks passed: ranking, exact reduction, zero, unknown, source dates and caveats.');
