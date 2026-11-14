import React, { useEffect, useRef, useState } from 'react';

const labels = {
  available_funds_eur: 'Money available now',
  emergency_reserve_eur: 'Keep untouched',
  upcoming_essential_bills_eur: 'Bills due during this period',
  additional_essential_bills_eur: 'Any other bills due?',
  everyday_spending_eur: 'Everyday spending during this period',
  voluntary_goal_contribution_eur: 'Amount to set aside for goals',
};
const sources = { user: 'Your input', historical_rate: 'Historical estimate', recorded_balance: 'Recorded balance',
  historical_rate_plus_user: 'Historical estimate and your input', policy: 'Estimate policy' };

export default function SafeToSpend({ customer, api, money, budget, assumptions, onPlan, refreshKey }) {
  const [range, setRange] = useState('Day');
  const [estimate, setEstimate] = useState(null);
  const [draft, setDraft] = useState({ mode: 'current', horizon_days: 7 });
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [retryLoad, setRetryLoad] = useState(0);
  const pending = useRef(null);
  const manual = budget?.status === 'estimated';
  useEffect(() => {
    pending.current?.abort();
    if (!api || !customer || manual) { pending.current = null; setBusy(false); setError(''); return; }
    const controller = new AbortController();
    pending.current = controller; setBusy(true); setError(''); setEstimate(null);
    api(`customers/${customer}/spending-estimate`, { signal: controller.signal })
      .then(value => { if (!controller.signal.aborted) setEstimate(value); })
      .catch(e => { if (!controller.signal.aborted) setError(e.message); })
      .finally(() => { if (!controller.signal.aborted) { pending.current = null; setBusy(false); } });
    return () => controller.abort();
  }, [api, customer, manual, refreshKey, retryLoad]);
  useEffect(() => () => pending.current?.abort(), []);

  async function calculate(event) {
    event.preventDefault();
    if (pending.current) return;
    const controller = new AbortController();
    pending.current = controller; setBusy(true); setError('');
    const payload = { mode: draft.mode, horizon_days: Number(draft.horizon_days) };
    for (const key of Object.keys(labels)) if (key in draft) payload[key] = draft[key] === '' ? null : draft[key];
    try {
      const result = await api(`customers/${customer}/spending-estimate`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload), signal: controller.signal,
      });
      if (!controller.signal.aborted) { setEstimate(result); setEditing(result.status !== 'estimated'); }
    } catch (e) { if (!controller.signal.aborted) setError(e.message); }
    finally { if (!controller.signal.aborted) { pending.current = null; setBusy(false); } }
  }
  const source = manual ? budget : estimate;
  const amount = range === 'Day' ? source?.daily_eur : source?.weekly_eur;
  const missing = estimate?.missing_inputs || [];
  const fields = [...new Set([...missing, ...Object.keys(draft)
    .filter(key => ['available_funds_eur', 'emergency_reserve_eur', 'upcoming_essential_bills_eur',
      'additional_essential_bills_eur'].includes(key))])]
    .filter(key => key in labels && key !== 'voluntary_goal_contribution_eur');
  return <section className="allowance-summary"><div className="allowance-heading"><h2>Safe to spend</h2>
    <div className="allowance-toggle">{['Day', 'Week'].map(value => <button key={value}
      aria-pressed={range === value} onClick={() => setRange(value)}>{value}</button>)}</div></div>
    <strong className="allowance-amount">{busy ? 'Checking…' : money(error ? null : amount)}</strong>
    <p className="fine">{manual ? `Confirmed ${budget.assumptions.horizon_days}-day plan`
      : estimate?.mode === 'historical' ? 'Historical scenario — not today’s affordability'
        : 'Cash-only estimate — future income excluded'}</p>
    {!manual && estimate && <p className="fine">{estimate.reference_date || estimate.as_of} · {estimate.horizon_days}-day period</p>}
    {!manual && estimate?.goal_policy && <p className="fine">{estimate.goal_policy}</p>}
    {source?.shortfall_eur > 0 && <p role="alert">Bills and reserve shortfall: {money(source.shortfall_eur)}</p>}
    {error && <div className="error" role="alert"><p>{error}</p>
      {!estimate && <button disabled={busy} onClick={() => setRetryLoad(value => value + 1)}>Try loading estimate again</button>}</div>}
    {!manual && <>
      {!editing && <button className="text-button" disabled={busy || !estimate} onClick={() => setEditing(true)}>
        {amount == null ? 'Complete the estimate' : 'Review estimate inputs'}</button>}
      {editing && <form className="estimate-form" onSubmit={calculate}><fieldset disabled={busy}>
        <legend>Complete your estimate</legend>
        <p className="fine">Banking history supplies estimates where available. Blank means unknown; enter zero only when correct.</p>
        {estimate?.observations?.bills && <p className="fine">
          Historical bills: {money(estimate.observations.bills.value_eur)} over {estimate.horizon_days} days,
          based on {estimate.observations.bills.source_period?.start}–{estimate.observations.bills.source_period?.end}.
          This is not a bill due-date schedule. Confirm the full amount actually due.</p>}
        {fields.map(key => <div key={key}><label htmlFor={`estimate-${key}`}>
          {key === 'upcoming_essential_bills_eur'
            ? draft.mode === 'historical' ? `Bills in the ${draft.horizon_days}-day scenario` : `Bills due in the next ${draft.horizon_days} days`
            : key === 'available_funds_eur' && draft.mode === 'historical' ? 'Scenario funds (blank uses dated balance)' : labels[key]} (EUR)</label>
          {key === 'additional_essential_bills_eur' && <p className="fine">
            In addition to estimated housing and utilities. Include all other obligations; zero confirms there are no additions.</p>}
          <input id={`estimate-${key}`} type="number" inputMode="decimal" min="0" max="9999999999.99" step="0.01"
            value={draft[key] ?? ''} placeholder="I don’t know" onChange={e => setDraft(old => ({ ...old, [key]: e.target.value }))} />
        </div>)}
        <details><summary>Adjust detected costs or set aside for goals</summary>
          {['upcoming_essential_bills_eur', 'everyday_spending_eur', 'voluntary_goal_contribution_eur']
            .filter(key => !fields.includes(key)).map(key => <div key={key}>
              <label htmlFor={`estimate-${key}`}>{labels[key]} (EUR)</label>
              <p className="fine">{key === 'voluntary_goal_contribution_eur' ? 'Optional. No earmark when blank.'
                : `Detected estimate: ${money(estimate?.inputs?.[key]?.value_eur)}. Blank keeps the estimate.`}</p>
              <input id={`estimate-${key}`} type="number" inputMode="decimal" min="0" max="9999999999.99" step="0.01"
                value={draft[key] ?? ''} onChange={e => setDraft(old => ({ ...old, [key]: e.target.value }))} />
            </div>)}
          <label htmlFor="estimate-days">Days covered</label><input id="estimate-days" type="number" min="1" max="366" required
            value={draft.horizon_days} onChange={e => setDraft(old => ({ ...old, horizon_days: e.target.value }))} />
          <label htmlFor="estimate-mode">Estimate basis</label><select id="estimate-mode" value={draft.mode}
            onChange={e => setDraft(old => ({ ...old, mode: e.target.value }))}>
            <option value="current">Current funds</option><option value="historical">Historical scenario (not today's affordability)</option>
          </select>
        </details>
        <button className="primary" disabled={busy}>{busy ? 'Checking…' : 'Calculate estimate'}</button>
        <button type="button" className="text-button" onClick={() => setEditing(false)}>Close inputs</button>
      </fieldset></form>}
      {estimate && <details><summary>How this estimate works</summary>
        {Object.entries(estimate.inputs || {}).map(([key, input]) => <p key={key}>
          {labels[key] || key.replaceAll('_', ' ')}: {money(input.value_eur)} <small>({sources[input.source] || 'Unavailable'})</small></p>)}
        {estimate.limitations?.map((text, index) => <p className="fine" key={index}>{text}</p>)}
        <p className="fine">This preview does not change your confirmed plan or goals.</p>
      </details>}
    </>}
    <button className="text-button" onClick={onPlan} disabled={!assumptions}>Review confirmed plan ›</button>
  </section>;
}
