import RemoveGoalButton from './RemoveGoalButton';
import SpendingTooltip from './SpendingTooltip';
import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, ReferenceLine } from 'recharts';
import './style.css';
import Coach from './Coach';
import CoachDialog from './CoachDialog';
import Icon from './Icon';
import HomeSummary, { ChartTargetContext } from './HomeSummary';
import PlanningForm from './PlanningForm';
import GoalContributions from './GoalContributions';
import { chartPeriods } from './chartPeriods';

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
  const [reload, setReload] = useState(0);
  const [coachQuestion, setCoachQuestion] = useState('');
  const [coachOpen, setCoachOpen] = useState(false);
  const [goalNotice, setGoalNotice] = useState('');
  const [focusGoal, setFocusGoal] = useState(false);
  const [targetField, setTargetField] = useState('');
  useEffect(() => { window.scrollTo(0, 0); }, [page]);
  useEffect(() => {
    if (page === 'Goals' && focusGoal) { document.getElementById('name')?.focus(); setFocusGoal(false); }
  }, [page, focusGoal]);
  useEffect(() => {
    if (page !== 'Home' || !targetField || !data.assumptions || !data['planning-state']) return;
    const plan = document.getElementById('spending-plan');
    plan.open = true;
    plan.querySelector('.advanced').open = true;
    document.getElementById(targetField)?.focus();
    setTargetField('');
  }, [page, targetField, data.assumptions, data['planning-state']]);
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
    setData({}); setError('');
    const resources = ['spending', 'spending-history', 'budget', 'goals', 'assumptions', 'mortgages',
      'recorded-balances', 'spending-comparison', 'planning-suggestions', 'planning-state', 'income'];
    resources.forEach(resource => {
      const query = ['spending-history', 'spending-comparison'].includes(resource) ? `?period=${period.toLowerCase()}` : '';
      api(`customers/${customer}/${resource}${query}`, { signal: controller.signal })
        .then(result => { if (!controller.signal.aborted) setData(old => ({ ...old, [resource]: result })); })
        .catch(e => { if (e.name !== 'AbortError') setError(e.message); });
    });
    return () => controller.abort();
  }, [customer, period, reload]);
  async function createGoal(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const fields = new FormData(form);
    setBusy(true); setError(''); setGoalNotice('');
    try {
      await api(`customers/${customer}/goals`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: fields.get('name').trim(), amount_eur: fields.get('amount'), priority: fields.get('priority') }),
      });
      setData({}); form.reset(); setReload(value => value + 1);
      setGoalNotice('Goal saved.');
      try {
        const result = await api(`customers/${customer}/goal-analysis`);
        setGoalNotice(`Goal saved. ${result.coach_message}`);
      } catch {
        setGoalNotice('Goal saved. Its explanation is unavailable right now. You can analyze it later.');
      }
    } catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  async function removeGoal(goal) {
    setBusy(true); setError(''); setGoalNotice('');
    try {
      await api(`customers/${customer}/goals/${encodeURIComponent(goal.id)}`, { method: 'DELETE' });
      setData({}); setReload(value => value + 1);
      setGoalNotice(`${goal.name} removed. Your estimates will update automatically.`);
    } catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  async function savePlan(payload) {
    setBusy(true); setError('');
    try {
      await api(`customers/${customer}/assumptions`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
      });
      setData({}); setGoalNotice(''); setReload(value => value + 1);
    } catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  function openCoach(question = '') { setCoachQuestion(question); setCoachOpen(true); }
  function openTarget() {
    setTargetField(period === 'Week' ? 'weekly_budget_eur' : 'monthly_budget_eur'); setPage('Home');
  }

  const history = data['spending-history'];
  const points = history?.periods;
  return <div className="app">
    <main>
      <div className="customer"><label htmlFor="customer">Your demo profile</label>
        <select id="customer" value={customer} disabled={busy || !customers.length} onChange={e => {
          setCoachOpen(false); setCoachQuestion('');
          setData({}); setGoalNotice(''); setCustomer(e.target.value);
        }}><option value="" disabled>Select customer</option>
          {customers.map(item => <option key={item.customer_id}>{item.customer_id}</option>)}</select></div>
      {page !== 'Home' && <div className="heading"><h1>{{ Home: 'Your money, made clearer',
        Spending: 'Your spending', Goals: 'Your goals', Coach: 'Ask your coach' }[page]}</h1></div>}
      {error && <div className="error" role="alert">{error}<button disabled={busy} onClick={() => setReload(reload + 1)}>Try again</button></div>}
      {!customer && !error && <p role="status">Loading your profiles…</p>}
      {page === 'Home' && <>
        <HomeSummary key={customer} data={data} money={money} openCoach={openCoach} onSpending={() => setPage('Spending')}
          customer={customer} api={api} refreshKey={`${reload}-${data.goals?.map(goal => goal.id).join(',')}`}
          onAddGoal={() => { setPage('Goals'); setFocusGoal(true); }}
          onTarget={openTarget}
          onPlan={() => {
            const plan = document.getElementById('spending-plan');
            if (plan) { plan.open = true; plan.scrollIntoView({ behavior: 'smooth', block: 'start' }); }
          }} />
        {data.assumptions && data['planning-state'] && <PlanningForm key={`${customer}-${reload}`}
          assumptions={data.assumptions} customer={customer} api={api} money={money}
          hasSavedPlan={data['planning-state'].has_saved_plan} busy={busy} onSave={savePlan} />}
        <details className="supporting"><summary>Account and mortgage information</summary><section>
          <p>Recorded balances are historical snapshots, not current available funds.</p><h2>Mortgage information</h2>
          <p>{data.mortgages ? (data.mortgages.applications.length
            ? 'Linked mortgage application data available.' : 'No linked mortgage application.') : 'Loading mortgage information…'}</p>
          <p>{data.mortgages?.note}</p></section></details>
      </>}
      {page === 'Spending' && <>
        <button className="journey-link" onClick={() => openCoach('Spending by category')}><Icon name="Coach" />
          <span><b>What am I spending on?</b><small>Ask the rule-based Coach</small></span><span>&rsaquo;</span></button>
        <section><div className="section-title"><h2>Spending history</h2><span className="tag">Recorded</span></div>
          <div className="segmented">{['Week', 'Month'].map(value => <button key={value} aria-pressed={period === value}
            disabled={busy} onClick={() => { if (value !== period) { setData({}); setPeriod(value); } }}>{value}</button>)}</div>
          {history ? <div className="chart" role="img" aria-label={`${period} spending with historical average and chart target`}>
            <ResponsiveContainer width="100%" height={230}><BarChart data={chartPeriods(history)}
              margin={{ top: 15, right: 5, left: -20, bottom: 0 }}>
              <XAxis dataKey="start" tickLine={false} axisLine={false} />
              <YAxis tickLine={false} axisLine={false} padding={{ top: 18, bottom: 8 }} /><Tooltip content={<SpendingTooltip period={history.period} income={data.income} money={money} />} />
              <Bar dataKey="spending_eur" name="Spent" fill="#008c45" radius={[5, 5, 0, 0]} />
              {history.historical_average_eur != null && <ReferenceLine y={history.historical_average_eur}
                stroke="#94662e" strokeDasharray="5 5" ifOverflow="extendDomain"
                label={{ value: 'avg.', position: 'insideBottomLeft', fill: '#94662e', fontSize: 11,
                  stroke: 'white', strokeWidth: 3, paintOrder: 'stroke' }} />}
              {history.budget_target_eur != null && <ReferenceLine y={Number(history.budget_target_eur)}
                stroke="#3653a0" strokeWidth={2} strokeDasharray="3 3" ifOverflow="extendDomain"
                label={{ value: 'goal', position: 'insideBottomLeft', fill: '#3653a0', fontSize: 11,
                  stroke: 'white', strokeWidth: 3, paintOrder: 'stroke' }} />}
            </BarChart></ResponsiveContainer></div> : <p role="status">{error ? 'Spending unavailable.' : 'Loading spending…'}</p>}
          <p className="legend">– – {period} average: {money(history?.historical_average_eur)}</p>
          {history?.budget_target_eur != null ? <p>{history.target_source === 'automatic_historical'
            ? 'Estimated plan target' : `${period} spending target`}: {money(history.budget_target_eur)}</p>
            : <button className="text-button" disabled={!data.assumptions} onClick={openTarget}>Set spending target</button>}
          <ChartTargetContext history={history} />
          <p className="fine">Chart targets are separate from safe spending allowances. Edge periods may be partial.</p>
          {points?.length > 0 && <><h3>Categories in the latest displayed period</h3>
          <p className="fine">{points?.at(-1)?.start} to {points?.at(-1)?.end}
            {points?.at(-1)?.partial ? ' / Partial period' : ''}</p>
          {Object.entries(points?.at(-1)?.categories || {}).map(([name, value]) =>
            <div className="row" key={name}><span>{name}</span><b>{money(value)}</b></div>)}</>}
          <details><summary>All periods and estimated spending baskets</summary>{points?.map(point => <div key={point.period}>
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
        <GoalContributions customer={customer} api={api} money={money} goals={data.goals} />
        {goalNotice && <section role="status">{goalNotice}</section>}
        <section><div className="section-title"><h2>Your goals</h2><span className="tag">One step at a time</span></div>
          {!data.goals && <p role="status">{error ? 'Goals unavailable.' : 'Loading goals…'}</p>}
          {data.goals?.length === 0 && <div className="empty"><span>◎</span><h3>What are you looking forward to?</h3>
          <p>Add your first goal below.</p></div>}
          {data.goals?.map(goal => <article className="goal" key={goal.id}><span className={`tag ${goal.priority}`}>{goal.priority}</span>
            <h3>{goal.name}</h3><strong>{money(goal.amount_eur)}</strong><p>Saved amount and progress not available</p>
            <RemoveGoalButton goal={goal} busy={busy} onRemove={removeGoal} /></article>)}
          <button className="primary" onClick={() => openCoach('Analyze my goals')} disabled={busy || !data.goals?.length}>{busy ? 'Please wait…' : 'Analyze my goals'}</button>
          </section>
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
      {customer && <CoachDialog open={coachOpen} onClose={() => setCoachOpen(false)}>
        <Coach key={customer} customer={customer}
        api={api} money={money} initialQuestion={coachQuestion} open={coachOpen}
        onSaved={() => {
          if (activeCustomer.current !== customer) return;
          ['goals', 'budget'].forEach(resource => api(`customers/${customer}/${resource}`)
            .then(result => {
              if (activeCustomer.current === customer) setData(old => ({ ...old, [resource]: result }));
            }).catch(e => { if (activeCustomer.current === customer) setError(e.message); }));
          setGoalNotice('');
        }} /></CoachDialog>}
      <footer>S-Bank inspired · Junction 2026<br />Historical synthetic demo data</footer>
    </main>
    <nav aria-label="Main navigation">{['Home', 'Spending', 'Coach', 'Goals'].map(name =>
      <button key={name} aria-current={page === name ? 'page' : undefined}
        onClick={() => { if (name === 'Coach') openCoach(); else { setPage(name); window.scrollTo(0, 0); } }}>
        <Icon name={name} />{name}</button>)}</nav>
  </div>;
}
createRoot(document.getElementById('root')).render(<App />);
