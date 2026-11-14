# Cash-only spending estimate handoff

Base: `/api/customers/{id}/spending-estimate`. GET returns default preview; POST is read-only and does not save preferences.
Default mode current, horizon 7 days. Existing assumptions, budget, goals and Coach runtime remain unchanged.
Frontend should prefer a complete manual `/budget`, label it accordingly, and offer the separate draft for review.
Partial manual inputs are never overwritten or copied. POST request omission/null means unknown or automatic historical fallback;
explicit zero is a user answer. No full-PUT behavior on this endpoint.

## POST request

```json
{
  "mode": "current",
  "horizon_days": 7,
  "available_funds_eur": "1000.00",
  "emergency_reserve_eur": "100.00",
  "upcoming_essential_bills_eur": "700.00"
}
```

Optional fields: `additional_essential_bills_eur`, `everyday_spending_eur`, `voluntary_goal_contribution_eur`.
All money fields nullable, nonnegative, max 12 digits / 2 decimal places. Extra keys rejected; horizon 1–366.
`mode` current or historical. UI must not auto-submit suggested bills as user-confirmed bills.

## Response

- customer_id, currency EUR, mode, as_of (server check date ISO), reference_date (ISO, null if historical coverage is absent), horizon_days.
- status insufficient_data or estimated; daily_eur/weekly_eur nullable EUR numbers rounded DOWN to cents.
- confidence low: coverage and historical living costs remain uncertain, even after user answers.
- missing_inputs: array of field names; missing_fields: array of `{field,label,reason,suggested_value_eur}`.
- inputs: keys available_funds_eur, emergency_reserve_eur, upcoming_essential_bills_eur, everyday_spending_eur,
  voluntary_goal_contribution_eur; historical mode may also contain additional_essential_bills_eur.
  Each value `{value_eur:number|null,source,confidence}`. Source user / historical_rate / recorded_balance /
  historical_rate_plus_user / policy. User inputs have confidence user_provided; historical/policy low.
- observations.bills and observations.everyday_purchases: `{value_eur,source,confidence,source_period:{start,end}|null,
  observations,covered_days,horizon_days,formula,confirmed:false}`. Formula recorded total / actual covered calendar days * horizon days.
  References use elapsed full months inside recorded coverage up to reference date; absence of matching observations is null, not zero.
- observations.balances: existing recorded-balances response, including per-account timestamps and simultaneous total if supported.
- observations.income: existing income response. Evidence only; NEVER added to funds in this cash-only flow.
- allocations: existing plan allocation shape; completion_periods always null. Savings_capacity_eur nullable; shortfall_eur nullable.
- manual_plan_available bool; goal_policy string; limitations array of strings. Render goal_policy and date/mode visibly.

Default GET current has missing_inputs available_funds_eur, emergency_reserve_eur, upcoming_essential_bills_eur.
The three values in the request example yield status estimated, daily_eur 28.57, weekly_eur 199.99, missing_inputs [],
missing_fields [], shortfall_eur 0. They are illustrative values, not customer figures.
The example has no goal earmark: `goal_policy: No money set aside for goals in this estimate.`
Voluntary contribution input is then `{value_eur:0,source:policy,confidence:low}`: explicit no-earmark policy, not inferred preference.

## Trust boundaries

Current mode ALWAYS requires user-confirmed accessible funds, reserve and complete TOTAL bills due in the horizon.
Historical prorated housing/utilities appear as references, not known upcoming obligations. A monthly rent average cannot
protect a rent payment due tomorrow. Missing bill metadata may show that reference as suggested_value_eur for review only.
Current additional_essential_bills_eur cannot bypass the required total. Even a recorded-today balance is not promoted to current funds.

Historical mode is explicitly hypothetical, never today's affordability. A simultaneous balance may supply funds only when dated
on/before today; reference_date is its actual timestamp date. Asynchronous account balances are never summed. If unavailable,
reference_date falls back to recorded coverage end and funds still require user input. Missing latest balances stay missing.
Historical bills may use the automatic rate plus explicit additional bills (including user-entered zero), or a full total override.
A reserve is always required. User current-fund overrides in historical mode are scenario inputs, not inferred past facts.

No future salary, recurring income, or mortgage income requirement is added to cash. Recorded income is already potentially
represented in balances. No mortgage approval becomes debt; users include actual active debt obligations in the bills total.
Food is not added to purchases; historical purchase amounts exclude bill types/transfers/refunds. Users should review any overlap
between irregular purchase essentials and full bill overrides. Coverage may omit transactions/accounts.

With positive explicit voluntary contribution, reuse plan() to allocate critical, important, flexible (stable within priority),
after protecting bills, reserve and historical or overridden everyday living costs. If no purchase history, everyday costs must
be supplied before allocating. Without contribution, no goals are earmarked. Missing everyday history alone does not block the
cash allowance when there is no goal earmark; savings capacity stays null. Allowance includes everyday spending, not extra money
on top of it. No completion extrapolation: starting cash is never repeated. Negative historical cash yields zero allowance/shortfall.

All calculations in Python. Daily = floor-to-cent(max(0,cash-reserve-bills-actual allocations)/horizon).
Weekly = min(remaining allowance,daily*7). No intra-horizon cash timing is modeled; users must cover bills before spending.

## Validation evidence

31 financial/API tests plus 44 offline mocked Coach regression tests passed: backend.test_spending_estimate, backend.test_financial, backend.test_data_coach, backend.test_api.
Includes both real demo customers via SBANK_DATA_DIR, three-input current flow, bill timing, explicit zero/missing distinction,
actual-day rate scaling, transfers, asynchronous/missing balance handling, historical reference date, priorities, reserve/bills
protection, no repeated starting cash, HTTP invalid inputs and byte-equivalent manual state before/after estimates.
No provider calls or ledger modifications. Original data remain outside the worktree and are not committed.
