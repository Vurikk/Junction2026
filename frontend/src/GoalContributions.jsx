import React, { useEffect, useState } from 'react';
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip } from 'recharts';

const monthLabel = value => new Intl.DateTimeFormat('en-GB', {
  month: 'short', year: 'numeric', timeZone: 'UTC',
}).format(new Date(`${value}-01T12:00:00Z`));

export default function GoalContributions({ customer, api, money, goals }) {
  const [result, setResult] = useState(null);
  const [error, setError] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    setResult(null); setError(false);
    api(`customers/${customer}/goal-contributions`, { signal: controller.signal }).then(data => {
      if (!controller.signal.aborted) setResult(data);
    }).catch(() => { if (!controller.signal.aborted) setError(true); });
    return () => controller.abort();
  }, [customer, api, goals]);
  return <section><h2>Monthly contributions</h2>
    {!result && <p role="status">{error ? 'Contributions could not be loaded. Try opening Goals again.' : 'Loading contributions…'}</p>}
    {result?.goals.length === 0 && <p>No contribution history is available for these goals.</p>}
    {result?.goals.map(goal => <div key={goal.goal_id}>
      <h3>{goal.name}</h3><p>Demo · Planned transfers to savings</p>
      <p>{money(goal.monthly_planned_eur)} each month · {money(goal.total_planned_eur)} planned across six months</p>
      <div role="img" aria-label={`${goal.name}: six months of planned ${money(goal.monthly_planned_eur)} savings transfers`}>
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={goal.months} margin={{ top: 15, right: 10, left: 0, bottom: 5 }}>
            <XAxis dataKey="month" tickFormatter={monthLabel} tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} width={45} />
            <Tooltip labelFormatter={monthLabel} formatter={value => money(value)} />
            <Bar dataKey="planned_eur" name="Planned contribution" fill="#4b83ce" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <p className="fine">{result.note}</p>
    </div>)}
  </section>;
}
