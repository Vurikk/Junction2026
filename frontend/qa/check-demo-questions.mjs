import assert from 'node:assert/strict';
import { loadDemoQuestions, canFollowUpReduction } from '../src/demoQuestions.js';
import { createCoachSession } from '../src/coachSession.js';

const requests = [];
const sample = { id: 'restaurant-reduction', label: 'Restaurants · July 2026 · 20%',
  question: 'What if I reduce restaurant spending in July 2026 by 20%?' };
const api = async (path, options) => {
  requests.push({ path, options });
  if (path.endsWith('/coach-demo-prompts')) return { questions: [sample], note: 'Recorded periods; hypothetical reductions.' };
  const body = JSON.parse(options.body);
  return { conversation_id: body.conversation_id || 'fixture-conversation', request_id: body.request_id,
    fallback_reason: body.conversation_id ? null : 'session_initialized' };
};
const signal = new AbortController().signal;
const result = await loadDemoQuestions(api, 'customer-a', signal);
assert.deepEqual(result.questions, [sample]);
assert.equal(requests.length, 1);
assert.equal(requests[0].path, 'customers/customer-a/coach-demo-prompts');
assert.equal(requests[0].options.method, undefined);
assert.equal(requests[0].options.body, undefined);
assert.equal(requests[0].options.credentials, 'same-origin');
assert.equal(requests[0].options.signal, signal);
// Selecting the suggestion uses the existing normal turn/deduplication workflow.
let count = 0;
const session = createCoachSession(api, 'customer-a', () => `fixture-${++count}`);
const turn = session.turn(result.questions[0].question);
await session.send(turn);
assert.equal(JSON.parse(requests.at(-1).options.body).question, sample.question);
const firstBody = requests.at(-1).options.body;
await session.send(turn);
assert.equal(requests.at(-1).options.body, firstBody);
await loadDemoQuestions(api, 'customer-b', signal);
assert.equal(requests.at(-1).path, 'customers/customer-b/coach-demo-prompts');
const malformed = await loadDemoQuestions(async () => ({ questions: [null, { ...sample, question: '' }, sample] }), 'a');
assert.deepEqual(malformed.questions, [sample]);
const four = ['overview', 'save-most', 'comparison', 'restaurants'].map(id => ({ ...sample, id }));
assert.deepEqual((await loadDemoQuestions(async () => ({ questions: four }), 'a')).questions, four);
await assert.rejects(loadDemoQuestions(async () => { throw new Error('offline'); }, 'a'), /offline/);
const reduction = { conversation_id: 'fixture-conversation', cards: [{ type: 'category_reduction', data: {} }] };
assert.equal(canFollowUpReduction(reduction), true);
assert.equal(canFollowUpReduction({ ...reduction, mode: 'rule_based', fallback_reason: 'provider_error' }), true);
for (const fallback_reason of ['request_in_progress', 'ledger_unavailable', 'clarification_needed', 'demo_guidance']) {
  assert.equal(canFollowUpReduction({ ...reduction, fallback_reason }), false);
}
assert.equal(canFollowUpReduction({ ...reduction, conversation_id: null }), false);
assert.equal(canFollowUpReduction({ ...reduction, cards: [{ type: 'category_spending', data: {} }] }), false);
console.log('Demo questions checks passed: read-only loading, customer scope, validation, existing send/retry identity.');
