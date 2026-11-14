import React, { useEffect, useRef, useState } from 'react';
import { categoriesFor, eligibleMonths, preferredCategory, validReduction } from './reductionOptions';

export default function CategoryReduction({ customer, api, money }) {
  const [months, setMonths] = useState([]);
  const [month, setMonth] = useState('');
  const [category, setCategory] = useState('');
  const [percent, setPercent] = useState('20');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [historyError, setHistoryError] = useState(false);
  const [reload, setReload] = useState(0);
  const [result, setResult] = useState(null);
  const request = useRef(null);
  const version = useRef(0);
  const mounted = useRef(false);
  const resultCard = useRef(null);
  useEffect(() => { if (result) resultCard.current?.scrollIntoView({ block: 'nearest' }); }, [result]);

  useEffect(() => {
    mounted.current = true;
    const controller = new AbortController();
    setLoading(true); setError(''); setHistoryError(false); setMonths([]); setResult(null);
    api(`customers/${customer}/spending-history?period=month`, { signal: controller.signal }).then(history => {
      if (controller.signal.aborted) return;
      const options = eligibleMonths(history);
      setMonths(options); setMonth(options[0]?.start || ''); setCategory(preferredCategory(options[0]));
    }).catch(e => {
      if (controller.signal.aborted) return;
      setError(e.message); setHistoryError(true);
    }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => {
      mounted.current = false; controller.abort(); request.current?.abort(); version.current += 1;
    };
  }, [customer, api, reload]);

  function invalidate() {
    version.current += 1; request.current?.abort(); request.current = null;
    setResult(null); setError(''); setBusy(false);
  }
  async function preview(event) {
    event.preventDefault();
    if (request.current) return;
    setResult(null); setError('');
    if (!month || !category || !validReduction(percent)) {
      setError('Choose a recorded month and category, and enter 0–100% with at most two decimal places.');
      return;
    }
    const controller = new AbortController();
    request.current = controller;
    const revision = ++version.current;
    setBusy(true);
    try {
      const response = await api(`customers/${customer}/category-reduction`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, signal: controller.signal,
        body: JSON.stringify({ category, period: 'month', period_start: month, reduction_percent: percent }),
      });
      if (mounted.current && revision === version.current && !controller.signal.aborted) setResult(response);
    } catch (e) {
      if (mounted.current && revision === version.current && !controller.signal.aborted) setError(e.message);
    } finally {
      if (mounted.current && revision === version.current) { setBusy(false); request.current = null; }
    }
  }
  const selected = months.find(item => item.start === month);
  return <div className="reduction-panel"><h3>Explore spending less</h3>
    <p className="fine">Try a change to a recorded month. This preview does not change your plan or goals.</p>
    {loading && <p role="status">Loading recorded months…</p>}
    {error && <p className="error" role="alert">{error}</p>}
    {!loading && historyError && <button onClick={() => setReload(value => value + 1)}>Retry loading months</button>}
    {!loading && !historyError && !months.length && <>
      <p>No complete recorded month with supported categories is available.</p>
      <button onClick={() => setReload(value => value + 1)}>Check again</button>
    </>}
    {!loading && !historyError && months.length > 0 && <form onSubmit={preview}>
      <label htmlFor="reduction-month">Recorded month</label>
      <select id="reduction-month" value={month} onChange={event => {
        invalidate(); setMonth(event.target.value);
        setCategory(preferredCategory(months.find(item => item.start === event.target.value)));
      }}>{months.map(item => <option key={item.start} value={item.start}>{item.start.slice(0, 7)}</option>)}</select>
      <label htmlFor="reduction-category">Category</label>
      <select id="reduction-category" value={category} onChange={event => { invalidate(); setCategory(event.target.value); }}>
        {categoriesFor(selected).map(name => <option key={name}>{name}</option>)}
      </select>
      <label htmlFor="reduction-percent">Spend less by (%)</label>
      <input id="reduction-percent" type="number" inputMode="decimal" min="0" max="100" step="0.01" required
        value={percent} onChange={event => { invalidate(); setPercent(event.target.value); }} />
      <button className="primary" disabled={busy}>{busy ? 'Calculating…' : error ? 'Retry preview' : 'Preview change'}</button>
    </form>}
    {result && <div className="reduction-result" role="status" ref={resultCard}>
      <h3>Potential spending reduction: {money(result.potential_reduction_eur)}</h3>
      <p>{result.category} · {result.source_period.start}–{result.source_period.end}</p>
      <div className="row"><span>Recorded spending</span><b>{money(result.baseline_spending_eur)}</b></div>
      <div className="row"><span>With {result.reduction_percent}% less</span><b>{money(result.hypothetical_spending_eur)}</b></div>
      <p className="fine">Hypothetical change, not money already saved. Goal timing impact is unavailable.</p>
      <details><summary>How to read this preview</summary><p>{result.note}</p><p>{result.goal_impact_unavailable_reason}</p></details>
    </div>}
  </div>;
}
