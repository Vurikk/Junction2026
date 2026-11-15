import React from 'react';
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, LabelList, Tooltip } from 'recharts';

export default function CoachSpendingChart({ rows, period, money }) {
  if (!rows?.length) return <p>No category spending is recorded for this period.</p>;
  const month = period?.start
    ? new Intl.DateTimeFormat('en', { month: 'long', year: 'numeric', timeZone: 'UTC' })
      .format(new Date(`${period.start}T12:00:00Z`)) : 'Recorded month';
  return <figure className="coach-spending-chart">
    <figcaption><strong>{month}</strong><span>Spending by category</span></figcaption>
    <div role="img" aria-label={`${month} spending: ${rows.map(row => `${row.label}: ${money(row.value)}`).join('; ')}`}>
      <ResponsiveContainer width="100%" height={Math.max(120, rows.length * 42)}>
        <BarChart data={rows} layout="vertical" margin={{ top: 4, right: 76, bottom: 4, left: 0 }}>
          <XAxis type="number" hide domain={[0, 'dataMax']} />
          <YAxis type="category" dataKey="label" width={90} axisLine={false} tickLine={false}
            tick={{ fontSize: 11, fill: '#244b36' }} interval={0} />
          <Tooltip formatter={value => money(value)} cursor={{ fill: '#e5f2e9' }} />
          <Bar dataKey="value" name="Spent" fill="#008c45" radius={[0, 4, 4, 0]} barSize={18} isAnimationActive={false}>
            <LabelList dataKey="value" position="right" formatter={money} style={{ fontSize: 11, fill: '#153e2b' }} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
    <details><summary>View amounts</summary>
      <table><caption className="sr-only">Recorded category spending</caption>
        <thead><tr><th scope="col">Category</th><th scope="col">Spent</th></tr></thead>
        <tbody>{rows.map((row, index) => <tr key={index}><th scope="row">{row.label}</th><td>{money(row.value)}</td></tr>)}</tbody>
      </table>
    </details>
  </figure>;
}
