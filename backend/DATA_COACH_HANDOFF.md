# Data-backed Home and category scenarios

Backend branch: `codex/data-backed-budget`, created from `origin/main` at
`00a9d050684e68410a69100721177297e43352b7`. Frontend contract inspected at
`origin/codex/s-mobiili-ui` commit `1fe7eaf`; no frontend files changed or branches merged.

## Integration

All paths below start with `/api/customers/{customer_id}`. Both existing demo IDs work.
These are additive, read-only endpoints. Existing budget, goal, coach, history and assumptions contracts are unchanged.
No LLM dependency, goal progress, automatic confirmations, or new allowance calculation policy is introduced.

| UI use | Request |
| --- | --- |
| Home recorded balance | `GET /recorded-balances` |
| Home comparison matching week/month selection | `GET /spending-comparison?period=week` or `month` (default) |
| Optional planning review | `GET /planning-suggestions` |
| Explicit category/period preview | `POST /category-reduction` |

Replace Home's hardcoded balance with dated **Recorded balance** wording. Never label it current or accessible funds.
Show individual accounts if the simultaneous total is null. A recorded zero is valid, distinct from null.
Use comparison dates in the Home text, never “today” or “this week” for an old period.
The existing textual `/coach` and chart `/spending-history` averages retain their old semantics for compatibility;
use `/spending-comparison` for the new baseline that excludes the comparison period.
Do not turn `below` into “on track”, a limit check or achieved goal savings.

## Shared response conventions

All response objects below list every field. `?` means nullable, not omitted. Dates are ISO `YYYY-MM-DD` strings.
Money is a JSON number in EUR rounded to cents using Python Decimal (half-even); confirmed inputs retain their
existing decimal-string representation. No raw transaction rows are returned by these endpoints.

`Coverage = {recorded_start: date?, recorded_end: date?, completeness_guaranteed: false}`.
These are the earliest/latest transaction dates, not a statement that every intervening transaction is present.
`DateRange = {start: date, end: date}`; both endpoints are inclusive.
Weeks are Monday-Sunday. Only elapsed full calendar periods inside the recorded date bounds qualify;
the period containing the current UTC date is excluded. Edge periods are never extrapolated.
Interior periods without payments contribute zero **recorded** spending, not proof of zero actual spending.
Included spending types are negative `purchase`, `housing_payment`, `utilities_payment` only.
Transfers, investment deposits, refunds and unknown types are excluded; refunds are not netted against purchases.

All unknown customer IDs return `404 {"detail":"Unknown demo customer"}`.
Invalid query/body inputs return HTTP 422. Pydantic validation errors use `{"detail":[...]}`;
semantic period errors use `{"detail":"..."}`. Missing category observations return `404 {"detail":"..."}`.

## GET /recorded-balances

No query parameters. Response:

```text
{
  customer_id: string, currency: "EUR", checked_on: date,
  current_balance_known: false,
  accounts: [{
    account_id: string, currency: "EUR", balance_eur: number?, recorded_at: string?,
    age_days: integer?, status: "historical" | "recorded_today" | "future_dated" | "unavailable",
    is_current: false
  }],
  simultaneous_total_eur: number?, total_recorded_at: string?, total_unavailable_reason: string?, note: string
}
```

Uses `Customer.get_account_balances()`: the last transaction per observed account, `balance_after_eur` and `tx_timestamp`.
Latest missing balances stay null; older non-null records are not silently substituted.
Missing/nonfinite balances or missing timestamps have status `unavailable`.
`age_days` is UTC checked date minus source timestamp's calendar date, negative for future-dated observations.
Source timestamps have no declared timezone; no timezone conversion is claimed. `recorded_at` is ISO date-time without offset.
Even same-day balances are not certified current: this is a historical file, not a live bank feed.
Only accounts with identical, non-null full timestamps and valid balances can produce a simultaneous total.
Different times on the same date also prevent a total. The sum covers observed accounts only.
An empty account list or any missing observation yields null total with a reason. Negative recorded balances are valid.
Current funds from `/assumptions` are never substituted for bank balances.

## GET /spending-comparison?period=week|month

Response:

```text
{
  customer_id: string, currency: "EUR", period: "week" | "month",
  status: "above" | "below" | "equal" | "insufficient_data",
  comparison: {start: date, end: date, spending_eur: number}?,
  baseline: {start: date, end: date, period_count: integer, average_spending_eur: number}?,
  difference_eur: number?, coverage: Coverage, confidence: "low", note: string,
  insufficient_data_reason: string?
}
```

Comparison is the latest qualifying full period. Baseline is **all prior qualifying periods**, excluding the comparison.
Difference = comparison spending minus baseline average rounded to cents. Its sign determines above/below/equal.
At least two full periods are needed. With one, comparison is present but baseline/difference are null;
with none, all three are null. Both cases return `insufficient_data` and a reason.
No percentage change is inferred from a zero baseline. No user chart target or allowance is used here.

## GET /planning-suggestions

Response:

```text
{
  customer_id: string, currency: "EUR", coverage: Coverage,
  observations: {
    income: Observation, housing_utilities: Observation, food: Observation, everyday_purchases: Observation
  },
  inputs: [{
    field: string, kind: "current_fact" | "future_fact" | "user_preference" | "user_plan",
    confirmed_value_eur: string?, needs_confirmation: boolean,
    observation_keys: string[], missing_reason: string?
  }],
  horizon_days: integer, missing_inputs: string[], note: string
}

Observation = {
  kind: "historical_estimate", average_monthly_eur: number?, source_period: DateRange?,
  period_count: integer, observations: integer, source: string, confidence: "low" | "unknown",
  confirmed: false, limitations: string[], unavailable_reason: string?
}
```

All full elapsed months in coverage form the denominator, including months without matching observations.
If no matching records occur in any qualifying month, the amount is unknown/null, not a suggested zero.
`observations` counts matching transactions; `period_count` counts all qualifying months.
`source_period` is null only when no qualifying months exist.
Confidence is low for available observations, unknown otherwise; never confirmed future income or expenses.
Income uses positive `salary`, `income`, `salary_payment`, `pension` only.
Housing/utilities use their explicit payment types; mortgage application fields are not inputs.
Food uses included payments with case-insensitive categories `groceries`, `restaurants`, `dining`, `food`,
`food & groceries`, `food & dining`. Everyday purchases use only the negative `purchase` type.
Food overlaps everyday purchases; never sum the two suggestions.
Monthly averages are not silently scaled to a 30-day or other planning horizon.

Exactly six `inputs` are returned, in the existing engine's required order:

| Field | Kind | Observation keys | Required review |
| --- | --- | --- | --- |
| `available_funds_eur` | current_fact | none | Currently accessible funds; old bank snapshots do not establish this |
| `confirmed_income_eur` | future_fact | income | Additional income in horizon, excluding funds already held |
| `upcoming_essential_bills_eur` | future_fact | housing_utilities | All required bills/active debt payments and timing |
| `emergency_reserve_eur` | user_preference | none | Additional funds to protect; no historical default |
| `everyday_spending_eur` | user_plan | everyday_purchases, food | Planned costs for horizon, excluding bills and overlap |
| `voluntary_goal_contribution_eur` | user_preference | none | Maximum chosen goal contribution; no historical default |

`confirmed_value_eur` copies the current assumptions field. `needs_confirmation` is true exactly when that field is null.
`missing_reason` is a field-specific explanation only for missing inputs; otherwise null.
`observation_keys` refers to observations even when their amount is unavailable; check confidence/amount before suggesting.
The response never writes assumptions. Existing confirmed zero stays confirmed zero.
The UI may ask for missing facts/preferences and review supported estimates, then submit the existing full-object
assumptions PUT only after confirmation. All six amounts still gate allowances; no zero defaults are introduced.

## POST /category-reduction

All request fields are required; extra fields are rejected. Category must be 1-100 characters and not whitespace-only.
`period_start` must be the first day of a month or a Monday for a week.
`reduction_percent` accepts a number or decimal string, 0-100 inclusive, at most two decimal places.

```json
{
  "category": "Restaurants",
  "period": "month",
  "period_start": "2026-08-01",
  "reduction_percent": "20"
}
```

Response:

```text
{
  customer_id: string, currency: "EUR", category: string, period: "week" | "month",
  source_period: DateRange, reduction_percent: number, baseline_spending_eur: number,
  hypothetical_spending_eur: number, potential_reduction_eur: number,
  coverage: Coverage, confidence: "low", read_only: true, goal_impact: null,
  goal_impact_unavailable_reason: string, note: string
}
```

Category matching trims whitespace and ignores case; response category is normalized lowercase.
Names come from spending-history categories; no fuzzy category guessing. `unknown`/`uncategorized` are unsupported.
Missing category or no included payments for the selected category/period returns 404, never an invented zero.
Partial, unelapsed, out-of-coverage or misaligned periods return 422. Empty/omitted category/period also fails validation.
Potential reduction = baseline * percentage / 100 rounded half-even to cents;
hypothetical spending = baseline - rounded reduction so the components reconcile exactly.
0% and 100% are valid. Transfers/refunds/investments never enter the baseline.
This is potential spending reduction, not actual savings. There is no save/confirm action on this route.
Goals, assumptions, allowances and the other customer's state remain unchanged on success, error and repeat calls.
Goal impact remains null even with confirmed inputs: the current model does not map category spending to future
horizon costs, so adding historical reductions to capacity could double-count money.

## Audit of supplied original demo datasets

Audited 2026-11-14 via the existing chunked loader, retaining only the two demo profiles.
Only aggregate findings are documented here; no raw records, account identifiers or balance amounts are committed.
All averages are gross historical observations with low confidence for future planning.

| Evidence | CUST04457 | CUST00001 |
| --- | --- | --- |
| Recorded transaction coverage | 2024-10-04 to 2026-09-25 | 2024-10-03 to 2026-09-30 |
| Latest balance available | One account, September 2026, historical | One account, September 2026, historical |
| Full months for suggestions | Nov 2024-Aug 2026 (22) | Nov 2024-Sep 2026 (23) |
| Income mean EUR/month | 3,107.00 (22 salary observations) | 2,399.02 (23 salary observations) |
| Housing/utilities mean EUR/month | 1,354.50 (88 observations) | 640.66 (92 observations) |
| Food mean EUR/month | 391.60 (215 observations) | 597.68 (249 observations) |
| All purchases mean EUR/month | 638.02 (313 observations) | 1,453.89 (425 observations) |
| Mortgage application records | Present; repayments unknown | Absent; active debt still unknown |

Food categories in these files are Groceries and Restaurants. The second profile also has investment deposits;
these are excluded from spending and income. No reserves, contribution preferences or goal progress can be inferred.
Known current funds, future income/bill timing, complete essential obligations and future living plans remain unconfirmed.
The absence of mortgage applications does not prove no debt. Salary observations do not guarantee future salary.

Latest comparison examples (from original files, not today's spending):

| Customer | Period | Spending EUR | Prior-period mean EUR | Difference EUR |
| --- | --- | --- | --- | --- |
| CUST04457 | Aug 2026 | 1,974.07 | 1,993.40 (21 months) | -19.33 |
| CUST00001 | Sep 2026 | 1,878.66 | 2,104.36 (22 months) | -225.70 |
| CUST04457 | 2026-09-14 to 2026-09-20 | 46.03 | 449.81 (101 weeks) | -403.78 |
| CUST00001 | 2026-09-21 to 2026-09-27 | 178.03 | 489.98 (102 weeks) | -311.95 |

Weekly results can vary greatly with bill timing; they are comparisons of recorded payments, not spare cash estimates.

## Historical demo plan: proposal for review, not implemented

Candidate retrospective horizons are August 2026 for CUST04457 and September 2026 for CUST00001.
There are pre-horizon balance observations on July 25 and August 30 respectively, not certified opening-midnight balances.
Consequently, even a historical plan cannot safely auto-populate opening accessible funds from those snapshots.
Using a closing balance plus that same period's salary would double-count income already reflected in the balance.

A future explicitly labelled retrospective mode would need a reviewed opening-balance policy and separate dated state.
It should use only pre-start observations for forecasts (avoid hindsight), distinguish actual period totals from estimates,
and require explicit scenario choices for reserve and maximum goal contribution. Users would also review complete bills,
living costs and horizon liquidity. Month length must match the horizon; 30 days is not interchangeable with every month.
No arbitrary reserve, contribution or income defaults are justified by these files. No synthetic plan is currently executed.
Any change to the six confirmed inputs, category-to-plan mapping or capacity formula requires separate policy review.

## Verification

Run from repository root, setting `SBANK_DATA_DIR` to the original dataset directory:

```powershell
.venv/Scripts/python.exe -m unittest backend.test_financial backend.test_coach backend.test_api backend.test_integration backend.test_data_coach -v
```

Synthetic-only suite: `backend.test_financial backend.test_coach backend.test_data_coach`.
The original two-profile API checks and isolated real-HTTP integration workflow are also run with the supplied datasets.
Result on 2026-11-14: **28 tests passed**, including both original demo profiles, synthetic edge cases and the existing
goal/allowance HTTP workflow. Tests ran with Python 3.12 and the repository requirements in a local virtual environment.
Windows sandbox loopback setup blocked asyncio startup; the suite passed outside that sandbox.
The installed Starlette version reports an httpx TestClient deprecation warning; no dependency change was needed.
New coverage includes missing/stale/zero/negative balances, differing timestamps, partial/ongoing periods,
insufficient history, equal spending, zero recorded interior periods, transfer exclusions, suggestions versus confirmations,
percentage/period/category validation, decimal rounding, repeated previews and non-mutation.

Frontend wiring is left to its owner. No frontend build or browser verification is claimed for this backend branch.
No remaining data-access blocker; numeric allowances still require confirmation, by design.
