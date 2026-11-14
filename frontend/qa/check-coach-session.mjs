import assert from 'node:assert/strict';
import { createCoachSession, coachModeLabel, fallbackNotice } from '../src/coachSession.js';

let count = 0;
const uuid = () => `fixture-${++count}`;
const calls = [];
let fail = false;
const api = async (path, options) => {
  const body = JSON.parse(options.body);
  calls.push({ path, body, credentials: options.credentials });
  if (!body.conversation_id) return { conversation_id: 'server-conversation', fallback_reason: 'session_initialized' };
  if (fail) throw new Error('Network failed after possible delivery');
  return { mode: 'llm', conversation_id: body.conversation_id, request_id: body.request_id, cards: [] };
};
const session = createCoachSession(api, 'customer-a', uuid);
const first = session.turn('Restaurants July 2026');
const answer = await session.send(first);
assert.equal(calls.length, 2);
assert.equal(calls[0].body.conversation_id, undefined);
assert.equal(calls[1].body.question, 'Restaurants July 2026');
assert.equal(answer.conversation_id, 'server-conversation');
assert.ok(calls.every(call => call.credentials === 'same-origin'));
const followup = session.turn('What about 10%?');
await session.send(followup);
assert.equal(calls.length, 3);
assert.equal(followup.conversation_id, first.conversation_id);
assert.notEqual(followup.request_id, first.request_id);
fail = true;
const retry = session.turn('Compare monthly spending');
await assert.rejects(session.send(retry));
const failedBody = calls.at(-1).body;
fail = false;
await session.send(retry);
assert.deepEqual(calls.at(-1).body, failedBody);
const scenario = session.turn('Preview this goal', { name: 'Fixture', amount_eur: '1', priority: 'flexible' });
await session.send(scenario);
assert.deepEqual(calls.at(-1).body.scenario, scenario.scenario);

// Customer-scoped instances bootstrap independently and never reuse the earlier request IDs.
const otherCalls = [];
const other = createCoachSession(async (path, options) => {
  const body = JSON.parse(options.body); otherCalls.push({ path, body });
  return { conversation_id: 'other-conversation' };
}, 'customer-b', uuid);
const otherTurn = other.turn('Spending by category');
await other.send(otherTurn);
assert.equal(otherTurn.conversation_id, 'other-conversation');
assert.ok(otherCalls.every(call => call.path.includes('customer-b')));
assert.notEqual(otherTurn.request_id, first.request_id);

// An abort-ignoring bootstrap must not initiate a paid turn after the component unmounts.
const abort = new AbortController();
let abortedCalls = 0;
const aborted = createCoachSession(async () => {
  abortedCalls++; abort.abort(); return { conversation_id: 'old' };
}, 'old-customer', uuid);
await assert.rejects(aborted.send(aborted.turn('Spending'), abort.signal), { name: 'AbortError' });
assert.equal(abortedCalls, 1);

// Legacy responses remain usable, and provider fallbacks never trigger hidden retries.
let legacyCalls = 0;
const legacy = createCoachSession(async () => { legacyCalls++; return { text: 'Legacy answer' }; }, 'legacy', uuid);
assert.equal((await legacy.send(legacy.turn('Spending'))).text, 'Legacy answer');
assert.equal(legacyCalls, 2);
let fallbackCalls = 0;
const fallback = createCoachSession(async () => {
  fallbackCalls++; return { conversation_id: 'fallback', mode: 'rule_based', fallback_reason: 'provider_error' };
}, 'fallback', uuid);
await fallback.send(fallback.turn('Spending'));
assert.equal(fallbackCalls, 2);
// Expired cookie bootstrap is the only bounded automatic replay; body and paid-turn ID remain unchanged.
const expiryBodies = [];
const expiry = createCoachSession(async (path, options) => {
  const body = JSON.parse(options.body); expiryBodies.push(body);
  if (expiryBodies.length <= 2) return { conversation_id: 'expiry-conversation', fallback_reason: 'session_initialized' };
  return { mode: 'rule_based', fallback_reason: 'conversation_mismatch' };
}, 'expiry', uuid);
const expiredResult = await expiry.send(expiry.turn('Spending'));
assert.equal(expiryBodies.length, 3);
assert.deepEqual(expiryBodies[1], expiryBodies[2]);
assert.equal(expiredResult.fallback_reason, 'conversation_mismatch');
assert.match(coachModeLabel({ mode: 'llm' }), /Python calculations/);
assert.match(coachModeLabel({}), /Rule-based/);
assert.match(fallbackNotice('budget_exhausted'), /budget/);
assert.match(fallbackNotice('clarification_needed'), /clarify/);
assert.match(fallbackNotice('unsupported_period_or_category'), /unavailable/);
assert.match(fallbackNotice('request_conflict'), /not automatically/);
// All non-bootstrap HTTP-200 fallback states stop after the original turn, even if a retry might later work.
for (const reason of ['timeout', 'budget_exhausted', 'request_in_progress', 'rate_limited', 'concurrency_limit', 'clarification_needed',
  'unsupported_period_or_category', 'request_conflict', 'conversation_mismatch', 'billing_uncertain']) {
  const bodies = [];
  const client = createCoachSession(async (path, options) => {
    bodies.push(JSON.parse(options.body));
    return { conversation_id: 'fixture', fallback_reason: reason, mode: 'rule_based' };
  }, 'fixture', uuid);
  const turn = client.turn('Spending');
  await client.send(turn);
  assert.equal(bodies.length, 2, reason);
  await client.send(turn);
  assert.deepEqual(bodies[2], bodies[1], reason);
}
console.log('Coach session checks passed: bootstrap, context, IDs, retries, isolation, abort, preview and fallback.');
