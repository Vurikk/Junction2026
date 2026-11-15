import React, { useEffect, useState } from 'react';
import { ResponsiveContainer, LineChart, Line, ReferenceLine, XAxis, YAxis, Tooltip } from 'recharts';

function GoalDot({ cx, cy, payload, goal, color }) {
  if (cx == null || cy == null || (goal.completion_months != null && payload.month > goal.completion_months)) return null;
  if (payload.month === goal.completion_months) return <g role="img"
    aria-label={`${goal.name}: projected completion in month ${goal.completion_months}`}>
    <title>{goal.name}: projected completion in month {goal.completion_months}</title>
    <circle cx={cx} cy={cy} r={4} fill={color} />
    <text x={cx} y={cy - 12} textAnchor="middle" fontSize={23}>{'\u{1F3C6}'}</text>
  </g>;
  return <circle cx={cx} cy={cy} r={3} fill={color} />;
}

export default function GoalContributions({ customer, api, money, goals }) {
  const [result, setResult] = useState(null);
  const [error, setError] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    setResult(null); setError(false);
    if (!goals?.length) return () => controller.abort();
    api(`customers/${customer}/goal-plan`, { signal: controller.signal }).then(data => {
      if (!controller.signal.aborted) setResult(data);
    }).catch(() => { if (!controller.signal.aborted) setError(true); });
    return () => controller.abort();
  }, [customer, api, goals]);
  const colors = ['#008c45', '#8060a6', '#4b83ce', '#b65145'];
  return <section><h2>Projected savings towards your goals</h2>
    {goals?.length === 0 ? <p>Add a goal to see your six-month projection.</p>
      : !result ? <p role="status">{error ? 'Projection unavailable. Try opening Goals again.' : 'Loading projection…'}</p>
      : result.status !== 'estimated' ? <p>Not enough recorded data to estimate savings.</p>
      : <>
        <p>Based on {money(result.goal_budget_eur)} towards goals per typical month, after usual costs and reserve contributions.</p>
        <div role="img" aria-label="Six-month projected savings by goal. Dashed lines show targets, not actual savings.">
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={result.projection} margin={{ top: 20, right: 12, left: 0, bottom: 5 }}>
              <XAxis dataKey="month" tickFormatter={value => `M${value}`} />
              <YAxis width={65} tick={{ fontSize: 11 }} />
              <Tooltip labelFormatter={value => `Projected month ${value}`} formatter={value => money(value)} />
              {result.goals.map((goal, index) => <ReferenceLine key={goal.goal_id} y={goal.target_eur}
                stroke={colors[index % colors.length]} strokeDasharray="4 5" ifOverflow="extendDomain" />)}
              {result.goals.map((goal, index) => <Line key={goal.goal_id} type="linear"
                dataKey={row => goal.completion_months != null && row.month > goal.completion_months
                  ? null : row.values[goal.goal_id]} name={goal.name}
                stroke={colors[index % colors.length]} strokeWidth={2.5} connectNulls={false}
                dot={<GoalDot goal={goal} color={colors[index % colors.length]} />} />)}
            </LineChart>
          </ResponsiveContainer>
        </div>
        <p className="fine">Solid lines: projected savings. Dashed lines: targets. Trophy: projected completion. M1–M6 are future typical months.</p>
        {result.goals.map((goal, index) => <p key={goal.goal_id}>
          <span style={{ color: colors[index % colors.length] }}>●</span> <b>{goal.name}</b> · {goal.priority_label}
          {' · '}{money(goal.target_eur)} target
          {' · '}{goal.completion_months == null ? 'No saving capacity currently estimated'
            : `${goal.completion_months <= 6 ? '\u{1F3C6} ' : ''}About ${goal.completion_months} ${goal.completion_months === 1 ? 'month' : 'months'}`}
        </p>)}
        <details><summary>How this is estimated</summary><p>{result.timing_basis}</p>
          <p>Starts at zero projected contributions; existing savings are unknown. Higher-priority goals are funded first.</p>
          <p>Future income and costs may change. This chart does not show deposits already made.</p>
        </details>
      </>}
  </section>;
}
