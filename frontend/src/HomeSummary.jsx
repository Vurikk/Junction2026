import React, { useState } from 'react';
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, ReferenceLine } from 'recharts';
import { chartPeriods } from './chartPeriods';

const date = value => value ? value.slice(0, 10) : 'Date unavailable';

export default function HomeSummary({ data, money, openCoach, onSpending, onPlan, onAddGoal, onTarget }) {
  const [range, setRange] = useState('Today');
  const balances = data['recorded-balances'];
  const comparison = data['spending-comparison'];
  const budget = data.budget;
  const history = data['spending-history'];
  const points = chartPeriods(history);
  const headlines = { below: 'Spending below your usual', above: 'Spending above your usual', equal: 'Spending matches your usual' };
  const headline = headlines[comparison?.status] || 'Let’s explore your spending';
  const allowance = range === 'Today' ? budget?.daily_eur : budget?.weekly_eur;
  return <>
    <div className="money-card">
    <section className="recorded-balance"><h1>Balance</h1>
      {balances?.simultaneous_total_eur != null ? <>
        <strong>{money(balances.simultaneous_total_eur)}</strong>
      </> : balances?.accounts?.length ? balances.accounts.map((account, index) => <div key={account.account_id}>
        <p className="fine">Account {index + 1}</p><strong>{money(account.balance_eur)}</strong>
      </div>) : <strong>Not available</strong>}
    </section>
    <div className="coach-allowance-group">
    <section className="coach-overview"><h2>Financial coach</h2>
      <button className="primary coach-action" onClick={() => openCoach('Spending by category')}>
        <svg width="19" height="19" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
          <path d="M12 1 15 9 23 12 15 15 12 23 9 15 1 12 9 9Z" /></svg>Ask Coach</button>
    </section>
    <section className="allowance-summary"><div className="allowance-heading"><h2>Safe to spend</h2>
      <div className="allowance-toggle">{['Today', 'Week'].map(value =>
        <button key={value} aria-pressed={range === value} onClick={() => setRange(value)}>{value}</button>)}</div></div>
      <strong className="allowance-amount">{money(allowance)}</strong>
      <p className="fine">Estimated {range === 'Today' ? 'per day' : 'per week'}</p>
      <div className="allowance-track" aria-hidden="true" />
      <p className="fine">Usage tracking unavailable</p>
      <button className="text-button" onClick={onPlan} disabled={!data.assumptions}>
        {allowance == null ? 'Complete your spending plan' : 'Review your spending plan'} ›</button>
      {budget?.shortfall_eur > 0 && <p role="alert">Bills and reserve shortfall: {money(budget.shortfall_eur)}</p>}
    </section>
    </div>
    <details className="money-details"><summary>Details</summary>
      <h3>Balance source</h3>
      <p>{balances?.note || 'This is not a live bank balance.'}</p>
      {balances?.simultaneous_total_eur != null ? <p>As of {date(balances.total_recorded_at)} · Historical snapshot</p>
        : <><p>{balances?.total_unavailable_reason}</p>{balances?.accounts?.map((account, index) =>
          <p key={account.account_id}>Account {index + 1}: {date(account.recorded_at)} · Historical snapshot</p>)}</>}
      <h3>{headline}</h3>
      <p>{comparison?.comparison && comparison?.baseline && headlines[comparison.status]
        ? `${date(comparison.comparison.start)}–${date(comparison.comparison.end)}: ${money(comparison.comparison.spending_eur)} spent.`
        : 'A comparison is unavailable; explore the spending we have recorded.'}</p>
        <p>Prior-period average: {money(comparison?.baseline?.average_spending_eur)}.</p>
        <p>Signed difference: {money(comparison?.difference_eur)}.</p>
        <p>{comparison?.baseline && `${comparison.baseline.start}–${comparison.baseline.end}, `}
          {comparison?.baseline?.period_count != null && `${comparison.baseline.period_count} prior periods.`}</p>
        <p>{comparison?.note || comparison?.insufficient_data_reason || 'Comparison data is unavailable.'}</p>
        <p>Rule-based demo. Historical spending is not a measure of goal progress.</p>
      <h3>Estimate details</h3>
        <p>{budget?.status === 'estimated' ? `Based on your confirmed ${budget.assumptions.horizon_days}-day plan.`
          : 'All six planning amounts need confirmation. Blank amounts remain unknown.'}</p>
        <p>Includes everyday costs. Today selects the daily estimate, not a live remaining balance. Payment timing is not modeled.
          No consumed fraction is available, so the neutral track does not show progress.</p>
    </details>
    </div>
    <section className="home-current-goals"><div className="section-title"><h2>Current goals</h2>
      <button className="text-button" onClick={onAddGoal}>Add goal</button></div>
      {!data.goals ? <p>Goals unavailable.</p> : data.goals.length === 0 ? <p>No goals yet.</p>
        : data.goals.map(goal => <div className="row" key={goal.id}>
          <span>{goal.name}<small className="fine">{goal.priority}</small></span><b>{money(goal.amount_eur)}</b>
        </div>)}
    </section>
    <section className="home-chart"><div className="section-title"><h2>Spending history</h2>
      <button className="text-button" onClick={onSpending}>View all ›</button></div>
      {points?.length ? <>
        <p className="fine">{points[0].start}–{points.at(-1).end} · Recorded {history.period} periods</p>
        <div role="img" aria-label="Recorded spending bars with historical average and optional chart target">
          <ResponsiveContainer width="100%" height={150}>
            <BarChart data={points} margin={{ top: 8, right: 4, left: 4, bottom: 0 }}>
              <XAxis dataKey="start" tick={{ fontSize: 10 }} tickLine={false} axisLine={false} minTickGap={45} />
              <YAxis hide padding={{ top: 18, bottom: 8 }} />
              <Tooltip formatter={value => money(value)} />
              <Bar dataKey="spending_eur" name="Recorded spending" fill="#008c45" radius={[3, 3, 0, 0]} />
              {history.historical_average_eur != null && <ReferenceLine y={history.historical_average_eur}
                stroke="#94662e" strokeDasharray="4 4" ifOverflow="extendDomain"
                label={{ value: 'avg.', position: 'insideBottomLeft', fill: '#94662e', fontSize: 11,
                  stroke: 'white', strokeWidth: 3, paintOrder: 'stroke' }} />}
              {history.budget_target_eur != null && <ReferenceLine y={Number(history.budget_target_eur)}
                stroke="#3653a0" strokeWidth={2} strokeDasharray="3 3" ifOverflow="extendDomain"
                label={{ value: 'goal', position: 'insideBottomLeft', fill: '#3653a0', fontSize: 11,
                  stroke: 'white', strokeWidth: 3, paintOrder: 'stroke' }} />}
            </BarChart>
          </ResponsiveContainer>
        </div><p className="fine">Dashed: historical average {money(history.historical_average_eur)}
          {history.budget_target_eur != null && ` · Target ${money(history.budget_target_eur)}`}</p>
      </> : <p className="fine">Spending history unavailable.</p>}
      {history && history.budget_target_eur == null && <button className="text-button" disabled={!data.assumptions}
        onClick={onTarget}>Set spending target</button>}
      <button className="text-button" onClick={onSpending}>See where it went ›</button>
    </section>
  </>;
}

export function PlanningContext({ suggestions, money }) {
  const labels = { income: 'Income', housing_utilities: 'Housing and utilities', food: 'Food', everyday_purchases: 'Everyday purchases' };
  return <details className="planning-context"><summary>Historical context for your review</summary>
    <p>Monthly observations, not confirmed future amounts. Food overlaps everyday purchases; do not add them together.</p>
    {suggestions ? Object.entries(suggestions.observations).map(([key, observation]) => <div key={key}>
      <h3>{labels[key]}</h3><p>{money(observation.average_monthly_eur)} per recorded month</p>
      <p className="fine">{observation.source_period
        ? `${observation.source_period.start}–${observation.source_period.end}` : 'Period unavailable'} · {observation.confidence} confidence</p>
      <p className="fine">{observation.unavailable_reason || observation.limitations.join(' ')}</p>
    </div>) : <p>Historical suggestions unavailable. Enter only amounts you can confirm.</p>}
    <p className="fine">Amounts are not scaled to your planning period or copied into the form automatically.</p>
  </details>;
}
