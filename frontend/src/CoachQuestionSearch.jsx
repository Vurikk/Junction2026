import React, { useState } from 'react';

const choices = [
  { action: 'savings', label: 'What could I save most on?', keywords: 'save savings reduce cut restaurants entertainment travel' },
  { action: 'monthly_savings', label: 'How much could I save each month?', keywords: 'save savings monthly income surplus' },
  { action: 'goal_timing', label: 'When could I reach my goals?', keywords: 'save savings goal goals when time weeks months reach finish' },
  { action: 'goals', label: 'Analyze my goals', keywords: 'goal goals analyze analysis priority allocation' },
  { action: 'overview', label: 'Where did my money go?', keywords: 'spending spent money categories purchases food' },
  { action: 'comparison', label: 'Am I spending more than usual?', keywords: 'spending compare comparison usual average more less' },
  { action: 'allowance', label: 'What extra could I spend?', keywords: 'spend safe allowance extra available daily weekly budget' },
  { action: 'tips', label: 'Everyday saving tips', keywords: 'saving tips advice habits help' },
];

export function findQuestions(value) {
  const query = value.trim().toLowerCase().replace(/[^a-z0-9 ]/g, '');
  if (!query) return [];
  const exact = choices.find(choice => choice.label.toLowerCase().replace(/[^a-z0-9 ]/g, '') === query);
  if (exact) return [exact];
  const terms = query.split(/\s+/).filter(term => term.length > 2 && !['the', 'can', 'could', 'how', 'what', 'does'].includes(term));
  return choices.filter(choice => terms.some(term => `${choice.label} ${choice.keywords}`.toLowerCase().includes(term))).slice(0, 3);
}

export default function CoachQuestionSearch({ busy, onAsk }) {
  const [value, setValue] = useState('');
  const [notice, setNotice] = useState('');
  const matches = findQuestions(value);
  function choose(choice) {
    if (busy) return;
    setValue(''); setNotice(''); onAsk(choice);
  }
  return <div className="coach-question-search">
    {value.trim() && <div className="coach-search-results" aria-label="Suggested questions">
      {matches.map(choice => <button key={choice.action} type="button" disabled={busy}
        onClick={() => choose(choice)}>{choice.label}</button>)}
      {!matches.length && <p role="status">Try “save”, “goals” or “spending”, or pick a question above.</p>}
    </div>}
    <form className="coach-search-form" onSubmit={event => {
      event.preventDefault();
      if (matches.length === 1) choose(matches[0]);
      else setNotice(matches.length ? 'Choose one of the suggested questions.' : 'Try save, goals or spending.');
    }}>
      <input type="text" value={value} maxLength={160} aria-label="Find a Coach question"
        placeholder="Type to find a question…" autoComplete="off" enterKeyHint="search"
        onChange={event => { setValue(event.target.value); setNotice(''); }} />
      <button type="button" className="coach-microphone" aria-label="Voice input (future feature)"
        onClick={() => setNotice('Voice input is a future feature. Please type or select a question for now.')}>
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
          <rect x="9" y="2" width="6" height="13" rx="3" />
          <path d="M5 10v2a7 7 0 0 0 14 0v-2M12 19v3M8 22h8" />
        </svg>
      </button>
    </form>
    {notice && <p className="fine" role="status">{notice}</p>}
  </div>;
}
