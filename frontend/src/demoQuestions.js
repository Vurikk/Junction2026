// Loading suggestions is read-only. A question is sent only when the user chooses it.
export async function loadDemoQuestions(api, customer, signal) {
  const result = await api(`customers/${customer}/coach-demo-prompts`, { credentials: 'same-origin', signal });
  const questions = Array.isArray(result?.questions) ? result.questions.filter(item =>
    typeof item?.id === 'string' && typeof item.label === 'string' && typeof item.question === 'string'
    && item.label.trim() && item.question.trim() && item.question.length <= 500).slice(0, 4) : [];
  return { questions, note: typeof result?.note === 'string' ? result.note : '' };
}

// Only offer context-dependent follow-ups when the backend returned a usable, remembered selection.
export function canFollowUpReduction(result) {
  const usable = [null, undefined, 'disabled', 'provider_error', 'timeout', 'budget_exhausted',
    'billing_uncertain', 'pricing_review_expired'];
  return Boolean(result.conversation_id && usable.includes(result.fallback_reason)
    && result.cards?.some(card => card.type === 'category_reduction' && card.data));
}
