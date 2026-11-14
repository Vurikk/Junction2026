import React, { useEffect, useRef, useState } from 'react';
import CategoryReduction from './CategoryReduction';
import CoachResult from './CoachResult';
import DemoQuestions from './DemoQuestions.jsx';
import GuidedCoach from './GuidedCoach.jsx';
import { guidedStarter, loadGuidedTurn } from './guidedCoach.js';
import { canFollowUpReduction } from './demoQuestions.js';
import { createCoachSession, coachModeLabel, fallbackNotice } from './coachSession';

export default function Coach({ customer, api, money, onSaved, initialQuestion = '', open = true }) {
  const [messages, setMessages] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [retry, setRetry] = useState(null);
  const [question, setQuestion] = useState(initialQuestion);
  const [preview, setPreview] = useState(null);
  const [draft, setDraft] = useState({ name: '', amount_eur: '', priority: 'flexible' });
  const pending = useRef(null);
  const session = useRef(null);
  if (!session.current || session.current.customer !== customer) {
    session.current = { customer, client: createCoachSession(api, customer) };
  }
  const mounted = useRef(false);
  const log = useRef(null);
  const composer = useRef(null);
  useEffect(() => {
    if (open && initialQuestion) setQuestion(current => current || initialQuestion);
  }, [initialQuestion, open]);
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
  async function guide(action, text, retryTurn = null) {
    if (pending.current) return;
    const controller = new AbortController();
    pending.current = controller;
    const turn = retryTurn || { id: crypto.randomUUID(), action, text };
    setBusy(true); setError(''); setRetry(null); setPreview(null);
    if (!retryTurn) setMessages(old => [...old, { text, user: true }]);
    try {
      const result = await loadGuidedTurn(api, customer, turn.action, controller.signal);
      if (!mounted.current || controller.signal.aborted) return;
      setMessages(old => [...old.filter(item => item.turnId !== turn.id), { ...result, turnId: turn.id }]);
    } catch (e) {
      if (!mounted.current || controller.signal.aborted) return;
      setError(e.message); setRetry({ guided: turn });
    } finally {
      if (mounted.current && pending.current === controller) { pending.current = null; setBusy(false); }
    }
  }
  async function ask(text, scenario, userText = text, retryTurn = null) {
    if (pending.current || !text.trim()) return;
    const guided = !scenario && !retryTurn && guidedStarter(text);
    if (guided) return guide(guided, userText);
    const controller = new AbortController();
    pending.current = controller;
    setBusy(true); setError(''); setRetry(null); setPreview(null);
    const turn = retryTurn || session.current.client.turn(text, scenario || null);
    if (!retryTurn) setMessages(old => [...old, { text: userText, user: true }]);
    try {
      const result = await session.current.client.send(turn, controller.signal);
      if (!mounted.current || controller.signal.aborted) return;
      const answer = { ...result, turnId: turn.request_id };
      setMessages(old => {
        const previous = old.filter(item => item.turnId !== turn.request_id);
        return result.kind === 'scenario' && !result.preview && !result.cards?.length && /\bgoal\b/i.test(text)
          ? [...previous.filter(item => !item.tool), answer, { tool: 'goal' }] : [...previous, answer];
      });
      if (['request_in_progress', 'rate_limited', 'concurrency_limit'].includes(result.fallback_reason)) {
        setError(fallbackNotice(result.fallback_reason)); setRetry({ text, scenario, userText, turn });
      }
      setPreview(result.preview || null);
    } catch (e) {
      if (!mounted.current || controller.signal.aborted) return;
      setError(e.message); setRetry({ text, scenario, userText, turn });
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
    <small className="guided-label">Guided coaching · explore without changing your plan</small>
    <div className="starting-actions">
      <button disabled={busy} onClick={() => guide({ type: 'savings' }, 'What could I save on?')}>What could I save on?</button>
      <button disabled={busy} onClick={() => guide({ type: 'goals' }, 'Are my goals realistic?')}>Are my goals realistic?</button>
      <button disabled={busy} onClick={() => guide({ type: 'habits' }, 'Help with everyday habits')}>Help with everyday habits</button>
    </div>
    <DemoQuestions customer={customer} api={api} busy={busy} onAsk={text => ask(text)} />
    <div className="conversation-log" ref={log} role="log" aria-label="Conversation" aria-live="polite" tabIndex={0}>
      {messages.length === 0 && <p className="conversation-empty">What would you like to explore?</p>}
      {messages.map((item, index) => <article className={item.user ? 'chat user' : 'chat'} key={index}>
        <small>{item.user ? 'You' : item.guided ? 'Guided coaching' : item.tool ? 'Coach' : coachModeLabel(item)}</small>
        {item.guided ? <GuidedCoach turn={item.guided} money={money} busy={busy}
          active={index === messages.length - 1 && !error && !retry} onChoose={guide}
          onCreateGoal={() => startTool('goal', 'Preview a new goal')} />
          : item.tool === 'savings' ? <CategoryReduction customer={customer} api={api} money={money} />
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
            {fallbackNotice(item.fallback_reason) && <p className="fine">{fallbackNotice(item.fallback_reason)}</p>}
            {item.cards?.map((card, cardIndex) => <CoachResult key={cardIndex} card={card} money={money} />)}
            {index === messages.length - 1 && !error && !retry && canFollowUpReduction(item) &&
              <button disabled={busy} onClick={() => ask('What about 10% instead?')}>What about 10% instead?</button>}
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
        {retry && <button disabled={busy}
          onClick={() => retry.guided ? guide(retry.guided.action, retry.guided.text, retry.guided)
            : ask(retry.text, retry.scenario, retry.userText, retry.turn)}>Retry answer</button>}</div>}
    </div>
    <form className="chat-composer" ref={composer} onSubmit={event => {
      event.preventDefault(); ask(question); setQuestion('');
    }}>
      <label htmlFor="question">Message Coach</label>
      <div><input id="question" value={question} onChange={event => setQuestion(event.target.value)} required maxLength={500}
        placeholder="Spending, averages or allowances" disabled={busy} autoComplete="off" />
        <button className="primary" disabled={busy || !question.trim()} aria-label="Send message">Send</button></div>
      <small>Free-text Coach remains available. Guided answers use local calculations; they do not send messages to AI.</small>
    </form>
  </section>;
}
