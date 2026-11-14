# Backend agent -> manager handoff

Updated: 2026-11-14 (Europe/Helsinki)
Owner: backend agent
Working branch: `codex/data-backed-budget`
Status: delivered backend features; allowance-progress policy awaits manager review.

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
- UI agent is connecting balances, comparisons and suggestions. Treat those contracts as frozen pending coordination.
- No frontend files were edited by this backend agent. The existing six-input allowance formula is unchanged.

Contracts and original-data audit: [backend/DATA_COACH_HANDOFF.md](backend/DATA_COACH_HANDOFF.md).
API reference: [backend/API.md](backend/API.md).

## Current task: spending-allowance progress bar

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
- This documentation delivery does not merge into main or implement policy. Runtime code remains at the verified backend commit.
- No new runtime tests were run for documentation-only work; the 28-test result belongs to the delivered implementation.
- Original datasets are available outside the backend worktree via `SBANK_DATA_DIR`; never commit them or raw records.
- On this Windows host, sandbox loopback setup blocked asyncio tests; the full suite passed outside the sandbox.
- The installed Starlette version emitted a TestClient/httpx deprecation warning; it did not fail tests.
- Backend Git operations and writes may require approval because the active chat workspace is the separate UI preview.
- Continue backend work on `codex/data-backed-budget`. Do not edit frontend files or merge without new authorization.

## Manager decisions / backend acknowledgements

- 2026-11-14: Awaiting manager review of the allowance-progress proposal. No approval recorded yet.
