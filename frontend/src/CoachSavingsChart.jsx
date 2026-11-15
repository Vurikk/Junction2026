import React from 'react';
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, Legend } from 'recharts';

export default function CoachSavingsChart({ data, money }) {
  if (!data?.series?.length || !data.points?.length) return null;
  const colors = ['#008c45', '#8060a6', '#2563a6'];
  return <figure className="coach-spending-chart">
    <figcaption><strong>What {data.percent}% less could add up to</strong><span>Hypothetical savings over six months</span></figcaption>
    <div role="img" aria-label={`Projected savings with a ${data.percent}% cut, by category over six months`}>
      <ResponsiveContainer width="100%" height={230}>
        <LineChart data={data.points} margin={{ top: 12, right: 12, left: 0, bottom: 0 }}>
          <XAxis dataKey="month" tickFormatter={value => `M${value}`} tick={{ fontSize: 11 }} />
          <YAxis width={48} tick={{ fontSize: 11 }} />
          <Tooltip labelFormatter={value => `Month ${value}`} formatter={money} />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          {data.series.map((series, index) => <Line key={series.key} dataKey={series.key} name={series.label}
            stroke={colors[index % colors.length]} strokeWidth={2.5} dot={{ r: 3 }} isAnimationActive={false} />)}
        </LineChart>
      </ResponsiveContainer>
    </div>
    <p className="fine">{data.note}</p>
    <details><summary>View projected amounts</summary>
      <table><thead><tr><th>Month</th>{data.series.map(series => <th key={series.key}>{series.label}</th>)}</tr></thead>
        <tbody>{data.points.map(point => <tr key={point.month}><th scope="row">{point.month}</th>
          {data.series.map(series => <td key={series.key}>{money(point[series.key])}</td>)}</tr>)}</tbody>
      </table>
    </details>
  </figure>;
}
