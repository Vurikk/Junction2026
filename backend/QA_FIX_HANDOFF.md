# Backend QA-01/02/03 fixes

Date: 2026-11-14 (Europe/Helsinki).
Branch: `codex/coach-backend-readiness`, retaining the prior readiness tests at `1039567`.
Backend implementation base: `0e43cbd`; reviewed findings: QA_COACH_HANDOFF.md at `fb574df`.
No frontend edits, API schema changes, merges, provider calls or deployment-ledger resets.

## Fixes

- **QA-01:** provider-disabled spending requests now pass through the existing canonical language/date resolver and Python tools.
  With the clock at 2026-11-14, restaurants `last month` requests October 2026. Missing October history returns
  unsupported_period_or_category with empty cards/rows, rather than silently using a partial historical month.
  Explicit periods, year rollover and Monday-based weeks use the same financial/date functions as the provider-enabled path.
- **QA-02:** dated reductions return Python cards in rule_based mode; Food asks groceries versus restaurants.
  Percentage-only follow-ups retain the validated category and period in a small process-local store.
  Unlike the earlier minimal proposal's no-context option, the authorized implementation includes actual disabled-mode continuity.
  Browser/customer isolation, request fingerprints, cached identical replies, expiry and capacity bounds are covered by tests.
  No raw question text, transaction rows or financial identifiers are stored in that context; only hashes, tool selections and aggregate responses.
- **QA-03:** a cached concurrency_limit receipt can be atomically reopened only with the original fingerprint, no provider-call
  record in its namespace (including zero-cost/reconciled records), and available rate-limit capacity.
  The row and fingerprint remain intact. There is no deletion/reset or billing change. Existing stuck busy receipts are eligible
  under the same proof-of-no-call check, without a migration. Once admitted, in-flight and completed deduplication remain unchanged.

The new free store never opens the deployment ledger or constructs a provider. It has 30-minute expiry, maximum 256 conversations
(32 per browser), and 2048 receipts. Capacity exhaustion fails with session_limit rather than evicting active identities.
Free context/receipts are lost on restart or expiry; users then need to restate category and period. This is not a persistent free chat store.
Paid receipts, billing uncertainty, reservations and the cumulative EUR 1 cap remain persistent and unchanged.

## API and UI notes

Existing keys, card shapes, mode values and reason codes are retained. Successful free calculations keep fallback_reason=disabled
or the relevant missing-configuration reason. Render returned cards independently of that reason, as already documented.
Privacy-blocked or unsupported spending requests must not reuse the legacy rows/text as if they answered the requested period.
Goals, confirmed inputs, previews, allowances, mortgages and current-balance handling are not changed.
The new backend allows an explicit same-ID retry after concurrency_limit; it does not retry automatically.
The final QA UI candidate previously removed its busy retry action. Re-enabling that action is a separate UI-owner decision.

## Regression coverage

`backend/test_coach_qa_regressions.py` adds 12 tests covering:

- Missing last-month and explicit-period data, partial history, valid months, calendar-year rollover and Monday-based weeks.
- Exact disabled reduction/follow-up fixture results: April 2024 restaurants 400/320/80 at 20%, then 400/360/40 at 10%.
- Food clarification, browser/customer isolation, unsafe wording, and no restoration of stale legacy rows.
- Identical replay, changed-body/conversation conflicts, no context rollback on replay, expiry, restart and capacity behavior.
- HTTP cookies, free follow-ups, read-only goal/assumption/budget state and unchanged goal-preview behavior.
- Busy rejection, restart, successful same-ID retry, concurrent duplicate rejection and completed-response replay.
- Refusal to reopen any busy receipt with a provider-call record and rate-limit rechecking without losing the busy receipt.

Disabled-mode tests actively fail if Ledger.transaction is called. Paid-path tests use httpx.MockTransport and disposable ledgers only.
Two existing disabled-mode assertions were updated: dated reductions now have a Python result; current balance uses its actual
legacy `unknown` classification and keeps the original non-spending answer.
The real-HTTP workflow now checks structured spending cards against their explicit full-period history and existing comparison
endpoint. It no longer expects the legacy latest-partial-month rows or a category answer with an unspecified period.
The `rows` field remains present; structured-card replies use an empty rows list as in the provider-enabled contract.

Commands use the existing Python environment with COACH_LLM_ENABLED=false and the existing SBANK_DATA_DIR:

```powershell
python -m unittest backend.test_coach_qa_regressions backend.test_coach_single_call backend.test_verda -q
python -m unittest discover -s backend -p 'test_*.py' -q
```

Targeted result: 44 tests passed. Final full-suite result: **98 tests passed** (including the 12 new QA regressions).
The existing free browser preview has not been restarted by these source changes; its Python process retains the prior backend code.
