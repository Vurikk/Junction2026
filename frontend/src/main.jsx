import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, ReferenceLine } from 'recharts';
import './style.css';

const money = value => value == null ? 'Not available' : new Intl.NumberFormat('en-FI', {
  style: 'currency', currency: 'EUR', maximumFractionDigits: 2,
}).format(Number(value));
async function api(path, options = {}) {
  const response = await fetch(`/api/${path}`, options);
  if (!response.ok) throw new Error('Could not load or save your information. Please try again.');
  return response.json();
}
function App() {
  const [customers, setCustomers] = useState([]);
  const [customer, setCustomer] = useState('');
  const [page, setPage] = useState('Home');
  const [data, setData] = useState({});
  const [month, setMonth] = useState('');
  const [period, setPeriod] = useState('Month');
  const [week, setWeek] = useState(0);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [analysis, setAnalysis] = useState(null);
  const [reload, setReload] = useState(0);
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
    ['spending', 'budget', 'goals'].forEach(resource => {
      const query = resource === 'spending' && month ? `?month=${month}` : '';
      api(`customers/${customer}/${resource}${query}`, { signal: controller.signal })
        .then(result => setData(old => ({ ...old, [resource]: result })))
        .catch(e => { if (e.name !== 'AbortError') setError(e.message); });
    });
    return () => controller.abort();
  }, [customer, month, reload]);
  async function createGoal(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const fields = new FormData(form);
    setBusy(true); setError('');
    try {
      const goal = await api(`customers/${customer}/goals`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: fields.get('name').trim(), amount_eur: fields.get('amount'), priority: fields.get('priority') }),
      });
      setData(old => ({ ...old, goals: [...(old.goals || []), goal] })); setAnalysis(null); form.reset();
    } catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  async function analyze() {
    setBusy(true); setError('');
    try { setAnalysis(await api(`customers/${customer}/goal-analysis`)); }
    catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  const spending = data.spending;
  const points = period === 'Week' ? spending?.daily.slice(week * 7, week * 7 + 7) : spending?.daily;
  const profile = customers.find(item => item.customer_id === customer);
  return <div className="app">
    <header><a className="brand" href="#" onClick={() => setPage('Home')}><b>S</b>
        <span>Financial coach<small>Your money, made clearer</small></span></a>
      <span className="demo">DEMO</span></header>
    <main>
      <div className="customer"><label htmlFor="customer">Your demo profile</label>
        <select id="customer" value={customer} disabled={busy || !customers.length} onChange={e => {
          setCustomer(e.target.value); setMonth(''); setWeek(0);
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
          <p>We need confirmed income, upcoming bills and an emergency reserve before showing a safe amount.</p></section>
        <section><p className="eyebrow">YOUR MONEY AT A GLANCE</p><h2>A small check-in. A clearer plan.</h2>
          <p>Recorded spending {spending?.month ? `in ${spending.month}` : ''}</p><strong className="amount">{money(spending?.spending_eur)}</strong>
          <p>Transfers are excluded from recorded spending.</p>
          <button className="text-button" onClick={() => setPage('Spending')}>Explore spending →</button></section>
        <button className="goal-link" onClick={() => setPage('Goals')}><span>◎</span>
          <div><b>Something to save for?</b><small>Give your next goal a name.</small></div><span>→</span></button>
      </>}
      {page === 'Spending' && <>
        <section><div className="section-title"><h2>Spending history</h2><span className="tag">Recorded</span></div>
          <label htmlFor="month">Month</label><select id="month" disabled={busy} value={month || spending?.month || ''} onChange={e => {
            setMonth(e.target.value); setWeek(0);
          }}>{profile?.months.map(value => <option key={value}>{value}</option>)}</select>
          <p className="amount">{money(spending?.spending_eur)}</p><p>Total for the selected month</p>
          <div className="segmented">{['Week', 'Month'].map(value => <button key={value} aria-pressed={period === value}
            onClick={() => setPeriod(value)}>{value}</button>)}</div>
          {period === 'Week' && <select aria-label="Week of month" value={week} onChange={e => setWeek(Number(e.target.value))}>
            {Array.from({ length: Math.ceil((spending?.daily.length || 0) / 7) }, (_, index) =>
              <option key={index} value={index}>Days {index * 7 + 1}–{Math.min(index * 7 + 7, spending.daily.length)}</option>)}
          </select>}
          {spending ? <div className="chart" role="img" aria-label="Daily spending in euros, with the monthly daily average">
            <ResponsiveContainer width="100%" height={230}><BarChart data={points} margin={{ top: 15, right: 5, left: -20, bottom: 0 }}>
              <XAxis dataKey="date" tickFormatter={value => value.slice(-2)} tickLine={false} axisLine={false} />
              <YAxis tickLine={false} axisLine={false} /><Tooltip formatter={value => money(value)} />
              <Bar dataKey="amount_eur" name="Spent" fill="#008c45" radius={[5, 5, 0, 0]} />
              <ReferenceLine y={spending.average_daily_eur} stroke="#94662e" strokeDasharray="5 5" ifOverflow="extendDomain" />
            </BarChart></ResponsiveContainer></div> : <p role="status">{error ? 'Spending unavailable.' : 'Loading spending…'}</p>}
          <p className="legend">– – Daily average: {money(spending?.average_daily_eur)}</p><p>Budget target: not available</p>
          <details><summary>View daily amounts</summary>{points?.map(point => <div className="row" key={point.date}>
            <span>{point.date}</span><b>{money(point.amount_eur)}</b></div>)}</details>
          <p className="fine">{spending?.note}</p></section>
        <section><h2>Spending categories</h2><div className="chips"><button aria-pressed="true">All spending</button>
          {['Purchases', 'Housing', 'Bills'].map(value => <button key={value} disabled>{value}</button>)}</div>
          <p>Category filters will be available when category totals are included.</p>
          <h2>Your three spending baskets</h2>
          <p>Basket names and amounts are not available in the current data.</p></section>
      </>}
      {page === 'Goals' && <>
        <section><div className="section-title"><h2>Your goals</h2><span className="tag">One step at a time</span></div>
          {!data.goals && <p role="status">{error ? 'Goals unavailable.' : 'Loading goals…'}</p>}
          {data.goals?.length === 0 && <div className="empty"><span>◎</span><h3>What are you looking forward to?</h3>
          <p>Add your first goal below.</p></div>}
          {data.goals?.map(goal => <article className="goal" key={goal.id}><span className={`tag ${goal.priority}`}>{goal.priority}</span>
            <h3>{goal.name}</h3><strong>{money(goal.amount_eur)}</strong><p>Saved amount and progress not available</p></article>)}
          <button className="primary" onClick={analyze} disabled={busy || !data.goals?.length}>{busy ? 'Please wait…' : 'Analyze my goals'}</button>
          {analysis && <div className="analysis" role="status"><h3>Can I reach my goals?</h3>
          <p>{analysis.explanation}</p>
            <dl><dt>Total goal amount</dt><dd>{money(analysis.total_target_eur)}</dd><dt>Savings per month</dt><dd>Not available</dd>
              <dt>Estimated completion</dt><dd>Not available</dd></dl></div>}</section>
        <section><h2>A new goal</h2>
          <p>Big or small, give your plan a place to start.</p><form onSubmit={createGoal}>
          <label htmlFor="name">Goal name</label><input id="name" name="name" placeholder="e.g. A rainy-day fund" required maxLength={100}
            pattern=".*\S.*" />
          <label htmlFor="amount">Target amount (€)</label><input id="amount" name="amount" type="number" inputMode="decimal"
            min="0.01" max="9999999999.99" step="0.01" placeholder="0.00" required />
          <label htmlFor="priority">How important is it?</label><select id="priority" name="priority" defaultValue="flexible">
            <option value="critical">Critical — must come first</option><option disabled>Important — not available yet</option>
            <option value="flexible">Flexible — can wait</option></select>
          <p className="fine">Critical goals come first. Important priority is not supported yet. Goals reset when the demo server restarts.</p>
          <button className="primary" disabled={busy || !customer || !data.goals}>{busy ? 'Please wait…' : 'Create goal'}</button>
        </form></section>
      </>}
      {page === 'Coach' && <section className="empty"><span>✦</span><p className="eyebrow">YOUR FINANCIAL COACH</p>
        <h2>A little guidance goes a long way.</h2>
          <p>Personal coaching is coming soon. For now, create a goal and check what we know about your plan.</p>
        <button className="primary" onClick={() => setPage('Goals')}>Explore my goals</button></section>}
      <footer>S-Bank inspired · Junction 2026<br />Historical synthetic demo data</footer>
    </main>
    <nav aria-label="Main navigation">{[['Home', '⌂'], ['Spending', '▥'], ['Goals', '◎'], ['Coach', '✦']].map(([name, icon]) =>
      <button key={name} aria-current={page === name ? 'page' : undefined} onClick={() => setPage(name)}>
        <span aria-hidden="true">{icon}</span>{name}</button>)}</nav>
  </div>;
}
createRoot(document.getElementById('root')).render(<App />);
