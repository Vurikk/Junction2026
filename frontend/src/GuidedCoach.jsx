import React from 'react';
import { feasibilityLabels, planningLabels } from './guidedCoach.js';

export default function GuidedCoach({ turn, money, active, busy, onChoose, onCreateGoal }) {
  const { type, data, category, analysis, goals } = turn;
  const row = (label, value) => <div className="row"><span>{label}</span><b>{money(value)}</b></div>;
  const choice = (label, action) => active &&
    <button type="button" disabled={busy} onClick={() => onChoose(action, label)}>{label}</button>;
  const commonChoices = <div className="context-actions">
    {choice('Are my goals realistic?', { type: 'goals' })}
    {choice('Help with everyday habits', { type: 'habits' })}
  </div>;
  if (type === 'savings' || type === 'reduction') {
    const month = data.source_period?.start?.slice(0, 7);
    const candidate = data.candidates?.find(item => item.category === category);
    return <div className="guided-turn">
      {data.source_period && <p className="fine">Historical records: {data.source_period.start} – {data.source_period.end}</p>}
      {data.status !== 'available' || !data.candidates?.length || (category && !candidate) ? <>
        <p>{data.status === 'unavailable_period' ? 'There is no usable full recorded month for this question.'
          : 'There are no eligible purchases to explore here. That does not mean you have no other spending.'}</p>
        <p>{data.note}</p>{commonChoices}
      </> : type === 'savings' ? <>
        <p>We can start with these recorded purchases. Which could you comfortably change?</p>
        <p className="fine">These are possibilities to discuss, not a judgement that the spending was unnecessary.</p>
        {data.candidates.map(item => <div className="conversation-result" key={item.category}>
          <h3>{item.category}</h3>
          {row('Eligible recorded purchases', item.baseline_spending_eur)}
          {row(`Potential reduction at ${data.reduction_percent}%`, item.potential_reduction_eur)}
          <div className="context-actions">{choice(`Explore ${item.category}`, {
            type: 'reduction', month, category: item.category, percent: data.reduction_percent,
          })}</div>
        </div>)}
        <p className="fine">{data.note}</p>
        <p>Protect essentials and your emergency reserve. A historical reduction is not money available today.</p>
        {commonChoices}
      </> : <>
        <p>What would {data.reduction_percent}% less on eligible {category} purchases have looked like in that month?</p>
        <div className="conversation-result">
          {row('Recorded eligible purchases', candidate.baseline_spending_eur)}
          {row('Hypothetical spending', candidate.hypothetical_spending_eur)}
          {row('Potential reduction', candidate.potential_reduction_eur)}
        </div>
        <p className="fine">{data.note}</p>
        <p>This is a historical what-if, not a forecast or money already saved. Your plan and goals are unchanged.</p>
        <div className="context-actions">
          {[10, 20].map(percent => <React.Fragment key={percent}>
            {choice(`Try ${percent}%`, { type: 'reduction', category, month, percent })}
          </React.Fragment>)}
          {choice('Is that realistic for me?', { type: 'realism', category, month })}
          {choice('Could this help my goals?', { type: 'goals', fromSavings: true })}
          {choice('Explore another category', { type: 'savings', month })}
        </div>
      </>}
    </div>;
  }
  if (type === 'realism') return <div className="guided-turn">
    <p>Only you can tell which {category} purchases were optional. The records from {turn.month} cannot tell us that.</p>
    <p>Think of one purchase you would happily skip or replace. Would that still leave room for essentials and things you value?</p>
    <p>Try a small change first and check what actually happens. We cannot promise the same spending or reduction in a future month.</p>
    <div className="context-actions">
      {choice('Try a smaller 10% scenario', { type: 'reduction', category, month: turn.month, percent: 10 })}
      {choice('Could this help my goals?', { type: 'goals', fromSavings: true })}
      {choice('Help me choose a habit', { type: 'habits' })}
    </div>
  </div>;
  if (type === 'goals') return <div className="guided-turn">
    {turn.fromSavings && <p>A change could help if it really leaves money available in your future plan.
      We have not added the historical reduction to your savings capacity.</p>}
    {!goals.length ? <>
      <p>You have no saved goals yet. Start with one thing you want to fund, its remaining cost and how important it is.</p>
      <p>You can preview it first. It is saved only after you confirm.</p>
    </> : <>
      <p>{analysis.coach_message || analysis.explanation}</p>
      <p>{analysis.assumptions?.horizon_days != null
        ? `Your planning period is ${analysis.assumptions.horizon_days} days.` : 'Your planning period is not available.'}
        {' '}Critical goals come first, then important, then flexible.</p>
      {row('Capacity from your confirmed plan', analysis.savings_capacity_eur)}
      {analysis.status === 'insufficient_data' && <p>We cannot judge feasibility until the missing planning amounts are confirmed.</p>}
      {row('Bills and reserve shortfall', analysis.shortfall_eur)}
      <p className="fine">Capacity is separate from your chosen contribution. A zero shortfall covers only bills and reserve,
        not proof that everyday costs are covered.</p>
      {(analysis.ordered_goal_ids || goals.map(goal => goal.id)).map(id => {
        const goal = goals.find(item => item.id === id);
        if (!goal) return null;
        const allocation = analysis.allocations?.find(item => item.goal_id === id);
        return <div className="conversation-result" key={id}>
          <h3>{goal.name}</h3><p className="fine">Priority: {goal.priority}</p>
          {row('Remaining target', goal.amount_eur)}
          {row('Allocated in this plan', allocation?.allocated_eur)}
          <p>{feasibilityLabels[allocation?.feasibility] || 'Cannot assess yet'}</p>
          <p>{analysis.status === 'estimated' && analysis.assumptions?.repeat_plan && allocation?.completion_periods != null
            ? `${allocation.completion_periods} plan periods of ${analysis.assumptions.horizon_days} days, if capacity and contribution repeat.`
            : 'Completion time is not available from the confirmed plan.'}</p>
        </div>;
      })}
      <p className="fine">Timing requires the same capacity each period. Actual saved progress is unknown.
        No interest or price changes are modelled. Check that bills can be paid before everyday spending.</p>
    </>}
    <div className="context-actions">
      {!!analysis.missing_inputs?.length && choice('What do I need to confirm?', {
        type: 'inputs', missing: analysis.missing_inputs, horizon: analysis.assumptions?.horizon_days,
      })}
      {choice('What could I save on?', { type: 'savings' })}
      {active && <button type="button" disabled={busy} onClick={onCreateGoal}>Preview a new goal</button>}
    </div>
  </div>;
  if (type === 'inputs') return <div className="guided-turn">
    <p>In Home, open your spending plan and confirm these amounts for the same
      {turn.horizon != null ? ` ${turn.horizon}-day` : ''} planning period:</p>
    <ul>{turn.missing.map(field => <li key={field}>{planningLabels[field] || 'Another required planning amount'}</li>)}</ul>
    <p>Use zero only when you know there is none; leave unknown amounts blank. Do not count income already in accessible funds.</p>
    <p>Keep essential bills and emergency reserves protected. Historical balances and possible reductions do not confirm future funds.</p>
    <div className="context-actions">{choice('Check my goals again', { type: 'goals' })}</div>
  </div>;
  if (type === 'habits') return <div className="guided-turn">
    <p>What would make everyday spending feel easier? Choose one small habit to try, without putting essentials at risk.</p>
    <div className="context-actions">
      {choice('Pause before optional purchases', { type: 'habit', habit: 'pause' })}
      {choice('Plan a weekly check-in', { type: 'habit', habit: 'check' })}
      {choice('Make room for things I enjoy', { type: 'habit', habit: 'enjoy' })}
    </div>
  </div>;
  return <div className="guided-turn">
    <p>{turn.habit === 'pause' ? 'Before an optional purchase, give yourself a pause. Ask whether you still want it tomorrow.'
      : turn.habit === 'check' ? 'Choose a regular time to review recent purchases and upcoming bills. Notice one change you want to try.'
        : 'Choose the things you most value, then look for optional purchases you would miss less. Essential spending comes first.'}</p>
    <p>These are general ideas, not calculated savings. Start small and see whether the habit works for you.</p>
    <div className="context-actions">
      {choice('Look at my recorded spending', { type: 'savings' })}
      {choice('Are my goals realistic?', { type: 'goals' })}
      {choice('Try another habit', { type: 'habits' })}
    </div>
  </div>;
}
