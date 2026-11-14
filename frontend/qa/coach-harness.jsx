// QA-only existing-contract fixtures. No Verda fields or paid calls.
import React, { useCallback, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import Coach from '../src/Coach';
import '../src/style.css';

function Harness() {
  const mode = useRef('success');
  const pending = useRef([]);
  const [customer, setCustomer] = useState('fixture-a');
  const [calls, setCalls] = useState(0);
  const api = useCallback(async () => {
    setCalls(value => value + 1);
    if (mode.current === 'error') throw new Error('QA-only network failure.');
    const result = { kind: 'categories', text: 'QA-only response, not live banking data.', rows: [{ label: 'Fixture category', value: 0 }] };
    if (mode.current === 'delayed') return new Promise(resolve => pending.current.push(() => resolve(result)));
    return result;
  }, []);
  return <main className="app"><h1>Coach QA fixtures only</h1>
    <label htmlFor="coach-mode">Response mode</label><select id="coach-mode" onChange={event => { mode.current = event.target.value; }}>
      <option>success</option><option>error</option><option>delayed</option>
    </select>
    <button onClick={() => setCustomer(value => value === 'fixture-a' ? 'fixture-b' : 'fixture-a')}>Switch fixture customer</button>
    <button onClick={() => pending.current.splice(0).forEach(resolve => resolve())}>Resolve delayed responses</button>
    <p>{customer} · Calls: {calls}</p>
    <Coach key={customer} customer={customer} api={api} onSaved={() => {}}
      money={value => value == null ? 'Not available' : `EUR ${Number(value).toFixed(2)}`} />
  </main>;
}
createRoot(document.getElementById('root')).render(<Harness />);
