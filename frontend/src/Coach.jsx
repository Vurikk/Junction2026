import React, { useEffect, useRef, useState } from 'react';
import CoachSpendingChart from './CoachSpendingChart';

const questions = [
  { action: 'savings', label: 'What could I save most on?', icon: '↘' },
  { action: 'overview', label: 'Where did my money go?', icon: '≡' },
  { action: 'goals', label: 'Analyze my goals', icon: '◎' },
  { action: 'comparison', label: 'Am I spending more than usual?', icon: '↔' },
  { action: 'allowance', label: 'What extra could I spend?', icon: '€' },
  { action: 'tips', label: 'Everyday saving tips', icon: '✦' },
];

export default function Coach({ customer, api, money, open = true, initialQuestion = '' }) {
  const [messages, setMessages] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [retry, setRetry] = useState(null);
  const [showQuestions, setShowQuestions] = useState(true);
  const pending = useRef(null);
  const log = useRef(null);
  const profile = useRef(customer);
  useEffect(() => {
    profile.current = customer;
    pending.current?.abort(); pending.current = null;
    setMessages([]); setError(''); setRetry(null); setBusy(false); setShowQuestions(true);
    return () => pending.current?.abort();
  }, [customer]);
  useEffect(() => {
    if (open && log.current) log.current.scrollTop = log.current.lastElementChild?.offsetTop || 0;
  }, [messages, busy, error, open]);

  useEffect(() => {
    if (!open || !initialQuestion) return;
    const choice = questions.find(item => item.label === initialQuestion)
      || (initialQuestion === 'Spending by category' ? questions.find(item => item.action === 'overview') : null);
    if (choice) ask(choice);
  }, [open, initialQuestion, customer]);

  async function ask(choice, replay = false) {
    if (pending.current) return;
    const controller = new AbortController();
    const requestedProfile = customer;
    pending.current = controller; setBusy(true); setError(''); setRetry(null);
    if (!replay) setMessages(old => [...old, { user: true, text: choice.label }]);
    const { action, percent, month, category } = choice;
    try {
      const result = await api(`customers/${customer}/guided-coach`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, signal: controller.signal,
        body: JSON.stringify({ action, ...(percent ? { percent } : {}), ...(month ? { month } : {}),
          ...(category ? { category } : {}) }),
      });
      if (!controller.signal.aborted && profile.current === requestedProfile) {
        setMessages(old => [...old, { ...result, action }]);
        setShowQuestions(false);
      }
    } catch {
      if (!controller.signal.aborted && profile.current === requestedProfile) {
        setError('Could not load that calculation. Please try again.'); setRetry(choice);
      }
    } finally {
      if (pending.current === controller) { pending.current = null; setBusy(false); }
    }
  }
  return <section className="coach coach-conversation guided-coach" aria-label="Guided financial coach">
    <div className="guided-badge">Guided demo · Calculated from your data</div>
    <div className="conversation-log" ref={log} role="log" aria-label="Conversation" aria-live="polite" tabIndex={0}>
      <article className="chat coach-welcome"><small>Coach</small>
        <h3>Let's make sense of your money.</h3>
        <p>Pick a question. I'll use your recorded spending and goals to explain the numbers.</p>
      </article>
      {messages.map((item, index) => <article className={item.user ? 'chat user' : 'chat'} key={index}>
        <small>{item.user ? 'You' : 'Coach'}</small>
        <p>{item.text}</p>
        {item.source_period && <p className="guided-period">Recorded {item.source_period.start} – {item.source_period.end}</p>}
        {item.action === 'overview'
          ? <CoachSpendingChart rows={item.rows} period={item.source_period} money={money} />
          : item.rows?.map((row, i) => <div className="guided-result" key={i}>
          <div className="row"><span>{row.label}</span><strong>{money(row.value)}</strong></div>
          {row.detail && <p className="fine">{row.detail}</p>}
        </div>)}
        {item.tips && <ul>{item.tips.map((tip, i) => <li key={i}>{tip}</li>)}</ul>}
        {item.note && <details className="guided-note"><summary>About these numbers</summary><p>{item.note}</p></details>}
        {item.actions?.length > 0 && <div className="context-actions">
          {item.actions.map((choice, i) => <button key={i} disabled={busy} onClick={() => ask(choice)}>{choice.label}</button>)}
        </div>}
      </article>)}
      {busy && <p role="status">Calculating from your recorded data…</p>}
      {error && <div role="alert" className="error"><p>{error}</p>
        <button disabled={busy} onClick={() => ask(retry, true)}>Try again</button></div>}
    </div>
    {showQuestions && <div className="guided-questions" aria-label="Choose a question">
      {questions.map(choice => <button key={choice.action} disabled={busy} onClick={() => ask(choice)}>
        <span aria-hidden="true">{choice.icon}</span>{choice.label}</button>)}
    </div>}
    {messages.length > 0 && <button className="guided-more" disabled={busy}
      onClick={() => setShowQuestions(value => !value)} aria-expanded={showQuestions}>
      {showQuestions ? 'Hide questions' : 'Ask another question'}</button>}
    <p className="guided-footer">Preset questions. Real recorded figures. Nothing is saved or changed.</p>
  </section>;
}
