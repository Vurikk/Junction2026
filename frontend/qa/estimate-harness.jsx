import React, { useCallback, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import SafeToSpend from '../src/SafeToSpend';
import '../src/style.css';
function Harness() {
  const [customer, setCustomer] = useState('fixture-a');
  const [request, setRequest] = useState('');
  const [revision, setRevision] = useState(0);
  const [goals, setGoals] = useState([{ id: 'fixture-goal' }]);
  const mode = useRef('success');
  const delayed = useRef([]);
  const api = useCallback(async (path, options = {}) => {
    setRequest(`${path} ${options.method || 'GET'}`);
    if (mode.current === 'error') throw new Error('Fixture error, no backend call.');
    const result = { status: mode.current === 'missing' ? 'insufficient_data' : 'estimated',
      daily_eur: mode.current === 'zero' ? 0 : 12.34, weekly_eur: mode.current === 'zero' ? 0 : 86.38,
      source_period: { start: '2026-06-01', end: '2026-08-31' },
      missing_inputs: mode.current === 'missing' ? ['income_evidence:2026-07'] : [],
      policy: { reserve_income_percent: 10, goal_surplus_percent: 50, basis: 'App demo assumptions, not bank policy.' },
      limitations: ['Mock fixture only.'] };
    if (mode.current === 'delayed') return new Promise(resolve => delayed.current.push(() => resolve(result)));
    return result;
  }, []);
  return <main className="app"><h1>Estimate fixtures only</h1>
    <label htmlFor="mode">Response mode</label><select id="mode" onChange={e => {
      mode.current = e.target.value; setRevision(value => value + 1);
    }}><option>success</option><option>zero</option><option>missing</option><option>error</option><option>delayed</option></select>
    <button onClick={() => setCustomer(value => value === 'fixture-a' ? 'fixture-b' : 'fixture-a')}>Switch customer</button>
    <button onClick={() => delayed.current.splice(0).forEach(resolve => resolve())}>Resolve delayed</button>
    <button onClick={() => setGoals([])}>Clear goals</button>
    <div className="money-card"><div className="coach-allowance-group">
    <SafeToSpend customer={customer} api={api} refreshKey={revision} goals={goals}
      money={value => value == null ? 'Not available' : `EUR ${value}`}
      onAddGoal={() => setGoals([{ id: 'fixture-goal' }])} /></div></div><output>{request}</output>
  </main>;
}
createRoot(document.getElementById('root')).render(<Harness />);
