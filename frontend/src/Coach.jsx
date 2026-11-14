import React, { useState } from 'react';
import CategoryReduction from './CategoryReduction';

const suggestions = [
  'Spending by category', 'Spending vs historical average', 'Daily and weekly allowance', 'Goal progress', 'What if I add a goal?'];
export default function Coach({ customer, api, money, onSaved, initialQuestion = '' }) {
  const [messages, setMessages] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [question, setQuestion] = useState(initialQuestion);
  const [preview, setPreview] = useState(null);
  const [scenario, setScenario] = useState(false);
  const [reductionOpen, setReductionOpen] = useState(false);
  async function ask(text, draft) {
    setBusy(true); setError(''); setPreview(null);
    setMessages(old => [...old, { text, user: true }]);
    try {
      const result = await api(`customers/${customer}/coach`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: text, scenario: draft || null }),
      });
      setMessages(old => [...old, result]);
      setScenario(result.kind === 'scenario'); setPreview(result.preview || null);
    } catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  async function confirm() {
    setBusy(true); setError('');
    try {
      await api(`customers/${customer}/goals`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(preview),
      });
      setPreview(null); setScenario(false); onSaved();
      setMessages(old => [...old, { text: 'Goal saved.' }]);
      try {
        const analysis = await api(`customers/${customer}/goal-analysis`);
        setMessages(old => [...old, { text: analysis.coach_message }]);
      } catch {
        setMessages(old => [...old, { text: 'Your goal is saved. Its explanation is unavailable right now.' }]);
      }
    } catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  return <section className="coach"><h2>Let's talk about your money</h2>
    <p className="coach-label">Rule-based demo coach</p>
    <p>Explore recorded categories, compare with your usual spending or check an allowance.</p>
    <p className="fine">Uses English keywords and prepared explanations, not a live AI model.
      Use the guided spending preview to explore a category change.
      Allowance and goal estimates need a confirmed optional Home plan.</p>
    <button className="primary" aria-expanded={reductionOpen} onClick={() => setReductionOpen(value => !value)}>
      {reductionOpen ? 'Close spending preview' : 'Explore spending less'}</button>
    {reductionOpen && <CategoryReduction key={customer} customer={customer} api={api} money={money} />}
    <div className="suggestions">{suggestions.map(text =>
      <button key={text} disabled={busy} onClick={() => ask(text)}>{text}</button>)}</div>
    <div role="log" aria-live="polite">{messages.map((item, i) =>
      <article className={item.user ? 'chat user' : 'chat'} key={i}>
        <small>{item.user ? 'You' : 'Coach'}</small><p>{item.text}</p>
        {item.analysis && <div>
          <p>Current allowance: {money(item.baseline.daily_eur)}/day; {money(item.baseline.weekly_eur)}/week.</p>
          <p>With this goal: {money(item.analysis.daily_eur)}/day; {money(item.analysis.weekly_eur)}/week.</p>
          <p>Preview uses your current confirmed inputs. Amounts are estimates; no savings progress is assumed.</p>
        </div>}
        {item.rows?.map(row => <div className="row" key={row.label}><span>{row.label}</span><b>{money(row.value)}</b></div>)}
      </article>)}</div>
    {error && <p role="alert">{error}</p>}
    {busy && <p role="status">Checking your plan...</p>}
    <form onSubmit={e => { e.preventDefault(); ask(question); setQuestion(''); }}>
      <label htmlFor="question">Your question</label>
      <input id="question" value={question} onChange={e => setQuestion(e.target.value)} required maxLength={500} disabled={busy} />
      <button className="primary" disabled={busy || !question.trim()}>Ask coach</button>
    </form>
    {scenario && <form onChange={() => setPreview(null)} onSubmit={e => {
      e.preventDefault(); const fields = new FormData(e.currentTarget);
      ask('Preview this goal', Object.fromEntries(fields));
    }}><fieldset disabled={busy}><legend>Try adding a goal</legend>
      <label htmlFor="preview-name">Name</label><input id="preview-name" name="name" required maxLength={100} />
      <label htmlFor="preview-amount">Amount (EUR)</label>
      <input id="preview-amount" name="amount_eur" type="number" min="0.01" max="9999999999.99" step="0.01" required />
      <label htmlFor="preview-priority">Priority</label><select id="preview-priority" name="priority">
        <option value="flexible">Flexible</option><option value="important">Important</option><option value="critical">Critical</option>
      </select><button disabled={busy}>Preview without saving</button></fieldset>
    </form>}
    {preview && <div><p>Save {preview.name}, {money(preview.amount_eur)}, {preview.priority}?</p>
      <button disabled={busy} onClick={confirm}>Confirm and create goal</button>
      <button disabled={busy} onClick={() => setPreview(null)}>Discard preview</button></div>}
  </section>;
}
