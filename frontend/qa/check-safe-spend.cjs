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
const render = goals => renderToStaticMarkup(React.createElement(component.exports.default, {
  goals, onAddGoal() {}, money: value => value == null ? 'Not available' : `EUR ${value}`,
}));
assert.match(render(undefined), /Goals unavailable/);
assert.doesNotMatch(render(undefined), /Create a goal/);
assert.match(render([]), /Create a goal/);
assert.doesNotMatch(render([]), /EUR|Checking|<input/);
assert.match(render([{ id: 'fixture' }]), /Extra spending estimate/);
assert.match(render([{ id: 'fixture' }]), /Checking/);
for (const goals of [undefined, [], [{ id: 'fixture' }]]) {
  assert.doesNotMatch(render(goals), /Complete the estimate|<input|<form|progressbar/);
}
console.log('PASS: unknown goals differ from no goals, existing goal CTA, loading and no manual form.');
