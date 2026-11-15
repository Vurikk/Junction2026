const assert = require('node:assert/strict');
const path = require('node:path');
const Module = require('node:module');
const { buildSync } = require('esbuild');
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');
const root = path.resolve(__dirname, '..');
const built = buildSync({ entryPoints: [path.join(root, 'src/PlanningForm.jsx')], bundle: true,
  platform: 'node', format: 'cjs', write: false, external: ['react'] });
const component = new Module(path.join(root, 'planning-check.cjs'));
component.filename = path.join(root, 'planning-check.cjs');
component.paths = Module._nodeModulePaths(root);
component._compile(built.outputFiles[0].text, component.filename);
const html = renderToStaticMarkup(React.createElement(component.exports.default, {
  customer: 'fixture', assumptions: { horizon_days: 30, available_funds_eur: '987654.00', confirmed_income_eur: '500.00',
    upcoming_essential_bills_eur: '1200.00', everyday_spending_eur: '50.00', voluntary_goal_contribution_eur: '999.00' },
  api: () => { throw new Error('No network in static render'); }, money: value => value == null ? 'Not available' : String(value),
}));
assert.doesNotMatch(html, /987654/);
assert.doesNotMatch(html, /name="available_funds_eur"/);
for (const value of ['500.00', '1200.00', '50.00', '999.00']) assert.ok(!html.includes(`value="${value}"`));
assert.match(html, /type="range" min="1" max="12" step="1" value="3"/);
assert.match(html, /suggested target, not money already held/);
assert.match(html, /Recorded daily average/);
assert.match(html, /class="money-input"/);
assert.match(html, /Income left for other savings/);
assert.match(html, /not chosen/);
assert.match(html, /not a safe-to-spend amount/);
assert.doesNotMatch(html, /Latest recorded balance \(read-only\)/);
assert.match(html, /Exclude food already in the bills and food total/);
assert.match(html, /disabled="">Confirm and calculate/);
assert.match(html, /historical draft/);
assert.match(html, /Loading historical defaults/);
console.log('Planning form checks passed: stale saved amounts ignored, goals blank, three-month slider, unknown balance and food caveat.');
const saved = renderToStaticMarkup(React.createElement(component.exports.default, {
  customer: 'fixture', hasSavedPlan: true,
  assumptions: { horizon_days: 45, repeat_plan: true, confirmed_income_eur: '500.00', upcoming_essential_bills_eur: '1200.00',
    emergency_reserve_eur: '700.00', voluntary_goal_contribution_eur: '25.00', weekly_budget_eur: '90.00', monthly_budget_eur: '360.00' },
  api: () => { throw new Error('No network'); }, money: value => value == null ? 'Not available' : String(value),
}));
for (const value of ['500.00', '1200.00', '700.00', '25.00', '90.00', '360.00', '45']) {
  assert.ok(saved.includes(`value="${value}"`), value);
}
assert.match(saved, /custom amount below/);
assert.match(saved, /name="repeat_plan"[^>]*checked/);
console.log('Confirmed-plan restoration checks passed: salary, bills, reserve, goal limit, targets, horizon and repeat.');
