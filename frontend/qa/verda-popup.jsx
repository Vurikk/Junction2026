// Local fixtures only: no fetch, provider, backend, cookie or financial calculation.
import React, { useCallback, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import Coach from '../src/Coach';
import CoachDialog from '../src/CoachDialog';
import '../src/style.css';

function Harness() {
  const [customer, setCustomer] = useState('fixture-a');
  const [open, setOpen] = useState(false);
  const [calls, setCalls] = useState([]);
  const [saves, setSaves] = useState(0);
  const mode = useRef('success');
  const delayed = useRef([]);
  const api = useCallback(async (path, options = {}) => {
    const body = JSON.parse(options.body || '{}');
    setCalls(old => [...old, { path, ...body }]);
    if (path.endsWith('/goals')) { setSaves(value => value + 1); return {}; }
    if (path.endsWith('/goal-analysis')) return { coach_message: 'Fixture goal saved locally in this harness only.' };
    if (!body.conversation_id) return { conversation_id: crypto.randomUUID(), fallback_reason: 'session_initialized' };
    const base = { conversation_id: body.conversation_id, request_id: body.request_id, mode: 'llm', cards: [] };
    if (mode.current === 'network') throw new Error('Fixture network failure');
    if (mode.current === 'delayed') return new Promise(resolve => delayed.current.push(() => resolve({
      ...base, text: 'Old customer delayed fixture response',
    })));
    if (mode.current === 'clarification') return { ...base, mode: 'rule_based',
      fallback_reason: 'clarification_needed', text: 'Which month do you mean?' };
    if (mode.current === 'missing') return { ...base, mode: 'rule_based',
      fallback_reason: 'unsupported_period_or_category', text: 'No matching recorded period.' };
    if (mode.current === 'busy') return { ...base, mode: 'rule_based',
      fallback_reason: 'request_in_progress', text: 'The original request is still being checked.' };
    if (body.scenario) return { ...base, mode: 'rule_based', fallback_reason: 'goal_preview', kind: 'scenario',
      text: 'Fixture preview only. Planning inputs are unknown.', preview: body.scenario,
      baseline: { daily_eur: null, weekly_eur: null }, analysis: { daily_eur: null, weekly_eur: null } };
    if (body.question === 'Goal progress') return { ...base, mode: 'rule_based', kind: 'goals', text: 'Fixture goals.' };
    return { ...base, mode: mode.current === 'fallback' ? 'rule_based' : 'llm',
      fallback_reason: mode.current === 'fallback' ? 'provider_error' : null,
      kind: 'scenario', text: 'Mocked Python result: a hypothetical reduction, not actual savings.',
      cards: [{ type: 'category_reduction', data: { category: 'restaurants', currency: 'EUR',
        period: 'month', source_period: { start: '2026-07-01', end: '2026-07-31' },
        reduction_percent: 20, baseline_spending_eur: 95.04, hypothetical_spending_eur: 76.03, potential_reduction_eur: 19.01 } }] };
  }, []);
  return <main className="app"><h1>Mocked popup QA</h1><p>No provider or backend calls. Amounts are fixtures.</p>
    <label htmlFor="mode">Fixture response</label><select id="mode" onChange={e => { mode.current = e.target.value; }}>
      {['success', 'network', 'delayed', 'clarification', 'missing', 'busy', 'fallback'].map(value =>
        <option key={value}>{value}</option>)}
    </select><button onClick={() => setCustomer(value => value === 'fixture-a' ? 'fixture-b' : 'fixture-a')}>Switch customer</button>
    <button onClick={() => delayed.current.splice(0).forEach(resolve => resolve())}>Resolve delayed</button>
    <button onClick={() => setOpen(true)}>Open Coach</button><p>{customer} · Saved goals: {saves}</p>
    <output aria-label="Request log"><pre style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>
      {JSON.stringify(calls, null, 2)}</pre></output>
    <CoachDialog open={open} onClose={() => setOpen(false)}><Coach key={customer} customer={customer} api={api}
      money={value => value == null ? 'Not available' : `EUR ${Number(value).toFixed(2)}`} onSaved={() => {}} open={open} />
    </CoachDialog>
  </main>;
}
createRoot(document.getElementById('root')).render(<Harness />);
