const assert = require('node:assert/strict');
const path = require('node:path');
const Module = require('node:module');
const { buildSync } = require('esbuild');
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');
const root = path.resolve(__dirname, '..');
const compiled = buildSync({ entryPoints: [path.join(root, 'src/SafeToSpend.jsx')], bundle: true,
  platform: 'node', format: 'cjs', write: false, external: ['react'] });
const component = new Module(path.join(root, 'safe-spend-check.cjs'));
component.filename = path.join(root, 'safe-spend-check.cjs');
component.paths = Module._nodeModulePaths(root);
component._compile(compiled.outputFiles[0].text, component.filename);
const render = budget => renderToStaticMarkup(React.createElement(component.exports.default, {
  budget, assumptions: {}, onPlan() {}, money: value => value == null ? 'Not available' : `EUR ${Number(value).toFixed(2)}`,
}));
const unknown = render({ status: 'insufficient_data', daily_eur: null });
assert.match(unknown, /Not available/);
assert.doesNotMatch(unknown, /EUR 0.00|progressbar|allowance-track/);
const manual = render({ status: 'estimated', daily_eur: 0, weekly_eur: 0, assumptions: { horizon_days: 30 } });
assert.match(manual, /EUR 0.00/);
assert.match(manual, /Confirmed 30-day plan/);
assert.doesNotMatch(manual, /Complete the estimate/);
console.log('PASS: unknown versus zero, confirmed manual plan precedence, no fake usage progress.');
