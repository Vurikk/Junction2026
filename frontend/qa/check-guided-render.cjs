const assert = require('node:assert/strict');
const path = require('node:path');
const Module = require('node:module');
const { buildSync } = require('esbuild');
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');
const root = path.resolve(__dirname, '..');
const compiled = buildSync({ entryPoints: [path.join(root, 'src/GuidedCoach.jsx')], bundle: true,
  platform: 'node', format: 'cjs', write: false, external: ['react'] });
const component = new Module(path.join(root, 'guided-check.cjs'));
component.filename = path.join(root, 'guided-check.cjs');
component.paths = Module._nodeModulePaths(root);
component._compile(compiled.outputFiles[0].text, component.filename);
const render = (turn, active = true) => renderToStaticMarkup(React.createElement(component.exports.default, {
  turn, active, busy: false, money: value => value == null ? 'Not available' : `EUR ${value}`,
}));
const data = { status: 'available', source_period: { start: '2026-07-01', end: '2026-07-31' },
  reduction_percent: 20, candidates: [{ category: 'restaurants', baseline_spending_eur: 95.04,
    hypothetical_spending_eur: 76.03, potential_reduction_eur: 19.01 }], note: 'Eligible purchases only.' };
const reduction = render({ type: 'reduction', category: 'restaurants', data });
for (const value of ['2026-07-01', '2026-07-31', 'EUR 95.04', 'EUR 76.03', 'EUR 19.01', 'Is that realistic for me?']) {
  assert.ok(reduction.includes(value), value);
}
assert.match(reduction, /not a forecast/);
assert.doesNotMatch(render({ type: 'reduction', category: 'restaurants', data }, false), /<button/);
const unavailable = render({ type: 'savings', data: { status: 'unavailable_period', candidates: [], source_period: null } });
assert.match(unavailable, /no usable full recorded month/);
assert.doesNotMatch(unavailable, /EUR 0/);
const noCandidates = render({ type: 'savings', data: { ...data, status: 'no_candidates', candidates: [] } });
assert.match(noCandidates, /does not mean you have no other spending/);
const goal = { id: 'goal-1', name: 'Emergency cushion', priority: 'critical', amount_eur: '200.00' };
const analysis = { status: 'insufficient_data', coach_message: 'Confirm your plan first.', savings_capacity_eur: null,
  shortfall_eur: null, missing_inputs: ['available_funds_eur'], assumptions: { horizon_days: 30, repeat_plan: false },
  ordered_goal_ids: ['goal-1'], allocations: [{ goal_id: 'goal-1', allocated_eur: null, feasibility: 'unknown', completion_periods: 2 }] };
const unknown = render({ type: 'goals', goals: [goal], analysis, fromSavings: true });
for (const text of ['Emergency cushion', 'Cannot assess yet', 'Not available', 'not added the historical reduction',
  'What do I need to confirm?', 'Confirm your plan first.']) assert.ok(unknown.includes(text), text);
assert.doesNotMatch(unknown, /2 plan periods/);
const estimated = render({ type: 'goals', goals: [goal], analysis: { ...analysis, status: 'estimated',
  assumptions: { horizon_days: 30, repeat_plan: true },
  allocations: [{ goal_id: 'goal-1', allocated_eur: 0, feasibility: 'conditional', completion_periods: 2 }] } });
assert.match(estimated, /EUR 0/);
assert.match(estimated, /2 plan periods of 30 days, if capacity and contribution repeat/);
assert.match(render({ type: 'goals', goals: [], analysis }), /no saved goals yet/);
assert.match(render({ type: 'inputs', missing: ['available_funds_eur'], horizon: 30 }), /Money you can access now/);
assert.match(render({ type: 'habit', habit: 'pause' }), /general ideas, not calculated savings/);
console.log('Guided rendering checks passed: historical figures, missing data, stale actions, goals and conditional timing.');
