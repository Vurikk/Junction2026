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
  customer: 'fixture', assumptions: { horizon_days: 30, available_funds_eur: '987654.00', confirmed_income_eur: '123.00' },
  api: () => { throw new Error('No network in static render'); }, money: value => value == null ? 'Not available' : String(value),
}));
assert.doesNotMatch(html, /987654/);
assert.doesNotMatch(html, /name="available_funds_eur"/);
assert.match(html, /value="123.00"/);
assert.match(html, /Exclude food already in the bills and food total/);
assert.match(html, /disabled="">Confirm and calculate/);
assert.match(html, /historical draft/);
assert.match(html, /Loading historical defaults/);
console.log('Planning form checks passed: saved balance ignored, saved income retained, unknown balance blocks, food caveat.');
