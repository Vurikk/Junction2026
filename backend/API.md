# Financial engine API extensions

Existing customer, spending and mortgage routes retain their fields and semantics.
No LLM is connected. All user inputs and goals are per-customer, in memory, reset on restart.

## Assumptions
`GET` / `PUT /api/customers/{id}/assumptions` reads/replaces the full assumptions object.
Only send PUT after user confirmation. Omitted monetary fields become null; explicit zero is allowed.
Money accepts nonnegative EUR decimal strings (two decimal places, 12 digits maximum).

- `available_funds_eur`: user-confirmed currently accessible funds, not historical balances.
- `confirmed_income_eur`: additional income confirmed to arrive within the horizon; exclude money already in available funds.
- `upcoming_essential_bills_eur`: all required payments in that horizon, including confirmed active debt payments.
- `emergency_reserve_eur`: funds to protect in addition to those bills.
- `everyday_spending_eur`: planned everyday living costs, excluding bills already listed above.
- `voluntary_goal_contribution_eur`: maximum voluntary savings contribution over the horizon.
- `weekly_budget_eur`, `monthly_budget_eur`: optional chart targets, independent of safe allowances.
- `horizon_days`: 1–366, default 30. All planning amounts refer to this same horizon.
- `repeat_plan`: default false. Explicitly confirms identical capacity each future horizon for conditional completion estimates.

All six planning money fields must be supplied for allowances, including explicit zeros.
Capacity = max(0, available + income - bills - reserve - everyday costs).
Goals receive at most the voluntary contribution and capacity, critical before important before flexible;
insertion order breaks ties. Unallocated contribution stays spendable. Allowance is remaining cash after bills,
reserve and actual goal allocations; it includes the planned everyday costs. Daily values round down;
weekly is capped at the remaining total. `shortfall_eur` reports bills/reserve cash deficit.
No historical balance, mortgage application or detected income becomes confirmed money automatically.
Inputs must cover the entire horizon; forecasts assume essentials can be paid before spending starts.
This aggregate model does not model intra-horizon payment timing; users must confirm liquidity themselves.

## Historical summaries
`GET /api/customers/{id}/spending-history?period=week|month` (default month).
`periods` contain calendar boundaries (weeks Monday–Sunday), `partial`, spending, category totals,
basket totals, classification evidence/confidence, target and remaining budget. Zero-spend periods inside
observed coverage are included. Averages use only full calendar periods between earliest/latest transactions;
null when none exist. Coverage is not guaranteed. No partial-period extrapolation is performed.
Baskets: mandatory_regular, mandatory_irregular, discretionary_everyday, plus uncertain.
Classifications are heuristics with visible reasons; everyday categories may include essentials.
Existing explicit payment-type exclusion applies, so transfers/refunds are never double-counted.

`GET /api/customers/{id}/income` returns explicit positive income by month and likely recurring candidates.
At least three similar payments (within 15%) and 25–35 day intervals are required. Types are salary,
income, salary_payment and pension. Transfers, refunds and unrecognized credits are excluded.
No candidate is confirmed income; payer identity is not inferred. Missing types may undercount actual income.

## Existing route extensions
Goal POST also accepts `important`. Existing critical/flexible requests still work.
Budget retains customer_id, status, daily_eur, weekly_eur and missing_inputs; adds confidence, assumptions,
allocations, savings_capacity_eur and shortfall_eur. Status is insufficient_data or estimated.
Goal-analysis retains ordered_goal_ids, total_target_eur and explanation, and includes the same planning fields.
Allocations contain goal_id, allocated_eur, feasibility and completion_periods (horizons, not months).
Unknown planning inputs yield null amounts/times. Zero capacity has no completion estimate.
Repeating estimates assume no interest, price changes or previously saved goal balances; targets are remaining amounts.
Analysis never mutates goals. No application approvals are treated as debt.

Run synthetic engine tests: `python -m unittest backend.test_financial -v`.
Run existing data-dependent API checks: `python -m unittest backend.test_api -v` with local demo data installed.
