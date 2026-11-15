import PlanTargetLabel from './PlanTargetLabel.jsx';
import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, ReferenceLine } from 'recharts';
import './style.css';
import Coach from './Coach';
import CoachDialog from './CoachDialog';
import Icon from './Icon';
import HomeSummary from './HomeSummary';
import PlanningForm from './PlanningForm.jsx';
import { chartPeriods } from './chartPeriods';

const money = value => value == null ? 'Not available' : new Intl.NumberFormat('en-FI', {
  minimumFractionDigits: 2, maximumFractionDigits: 2,
}).format(Number(value)) + '\u00a0€';
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
  const [analysis, setAnalysis] = useState(null);
  const [reload, setReload] = useState(0);
  const [coachQuestion, setCoachQuestion] = useState('');
  const [coachOpen, setCoachOpen] = useState(false);
  const [goalNotice, setGoalNotice] = useState('');
  const [savedPlanCustomer, setSavedPlanCustomer] = useState(null);
  const [focusGoal, setFocusGoal] = useState(false);
  useEffect(() => { window.scrollTo(0, 0); }, [page]);
  useEffect(() => {
    if (page === 'Goals' && focusGoal) { document.getElementById('name')?.focus(); setFocusGoal(false); }
  }, [page, focusGoal]);
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
    const resources = ['spending', 'spending-history', 'budget', 'goals', 'assumptions', 'mortgages',
      'recorded-balances', 'spending-comparison', 'planning-suggestions', 'planning-state'];
    resources.forEach(resource => {
      const query = ['spending-history', 'spending-comparison'].includes(resource) ? `?period=${period.toLowerCase()}` : '';
      const endpoint = `${resource}${query}`;
      api(`customers/${customer}/${endpoint}`, { signal: controller.signal })
        .then(async result => {
          if (controller.signal.aborted) return;
          setData(old => ({ ...old, [resource]: result }));
          if (resource !== 'budget') return;
          const keys = ['confirmed_income_eur', 'upcoming_essential_bills_eur', 'everyday_spending_eur',
            'voluntary_goal_contribution_eur'];
          if (keys.some(key => result.assumptions[key] == null)) return;
          const remainder = await api(`customers/${customer}/planning-remainder`, {
            method: 'POST', signal: controller.signal, headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ...Object.fromEntries(keys.map(key => [key, result.assumptions[key]])),
              horizon_days: result.assumptions.horizon_days }),
          });
          if (!controller.signal.aborted) setData(old => ({ ...old, 'saved-income-remainder': remainder }));
        })
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
      setData({}); setAnalysis(null); form.reset(); setReload(value => value + 1);
      setGoalNotice('Goal saved.');
      try {
        const result = await api(`customers/${customer}/goal-analysis`);
        setGoalNotice(`Goal saved. ${result.coach_message}`);
      } catch {
        setGoalNotice('Goal saved. Its explanation is unavailable right now. You can analyze it later.');
      }
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
      setSavedPlanCustomer(customer);
      setData({}); setAnalysis(null); setGoalNotice(''); setReload(value => value + 1);
    } catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  function openCoach(question = '') { setCoachQuestion(question); setCoachOpen(true); }

  const history = data['spending-history'];
  const points = history?.periods;
  return <div className="app">
    <header><button className="brand" onClick={() => setPage('Home')}>Financial coach</button>
      <button className="header-chat" aria-label="Open Coach" onClick={() => openCoach()}><Icon name="Coach" /></button>
    </header><div className="concept">Junction 2026 concept / Not an official banking app</div>
    <main>
      <div className="customer"><label htmlFor="customer">Your demo profile</label>
        <select id="customer" value={customer} disabled={busy || !customers.length} onChange={e => {
          setCoachOpen(false); setCoachQuestion('');
          setData({}); setAnalysis(null); setGoalNotice(''); setCustomer(e.target.value);
        }}><option value="" disabled>Select customer</option>
          {customers.map(item => <option key={item.customer_id}>{item.customer_id}</option>)}</select></div>
      {page !== 'Home' && <div className="heading"><h1>{{ Home: 'Your money, made clearer',
        Spending: 'Your spending', Goals: 'Your goals', Coach: 'Ask your coach' }[page]}</h1></div>}
      {error && <div className="error" role="alert">{error}<button disabled={busy} onClick={() => setReload(reload + 1)}>Try again</button></div>}
      {!customer && !error && <p role="status">Loading your profiles…</p>}
      {page === 'Home' && <>
        <HomeSummary key={customer} data={data} money={money} openCoach={openCoach} onSpending={() => setPage('Spending')}
          onLastFiveWeeks={() => { if (period !== 'Week') { setData({}); setPeriod('Week'); } }}
          onAddGoal={() => { setPage('Goals'); setFocusGoal(true); }}
          onPlan={() => {
            const plan = document.getElementById('spending-plan');
            if (plan) { plan.open = true; plan.scrollIntoView({ behavior: 'smooth', block: 'start' }); }
          }} />
        {savedPlanCustomer === customer && <p role="status">Spending plan saved. Your confirmed amounts and extra options will be restored.</p>}
        {data.assumptions && data['planning-state'] && <PlanningForm key={`${customer}-${reload}`}
          assumptions={data.assumptions} customer={customer} api={api} money={money} hasSavedPlan={data['planning-state'].has_saved_plan}
          suggestions={data['planning-suggestions']} busy={busy} onSave={savePlan} />}
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
            disabled={busy} onClick={() => { if (value !== period) { setData({}); setPeriod(value); } }}>
            {value === 'Week' ? 'Last 5 weeks' : value}</button>)}</div>
          {history?.period === 'week' && chartPeriods(history)?.length > 0 && <p className="fine">
            Recorded weeks: {chartPeriods(history)[0].start} – {chartPeriods(history).at(-1).end}. These are historical records.
          </p>}
          {history ? <div className="chart" role="img" aria-label={`${period} spending with historical average and confirmed chart target`}>
            <ResponsiveContainer width="100%" height={230}><BarChart data={chartPeriods(history)}
              margin={{ top: 15, right: 5, left: -20, bottom: 0 }}>
              <XAxis dataKey="start" tickLine={false} axisLine={false} />
              <YAxis tickLine={false} axisLine={false} /><Tooltip formatter={value => money(value)} />
              <Bar dataKey="spending_eur" name="Spent" fill="#008c45" radius={[5, 5, 0, 0]} />
              {history.historical_average_eur != null && <ReferenceLine y={history.historical_average_eur}
                stroke="#94662e" strokeDasharray="5 5" ifOverflow="extendDomain" />}
              {history.budget_target_eur != null && <ReferenceLine y={Number(history.budget_target_eur)}
                stroke="#4b83ce" strokeWidth={1.5} strokeDasharray="3 5" label={<PlanTargetLabel />} ifOverflow="extendDomain" />}
            </BarChart></ResponsiveContainer></div> : <p role="status">{error ? 'Spending unavailable.' : 'Loading spending…'}</p>}
          <p className="legend">– – {period} average: {money(history?.historical_average_eur)}</p>
          <p>Plan target: {money(history?.budget_target_eur)}. Confirm a spending plan on Home to add the blue line.</p>
          <p className="fine">The blue line compares planned bills and everyday costs with recorded spending. Monthly targets use a 30-day equivalent. It is not money already saved.</p>
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
      {customer && <CoachDialog open={coachOpen} onClose={() => setCoachOpen(false)}>
        <Coach key={customer} customer={customer}
        api={api} money={money} initialQuestion={coachQuestion} open={coachOpen}
        onSaved={() => {
          if (activeCustomer.current !== customer) return;
          ['goals', 'budget'].forEach(resource => api(`customers/${customer}/${resource}`)
            .then(result => {
              if (activeCustomer.current === customer) setData(old => ({ ...old, [resource]: result }));
            }).catch(e => { if (activeCustomer.current === customer) setError(e.message); }));
          setAnalysis(null); setGoalNotice('');
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
