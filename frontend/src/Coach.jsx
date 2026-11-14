import React, { useEffect, useRef, useState } from 'react';
import CategoryReduction from './CategoryReduction';

export default function Coach({ customer, api, money, onSaved, initialQuestion = '' }) {
  const [messages, setMessages] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [retry, setRetry] = useState(null);
  const [question, setQuestion] = useState(initialQuestion);
  const [preview, setPreview] = useState(null);
  const [draft, setDraft] = useState({ name: '', amount_eur: '', priority: 'flexible' });
  const pending = useRef(null);
  const mounted = useRef(false);
  const log = useRef(null);
  const composer = useRef(null);
  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; pending.current?.abort(); };
  }, [customer]);
  useEffect(() => {
    if (log.current) log.current.scrollTop = log.current.scrollHeight;
  }, [messages, busy, error]);
  useEffect(() => {
    const keepComposerVisible = () => {
      if (composer.current?.contains(document.activeElement)) composer.current.scrollIntoView({ block: 'nearest' });
    };
    window.visualViewport?.addEventListener('resize', keepComposerVisible);
    return () => window.visualViewport?.removeEventListener('resize', keepComposerVisible);
  }, []);

  function startTool(tool, text) {
    if (pending.current) return;
    setPreview(null); setError(''); setRetry(null);
    setMessages(old => [...old.filter(item => !item.tool), { text, user: true }, { tool }]);
  }
  async function ask(text, scenario, userText = text) {
    if (pending.current || !text.trim()) return;
    const controller = new AbortController();
    pending.current = controller;
    setBusy(true); setError(''); setRetry(null); setPreview(null);
    setMessages(old => [...old, { text: userText, user: true }]);
    try {
      const result = await api(`customers/${customer}/coach`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, signal: controller.signal,
        body: JSON.stringify({ question: text, scenario: scenario || null }),
      });
      if (!mounted.current || controller.signal.aborted) return;
      setMessages(old => result.kind === 'scenario' && !result.preview
        ? [...old.filter(item => !item.tool), result, { tool: 'goal' }] : [...old, result]);
      setPreview(result.preview || null);
    } catch (e) {
      if (!mounted.current || controller.signal.aborted) return;
      setError(e.message); setRetry({ text, scenario, userText });
    } finally {
      if (mounted.current && pending.current === controller) { pending.current = null; setBusy(false); }
    }
  }
  async function confirm() {
    if (pending.current || !preview) return;
    const controller = new AbortController();
    pending.current = controller;
    setBusy(true); setError(''); setRetry(null);
    try {
      await api(`customers/${customer}/goals`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, signal: controller.signal,
        body: JSON.stringify(preview),
      });
      if (!mounted.current || controller.signal.aborted) return;
      setPreview(null); onSaved();
      setMessages(old => [...old.filter(item => !item.tool), { text: 'Goal saved.' }]);
      try {
        const analysis = await api(`customers/${customer}/goal-analysis`, { signal: controller.signal });
        if (mounted.current && !controller.signal.aborted) setMessages(old => [...old, { text: analysis.coach_message }]);
      } catch {
        if (mounted.current && !controller.signal.aborted) {
          setMessages(old => [...old, { text: 'Your goal is saved. Its explanation is unavailable right now.' }]);
        }
      }
    } catch (e) {
      if (mounted.current && !controller.signal.aborted) {
        setPreview(null); setError(`${e.message} Check Goals before trying to create it again.`);
      }
    } finally {
      if (mounted.current && pending.current === controller) { pending.current = null; setBusy(false); }
    }
  }
  function editDraft(key, value) {
    setPreview(null); setRetry(null);
    setDraft(old => ({ ...old, [key]: value }));
  }
  return <section className="coach coach-conversation" aria-label="Financial coach conversation">
    <div className="conversation-mode"><span>Rule-based demo</span><details><summary>How it works</summary>
      <p>Prepared explanations and guided calculations. English keywords only; follow-up memory and live AI are not connected.</p>
    </details></div>
    <p className="conversation-welcome">Let’s make sense of your money. Where shall we start?</p>
    <div className="starting-actions">
      <button disabled={busy} onClick={() => ask('Spending by category', null, 'Understand spending')}>Understand spending</button>
      <button disabled={busy} onClick={() => startTool('savings', 'Explore savings')}>Explore savings</button>
      <button disabled={busy} onClick={() => ask('Goal progress', null, 'My goals')}>My goals</button>
    </div>
    <div className="conversation-log" ref={log} role="log" aria-label="Conversation" aria-live="polite" tabIndex={0}>
      {messages.length === 0 && <p className="conversation-empty">Choose a starting point or ask a question below.</p>}
      {messages.map((item, index) => <article className={item.user ? 'chat user' : 'chat'} key={index}>
        <small>{item.user ? 'You' : 'Coach'}</small>
        {item.tool === 'savings' ? <CategoryReduction customer={customer} api={api} money={money} />
          : item.tool === 'goal' ? <form onSubmit={event => {
            event.preventDefault(); ask('Preview this goal', draft);
          }}><fieldset disabled={busy}><legend>Try a goal</legend>
            <label htmlFor="preview-name">Name</label><input id="preview-name" value={draft.name} required maxLength={100}
              onChange={event => editDraft('name', event.target.value)} />
            <label htmlFor="preview-amount">Amount (EUR)</label>
            <input id="preview-amount" type="number" min="0.01" max="9999999999.99" step="0.01" required
              value={draft.amount_eur} onChange={event => editDraft('amount_eur', event.target.value)} />
            <label htmlFor="preview-priority">Priority</label>
            <select id="preview-priority" value={draft.priority} onChange={event => editDraft('priority', event.target.value)}>
              <option value="flexible">Flexible</option><option value="important">Important</option><option value="critical">Critical</option>
            </select><button className="primary" disabled={busy}>Preview without saving</button>
          </fieldset></form> : <>
            <p>{item.text}</p>
            {item.analysis && <div className="conversation-result">
              <div className="row"><span>Current daily estimate</span><b>{money(item.baseline.daily_eur)}</b></div>
              <div className="row"><span>With this goal</span><b>{money(item.analysis.daily_eur)}</b></div>
              <p className="fine">Hypothetical goal · not saved yet</p>
              <details><summary>Plan details</summary>
                <p>Weekly estimate: {money(item.baseline.weekly_eur)} → {money(item.analysis.weekly_eur)}.</p>
                <p>Uses confirmed planning inputs; actual saved progress is unknown.</p>
              </details>
            </div>}
            {item.rows?.map(row => <div className="row" key={row.label}><span>{row.label}</span><b>{money(row.value)}</b></div>)}
            {item.kind === 'categories' && <div className="context-actions">
              <button disabled={busy} onClick={() => ask('Spending vs historical average')}>Compare with usual</button>
              <button disabled={busy} onClick={() => ask('Daily and weekly allowance')}>Check safe spending</button>
            </div>}
            {item.kind === 'goals' && <button disabled={busy}
              onClick={() => startTool('goal', 'Try adding a goal')}>Preview a new goal</button>}
          </>}
      </article>)}
      {preview && <div className="chat confirmation"><p>Create {preview.name}, {money(preview.amount_eur)}, {preview.priority}?</p>
        <button className="primary" disabled={busy} onClick={confirm}>Confirm and create goal</button>
        <button disabled={busy} onClick={() => setPreview(null)}>Discard preview</button></div>}
      {busy && <p role="status" className="checking">Checking your recorded information…</p>}
      {error && <div className="error" role="alert"><p>{error}</p>
        {retry && <button disabled={busy} onClick={() => ask(retry.text, retry.scenario, retry.userText)}>Retry answer</button>}</div>}
    </div>
    <form className="chat-composer" ref={composer} onSubmit={event => {
      event.preventDefault(); ask(question); setQuestion('');
    }}>
      <label htmlFor="question">Message Coach</label>
      <div><input id="question" value={question} onChange={event => setQuestion(event.target.value)} required maxLength={500}
        placeholder="Spending, averages or allowances" disabled={busy} autoComplete="off" />
        <button className="primary" disabled={busy || !question.trim()} aria-label="Send message">Send</button></div>
      <small>No conversation memory yet. Use guided controls for changes.</small>
    </form>
  </section>;
}
