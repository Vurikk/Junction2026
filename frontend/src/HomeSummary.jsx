import PlanTargetLabel from './PlanTargetLabel.jsx';
import React, { useState } from 'react';
import { ResponsiveContainer, BarChart, Bar, XAxis, Tooltip, ReferenceLine } from 'recharts';
import { chartPeriods } from './chartPeriods';

const date = value => {
  const parsed = new Date(`${value?.slice(0, 10)}T12:00:00Z`);
  return Number.isNaN(parsed.getTime()) ? 'Date unavailable'
    : new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' }).format(parsed);
};

export default function HomeSummary({ data, money, openCoach, onSpending, onPlan, onAddGoal, onLastFiveWeeks }) {
  const [range, setRange] = useState('Today');
  const balances = data['recorded-balances'];
  const comparison = data['spending-comparison'];
  const budget = data.budget;
  const history = data['spending-history'];
  const points = chartPeriods(history);
  const headlines = { below: 'Spending below your usual', above: 'Spending above your usual', equal: 'Spending matches your usual' };
  const headline = headlines[comparison?.status] || 'Let’s explore your spending';
  const incomeLeft = data['saved-income-remainder'];
  const allowance = range === 'Today' ? incomeLeft?.daily_eur : incomeLeft?.weekly_eur;
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
      <p className="fine">{range === 'Today' ? 'Daily' : 'Weekly'} share of income left after your confirmed plan</p>
      <p className="fine">Salary minus bills, everyday spending and your chosen goal contribution.</p>
      <div className="allowance-track" aria-hidden="true" />
      <p className="fine" role="status">Purchases {range === 'Today' ? 'today' : 'this week'}: <span aria-label="Not yet known">—</span></p>
      {incomeLeft?.remaining_income_eur < 0 && <p role="alert">Your planned costs and goal contribution exceed your income.</p>}
      <button className="text-button" onClick={onPlan} disabled={!data.assumptions}>
        {allowance == null ? 'Complete your spending plan' : 'Review your spending plan'} ›</button>
      {budget?.shortfall_eur > 0 && <p role="alert">Bills and reserve shortfall: {money(budget.shortfall_eur)}</p>}
    </section>
    </div>
    <details className="money-details"><summary>Details</summary>
      <h3>About your balance</h3>
      <p>These are past account balances, not live balances. Check your bank for the money you can use today.</p>
      {balances?.simultaneous_total_eur != null ? <p>As of {date(balances.total_recorded_at)} · Past account balance</p>
        : <><p>A combined balance is unavailable when account records are missing or come from different times.</p>{balances?.accounts?.map((account, index) =>
          <p key={account.account_id}>Account {index + 1}: {date(account.recorded_at)} · Past account balance</p>)}</>}
      <h3>{headline}</h3>
      <p>{comparison?.comparison && comparison?.baseline && headlines[comparison.status]
        ? `${date(comparison.comparison.start)}–${date(comparison.comparison.end)}: ${money(comparison.comparison.spending_eur)} spent.`
        : 'A comparison is unavailable; explore the spending we have recorded.'}</p>
        <p>Average in earlier months: {money(comparison?.baseline?.average_spending_eur)}.</p>
        <p>Difference from that average: {money(comparison?.difference_eur)}.</p>
        <p>{comparison?.baseline && `${date(comparison.baseline.start)} – ${date(comparison.baseline.end)} · `}
          {comparison?.baseline?.period_count != null && `${comparison.baseline.period_count} earlier months.`}</p>
        <p>Some transactions may be missing. Transfers and refunds are not included.</p>
        <p>Past spending does not tell us how much you have saved towards your goals.</p>
      <h3>About this amount</h3>
        <p>Current purchases are not available in these records. The dash and neutral bar do not mean zero spending.</p>
        <p>Uses your last confirmed spending plan. Enter a goal contribution, including zero if appropriate,
          and confirm the plan to update it.</p>
        <p>This is planned income left, not a live bank balance. Existing savings and emergency reserves are excluded;
          purchases are not deducted automatically. Check bill and salary dates before spending.</p>
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
      <button className="text-button" aria-pressed={history?.period === 'week'} onClick={onLastFiveWeeks}>Last 5 weeks</button>
      {points?.length ? <>
        <p className="fine">{date(points[0].start)} – {date(points.at(-1).end)} · Recorded {history.period} periods</p>
        <div role="img" aria-label="Recorded spending bars with historical average and optional chart target">
          <ResponsiveContainer width="100%" height={150}>
            <BarChart data={points} margin={{ top: 14, right: 4, left: 28, bottom: 0 }}>
              <XAxis tickFormatter={date} dataKey="start" tick={{ fontSize: 10 }} tickLine={false} axisLine={false} minTickGap={45} />
              <Tooltip labelFormatter={date} formatter={value => money(value)} />
              <Bar dataKey="spending_eur" name="Recorded spending" fill="#008c45" radius={[3, 3, 0, 0]} />
              {history.historical_average_eur != null && <ReferenceLine y={history.historical_average_eur}
                stroke="#94662e" strokeDasharray="4 4" ifOverflow="extendDomain" />}
              {history.budget_target_eur != null && <ReferenceLine y={Number(history.budget_target_eur)}
                stroke="#4b83ce" strokeWidth={1.5} strokeDasharray="3 5" label={<PlanTargetLabel />} ifOverflow="extendDomain" />}
            </BarChart>
          </ResponsiveContainer>
        </div><p className="fine">Dashed: historical average {money(history.historical_average_eur)}
          {history.budget_target_eur != null && ` · Plan target ${money(history.budget_target_eur)}`}</p>
        {history.budget_target_eur != null && <p className="fine">Blue line: planned spending, shown per {history.period === 'week' ? '7' : '30'} days.</p>}
      </> : <p className="fine">Spending history unavailable.</p>}
      <button className="text-button" onClick={onSpending}>See where it went ›</button>
    </section>
  </>;
}

export function PlanningContext({ suggestions, money }) {
  const labels = { income: 'Income', housing_utilities: 'Housing and utilities', food: 'Food', everyday_purchases: 'Everyday purchases' };
  return <details className="planning-context"><summary>Past spending to help you plan</summary>
    <p>These monthly averages are a starting point, not a forecast. Food is already included in everyday purchases, so do not add both amounts together.</p>
    {suggestions ? Object.entries(suggestions.observations).map(([key, observation]) => <div key={key}>
      <h3>{labels[key]}</h3><p>{money(observation.average_monthly_eur)} per recorded month</p>
      <p className="fine">{observation.source_period
        ? `${date(observation.source_period.start)} – ${date(observation.source_period.end)}` : 'Period unavailable'}</p>
      <p className="fine">{observation.average_monthly_eur == null ? 'Not enough records to estimate this amount.' : 'Some records may be missing. Check what you expect to receive or spend before using this amount.'}</p>
    </div>) : <p>Historical suggestions unavailable. Enter only amounts you can confirm.</p>}
    <p className="fine">These are monthly averages. Adjust them for the length of your plan and enter only amounts you can confirm.</p>
  </details>;
}
