import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, ReferenceLine } from 'recharts';
import './style.css';
import Coach from './Coach';

const money = value => value == null ? 'Not available' : new Intl.NumberFormat('en-FI', {
  style: 'currency', currency: 'EUR', maximumFractionDigits: 2,
}).format(Number(value));
async function api(path, options = {}) {
  const response = await fetch(`/api/${path}`, options);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const detail = Array.isArray(body.detail) ? body.detail.map(item => item.msg).join('; ') : body.detail;
    throw new Error(detail || 'Could not load or save your information. Please try again.');
  }
  return response.json();
}

const planningFields = [
  ['available_funds_eur', 'Accessible funds now'],
  ['confirmed_income_eur', 'Additional confirmed income during the plan'],
  ['upcoming_essential_bills_eur', 'Upcoming essential bills and debt payments'],
  ['emergency_reserve_eur', 'Emergency reserve to protect'],
  ['everyday_spending_eur', 'Planned everyday costs, excluding bills above'],
  ['voluntary_goal_contribution_eur', 'Maximum voluntary goal contribution'],
  ['weekly_budget_eur', 'Weekly chart target (optional)'],
  ['monthly_budget_eur', 'Monthly chart target (optional)'],
];

function PlanningForm({ assumptions, busy, onSave }) {
  return <section><h2>Confirm your spending plan</h2>
    <p>All amounts cover the same planning period. Enter zero where appropriate; blank means unknown.
      Do not include income already held in accessible funds. Confirm you can pay bills before everyday spending starts.</p>
    <form onSubmit={event => {
      event.preventDefault();
      const values = new FormData(event.currentTarget);
      const payload = Object.fromEntries(planningFields.map(([key]) => [key, values.get(key) || null]));
      payload.horizon_days = Number(values.get('horizon_days'));
      payload.repeat_plan = values.get('repeat_plan') === 'on';
      onSave(payload);
    }}>
      <label htmlFor="horizon_days">Planning period (days)</label>
      <input id="horizon_days" name="horizon_days" type="number" min="1" max="366" step="1"
        defaultValue={assumptions.horizon_days} required />
      {planningFields.map(([key, label]) => <React.Fragment key={key}>
        <label htmlFor={key}>{label} (€)</label>
        <input id={key} name={key} type="number" inputMode="decimal" min="0" max="9999999999.99" step="0.01"
          defaultValue={assumptions[key] ?? ''} placeholder="Unknown" />
      </React.Fragment>)}
      <label className="check"><input name="repeat_plan" type="checkbox" defaultChecked={assumptions.repeat_plan} />
        I confirm the same savings capacity will be available in each future planning period.</label>
      <label className="check"><input type="checkbox" required />
        I confirm these inputs and that essential bills can be paid before spending.</label>
      <button className="primary" disabled={busy}>Confirm and calculate</button>
    </form></section>;
}

function App() {
  const [customers, setCustomers] = useState([]);
  const [customer, setCustomer] = useState('');
  const activeCustomer = useRef(customer);
  activeCustomer.current = customer;
  const [page, setPage] = useState('Home');
  const [data, setData] = useState({});
  const [period, setPeriod] = useState('Month');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [analysis, setAnalysis] = useState(null);
  const [reload, setReload] = useState(0);
  const [goalNotice, setGoalNotice] = useState('');
  useEffect(() => {
    const controller = new AbortController();
    api('customers', { signal: controller.signal }).then(items => {
      setCustomers(items); setCustomer(current => current || items[0]?.customer_id || '');
    }).catch(e => { if (e.name !== 'AbortError') setError(e.message); });
    return () => controller.abort();
  }, [reload]);
  useEffect(() => {
    if (!customer) return;
    const controller = new AbortController();
    setData({}); setError(''); setAnalysis(null);
    ['spending', 'spending-history', 'budget', 'goals', 'assumptions', 'mortgages'].forEach(resource => {
      const query = resource === 'spending-history' ? `?period=${period.toLowerCase()}` : '';
      api(`customers/${customer}/${resource}${query}`, { signal: controller.signal })
        .then(result => setData(old => ({ ...old, [resource]: result })))
        .catch(e => { if (e.name !== 'AbortError') setError(e.message); });
    });
    return () => controller.abort();
  }, [customer, period, reload]);
  async function createGoal(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const fields = new FormData(form);
    setBusy(true); setError('');
    try {
      await api(`customers/${customer}/goals`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: fields.get('name').trim(), amount_eur: fields.get('amount'), priority: fields.get('priority') }),
      });
      setData({}); setAnalysis(null); form.reset(); setReload(value => value + 1);
      const result = await api(`customers/${customer}/goal-analysis`);
      setGoalNotice(result.coach_message);
    } catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  async function analyze() {
    setBusy(true); setError('');
    try { setAnalysis(await api(`customers/${customer}/goal-analysis`)); }
    catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  async function savePlan(payload) {
    setBusy(true); setError('');
    try {
      await api(`customers/${customer}/assumptions`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
      });
      setData({}); setAnalysis(null); setReload(value => value + 1);
    } catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  const spending = data.spending;
  const history = data['spending-history'];
  const points = history?.periods;
  return <div className="app">
    <header><a className="brand" href="#" onClick={() => setPage('Home')}><b>S</b>
        <span>Financial coach<small>Your money, made clearer</small></span></a>
      <span className="demo">DEMO</span></header>
    <main>
      <div className="customer"><label htmlFor="customer">Your demo profile</label>
        <select id="customer" value={customer} disabled={busy || !customers.length} onChange={e => {
          setData({}); setAnalysis(null); setGoalNotice(''); setCustomer(e.target.value);
        }}><option value="" disabled>Select customer</option>
          {customers.map(item => <option key={item.customer_id}>{item.customer_id}</option>)}</select></div>
      <div className="heading"><p className="eyebrow">A LITTLE CLARITY, EVERY DAY</p>
        <h1>{ { Home: 'Hello, let’s look ahead.',
          Spending: 'Where your money goes.', Goals: 'Make room for your plans.',
          Coach: 'Your next step starts here.' }[page] }</h1>
      </div>
      {error && <div className="error" role="alert">{error}<button disabled={busy} onClick={() => setReload(reload + 1)}>Try again</button></div>}
      {!customer && !error && <p role="status">Loading your profiles…</p>}
      {page === 'Home' && <>
        <section className="balance"><p>Account balance</p><h2>Not available</h2>
          <p>Your account balance is not included in this demo.</p>
          <span className="pill">A clearer picture starts here</span></section>
        <section><div className="section-title"><h2>Your spending room</h2><span className="tag">Estimate</span></div>
          <div className="metrics"><div><small>Per day</small><strong>{money(data.budget?.daily_eur)}</strong></div>
            <div><small>Per week</small><strong>{money(data.budget?.weekly_eur)}</strong></div></div>
          <p>{data.budget?.status === 'estimated'
            ? `Based on your confirmed ${data.budget.assumptions.horizon_days}-day plan. Includes planned everyday costs.`
            : 'Confirm all six planning amounts below to calculate your spending allowance.'}</p>
          {data.budget?.shortfall_eur > 0 && <p role="alert">Bills and reserve shortfall: {money(data.budget.shortfall_eur)}</p>}
          <p className="fine">Estimates depend on your inputs and do not model payment timing.</p></section>
        <section><p className="eyebrow">YOUR MONEY AT A GLANCE</p><h2>A small check-in. A clearer plan.</h2>
          <p>Recorded spending {spending?.month ? `in ${spending.month}` : ''}</p><strong className="amount">{money(spending?.spending_eur)}</strong>
          <p>Transfers are excluded from recorded spending.</p>
          <button className="text-button" onClick={() => setPage('Spending')}>Explore spending →</button></section>
        <button className="goal-link" onClick={() => setPage('Goals')}><span>◎</span>
          <div><b>Something to save for?</b><small>Give your next goal a name.</small></div><span>→</span></button>
        {data.assumptions && <PlanningForm key={`${customer}-${reload}`} assumptions={data.assumptions}
          busy={busy} onSave={savePlan} />}
        <section><h2>Mortgage information</h2>
          <p>{data.mortgages ? (data.mortgages.applications.length
            ? 'Linked mortgage application data available.' : 'No linked mortgage application.') : 'Loading mortgage information…'}</p>
          <p>{data.mortgages?.note}</p></section>
      </>}
      {page === 'Spending' && <>
        <section><div className="section-title"><h2>Spending history</h2><span className="tag">Recorded</span></div>
          <div className="segmented">{['Week', 'Month'].map(value => <button key={value} aria-pressed={period === value}
            disabled={busy} onClick={() => { if (value !== period) { setData({}); setPeriod(value); } }}>{value}</button>)}</div>
          {history ? <div className="chart" role="img" aria-label={`${period} spending with historical average and confirmed chart target`}>
            <ResponsiveContainer width="100%" height={230}><BarChart data={points} margin={{ top: 15, right: 5, left: -20, bottom: 0 }}>
              <XAxis dataKey="start" tickLine={false} axisLine={false} />
              <YAxis tickLine={false} axisLine={false} /><Tooltip formatter={value => money(value)} />
              <Bar dataKey="spending_eur" name="Spent" fill="#008c45" radius={[5, 5, 0, 0]} />
              {history.historical_average_eur != null && <ReferenceLine y={history.historical_average_eur}
                stroke="#94662e" strokeDasharray="5 5" ifOverflow="extendDomain" />}
              {history.budget_target_eur != null && <ReferenceLine y={Number(history.budget_target_eur)}
                stroke="#3653a0" strokeDasharray="3 3" ifOverflow="extendDomain" />}
            </BarChart></ResponsiveContainer></div> : <p role="status">{error ? 'Spending unavailable.' : 'Loading spending…'}</p>}
          <p className="legend">– – {period} average: {money(history?.historical_average_eur)}</p>
          <p>Chart target: {money(history?.budget_target_eur)}. Set targets in your Home spending plan.</p>
          <p className="fine">Chart targets are separate from safe spending allowances. Edge periods may be partial.</p>
          <details><summary>View periods, categories and baskets</summary>{points?.map(point => <div key={point.period}>
            <h3>{point.start} – {point.end}{point.partial ? ' (partial)' : ''}</h3>
            <div className="row"><span>Spending</span><b>{money(point.spending_eur)}</b></div>
            <div className="row"><span>Remaining chart budget</span><b>{money(point.remaining_budget_eur)}</b></div>
            {Object.entries(point.categories).map(([name, value]) =>
              <div className="row" key={name}><span>{name}</span><b>{money(value)}</b></div>)}
            <p>Estimated baskets (heuristic classification)</p>
            {Object.entries(point.baskets).map(([name, value]) =>
              <div className="row" key={name}><span>{name.replaceAll('_', ' ')}</span><b>{money(value)}</b></div>)}
          </div>)}</details>
          <p className="fine">{history?.note} Basket classifications are uncertain; everyday categories can contain essentials.</p></section>
      </>}
      {page === 'Goals' && <>
        {goalNotice && <section role="status">{goalNotice}</section>}
        <section><div className="section-title"><h2>Your goals</h2><span className="tag">One step at a time</span></div>
          {!data.goals && <p role="status">{error ? 'Goals unavailable.' : 'Loading goals…'}</p>}
          {data.goals?.length === 0 && <div className="empty"><span>◎</span><h3>What are you looking forward to?</h3>
          <p>Add your first goal below.</p></div>}
          {data.goals?.map(goal => <article className="goal" key={goal.id}><span className={`tag ${goal.priority}`}>{goal.priority}</span>
            <h3>{goal.name}</h3><strong>{money(goal.amount_eur)}</strong><p>Saved amount and progress not available</p></article>)}
          <button className="primary" onClick={analyze} disabled={busy || !data.goals?.length}>{busy ? 'Please wait…' : 'Analyze my goals'}</button>
          {analysis && <div className="analysis" role="status"><h3>Can I reach my goals?</h3>
          <p>{analysis.explanation}</p>
            <dl><dt>Total goal amount</dt><dd>{money(analysis.total_target_eur)}</dd>
              <dt>Savings capacity per planning period</dt><dd>{money(analysis.savings_capacity_eur)}</dd></dl>
            {analysis.allocations.map(item => <div key={item.goal_id}>
              <h3>{data.goals?.find(goal => goal.id === item.goal_id)?.name}</h3>
              <p>Allocated: {money(item.allocated_eur)} · {item.feasibility.replaceAll('_', ' ')}</p>
              <p>Completion: {item.completion_periods == null ? 'Not available'
                : `${item.completion_periods} planning periods of ${analysis.assumptions.horizon_days} days`}</p>
            </div>)}</div>}</section>
        <section><h2>A new goal</h2>
          <p>Big or small, give your plan a place to start.</p><form onSubmit={createGoal}>
          <label htmlFor="name">Goal name</label><input id="name" name="name" placeholder="e.g. A rainy-day fund" required maxLength={100}
            pattern=".*\S.*" />
          <label htmlFor="amount">Target amount (€)</label><input id="amount" name="amount" type="number" inputMode="decimal"
            min="0.01" max="9999999999.99" step="0.01" placeholder="0.00" required />
          <label htmlFor="priority">How important is it?</label><select id="priority" name="priority" defaultValue="flexible">
            <option value="critical">Critical — must come first</option><option value="important">Important — comes next</option>
            <option value="flexible">Flexible — can wait</option></select>
          <p className="fine">Critical, then important, then flexible. Goals reset when the demo server restarts.</p>
          <button className="primary" disabled={busy || !customer || !data.goals}>{busy ? 'Please wait…' : 'Create goal'}</button>
        </form></section>
      </>}
      {page === 'Coach' && customer && <Coach key={`${customer}-${reload}`} customer={customer} api={api} money={money}
        onSaved={() => {
          if (activeCustomer.current !== customer) return;
          ['goals', 'budget'].forEach(resource => api(`customers/${customer}/${resource}`)
            .then(result => {
              if (activeCustomer.current === customer) setData(old => ({ ...old, [resource]: result }));
            }).catch(e => { if (activeCustomer.current === customer) setError(e.message); }));
          setAnalysis(null); setGoalNotice('');
        }} />}
      <footer>S-Bank inspired · Junction 2026<br />Historical synthetic demo data</footer>
    </main>
    <nav aria-label="Main navigation">{[['Home', '⌂'], ['Spending', '▥'], ['Goals', '◎'], ['Coach', '✦']].map(([name, icon]) =>
      <button key={name} aria-current={page === name ? 'page' : undefined} onClick={() => setPage(name)}>
        <span aria-hidden="true">{icon}</span>{name}</button>)}</nav>
  </div>;
}
createRoot(document.getElementById('root')).render(<App />);
