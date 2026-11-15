import React from 'react';

export default function MortgageSummary({ data, money }) {
  const statuses = { approved: 'Approved application', rejected: 'Application declined', pending: 'Application pending' };
  return <section className="mortgage-summary"><h2>Mortgage information</h2>
    {!data ? <p role="status">Loading mortgage information…</p>
      : !data.applications.length ? <p>No mortgage application is linked to this demo profile.</p>
      : <>
        {data.applications.map((application, index) => <article className="mortgage-card" key={application.mortgage_customer_id}>
          <div className="section-title"><h3>Home loan application{data.applications.length > 1 ? ` ${index + 1}` : ''}</h3>
            <span className="tag">Application record</span></div>
          <p className="mortgage-status">{statuses[application.final_decision] || 'Decision unavailable'}</p>
          <dl><div><dt>Requested amount</dt><dd>{money(application.final_requested_loan_eur)}</dd></div>
            <div><dt>Monthly repayment</dt><dd>Not available</dd></div></dl>
        </article>)}
        <p className="fine">An application decision does not confirm an active loan. Repayments are not included as a separate
          mortgage cost in your spending estimate because they are unknown.</p>
      </>}
  </section>;
}
