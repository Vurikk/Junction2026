import React, { useEffect, useState } from 'react';

export default function SafeToSpend(props) {
  if (!Array.isArray(props.goals)) return <section className="allowance-summary">
    <h2>Safe to spend</h2><p role="status">Goals unavailable.</p>
  </section>;
  if (!props.goals.length) return <GoalPrompt onAddGoal={props.onAddGoal} />;
  return <SpendingEstimate key={props.customer} {...props} />;
}

function GoalPrompt({ onAddGoal }) {
  return <section className="allowance-summary"><h2>Safe to spend</h2>
    <p>Create a goal to see your spending estimate.</p>
    <button className="text-button" onClick={onAddGoal}>Create a goal</button>
  </section>;
}

function SpendingEstimate({ customer, api, money, refreshKey, onAddGoal }) {
  const [range, setRange] = useState('Day');
  const [estimate, setEstimate] = useState(null);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState('');
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setBusy(true); setError(''); setEstimate(null);
    if (!api || !customer) { setBusy(false); return; }
    api(`customers/${customer}/automatic-demo-budget`, { signal: controller.signal })
      .then(value => { if (!controller.signal.aborted) setEstimate(value); })
      .catch(e => { if (!controller.signal.aborted) setError(e.message); })
      .finally(() => { if (!controller.signal.aborted) setBusy(false); });
    return () => controller.abort();
  }, [api, customer, refreshKey, retry]);
  if (estimate?.status === 'needs_goal') return <GoalPrompt onAddGoal={onAddGoal} />;
  return <section className="allowance-summary"><div className="allowance-heading"><h2>Extra spending estimate</h2>
    <div className="allowance-toggle">{['Day', 'Week'].map(value => <button key={value}
      aria-pressed={range === value} onClick={() => setRange(value)}>{value}</button>)}</div></div>
    <strong className="allowance-amount">{busy ? 'Checking…' : money(error || estimate?.status !== 'estimated' ? null
      : range === 'Day' ? estimate?.daily_eur : estimate?.weekly_eur)}</strong>
    <p className="fine">Above your usual spending. Historical estimate, not guaranteed money available today.</p>
    {estimate?.source_period && <p className="fine">Based on {estimate.source_period.start}–{estimate.source_period.end}.</p>}
    {estimate?.status === 'insufficient_data' && <p role="status">
      Not enough recorded income and spending across three complete months to estimate this.</p>}
    {error && <div className="error" role="alert"><p>{error}</p>
      <button disabled={busy} onClick={() => setRetry(value => value + 1)}>Try again</button></div>}
    {estimate && <details><summary>How this estimate works</summary>
      <p className="fine">{estimate.policy?.basis}</p>
      <p className="fine">Usual recorded spending is protected. Up to {estimate.policy?.reserve_income_percent}% of income
        builds a hypothetical reserve, then {estimate.policy?.goal_surplus_percent}% of the remaining surplus is offered to goals
        in Critical, Important, Flexible order.</p>
      {estimate.status === 'estimated' && <>
        <p className="fine">Monthly averages over the recorded period:</p>
        <p>Income: {money(estimate.income_eur)}</p>
        <p>Usual spending: {money(estimate.protected_spending_eur)}</p>
        <p>Reserve contribution: {money(estimate.reserve_contribution_eur)}</p>
        <p>Allocated to goals: {money(estimate.goal_allocated_eur)}</p>
        <p>Extra spending: {money(estimate.monthly_extra_eur)}</p>
      </>}
      {estimate.missing_inputs?.map(field => <p className="fine" key={field}>{missingReason(field)}</p>)}
      {estimate.limitations?.map((text, index) => <p className="fine" key={index}>{text}</p>)}
    </details>}
  </section>;
}

function missingReason(field) {
  if (field === 'three_complete_recorded_months') return 'Three complete months of recorded history are required.';
  if (field.startsWith('income_evidence:')) return `Income records missing for ${field.split(':')[1]}.`;
  if (field.startsWith('spending_evidence:')) return `Spending records missing for ${field.split(':')[1]}.`;
  if (field.startsWith('unclassified_debit_evidence:')) return `Some outgoing payments need classification for ${field.split(':')[1]}.`;
  return 'Some required banking data is unavailable.';
}
