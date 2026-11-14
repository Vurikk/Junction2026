import React, { useState } from 'react';
import { ResponsiveContainer, BarChart, Bar, XAxis, Tooltip, ReferenceLine } from 'recharts';

const date = value => value ? value.slice(0, 10) : 'Date unavailable';

export default function HomeSummary({ data, money, openCoach, onSpending, onPlan }) {
  const [range, setRange] = useState('Today');
  const balances = data['recorded-balances'];
  const comparison = data['spending-comparison'];
  const budget = data.budget;
  const history = data['spending-history'];
  const headlines = { below: 'Spending below your usual', above: 'Spending above your usual', equal: 'Spending matches your usual' };
  const headline = headlines[comparison?.status] || 'Let’s explore your spending';
  const allowance = range === 'Today' ? budget?.daily_eur : budget?.weekly_eur;
  return <>
    <section className="recorded-balance"><h1>Recorded balance</h1>
      {balances?.simultaneous_total_eur != null ? <>
        <strong>{money(balances.simultaneous_total_eur)}</strong>
        <p className="fine">As of {date(balances.total_recorded_at)} · Historical snapshot</p>
      </> : balances?.accounts?.length ? balances.accounts.map((account, index) => <div key={account.account_id}>
        <p className="fine">Account {index + 1}</p><strong>{money(account.balance_eur)}</strong>
        <p className="fine">As of {date(account.recorded_at)} · Historical snapshot</p>
      </div>) : <><strong>Not available</strong><p className="fine">No recorded balance available.</p></>}
      <details><summary>About this balance</summary><p>{balances?.note || 'This is not a live bank balance.'}</p>
        {balances?.simultaneous_total_eur == null && <p>{balances?.total_unavailable_reason}</p>}</details>
    </section>
    <section className="coach-overview"><p className="coach-kicker">Your financial coach</p><h2>{headline}</h2>
      <p>{comparison?.comparison && comparison?.baseline && headlines[comparison.status]
        ? `${date(comparison.comparison.start)}–${date(comparison.comparison.end)}: ${money(comparison.comparison.spending_eur)} spent.`
        : 'A comparison is unavailable; explore the spending we have recorded.'}</p>
      <button className="primary coach-action" onClick={() => openCoach('Spending by category')}>Ask Coach <span>→</span></button>
      <details><summary>Comparison details</summary>
        <p>Prior-period average: {money(comparison?.baseline?.average_spending_eur)}.</p>
        <p>Signed difference: {money(comparison?.difference_eur)}.</p>
        <p>{comparison?.baseline && `${comparison.baseline.start}–${comparison.baseline.end}, `}
          {comparison?.baseline?.period_count != null && `${comparison.baseline.period_count} prior periods.`}</p>
        <p>{comparison?.note || comparison?.insufficient_data_reason || 'Comparison data is unavailable.'}</p>
        <p>Rule-based demo. Historical spending is not a measure of goal progress.</p>
      </details>
    </section>
    <section className="allowance-summary"><div className="allowance-heading"><h2>Safe to spend</h2>
      <div className="allowance-toggle">{['Today', 'Week'].map(value =>
        <button key={value} aria-pressed={range === value} onClick={() => setRange(value)}>{value}</button>)}</div></div>
      <strong className="allowance-amount">{money(allowance)}</strong>
      <p className="fine">Estimated {range === 'Today' ? 'per day' : 'per week'} · Includes everyday costs</p>
      <div className="allowance-track" aria-hidden="true" />
      <p className="fine">Usage tracking unavailable</p>
      <button className="text-button" onClick={onPlan} disabled={!data.assumptions}>
        {allowance == null ? 'Complete your spending plan' : 'Review your spending plan'} ›</button>
      <details><summary>Estimate details</summary>
        <p>{budget?.status === 'estimated' ? `Based on your confirmed ${budget.assumptions.horizon_days}-day plan.`
          : 'All six planning amounts need confirmation. Blank amounts remain unknown.'}</p>
        <p>Today selects the daily estimate, not a live remaining balance. Payment timing is not modeled.
          No consumed fraction is available, so the neutral track does not show progress.</p>
      </details>
      {budget?.shortfall_eur > 0 && <p role="alert">Bills and reserve shortfall: {money(budget.shortfall_eur)}</p>}
    </section>
    <section className="home-chart"><div className="section-title"><h2>Spending history</h2>
      <button className="text-button" onClick={onSpending}>View all ›</button></div>
      {history?.periods?.length ? <>
        <p className="fine">{history.periods[0].start}–{history.periods.at(-1).end} · Recorded {history.period} periods</p>
        <div role="img" aria-label="Recorded spending bars with historical average and optional chart target">
          <ResponsiveContainer width="100%" height={150}>
            <BarChart data={history.periods} margin={{ top: 8, right: 4, left: 4, bottom: 0 }}>
              <XAxis dataKey="start" tick={{ fontSize: 10 }} tickLine={false} axisLine={false} minTickGap={45} />
              <Tooltip formatter={value => money(value)} />
              <Bar dataKey="spending_eur" name="Recorded spending" fill="#008c45" radius={[3, 3, 0, 0]} />
              {history.historical_average_eur != null && <ReferenceLine y={history.historical_average_eur}
                stroke="#94662e" strokeDasharray="4 4" ifOverflow="extendDomain" />}
              {history.budget_target_eur != null && <ReferenceLine y={Number(history.budget_target_eur)}
                stroke="#3653a0" strokeDasharray="3 3" ifOverflow="extendDomain" />}
            </BarChart>
          </ResponsiveContainer>
        </div><p className="fine">Dashed: historical average {money(history.historical_average_eur)}
          {history.budget_target_eur != null && ` · Target ${money(history.budget_target_eur)}`}</p>
      </> : <p className="fine">Spending history unavailable.</p>}
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
