import React from 'react';

export default function CoachResult({ card, money }) {
  const data = card.data;
  if (!data) return null;
  const dates = data.source_period || data.comparison;
  const row = (label, value) => <div className="row"><span>{label}</span><b>{money(value)}</b></div>;
  return <div className="conversation-result">
    {dates && <p className="fine">Recorded period: {dates.start} – {dates.end}</p>}
    {card.type === 'category_spending' && <>
      <h3>{data.category === 'all' ? 'Where your money went' : data.category}</h3>
      {row('Recorded spending', data.spending_eur)}
      {data.categories?.map(item => <React.Fragment key={item.category}>
        {row(item.category, item.spending_eur)}
      </React.Fragment>)}
      {data.categories && row('Remaining categories', data.other_spending_eur)}
    </>}
    {card.type === 'spending_comparison' && <>
      <h3>Compared with usual</h3>
      {row('Recorded spending', data.comparison?.spending_eur)}
      {row('Earlier-period average', data.baseline?.average_spending_eur)}
      {data.baseline && <p className="fine">Average period: {data.baseline.start} – {data.baseline.end}</p>}
      {row('Difference', data.difference_eur)}
      <p className="fine">{data.status === 'insufficient_data' ? 'Not enough complete periods to compare.'
        : `Recorded spending is ${data.status === 'equal' ? 'the same as' : data.status} the earlier-period average.`}</p>
    </>}
    {card.type === 'category_reduction' && <>
      <h3>{data.category}: {data.reduction_percent}% less</h3>
      {row('Recorded spending', data.baseline_spending_eur)}
      {row('Hypothetical spending', data.hypothetical_spending_eur)}
      {row('Potential reduction', data.potential_reduction_eur)}
      <p className="fine">A possibility, not money already saved. Your goals are unchanged.</p>
    </>}
    <details><summary>About these figures</summary>
      <p>Python calculates these amounts from recorded data. Coverage may be incomplete. Transfers and refunds are excluded.</p>
    </details>
  </div>;
}
