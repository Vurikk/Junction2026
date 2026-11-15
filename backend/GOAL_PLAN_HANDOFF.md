# Goal savings and spending-impact contract

Frontend owner: no UI files modified in this task. All endpoints are local deterministic Python; no LLM.

GET `/api/customers/{id}/goal-plan` returns existing automatic-demo-budget fields plus:
- `monthly_savings_capacity_eur`: income minus protected usual spending minus reserve contribution, floored at zero.
- `goal_allocated_eur`: first-month actual goal allocations (already deducted from spending).
- `monthly_extra_eur`, `daily_eur`, `weekly_eur`: same spending values as Home when goals exist.
- `additional_savings_if_redirect_extra_eur`: monthly extra headroom that could be redirected, NOT new income.
- `goals`: ordered by priority, with goal_id, name, priority, priority_label, target_eur, monthly_allocation_eur,
  completion_months, completion_weeks, save_all_extra_months, save_all_extra_weeks.
- `timing_basis`: explicit repeating historical cash-flow assumptions. Actual saved progress remains unknown.

This endpoint calculates capacity even with no goals; Home automatic-demo-budget still returns needs_goal as before.
Missing evidence returns null amounts/times; zero capacity returns zero amounts and null times. No invented zero for missing data.
Capacity equals actual goal allocations PLUS extra headroom. Never add extra to capacity again.

Timing uses the existing monthly goal budget (50% of after-reserve surplus). Cumulative targets divided by that pool,
rounded up to whole months, allow finished higher-priority goals to release their savings to the next goal.
Weeks = ceiling(months * covered_days / 3 / 7), using the same three recorded months as Home.
save_all_extra timings use the full after-reserve capacity; hypothetical only, never changes the spending plan.

POST `/api/customers/{id}/goal-plan/preview` accepts the existing GoalInput `{name,amount_eur,priority}`.
Returns `{before,after,spending_change,proposed_goal_id,saved:false,note}`.
`before` and `after` are full goal-plan results; changes include signed daily_eur/weekly_eur/monthly_extra_eur.
Negative means less spending headroom. Zero can mean the existing savings pool is reassigned rather than increased.
Use after.daily_eur etc to say "With this goal, your estimated extra spending would be X/day".
Do not persist a preview. Actual goal creation stays explicit POST /goals; existing contract unchanged.
With no goals the before figures are a clearly defined no-goal scenario, not a numeric Home card previously displayed.

Guided Coach supports two NEW action IDs via POST /guided-coach:
- `monthly_savings`: income/spending/reserve/capacity/allocated/extra breakdown, even with no goals.
- `goal_timing`: same goal analysis as `goals`, with priority-rollover months/weeks and faster full-saving comparison.
Existing goals answer now uses these correct rollover estimates rather than permanently treating lower-priority zero allocation as blocked.

UI naming only: critical -> Urgent; important -> Important; flexible -> Flexible (aligned with UI owner's latest user request).
Request/storage enums stay critical/important/flexible. Labels available as priority_label on each result.
Suggested button copy: How much could I save each month? / When could I reach my goals?

Policy remains disclosed historical demo assumptions: all usual recorded spending protected; up to10% income reserve-building;
50% remaining surplus goal pool. No balances added, no actual reserve adequacy claimed, no promised future income.

## Verification

19 tests passed with original demo datasets available: test_goal_plan, test_guided_demo, test_automatic_demo_budget.
Checks include no-goal savings (without changing Home's needs_goal state), priority rollover, weeks/months,
zero/missing capacity, extra-headroom non-double-counting, preview nonmutation, same estimate after explicit creation,
unchanged create contract, customer isolation and a failing guard if CoachLLM.respond is called. No provider traffic.
No frontend files modified. Running preview backend must be safely reloaded by its owner to expose these new routes;
the test client verifies source independently of the existing long-lived preview process.
