# Financial engine API extensions

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

## Curated demo questions

GET `/api/customers/{id}/coach-demo-prompts` returns `{questions: [{id, label, question}], note}`.
Dates are drawn from full recorded months; unavailable comparisons/categories are omitted. This GET is local and read-only.
See [DEMO_PROMPTS_HANDOFF.md](DEMO_PROMPTS_HANDOFF.md) for scope and UI pairing.
Exact supported broad demo queries receive local `mode=rule_based`, `fallback_reason=demo_guidance`, with no paid call.
Selecting a dated question uses the existing Coach API, financial tools, request deduplication and spending limits.


### Local savings demo question

The demo prompt list now contains up to four items, including `save-most` with an explicit recorded YYYY-MM.
POST /api/customers/{id}/coach accepts `Where could I save (the) most?` (also `can`), optionally `in YYYY-MM`.
Response uses existing kind=help, mode=rule_based, fallback_reason=demo_guidance, text, and empty cards/rows.
Python ranks hypothetical 10% reductions for restaurant, entertainment and travel purchases in one dated month.
No date means latest full recorded month; an unavailable explicit month never falls back to another period.
These are review candidates, not confirmed nonessential costs or a comprehensive savings recommendation.
No provider call or reservation occurs. Conversation ownership and request deduplication remain enforced.
Existing goals/allowances/confirmed inputs and prior calculation context remain unchanged.
Exact grocery-saving and online impulse-buying education questions documented in DEMO_PROMPTS_HANDOFF.md also
return local general tips through this same response shape. No new financial tool or paid configuration is added.


### Guided savings conversation (read-only)

GET /api/customers/{id}/savings-opportunities accepts optional `month=YYYY-MM` and
`reduction_percent` (default 10, range 0..100, at most two decimal places).
Unknown customers: 404; invalid argument syntax/range: 422.
Response:
```
{
  "currency": "EUR",
  "status": "available | no_candidates | unavailable_period",
  "source_period": {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"},
  "reduction_percent": 10,
  "candidates": [{"category": "restaurants", "baseline_spending_eur": 95.04,
                  "hypothetical_spending_eur": 85.54, "potential_reduction_eur": 9.50}],
  "note": "Coverage, exclusions and hypothetical-only limitations"
}
```
The example figures illustrate the response, not a default value. Python calculates all values per customer.
`unavailable_period` returns null source_period and empty candidates; `no_candidates` retains the requested recorded dates.
No month chooses latest full recorded calendar month. Explicit missing/partial months never substitute older data.
Only negative purchase-type restaurant, entertainment and travel records qualify; explicit bill types are excluded even if
misclassified into those categories. Same rounding as existing reductions. Sort by potential reduction descending, then category.
The list is bounded to three approved aggregate categories. No records, merchant names, account IDs or goal IDs are returned.
GET does not call a provider, access the spending ledger, create Coach receipts or change financial state.
The guided UI should pin the source month for percentage reruns and never add these historical scenarios to goal capacity.

Goal conversation reuses GET goals and GET goal-analysis. Existing fields and plan formulas are unchanged;
coach_message now explains funded-within-horizon, conditional repeating-plan feasibility, no capacity and missing confirmations.
Planned allocation is not saved progress. Completion periods are conditional plan periods, never promised calendar deadlines.


### Automatic planning drafts
GET /api/customers/{id}/planning-defaults?horizon_days=30 (integer1..366) returns read-only draft defaults.
`balance:{amount_eur,recorded_at,note}` uses latest recorded simultaneous account total; missing, negative,
future-dated or differently dated account balances stay null. This is historical, not a live bank balance.
`income:{amount_eur,note}` uses explicit salary/salary_payment averages over the latest up to3full months.
`bills:{items:[{label,amount_eur}],total_eur,note}` uses separate housing payments, utility payments and grocery purchases.
Food includes groceries/grocery category purchases only, not restaurants or housing rows with a grocery label.
Income and each cost average scale by horizon_days/30, then round to cents; total sums rounded cost lines.
If a component lacks observations its amount and combined total are null, never assumed zero.
`note` identifies these as historical drafts requiring user review. No assumptions/goals/ledger are changed by GET.
UI makes recorded balance read-only, lets users edit income and combined costs, and excludes food from remaining everyday costs.
Only explicit existing plan confirmation saves these drafts as user inputs. Dates/amounts are not future guarantees.

Planning defaults now also return everyday.amount_eur and daily_average_eur (remaining purchase rows excluding the food/housing/utilities groups) and reserve.monthly_expenses_eur, default_months=3, and options for 1..12 months with amount_eur/exceeds_balance. Reserve targets use total average recorded expenses and are independent of plan length. No reserve is capped to the balance or claimed already saved. UI starts calculated fields afresh, retains only current-form edits, and leaves goal contribution blank for user choice.

POST planning-remainder accepts the four nullable nonnegative monetary fields confirmed_income_eur, upcoming_essential_bills_eur, everyday_spending_eur, voluntary_goal_contribution_eur. Returns remaining_income_eur, goal_contribution_included and note. Python subtracts bills/everyday/entered goals from income; missing first three returns null, missing goal previews zero with explicit before-goal label. Negative remainder is preserved. Existing balance/reserve are excluded; not safe-to-spend. No writes, provider or ledger.
