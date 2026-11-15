import React, { useEffect, useState } from 'react';
import { ResponsiveContainer, LineChart, Line, ReferenceLine, XAxis, YAxis, Tooltip } from 'recharts';

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
  const colors = { critical: '#b65145', important: '#8060a6', flexible: '#4b83ce' };
  const widths = { critical: 3, important: 2.5, flexible: 2 };
  return <section><h2>Contributions towards your goals</h2>
    {!result && <p role="status">{error ? 'Contributions could not be loaded. Try opening Goals again.' : 'Loading contributions…'}</p>}
    {result?.goals.length === 0 && <p>Add a goal to see its target here.</p>}
    {result?.goals.length > 0 && <>
      <p>Solid lines: cumulative planned savings. Dashed lines: goal targets.</p>
      <div role="img" aria-label="Cumulative planned contributions and goal targets, ordered by importance">
        <ResponsiveContainer width="100%" height={260}>
          <LineChart data={result.chart_data} margin={{ top: 25, right: 15, left: 5, bottom: 5 }}>
            <XAxis dataKey="month" tickFormatter={monthLabel} tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} width={55} />
            <Tooltip labelFormatter={monthLabel} formatter={value => money(value)} />
            {result.goals.map(goal => <ReferenceLine key={`target-${goal.goal_id}`} y={goal.target_eur}
              stroke={colors[goal.priority]} strokeDasharray="4 5" ifOverflow="extendDomain"
              label={{ value: `${goal.name} target`, position: 'insideTopRight', fontSize: 11, fill: colors[goal.priority] }} />)}
            {result.goals.filter(goal => goal.months.length > 0).map(goal => <Line key={goal.goal_id}
              type="linear" dataKey={row => row.values[goal.goal_id]} name={goal.name}
              stroke={colors[goal.priority]} strokeWidth={widths[goal.priority]} dot={{ r: 3 }} connectNulls={false} />)}
          </LineChart>
        </ResponsiveContainer>
      </div>
      {result.goals.map(goal => <div key={goal.goal_id}>
        <p><span style={{ color: colors[goal.priority] }}>●</span> <b>{goal.name}</b> · {goal.priority} · Target {money(goal.target_eur)}</p>
        <p className="fine">{goal.total_planned_eur == null ? 'Target shown; no contribution history available.'
          : `${money(goal.monthly_planned_eur)} planned each month · ${money(goal.total_planned_eur)} across six months`}</p>
      </div>)}
      <p className="fine">{result.note} Goals are listed critical first, then important, then flexible.</p>
    </>}
  </section>;
}
