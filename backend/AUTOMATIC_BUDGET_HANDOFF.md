# Automatic historical demo budget

GET `/api/customers/{id}/automatic-demo-budget`. No request body, inputs, persistence or provider call.
UI: replace only automatic Safe to spend component; keep Add goal. Label numbers **Extra spending estimate**,
above usual spending, show source dates and historical disclaimer directly. No goals -> existing Create a goal CTA.
No money form. Existing manual budget and assumptions routes are unchanged.

## Exact response schema

```text
{
 customer_id:string,currency:"EUR",label:"Extra spending estimate",
 status:"needs_goal"|"insufficient_data"|"estimated",action:"create_goal"|null,
 mode:"historical_demo",as_of:ISOdate,source_period:{start:ISOdate,end:ISOdate}|null,
 period_count:integer,covered_days:integer,confidence:"low",
 daily_eur:number|null,weekly_eur:number|null,monthly_extra_eur:number|null,
 income_eur:number|null,protected_spending_eur:number|null,surplus_eur:number|null,deficit_eur:number|null,
 reserve_target_eur:number|null,reserve_contribution_eur:number|null,reserve_shortfall_eur:number|null,
 goal_budget_eur:number|null,goal_allocated_eur:number|null,
 goal_allocations:[{goal_id:string,priority:string,target_eur:number,allocated_eur:number,completion_periods:null}],
 policy:{reserve_income_percent:10,goal_surplus_percent:50,basis:string},
 missing_inputs:[string],limitations:[string]
}
```

Status needs_goal takes precedence with no stored goals, action create_goal and numeric planning fields null.
Missing history gives insufficient_data, null numeric planning fields, no create-goal action when goals exist.
`missing_inputs` names evidence gaps, NOT manual form fields: three_complete_recorded_months,
income_evidence:YYYY-MM, spending_evidence:YYYY-MM, unclassified_debit_evidence:YYYY-MM. Every selected month requires positive explicit income
and at least one included spending payment. No evidence is never converted to zero income or expenses.
Unknown customer ->404; existing endpoints and response schemas unchanged.

## Selected app policy and exact arithmetic

Use the SAME latest three full elapsed calendar months bracketed by recorded transactions. Exclude partial/ongoing/future months.
All monthly income and spending figures use exact transaction cents /3, rounded half-even to cents.
Income uses positive salary/income/salary_payment/pension. Protect ALL negative purchase/housing_payment/utilities_payment,
including groceries, irregular essentials and uncertain categories; no extra food addition. Exclude transfers, investment
deposits, refunds and mortgage application amounts. Unknown negative transaction types BLOCK a numeric estimate. Coverage may omit actual obligations/accounts.

I=monthly income; E=monthly protected spending; F=max(0,I-E); deficit=max(0,E-I).
Reserve-building target=round(10%*I); reserve contribution R=min(F,target); reserve_shortfall=target-R.
Goal budget=floor-to-cent(50%*(F-R)). Allocate to stored remaining goal targets, critical->important->flexible,
stable insertion order for ties, each capped at target. A=sum(ACTUAL allocations).
Monthly extra spending headroom H=F-R-A: unused goal budget returns to headroom.
Daily=floor-to-cent(H*3/covered_days); weekly=min(H,daily*7).
covered_days is actual sum of calendar days in the selected three months, including leap-day behavior.
This is a hypothetical TYPICAL MONTH cash-flow plan, not allocating three months of capacity to targets.
Completion_periods always null; no repeated starting cash, goal progress assumptions or interest models.

10% reserve and 50% goal allocation are explicitly selected APP DEMO assumptions, not S-Bank policy or customer preferences.
A reserve-building contribution is NOT an established emergency reserve. Actual reserve adequacy/active debt are unknown.
No opening or closing balance is added to income; income already in balances is never counted a second time.
The estimate is NOT today's affordability, a forecast of bill timing or a verified future surplus. Render limitations.
Nothing changes stored goals, assumptions, budget or Coach state. Existing cash-only estimate86d657f is preserved.
No Coach runtime files changed; no merge/provider calls.

## Independent synthetic oracle

Three complete months Jan-Mar2024 cover91days. I1000/E600 yields F400,R100,goalbudget150.
Goal target1000: allocated150,monthly_extra150,daily4.94,weekly34.58.
Goal target20: allocated20,monthly_extra280,daily9.23,weekly64.61.
I1000/E1100: deficit100,reserve_shortfall100,all allocations/headroom zero.
No goals: needs_goal,null amounts. One month without income: insufficient_data,null amounts,dated reason.

## Checks

`python -m unittest backend.test_automatic_demo_budget backend.test_spending_estimate backend.test_financial
backend.test_data_coach backend.test_api -q` with SBANK_DATA_DIR set to original local files: **39 tests passed**.
Includes independent monthly arithmetic for both real demo profiles, source coverage, no-goal state,
missing/empty history, actual-day denominator, protected groceries/irregular spending, transfer/refund exclusion,
priority/target caps, reserve shortfall, negative surplus and manual-plan/goal nonmutation.
Source files parse and new Python lines are under150characters. No raw data committed.
