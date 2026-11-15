import React, { useState } from 'react';

export default function RemoveGoalButton({ goal, busy, onRemove }) {
  const [confirming, setConfirming] = useState(false);
  if (!confirming) return <button type="button" className="text-button" disabled={busy}
    aria-label={`Remove ${goal.name}`} onClick={() => setConfirming(true)}>Remove goal</button>;
  return <div className="goal-remove-confirm">
    <p>Remove “{goal.name}” from your plan?</p>
    <button type="button" disabled={busy} onClick={() => onRemove(goal)}>Yes, remove</button>
    <button type="button" disabled={busy} onClick={() => setConfirming(false)}>Keep goal</button>
  </div>;
}
