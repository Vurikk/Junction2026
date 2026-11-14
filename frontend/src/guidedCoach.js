// Guided turns read local Python results. They never call the paid Coach endpoint or write a plan.
export function guidedStarter(question) {
  const normalized = question.trim().toLowerCase().replace(/\s+/g, ' ').replace(/[?!.]+$/, '').trim();
  if (['what could i save on', 'where could i save the most', 'how can i save money'].includes(normalized)) {
    return { type: 'savings' };
  }
  if (['are my goals realistic', 'can i reach my goals'].includes(normalized)) return { type: 'goals' };
  if (normalized === 'help with everyday habits') return { type: 'habits' };
  return null;
}

export async function loadGuidedTurn(api, customer, action, signal) {
  const get = resource => api(`customers/${customer}/${resource}`, { credentials: 'same-origin', signal });
  if (action.type === 'savings' || action.type === 'reduction') {
    const query = new URLSearchParams({ reduction_percent: String(action.percent ?? 10) });
    if (action.month) query.set('month', action.month);
    const data = await get(`savings-opportunities?${query}`);
    return { guided: { ...action, data } };
  }
  if (action.type === 'goals') {
    const [goals, analysis] = await Promise.all([get('goals'), get('goal-analysis')]);
    return { guided: { ...action, goals, analysis } };
  }
  return { guided: action };
}

export const planningLabels = {
  available_funds_eur: 'Money you can access now',
  confirmed_income_eur: 'Additional income confirmed during the plan',
  upcoming_essential_bills_eur: 'Essential bills and debt payments during the plan',
  emergency_reserve_eur: 'Emergency money to keep protected',
  everyday_spending_eur: 'Everyday costs, excluding those bills',
  voluntary_goal_contribution_eur: 'The most you want to put toward goals during the plan',
};

export const feasibilityLabels = {
  unknown: 'Cannot assess yet',
  funded: 'Covered within this planning period',
  conditional: 'Depends on repeating this plan',
  not_funded_in_horizon: 'Not fully covered in this planning period',
};
