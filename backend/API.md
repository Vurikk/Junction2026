# Financial engine API extensions

## Scripted Coach (no LLM)

Goal demo extension: GET `/api/customers/{id}/goal-plan` returns monthly saving capacity, current spending headroom
and conditional priority-rollover timelines. POST `/api/customers/{id}/goal-plan/preview` accepts existing GoalInput,
returns before/after plans and signed spending_change, and does not save the goal. Full fields and assumptions:
`GOAL_PLAN_HANDOFF.md`. Guided action IDs also accept `monthly_savings` and `goal_timing`.

POST `/api/customers/{id}/guided-coach` accepts action: overview, savings, goals, comparison, allowance or tips.
Optional percent is10 or20 (default10), month is YYYY-MM, category is restaurants, entertainment or travel.
Returns mode=guided, text, source_period, rows, note and follow-up actions. All financial math runs in Python.
This read-only route never calls the LLM path or changes goals, assumptions or usage ledgers.
Goal timings are conditional on repeating the historical monthly allocation with no known saved progress.

Existing customer, spending and mortgage routes retain their fields and semantics.
Optional Verda support is disabled/gated by default. Goals and confirmed inputs remain per-customer, in memory, reset on restart.

## Data-backed Home and read-only reduction scenarios

Four additive routes are available; existing routes and the six confirmed allowance inputs remain unchanged.
Exact request/response schemas, data audit, UI guidance and historical demo policy proposal are in
[DATA_COACH_HANDOFF.md](DATA_COACH_HANDOFF.md).

| Request (under `/api/customers/{id}`) | Result |
| --- | --- |
| `GET /recorded-balances` | Latest per-account balance, EUR, timestamp, historical status; current funds remain unknown |
| `GET /spending-comparison?period=week\|month` | Latest full elapsed period versus prior full periods, dates, difference and status |
| `GET /planning-suggestions` | Dated historical monthly estimates, confidence, limitations and six field-specific confirmation reasons |
| `POST /category-reduction` | Read-only potential category spending reduction for an explicit historical week/month |

The reduction request requires `category`, `period` (`week` or `month`), `period_start` (ISO date), and
`reduction_percent` (0-100, at most two decimal places). Returns baseline, hypothetical spending and potential reduction;
never actual savings or goal mutations. Unsupported/missing category observations return 404; invalid/partial periods return 422.
The comparison baseline excludes the comparison period. Coverage is not guaranteed completeness.
Balances from different timestamps are never added into a simultaneous total. These endpoints do not confirm assumptions.

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

## Integrated frontend calls

| Screen/action | Request | Fields consumed |
| --- | --- | --- |
| Customer switch | `GET /api/customers` | `customer_id` |
| Home recorded spending | `GET /api/customers/{id}/spending` | `month`, `spending_eur` |
| Home allowances | `GET /api/customers/{id}/budget` | `status`, `daily_eur`, `weekly_eur`, `shortfall_eur`, `assumptions` |
| Planning form | `GET`, confirmed `PUT /api/customers/{id}/assumptions` | Full object below |
| Week/month chart | `GET /api/customers/{id}/spending-history?period=week\|month` | `periods`, `historical_average_eur`, `budget_target_eur` |
| Goal list/create | `GET`, `POST /api/customers/{id}/goals` | Name, EUR target, critical/important/flexible priority |
| Analyze goals | `GET /api/customers/{id}/goal-analysis` | Ordered allocations, capacity, completion periods, explanation |
| Mortgage availability | `GET /api/customers/{id}/mortgages` | `applications`, `note` |

All financial arithmetic remains in Python. Frontend number conversions only format/display API values.
Changing customers reloads their data; successful goal creation or input confirmation reloads budget and clears stale analysis.
Weeks are Monday through Sunday, not seven-day slices of a month. Chart targets are not safe allowance estimates.

Example confirmed assumptions (illustrative values, not customer data):

```json
{
  "available_funds_eur": "1000.00",
  "confirmed_income_eur": "0.00",
  "upcoming_essential_bills_eur": "400.00",
  "emergency_reserve_eur": "200.00",
  "everyday_spending_eur": "100.00",
  "voluntary_goal_contribution_eur": "300.00",
  "weekly_budget_eur": "70.00",
  "monthly_budget_eur": "300.00",
  "horizon_days": 30,
  "repeat_plan": true
}
```

For three EUR 200 goals (one per priority), this allocates EUR 200/100/0 in priority order,
leaves daily EUR 3.33 and weekly EUR 23.31, and conditionally estimates completion in 1/2/2 planning periods.
Without repeat confirmation, completion periods are null. Without all six money inputs, status is `insufficient_data`.
History monetary totals are JSON numbers; optional chart targets and confirmed inputs may be decimal strings.

Run real HTTP checks with `python -m unittest backend.test_integration -v`.
The test uses local demo data and an isolated server; it never changes goals in an already-running app.

## Rule-based coach
`POST /api/customers/{id}/coach` accepts `question` (1-500 characters) and optional
`scenario` with the existing GoalInput fields (name, amount_eur, priority).
Returns `kind`, short `text`, and category `rows` (`label`, `value`) where relevant.
Scenario replies also return the validated `preview` payload. This endpoint never writes state;
confirming in the UI calls the existing goal POST. Scenarios model adding a goal, not editing one.
Scenario replies include `baseline` and `analysis` objects with the Budget response fields, calculated before/after adding
the hypothetical goal. Its temporary allocation ID is `preview`; confirmation creates a new actual goal ID.
Unknown input amounts remain null in both views. Repeated previews leave stored goals, assumptions and budgets unchanged.
Editing the scenario invalidates UI confirmation until a new preview is requested. Discard and customer switching do not save it.
Goal-analysis adds `coach_message`; all existing fields remain compatible.
No external provider or API key is required for the rule-based path. Unknown questions get suggested topics.
Whitespace-only questions are rejected (422). Category names can be asked directly; answers refer to the latest recorded month.
An absent category is not proof of zero actual spending. Mortgage answers distinguish application data from active debt;
monthly repayments and current account balances are not inferred from historical records.


## Optional Verda Coach integration (additive, gated)

`POST /api/customers/{id}/coach` additionally accepts optional UUID `conversation_id` and `request_id`.
Existing question/scenario and response fields are preserved. Adds `mode` (`llm` or `rule_based`), nullable `fallback_reason`,
returned conversation/request IDs and `cards` containing validated Python aggregates. Goal previews stay local and read-only.
The first request establishes an HttpOnly session cookie; paid calls require a supplied conversation ID and that cookie.
Keep the same IDs/body on retries; use a new request ID for a new turn and a new conversation on customer change.

Only category spending, spending comparison and category reduction are approved tools. One model call selects a validated
tool; Python calculates the card and renders its explanation. There is no second explanation call or automatic goal/input change.
Outbound requests contain canonical intent/category/date/percentage slots and validated context, never the user's raw prose.
Category-spending cards with `category: "all"` also contain up to five `categories` entries and `other_spending_eur`;
listed entries plus that remainder equal `spending_eur`. The remainder is not a second copy of the displayed `other` category.
The user-approved cumulative limit is **EUR 1.00**, replacing the earlier USD wording. Paid deployment requires explicit local review,
a persistent host-bound SQLite ledger, and `COACH_LLM_BUDGET_EUR`; the old USD variable does not enable paid calls.

See [VERDA_HANDOFF.md](VERDA_HANDOFF.md) for exact fields/card schemas, fallback reasons, privacy controls,
model/pricing evidence, duplicate semantics, setup gates and the controlled smoke command. No paid mode was enabled during implementation.

### Disabled/unavailable provider behavior (QA-01/02)

Supported spending questions use the same local language/date validation and Python tools even without a provider.
Successful local answers have `mode: rule_based`, existing cards/text fields, and the configuration fallback reason
(for example `disabled` or `missing_configuration`). They do not imply a model call.
Ambiguity returns `clarification_needed`; absent/partial requested history returns `unsupported_period_or_category`
with empty cards/rows. An unavailable requested month is never replaced with the latest observed month.
Food ambiguity and dated percentage follow-ups use validated local context. Goal previews and other existing non-spending
answers retain their behavior. No financial formulas, confirmed inputs or goals change.

Free-mode context and duplicate receipts live only in this backend process, independently of the paid ledger.
They expire after 30 minutes and are bounded to 256 conversations overall, 32 per browser and 2048 request receipts.
Context is isolated by browser session and customer. Matching receipts return the original response; changed bodies with
the same request identity return `request_conflict`. A capacity limit returns `session_limit` rather than evicting live receipts.
After a restart or expiry, repeat the category and recorded period; free context is not recovered from the billing ledger.
Paid request receipts/reservations retain their existing persistent behavior.

### Retrying a busy rejection (QA-03)

An identical request that returned `concurrency_limit` may be retried explicitly with the SAME IDs and body.
The backend atomically readmits it only if no provider-call record/reservation exists and rate limits permit admission.
An admitted duplicate returns `request_in_progress`; a completed duplicate returns its saved response.
Other failures, completed answers and requests with uncertain billing are never reopened by this rule.
No automatic retry, new request ID, ledger deletion or schema migration is required.

## Read-only cash-only spending estimate

`GET /api/customers/{id}/spending-estimate` previews defaults; `POST` the same path calculates overrides.
See [SPENDING_ESTIMATE_HANDOFF.md](SPENDING_ESTIMATE_HANDOFF.md) for exact UI contract and safety policy.
Neither endpoint saves inputs, changes goals, calls a provider, nor changes the existing confirmed-plan `/budget` contract.
Current mode requires accessible funds, reserve and the TOTAL essential bills due within the selected horizon.
Historical bill/purchase references are automatic, dated estimates; current bills are never automatically prorated.

## Automatic historical demo budget (default goal-driven flow)

`GET /api/customers/{id}/automatic-demo-budget`: no money inputs, no goals -> needs_goal / Create a goal.
Returns extra spending above protected usual spending, using the same latest three complete recorded months,
explicit 10% income reserve-building and 50% remaining-surplus goal allocation app policies.
Not today's affordability; current reserve adequacy and active debt remain unknown. No balances are added to income.
See [AUTOMATIC_BUDGET_HANDOFF.md](AUTOMATIC_BUDGET_HANDOFF.md) for exact schema, arithmetic, examples and 39-test evidence.
Existing confirmed manual plans, cash-only draft endpoint, goals and Coach runtime are unchanged.

Chart integration: spending-history now falls back to the automatic TOTAL historical spending benchmark when the
matching-period manual target is null. Explicit manual0 wins. Additive target_source (manual|automatic_historical|null),
target_source_period, target_basis and target_limitations describe provenance. Exact weekly formula and tests in handoff.


## Optional spending plan integration

- GET `/api/customers/{id}/planning-defaults?horizon_days=30`: historical editable suggestions;
  never confirms assumptions or changes goals. Horizon 1?366 days.
- POST `/api/customers/{id}/planning-remainder`: income minus bills, everyday costs and optional
  voluntary contribution; accepts `horizon_days`. This preview is not the automatic home allowance.
- GET `/api/customers/{id}/planning-state`: `has_saved_plan` indicates an explicitly saved assumptions payload.
- PUT `/assumptions` retains its existing contract. Optional backend environment variable
  `SBANK_PLAN_STATE_PATH` enables SQLite persistence across restarts. Without it, plans remain in memory.
  Keep the SQLite file outside version control; goals are still session-only.

Automatic allowance, goal-plan and historical chart fallback remain unchanged. Explicit chart target
settings retain their existing precedence. Optional plan costs do not override automatic calculations.

Goal-plan also returns projection: seven points (month 0 through 6), each with values keyed by goal ID. Python repeats the monthly goal budget, allocates by priority, caps each target and rolls remaining funds forward. These are hypothetical future contributions, not historical deposits.

Automatic-demo-budget target_comparison compares the latest complete recorded month with the automatic monthly target. Status over means spending exceeds target; near means 90�100% of a positive target. Includes dated period, spending_eur, target_eur and over_eur; null when unavailable. It is not live usage or a comparison with a manual chart override.

Guided-coach savings replies add savings_projection (percent, series, points months 0-6, note). Each value repeats the existing rounded monthly reduction; no interest or actual saved balance. Missing categories have no line.

DELETE /api/customers/{customer_id}/goals/{goal_id}: removes only a goal owned by that demo customer; returns deleted_goal_id. Unknown customer/goal returns 404. Frontend requires explicit confirmation and refreshes goals, allowance and charts.
