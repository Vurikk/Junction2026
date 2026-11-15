import React from 'react';

export default function SpendingTooltip({ active, payload, period, income, money }) {
  const point = payload?.[0]?.payload;
  if (!active || !point) return null;
  const monthly = period === 'month';
  const recordedIncome = income?.monthly?.[point.start?.slice(0, 7)];
  return <div className="spending-tooltip">
    <p><strong>{point.start} – {point.end}</strong></p>
    <p>Recorded spending: <strong>{money(point.spending_eur)}</strong></p>
    {monthly && <p>Recorded income: <strong>{money(recordedIncome)}</strong></p>}
    {point.partial && <p className="fine">Partial recorded period</p>}
    {monthly && <p className="fine">Recorded income excludes transfers and refunds.</p>}
  </div>;
}
