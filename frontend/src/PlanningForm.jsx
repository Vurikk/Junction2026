import React, { useEffect, useRef, useState } from 'react';

const readableDate = value => new Intl.DateTimeFormat('en-GB', {
  day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC',
}).format(new Date(`${value.slice(0, 10)}T12:00:00Z`));

const fields = [
  ['confirmed_income_eur', 'Salary and other expected income', 'Only additional income during this plan; exclude money already in the balance.'],
  ['upcoming_essential_bills_eur', 'Bills and food total',
    'Review the estimate below. Include all required debt and other bills; override the total as needed.'],
  ['emergency_reserve_eur', 'Money to keep untouched', 'Protect money for emergencies.'],
  ['everyday_spending_eur', 'Other everyday spending', 'Exclude food already in the bills and food total. Include other daily costs only once.'],
  ['voluntary_goal_contribution_eur', 'Most you want to put towards goals', 'A limit for all goals together, only if enough money remains after your costs.'],
  ['weekly_budget_eur', 'Weekly chart target (optional)', 'A chart reference, separate from this spending plan.'],
  ['monthly_budget_eur', 'Monthly chart target (optional)', 'A chart reference, separate from this spending plan.'],
];

export default function PlanningForm({ customer, assumptions, api, money, busy, onSave }) {
  const [days, setDays] = useState(String(assumptions.horizon_days));
  const [values, setValues] = useState(() => Object.fromEntries(fields.map(([key]) => [key, ''])));
  const [reserveMonths, setReserveMonths] = useState(3);
  const selectedMonths = useRef(3);
  const [customReserve, setCustomReserve] = useState(false);
  const [defaults, setDefaults] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [review, setReview] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const edited = useRef(new Set());
  const [remainder, setRemainder] = useState(null);
  const remainderBody = JSON.stringify(Object.fromEntries([
    'confirmed_income_eur', 'upcoming_essential_bills_eur', 'everyday_spending_eur', 'voluntary_goal_contribution_eur',
  ].map(key => [key, values[key] === '' ? null : String(values[key])])));
  useEffect(() => {
    const controller = new AbortController();
    setRemainder(null);
    const timer = setTimeout(() => {
      api(`customers/${customer}/planning-remainder`, {
        method: 'POST', credentials: 'same-origin', signal: controller.signal,
        headers: { 'Content-Type': 'application/json' }, body: remainderBody,
      }).then(result => {
        if (!controller.signal.aborted) setRemainder({ body: remainderBody, result });
      }).catch(() => {
        if (!controller.signal.aborted) setRemainder({ body: remainderBody, error: true });
      });
    }, 300);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [api, customer, remainderBody]);
  const currentRemainder = remainder?.body === remainderBody ? remainder : null;
  useEffect(() => {
    const controller = new AbortController();
    setDefaults(null); setError(''); setLoading(true); setConfirmed(false);
    if (!/^\d+$/.test(days) || Number(days) < 1 || Number(days) > 366) { setLoading(false); return; }
    api(`customers/${customer}/planning-defaults?horizon_days=${days}`, { signal: controller.signal, credentials: 'same-origin' })
      .then(result => {
        if (controller.signal.aborted) return;
        setDefaults(result);
        setValues(old => ({ ...old,
          confirmed_income_eur: edited.current.has('confirmed_income_eur') ? old.confirmed_income_eur : result.income.amount_eur ?? '',
          upcoming_essential_bills_eur: edited.current.has('upcoming_essential_bills_eur')
            ? old.upcoming_essential_bills_eur : result.bills.total_eur ?? '',
          everyday_spending_eur: edited.current.has('everyday_spending_eur')
            ? old.everyday_spending_eur : result.everyday?.amount_eur ?? '',
          emergency_reserve_eur: edited.current.has('emergency_reserve_eur') ? old.emergency_reserve_eur
            : result.reserve?.options.find(option => option.months === selectedMonths.current)?.amount_eur ?? '',
        }));
      }).catch(e => { if (!controller.signal.aborted) setError(e.message); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [customer, days, api]);
  const balance = defaults?.balance;
  const unavailable = loading || balance?.amount_eur == null;
  function edit(key, value) {
    if (key === 'emergency_reserve_eur') setCustomReserve(true);
    edited.current.add(key); setConfirmed(false); setValues(old => ({ ...old, [key]: value }));
  }
  function input([key, label, hint]) {
    return <React.Fragment key={key}><label htmlFor={key}>{label} (€)</label><p className="fine">{hint}</p>
      {key === 'confirmed_income_eur' && <p className="fine">{defaults?.income.note}</p>}
      {key === 'everyday_spending_eur' && <div>
        <p>Recorded daily average: {money(defaults?.everyday?.daily_average_eur)}.</p>
        <p className="fine">{defaults?.everyday?.note} The amount below covers the whole plan and excludes housing, utilities and food.</p>
      </div>}
      {key === 'emergency_reserve_eur' && <div>
        <label htmlFor="reserve-months">Emergency reserve target: {reserveMonths} months{customReserve ? ' (custom amount below)' : ''}</label>
        <input id="reserve-months" type="range" min="1" max="12" step="1" value={reserveMonths}
          onChange={event => {
            const months = Number(event.target.value);
            selectedMonths.current = months; setReserveMonths(months); setCustomReserve(false);
            edited.current.delete('emergency_reserve_eur'); setConfirmed(false);
            setValues(old => ({ ...old,
              emergency_reserve_eur: defaults?.reserve?.options.find(option => option.months === months)?.amount_eur ?? '',
            }));
          }} />
        <p className="fine">Start with three months, or choose 1–12 months or enter your own amount below.
          {defaults?.reserve?.note}</p>
        <p>This is a suggested target, not money already held. It is not capped to your recorded balance.</p>
        {!customReserve && defaults?.reserve?.options.find(option => option.months === reserveMonths)?.exceeds_balance &&
          <p role="status">This reserve target exceeds your recorded balance. Review what you can actually protect before confirming.</p>}
      </div>}
      {key === 'upcoming_essential_bills_eur' && defaults && <div>
        {defaults.bills.items.map(item => <div className="row" key={item.label}>
          <span>{item.label}</span><b>{money(item.amount_eur)}</b></div>)}
        <p className="fine">{defaults.bills.note}</p>
      </div>}
      <div className="money-input"><input id={key} name={key} type="number" inputMode="decimal" min="0" max="9999999999.99" step="0.01"
        onWheel={event => event.currentTarget.blur()} value={values[key]} placeholder="Unknown"
        onChange={event => edit(key, event.target.value)} /><span aria-hidden="true">€</span></div>
      {key === 'voluntary_goal_contribution_eur' && <div className="fine" aria-live="polite">
        <p>Your income − planned expenses = <b>{money(currentRemainder?.result?.remaining_income_eur)}</b> left.</p>
        <p>Includes bills, everyday spending and any goal contribution you enter.</p>
        {!currentRemainder && <p>Updating preview…</p>}
        {currentRemainder?.error && <p>Remainder preview is unavailable. Review the entered amounts.</p>}
        <details><summary>What this includes</summary>
          <p>{currentRemainder?.result?.note}</p>
        </details>
      </div>}
    </React.Fragment>;
  }
  return <details className="planning" id="spending-plan"><summary>Optional spending plan</summary><section>
    <h2>Confirm your spending plan</h2>
    <p>These recorded amounts are a historical draft. Review what is available and what you expect for the whole plan before confirming.</p>
    <form onSubmit={event => {
      event.preventDefault();
      if (unavailable || !confirmed) return;
      const form = new FormData(event.currentTarget);
      onSave({ ...Object.fromEntries(fields.map(([key]) => [key, values[key] === '' ? null : String(values[key])])),
        available_funds_eur: String(balance.amount_eur), horizon_days: Number(days), repeat_plan: form.get('repeat_plan') === 'on' });
    }}>
      <details className="advanced"><summary>Plan length and extra options</summary>
        <label htmlFor="horizon_days">How many days should this plan cover?</label>
        <input id="horizon_days" type="number" min="1" max="366" step="1" value={days} required
          onWheel={event => event.currentTarget.blur()} onChange={event => {
            setDays(event.target.value); setReview(true); setConfirmed(false); setDefaults(null);
            setValues(old => ({ ...old,
              confirmed_income_eur: edited.current.has('confirmed_income_eur') ? old.confirmed_income_eur : '',
              upcoming_essential_bills_eur: edited.current.has('upcoming_essential_bills_eur') ? old.upcoming_essential_bills_eur : '',
              everyday_spending_eur: edited.current.has('everyday_spending_eur') ? old.everyday_spending_eur : '',
              emergency_reserve_eur: edited.current.has('emergency_reserve_eur') ? old.emergency_reserve_eur : '',
            }));
          }} />
        {fields.slice(5).map(input)}
        <label className="check"><input name="repeat_plan" type="checkbox" defaultChecked={assumptions.repeat_plan}
          onChange={() => setConfirmed(false)} />I expect to have the same money available and put the same amount towards goals each time this plan repeats.</label>
      </details>
      <p>Your plan covers {days || 'an unknown number of'} days.</p>
      {review && <p role="status">Plan length changed. Automatic estimates reload; your current edits remain.
        Review every retained amount for the new period.</p>}
      <label>Latest recorded balance</label><p><strong>{money(balance?.amount_eur)}</strong></p>
      {balance?.recorded_at && <p>Recorded on {readableDate(balance.recorded_at)}</p>}
      <p className="fine">{balance?.note}</p>
      {loading && <p role="status">Loading historical defaults…</p>}
      {error && <p role="alert">{error}</p>}
      {!loading && unavailable && <p role="alert">A usable recorded balance is unavailable. This plan cannot be confirmed.</p>}
      <p className="fine">{defaults?.note}</p>
      {fields.slice(0, 5).map(input)}
      <label className="check"><input type="checkbox" checked={confirmed} required onChange={event => setConfirmed(event.target.checked)} />
        I checked that the recorded balance is still accessible and these whole-plan amounts cover my essentials before spending.</label>
      <button className="primary" disabled={busy || unavailable || !confirmed}>Confirm and calculate</button>
    </form>
  </section></details>;
}
