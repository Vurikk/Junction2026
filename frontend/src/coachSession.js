// IDs remain local to this mounted customer's conversation. Never persist provider credentials.
export function createCoachSession(api, customer, uuid = () => crypto.randomUUID()) {
  let initialized = false;
  let conversationId = uuid();
  const bootstrapId = uuid();
  const path = `customers/${customer}/coach`;
  async function post(body, signal) {
    return api(path, {
      method: 'POST', credentials: 'same-origin', signal,
      headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
    });
  }
  return {
    turn(question, scenario = null) {
      return { question, scenario, request_id: uuid() };
    },
    async send(turn, signal) {
      if (!initialized) {
        // Omitting conversation_id makes this a free initialization, even with an existing cookie.
        const bootstrap = await post({ question: 'Spending by category', request_id: bootstrapId }, signal);
        if (signal?.aborted) throw new DOMException('Aborted', 'AbortError');
        conversationId = bootstrap.conversation_id || conversationId;
        initialized = true;
      }
      // Keep the identical body on explicit retries, including after an uncertain network failure.
      turn.conversation_id ??= conversationId;
      const result = await post(turn, signal);
      // A missing/expired cookie returns this explicit free bootstrap result before any paid claim.
      // Retry only that condition once with the SAME body; never retry provider failures automatically.
      if (result.fallback_reason === 'session_initialized' && !signal?.aborted) return post(turn, signal);
      return result;
    },
  };
}

export function coachModeLabel(item) {
  if (item.mode === 'llm') return 'AI-assisted · Python calculations';
  return 'Rule-based explanation';
}

export function fallbackNotice(reason) {
  if (reason === 'clarification_needed') return 'Please clarify the category, period or percentage in your next message.';
  if (reason === 'unsupported_period_or_category') return 'Recorded data is unavailable for that category or period.';
  if (reason === 'request_conflict') return 'This message could not be replayed safely. It was not automatically resubmitted.';
  if (reason === 'session_limit') return 'This browser session has reached its conversation limit.';
  if (['session_initialized', 'conversation_required'].includes(reason)) {
    return 'The conversation could not finish starting. No automatic new request will be made.';
  }
  if (reason === 'unsupported_topic') return 'This topic uses the local Coach. Try a supported spending question or guided preview.';
  if (reason === 'budget_exhausted') return 'AI budget reached. Showing the rule-based answer.';
  if (['provider_error', 'timeout', 'invalid_model_output', 'billing_uncertain'].includes(reason)) {
    return 'AI is unavailable. Showing the rule-based answer.';
  }
  if (reason === 'concurrency_limit') {
    return 'Coach could not process this message while another was active. This result is final for this request.';
  }
  if (['rate_limited', 'request_in_progress'].includes(reason)) {
    return 'Coach is busy. You can retry this same message.';
  }
  if (reason === 'privacy_blocked') return 'Please ask without personal details or pasted transaction records.';
  if (reason === 'conversation_mismatch') return 'This conversation is unavailable. Switch profiles to start a new one.';
  return null;
}
