# Backend agent -> manager handoff

Updated: 2026-11-14 (Europe/Helsinki)
Owner: backend agent
Working branch: `codex/data-backed-budget`
Status: Verda integration verified with 49 passing tests; paid mode remains off pending review. Allowance policy deferred.

## How to use this file

This is the backend agent's persistent handoff to the manager agent.
Read it when resuming or coordinating backend work. Update completed work, blockers, test evidence and decisions here.
The manager can append dated decisions or requests below; the backend agent should acknowledge them on its next task.
This file does not imply continuous monitoring or automatic delivery to another chat.
Do not interpret a proposal as approved policy. Coordinate API changes with the UI owner before implementation.

## Delivered and verified

- Commit `b9a6e39e0bf7b0859f3f56f09e6e7f8cfaed9554` was pushed to the backend branch and fast-forwarded to `main`.
- Four additive routes under `/api/customers/{id}`:
  - `GET /recorded-balances`: historical account observations with timestamps; no false current balance.
  - `GET /spending-comparison?period=week|month`: full-period comparison excluding the target from its baseline.
  - `GET /planning-suggestions`: dated estimates and field-specific missing-confirmation reasons.
  - `POST /category-reduction`: dated, read-only hypothetical reductions; no goal mutation.
- All 28 backend tests passed against the two supplied datasets and synthetic cases, including existing HTTP workflows.
- User reports these changes are integrated into the UI branch and its 28 tests pass.
- UI agent is now connecting `/category-reduction` to Coach. All published contracts remain frozen pending coordination.
- No frontend files were edited by this backend agent. The existing six-input allowance formula is unchanged.

Contracts and original-data audit: [backend/DATA_COACH_HANDOFF.md](backend/DATA_COACH_HANDOFF.md).
API reference: [backend/API.md](backend/API.md).

## Current task: minimal Verda integration

User explicitly approved an additive Coach integration, then corrected the cumulative cap to **EUR 1.00**.
The Console screenshot identifies DeepSeek 4.1 Flash 1017 at EUR 0.1336 input / EUR 0.5346 output per million tokens.
Supported model ID is exactly `deepseek-4-1-flash-1017`; unverified models/configuration fail closed.

Implementation, exact additive UI contract and review-only smoke command: [backend/VERDA_HANDOFF.md](backend/VERDA_HANDOFF.md).

- Existing financial/data endpoints and goal preview contracts stay intact; no allowance-progress policy implemented.
- Optional conversation/request UUIDs, browser/customer isolation, three approved read-only tools, independent Python result cards.
- Explanations select Python fact IDs; no free model-generated numerical claims. Privacy blocks unsafe/uncertain pasted content.
- Cumulative EUR ledger reserves worst-case context/output cost atomically; no reset on restart, no automatic retries/refunds.
- Host-bound review, one paid worker, two calls/message, 15-second deadline, persistent deduplication and session/global rate limits.
- `COACH_LLM_BUDGET_EUR=1.00` is now required. The old USD variable is migration-only, never silently interpreted as euros.
- No real key was inspected or printed, no actual Verda request made, and no real approval/paid deployment initialized.
- UI must retain the session cookie and reuse conversation/request IDs for retries. Legacy callers remain on the free fallback path.
- Manager must review privacy/language limits, euro pricing and the ONE designated host before activation.
  Other PCs call that backend; they must not create their own ledgers or independent paid deployments.
- All 49 tests passed, including 19 Verda tests with mocked transport; existing data-backed HTTP workflows still pass.
- Existing interactive servers were not restarted. Frontend integration and a real provider smoke test remain pending.

## Verified restaurant-reduction demo

Verified on 2026-11-14 using the actual supplied datasets through the Python endpoint, then pinned in isolated real-HTTP tests.
Use these exact periods; the latest overall month does not necessarily contain restaurant purchases.

1. Select the customer, open Coach's category-reduction control, and choose the month/category below.
2. Enter 20%. Show the source dates, baseline, hypothetical spending and **potential spending reduction**.
3. Repeat the request or switch customer and use that customer's month. Existing goals, inputs and allowances stay unchanged.
4. Show that 0% changes nothing and 100% reduces the hypothetical amount to zero. Neither result is actual saved money.

Exact requests (same relative paths through the Vite proxy or the Python API at `http://127.0.0.1:8000`):

```http
POST /api/customers/CUST04457/category-reduction
Content-Type: application/json

{"category":"Restaurants","period":"month","period_start":"2026-07-01","reduction_percent":20}
```

```http
POST /api/customers/CUST00001/category-reduction
Content-Type: application/json

{"category":"Restaurants","period":"month","period_start":"2026-09-01","reduction_percent":20}
```

Both return HTTP 200, `category: "restaurants"`, `read_only: true`, `goal_impact: null`, and EUR amounts:

| Customer | Recorded source period | Reduction | Baseline | Hypothetical spending | Potential reduction |
| --- | --- | --- | --- | --- | --- |
| CUST04457 | 2026-07-01 to 2026-07-31 | 0% | 95.04 | 95.04 | 0.00 |
| CUST04457 | 2026-07-01 to 2026-07-31 | 20% | 95.04 | 76.03 | 19.01 |
| CUST04457 | 2026-07-01 to 2026-07-31 | 100% | 95.04 | 0.00 | 95.04 |
| CUST00001 | 2026-09-01 to 2026-09-30 | 0% | 225.70 | 225.70 | 0.00 |
| CUST00001 | 2026-09-01 to 2026-09-30 | 20% | 225.70 | 180.56 | 45.14 |
| CUST00001 | 2026-09-01 to 2026-09-30 | 100% | 225.70 | 0.00 | 225.70 |

The response amount keys are `baseline_spending_eur`, `hypothetical_spending_eur`, and `potential_reduction_eur`.
`source_period` contains the table's inclusive start/end dates. JSON numbers need not retain trailing zeroes.

**Important demo trap:** CUST04457 has no recorded Restaurants purchases in August 2026. That request correctly returns 404.
Use July for this customer. Do not display an absent category as zero or silently relabel an older month as the latest month.

### Verification and bug review

- Full suite: **30 tests passed** using both original datasets, synthetic cases and an isolated Uvicorn HTTP server.
- Exact 0%, 20%, 100%, then repeated 20% responses are asserted for both demo customers.
- These run after creating goals and confirming a nonzero plan: goals, assumptions and budget/allowances remain identical.
  Both the selected customer's state and the other customer's state are checked after successful and rejected requests.
- -1%, 101%, NaN, Infinity and excess decimal precision are rejected with 422 (synthetic/API coverage as applicable).
- Omitted/blank category or required period fields return 422. Unknown/unrecorded category returns 404.
- October 2024 is incomplete for both source files: `period_start: "2024-10-01"` returns 422.
  Misaligned, out-of-coverage and incomplete periods remain rejected; no extrapolation is performed.
- Reproduced and fixed one balance fallback bug: an absent `balance_after_eur` column erased an available timestamp.
  It now preserves that timestamp/age while balance stays null, status unavailable, and simultaneous total null.
  The regression test failed before the fix and passes afterward. Response keys/types and financial policy are unchanged.
- Reviewed comparison/suggestion date boundaries and exclusions. Added a focused year-boundary/leap-day case with a missing
  category and transfers/investments: partial edge months are excluded, amounts reconcile and suggestions stay unconfirmed.
  Existing tests cover missing/zero balances, differing timestamps, equal spending, insufficient history and rounding.
- No additional verified comparison/suggestion bug was found. No allowance-progress implementation or new feature was added.

Reproduce from the backend checkout with `SBANK_DATA_DIR` set to the supplied original dataset folder:

```powershell
.venv/Scripts/python.exe -m unittest backend.test_financial backend.test_coach backend.test_api backend.test_integration backend.test_data_coach -v
```

Known limits: coverage is not guaranteed complete; restaurant reductions are historical hypotheticals, never actual savings.
Goal impact remains unavailable; no progress or live remaining allowance is inferred. Frontend/browser integration is owned by the UI agent.
Verification used isolated app/server instances; the interactive server was not restarted or its in-memory state reset.
Restart the backend when ready to load the missing-column fix; restarting clears its in-memory goals and inputs.

## Deferred task: spending-allowance progress bar

Request: Today/Week, amount remaining, and a horizontal fill bar.
Investigation/proposal only was authorized; no new financial policy has been implemented.
Proposal: [backend/ALLOWANCE_PROGRESS_PROPOSAL.md](backend/ALLOWANCE_PROGRESS_PROPOSAL.md).

Recommendation for the deadline: retain **Estimated per day/week** with a neutral track.
Do not label the current `daily_eur` or `weekly_eur` values "remaining": neither has actual spending deducted.
Do not derive progress from daily divided by weekly allowance or use an arbitrary fill percentage.

Proposed future model: snapshot a dated confirmed plan and opening-funds checkpoint, then subtract eligible purchases
once from a defined day/week envelope. Protected bills must not be deducted twice. Unknown completeness makes the
remaining amount/fill unavailable. A historical replay must be visibly dated and separated from today's plan.
See the proposal for the exact formulas, additive fields, required choices and acceptance-test matrix.

## Issues and limitations the manager needs to know

| Issue | Consequence / next decision |
| --- | --- |
| Original records end in September 2026 | Cannot deduct them from a November/current plan or claim live spending progress |
| Existing plans have no start date or opening checkpoint | Cannot distinguish spending already included in accessible funds |
| No verified transaction completeness watermark | Last transaction date does not prove all earlier spending is present |
| No stable transaction ID in source data | A live incremental ledger needs identity/deduplication support |
| Some purchases may overlap protected essential bills | Need explicit scope confirmation or mapping before deducting purchases |
| Historical balances are not certified opening-midnight/current funds | Never silently populate opening funds from them |
| Reserve and goal-contribution amounts are preferences | Cannot infer them from historical averages or substitute zero |
| Goal/input changes can invalidate a tracked envelope | Requires explicit plan version/checkpoint policy; not silent recalculation |
| No confirmed category-to-future-plan mapping | Category reduction has null goal impact to avoid double-counting capacity |

Both profiles have one observed account, populated timestamps/balances and matching transaction-date/timestamp dates.
No duplicate account/timestamp pairs were found in the inspected profiles; that is not a stable-ID guarantee.
Both files cover 3-9 August 2026, a possible shared historical replay week.
A replay still needs reviewed scenario inputs/opening funds, an explicit replay cutoff, and an incomplete-source notice.
Source timestamps have no declared timezone; interpreting them as Helsinki time must be an explicit demo assumption.

## Decisions requested from manager

1. Confirm the deadline UI fallback: estimated amounts plus neutral track, with no "remaining" claim.
2. If a filled demo bar is necessary, approve/revise the dated-replay policy and explicit scenario inputs first.
3. Coordinate any new progress route/fields with the UI agent before authorizing implementation.

No existing contracts should change merely to make the bar look populated.

## Local work and operational notes

- `backend/ALLOWANCE_PROGRESS_PROPOSAL.md` and this handoff are maintained on `codex/data-backed-budget` for manager review.
- Current delivery is gated Verda support with additive Coach fields and mocked verification; no frontend changes or main merge.
- Latest full verification is 49 passing tests (19 Verda tests); the restaurant-demo delivery had 30 passing tests.
- Original datasets are available outside the backend worktree via `SBANK_DATA_DIR`; never commit them or raw records.
- On this Windows host, sandbox loopback setup blocked asyncio tests; the full suite passed outside the sandbox.
- The installed Starlette version emitted a TestClient/httpx deprecation warning; it did not fail tests.
- Backend Git operations and writes may require approval because the active chat workspace is the separate UI preview.
- Continue backend work on `codex/data-backed-budget`. Do not edit frontend files or merge without new authorization.

## Manager decisions / backend acknowledgements

- 2026-11-14: Awaiting manager review of the allowance-progress proposal. No approval recorded yet.

- 2026-11-14: Prioritize Coach restaurant-reduction demo; allowance-progress proposal remains unimplemented.

- 2026-11-14: User changed Verda limit to EUR 1.00; implement with mocks, commit/push, no automatic paid activation or merge.
