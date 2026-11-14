import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './style.css';

async function get(path, signal) {
  const response = await fetch(path, { signal });
  if (!response.ok) throw new Error(`API request failed (${response.status}). Check the backend and local data files.`);
  return response.json();
}

function App() {
  const [customers, setCustomers] = useState([]);
  const [selected, setSelected] = useState('');
  const [overview, setOverview] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    const controller = new AbortController();
    get('/api/customers', controller.signal).then((items) => {
      setCustomers(items);
      setSelected(items[0]?.customer_id ?? '');
    }).catch((reason) => { if (reason.name !== 'AbortError') setError(reason.message); });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (!selected) return;
    const controller = new AbortController();
    setOverview(null);
    setError('');
    Promise.all(['spending', 'budget', 'mortgages'].map((resource) =>
      get(`/api/customers/${selected}/${resource}`, controller.signal)
    )).then(([spending, budget, mortgages]) => setOverview({ spending, budget, mortgages }))
      .catch((reason) => { if (reason.name !== 'AbortError') setError(reason.message); });
    return () => controller.abort();
  }, [selected]);

  return <main>
    <header><span className="brand">S / Financial Coach</span><p>Demo · Project foundation</p>
      <h1>A clearer view of your money.</h1><p>Explore recorded spending and plan your next steps.</p></header>
    <label htmlFor="customer">Demo customer</label>
    <select id="customer" value={selected} onChange={(event) => setSelected(event.target.value)} disabled={!customers.length}>
      {!customers.length && <option>Loading customers…</option>}
      {customers.map((customer) => <option key={customer.customer_id}>{customer.customer_id}</option>)}
    </select>
    {error && <p role="alert" className="error">{error}</p>}
    {!overview && !error && <p role="status">Loading overview…</p>}
    {overview && <div className="cards">
      <section><h2>Recorded spending</h2><p>{overview.spending.month}</p>
        <strong>€{overview.spending.spending_eur.toLocaleString('en-FI', { minimumFractionDigits: 2 })}</strong>
        <p>{overview.spending.note}</p><div className="placeholder">Spending chart coming next</div></section>
      <section><h2>Daily & weekly allowance</h2><strong>Not available yet</strong>
        <p>Confirm income, upcoming essential bills and your emergency reserve before calculating a safe allowance.</p></section>
      <section><h2>Your goals</h2><p>Goal creation and analysis APIs are ready. Goal controls are coming next.</p>
        <p>Critical goals take priority over flexible savings.</p></section>
      <section><h2>Mortgage information</h2>
        <p>{overview.mortgages.applications.length ? 'Linked mortgage application data available.' : 'No linked mortgage application.'}</p>
        <p>{overview.mortgages.note}</p></section>
    </div>}
    <footer>Historical synthetic demo data · No AI connected · Goals stored only while the backend runs</footer>
  </main>;
}

createRoot(document.getElementById('root')).render(<App />);
