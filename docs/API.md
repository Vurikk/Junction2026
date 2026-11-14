# JSON API contracts (v0.1)

Base path: `/api`. Interactive, typed contracts: backend `/docs`; machine-readable schemas: `/openapi.json`.
Responses use JSON. All monetary values represent EUR. Goal amounts use decimal strings for exact cents;
historical chart values are JSON numbers rounded to cents by Python. Missing values are `null`, never invented zeros.
This is a local, unauthenticated demo, intended for loopback only. Do not expose it publicly.

## Customer selection

`GET /api/customers` → 200, array of:

```json
{
  "customer_id": "CUST04457",
  "customer_age": null,
  "customer_postal_code": null,
  "months": ["2024-10"],
  "has_mortgage_data": true
}
```

Examples illustrate structure, not actual customer values. The two existing IDs are `CUST04457` and `CUST00001`.
Selection is client-side: pass the chosen ID in subsequent URLs. No global active customer or selection mutation exists.
Postal codes remain strings. Months are sorted ascending, drawn from actual transactions.

## Spending summary

`GET /api/customers/{customer_id}/spending?month=YYYY-MM` → 200:

```json
{
  "customer_id": "CUST04457",
  "month": "2024-10",
  "currency": "EUR",
  "spending_eur": 310,
  "average_daily_eur": 10,
  "daily": [{"date": "2024-10-01", "amount_eur": 10}],
  "excluded_transaction_count": 5,
  "note": "Recorded purchases, utilities and housing outflows only. Transfers and other types excluded; refunds not netted."
}
```

`daily` actually contains every calendar day of the requested month, with zero for no recorded included payments;
the example abbreviates that array. This is historical recorded spending, not a forecast or proof of complete data.
Default month is the customer's latest recorded month, not today's month.
Only negative `purchase`, `utilities_payment`, and `housing_payment` transactions count.
Transfers, investment deposits, income, refunds and unrecognised types are excluded to avoid counting money movements as purchases.
This is deliberately a conservative subset of gross outflows, not the prototype's transfer-inclusive `get_total_spent`.
The exclusion count covers all omitted rows. Average is included spending divided by calendar days in the month.
No mortgage application expense is added to transaction spending. Budget lines remain unavailable.

## Daily / weekly budget

`GET /api/customers/{customer_id}/budget` → 200:

```json
{
  "customer_id": "CUST04457",
  "status": "insufficient_data",
  "daily_eur": null,
  "weekly_eur": null,
  "missing_inputs": ["upcoming_essential_bills", "emergency_reserve", "confirmed_income"]
}
```

Historical balances and mortgage income requirements do not establish a safe allowance.
Until essential obligations, confirmed income and reserves are established, no spendable amount is estimated.

## Goals

`GET /api/customers/{customer_id}/goals` → 200, array of goals (initially `[]`).

`POST /api/customers/{customer_id}/goals` with explicit user-submitted JSON:

```json
{"name": "Emergency fund", "amount_eur": "1000.00", "priority": "critical"}
```

→ 201:

```json
{
  "id": "generated-uuid",
  "customer_id": "CUST04457",
  "name": "Emergency fund",
  "amount_eur": "1000.00",
  "priority": "critical"
}
```

Name: 1–100 characters, at least one non-whitespace character. Amount: positive EUR target with at most two decimal places
and 12 total digits. Priority: `critical` or `flexible`. Extra request fields are rejected.
Goals belong to the selected customer, are in memory, and reset on restart/reload. Use one backend worker.
No edit/delete or automatic modification is implemented. Repeated POSTs create distinct goals.

## Goal analysis

`GET /api/customers/{customer_id}/goal-analysis` → 200:

```json
{
  "customer_id": "CUST04457",
  "status": "insufficient_data",
  "ordered_goal_ids": ["generated-uuid"],
  "total_target_eur": "1000.00",
  "explanation": "Critical goals come first. Feasibility is unknown until income, essential bills and reserve are confirmed."
}
```

Deterministic Python analysis only: critical goals first, insertion order within each priority, exact sum of targets.
This does not allocate savings or claim feasibility. The endpoint never modifies goals. No external LLM requests occur.

## Mortgage applications

`GET /api/customers/{customer_id}/mortgages` → 200:

```json
{
  "customer_id": "CUST04457",
  "applications": [{
    "mortgage_customer_id": "example-id",
    "final_decision": "approved",
    "final_requested_loan_eur": 100000,
    "monthly_payment_eur": null
  }],
  "note": "Application records only; these do not establish an active loan or monthly repayments."
}
```

Absent mortgage applications yield `[]`. Missing fields are `null`. Existing `Customer` links application history;
raw negotiation history is not sent to the browser. Approval does not establish an active mortgage.

## Errors and health

`GET /api/health` → 200 `{"status":"ok"}` after data loading completes.
Unknown customer or unavailable month → 404 `{"detail":"..."}`.
Invalid query/body → 422 `{"detail":[...]}` (FastAPI validation errors).
Missing source files cause startup failure with a local traceback; no fabricated fallback dataset is used.
