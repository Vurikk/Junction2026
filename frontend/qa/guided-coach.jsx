// In-memory fixtures only. This page never fetches a backend or calls a provider.
import React, { useCallback, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import Coach from '../src/Coach.jsx';
import '../src/style.css';

function Harness() {
  const [customer, setCustomer] = useState('fixture-a');
  const [calls, setCalls] = useState([]);
  const mode = useRef('success');
  const pending = useRef([]);
  const api = useCallback(async (path, options = {}) => {
    setCalls(old => [...old, { path, method: options.method || 'GET', body: options.body }]);
    if (path.endsWith('coach-demo-prompts')) return { questions: [], note: 'Fixture-only guided test.' };
    if (mode.current === 'error') throw new Error('Fixture network failure.');
    const run = () => {
      if (path.includes('/savings-opportunities?')) {
        const twenty = path.includes('reduction_percent=20');
        return { status: mode.current === 'empty' ? 'no_candidates' : 'available', currency: 'EUR',
          source_period: { start: '2026-07-01', end: '2026-07-31' }, reduction_percent: twenty ? 20 : 10,
          candidates: mode.current === 'empty' ? [] : [{ category: 'restaurants', baseline_spending_eur: 95.04,
            hypothetical_spending_eur: twenty ? 76.03 : 85.54, potential_reduction_eur: twenty ? 19.01 : 9.50 }],
          note: 'Fixture amounts from an eligible historical purchase subset; incomplete coverage.' };
      }
      if (path.endsWith('/goals')) return path.includes('fixture-b') ? []
        : [{ id: 'g1', name: 'Emergency cushion', amount_eur: '200.00', priority: 'critical' }];
      if (path.endsWith('/goal-analysis')) return { status: 'insufficient_data',
        coach_message: 'Confirm your planning inputs before judging feasibility.', savings_capacity_eur: null, shortfall_eur: null,
        assumptions: { horizon_days: 30, repeat_plan: false }, missing_inputs: ['available_funds_eur', 'emergency_reserve_eur'],
        ordered_goal_ids: path.includes('fixture-b') ? [] : ['g1'],
        allocations: [{ goal_id: 'g1', allocated_eur: null, feasibility: 'unknown', completion_periods: null }] };
      const body = JSON.parse(options.body || '{}');
      return { conversation_id: body.conversation_id || crypto.randomUUID(), request_id: body.request_id,
        mode: 'rule_based', fallback_reason: 'disabled', text: 'Fixture free-text answer.', rows: [], cards: [] };
    };
    if (mode.current === 'delayed') return new Promise(resolve => pending.current.push(() => resolve(run())));
    return run();
  }, []);
  return <main className="app"><h1>Guided Coach fixtures</h1><p>No provider or backend calls. Amounts are fixed fixtures.</p>
    <label htmlFor="fixture-mode">Response mode</label>
    <select id="fixture-mode" onChange={event => { mode.current = event.target.value; }}>
      {['success', 'empty', 'error', 'delayed'].map(value => <option key={value}>{value}</option>)}
    </select>
    <button onClick={() => setCustomer(value => value === 'fixture-a' ? 'fixture-b' : 'fixture-a')}>Switch fixture customer</button>
    <button onClick={() => pending.current.splice(0).forEach(resolve => resolve())}>Resolve delayed requests</button>
    <p>Current customer: {customer}</p>
    <Coach key={customer} customer={customer} api={api} onSaved={() => {}}
      money={value => value == null ? 'Not available' : `EUR ${value}`} />
    <details><summary>Fixture request log</summary><pre>{JSON.stringify(calls, null, 2)}</pre></details>
  </main>;
}
createRoot(document.getElementById('root')).render(<Harness />);
