import React, { useEffect, useState } from 'react';
import { loadDemoQuestions } from './demoQuestions.js';

export default function DemoQuestions({ customer, api, busy, onAsk }) {
  const [state, setState] = useState({ questions: [], note: '', loading: true });
  useEffect(() => {
    const controller = new AbortController();
    setState({ questions: [], note: '', loading: true });
    loadDemoQuestions(api, customer, controller.signal).then(result => {
      if (!controller.signal.aborted) setState({ ...result, loading: false });
    }).catch(() => {
      if (!controller.signal.aborted) setState({ questions: [], note: 'Demo questions are unavailable right now.', loading: false });
    });
    return () => controller.abort();
  }, [api, customer]);
  return <details className="demo-questions">
    <summary>Demo questions</summary>
    {state.loading ? <p className="fine" role="status">Loading recorded-period questions…</p> : <>
      <div className="starting-actions">
        {state.questions.map(item => <button key={item.id} type="button" disabled={busy}
          title={item.question} onClick={() => onAsk(item.question)}>{item.label}</button>)}
      </div>
      {state.note && <p className="fine">{state.note}</p>}
    </>}
  </details>;
}
