import React, { useCallback, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import SafeToSpend from '../src/SafeToSpend';
import '../src/style.css';
const missing = ['available_funds_eur', 'emergency_reserve_eur', 'upcoming_essential_bills_eur'];
function Harness() {
  const [customer, setCustomer] = useState('fixture-a');
  const [request, setRequest] = useState('');
  const mode = useRef('success');
  const delayed = useRef([]);
  const api = useCallback(async (path, options = {}) => {
    setRequest(`${path} ${options.method || 'GET'} ${options.body || ''}`);
    if (mode.current === 'error') throw new Error('Fixture error, no backend call.');
    const result = { mode: 'current', reference_date: '2026-11-14', horizon_days: 7, status: 'insufficient_data',
      daily_eur: null, weekly_eur: null, missing_inputs: missing, inputs: {},
      goal_policy: 'No money set aside for goals in this estimate.', limitations: ['Mock fixture only.'] };
    if (mode.current === 'delayed') return new Promise(resolve => delayed.current.push(() => resolve(result)));
    return result;
  }, []);
  return <main className="app"><h1>Estimate fixtures only</h1>
    <label htmlFor="mode">Response mode</label><select id="mode" onChange={e => { mode.current = e.target.value; }}>
      <option>success</option><option>error</option><option>delayed</option></select>
    <button onClick={() => setCustomer(value => value === 'fixture-a' ? 'fixture-b' : 'fixture-a')}>Switch customer</button>
    <button onClick={() => delayed.current.splice(0).forEach(resolve => resolve())}>Resolve delayed</button>
    <SafeToSpend key={customer} customer={customer} api={api} money={value => value == null ? 'Not available' : `EUR ${value}`}
      assumptions={{}} onPlan={() => {}} /><output>{request}</output>
  </main>;
}
createRoot(document.getElementById('root')).render(<Harness />);
