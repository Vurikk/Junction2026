// Local Vite-only manual QA harness. Not imported by the production application.
import React, { useCallback, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import CategoryReduction from '../src/CategoryReduction';
import '../src/style.css';

function Harness() {
  const mode = useRef('success');
  const pending = useRef([]);
  const [customer, setCustomer] = useState('fixture-a');
  const [generation, setGeneration] = useState(0);
  const [calls, setCalls] = useState(0);
  const api = useCallback(async (path, options = {}) => {
    if (path.includes('spending-history')) {
      if (mode.current === 'history-error') throw new Error('Fixture network failure loading months.');
      return { periods: mode.current === 'empty' ? [] : [
        { start: '2025-01-01', end: '2025-01-31', partial: false, categories: { Groceries: 50 } },
        { start: '2025-02-01', end: '2025-02-28', partial: false, categories: { Restaurants: 50, Groceries: 50 } },
      ] };
    }
    setCalls(value => value + 1);
    if (mode.current === '404') throw new Error('No recorded payments for this category (404 fixture). Choose another category.');
    if (mode.current === '422') throw new Error('This period is not eligible (422 fixture). Choose another month.');
    if (mode.current === 'network') throw new Error('Network unavailable (fixture). Retry the preview.');
    const body = JSON.parse(options.body);
    const result = {
      category: body.category, source_period: { start: body.period_start, end: '2025-02-28' },
      reduction_percent: 20, baseline_spending_eur: 50, hypothetical_spending_eur: 40, potential_reduction_eur: 10,
      goal_impact: null, note: 'QA fixture only.', goal_impact_unavailable_reason: 'Fixture: unavailable.',
    };
    // Deliberately ignores abort to exercise the component's stale-result guard.
    if (mode.current === 'delayed') return new Promise(resolve => pending.current.push(() => resolve(result)));
    return result;
  }, []);
  return <main className="app"><h1>QA fixtures only</h1>
    <label htmlFor="fixture-mode">Response mode</label><select id="fixture-mode" onChange={event => { mode.current = event.target.value; }}>
      {['success', '404', '422', 'network', 'delayed', 'empty', 'history-error'].map(value => <option key={value}>{value}</option>)}
    </select>
    <button onClick={() => setGeneration(value => value + 1)}>Remount fixture</button>
    <button onClick={() => setCustomer(value => value === 'fixture-a' ? 'fixture-b' : 'fixture-a')}>Switch fixture customer</button>
    <button onClick={() => pending.current.splice(0).forEach(resolve => resolve())}>Resolve delayed responses</button>
    <p>Customer: {customer} · Preview calls: {calls}</p>
    <CategoryReduction key={`${customer}-${generation}`} customer={customer} api={api}
      money={value => value == null ? 'Not available' : `EUR ${Number(value).toFixed(2)}`} />
  </main>;
}
createRoot(document.getElementById('root')).render(<Harness />);
