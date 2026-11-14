# Single-call Coach handoff

Date: 2026-11-14. Branch: `codex/coach-single-call`.
Published to `origin/codex/coach-single-call`; not merged.

Base: `c3da04b6bb8ce453ce9d6c5f3f899adc77e8190c`.
Implementation and focused tests: `2bbb09f11e02e01110de79411bf4c3dbba3d6716`.
This handoff is a separate documentation commit after that implementation commit.

Separate managed worktree: `C:/Users/vanal/.codex/worktrees/coach-single-call/Junction2026`.
No branch switch or file edits were made in the existing backend agent's worktree.

## Behavior

Each new successful conversational calculation uses exactly one Verda call to select an approved read-only tool.
The existing `selection` validation runs before `run_tool`. Python calculates the independent card, then renders
`facts_for(card)` with `summary` first and every remaining fact in its existing order. Coverage and hypothetical
caveats are retained. No facts or cards are sent to a second provider call. No new financial calculations were added.

`mode='llm'` means an LLM selected a validated tool and its Python calculation succeeded.
**The explanation is Python-rendered; this is not unconstrained LLM-generated financial advice.**
There is no model-generated numerical prose and no model-selected fact ordering.

The response fields, card types/data, conversation context, customer/browser isolation, durable request claims,
cached responses, deadlines, fallbacks and goal previews retain their existing contracts.
Provider or validation failures return `mode='rule_based'` with the existing safe reason codes.
Goal previews remain local, read-only and confirmation-based. Cache-write failures still report `ledger_unavailable`.

The persistent EUR 1 cap, approval gates, transport, ledger schema, reservation bounds and reconciliation are unchanged.
The sole provider call retains the `:1` key; there is no `:2` call or cost reservation.
At the existing reviewed bounds/rates, one worst-case reservation is EUR 0.1402266112.
Unknown usage/errors retain that full reservation; removing the second call does not refund earlier spending.
The focused near-cap test starts at EUR 0.80, succeeds with one un-reconciled call at EUR 0.9402266112,
then refuses a new call after a service/ledger restart.

No paid mode was enabled, no live Verda request was made, and no real approval or ledger was created or changed.
Every provider request in the tests used `httpx.MockTransport`, dummy keys and temporary SQLite ledgers.

## Ownership and integration

Only these files changed:

- `backend/coach_llm.py`
- `backend/test_coach_single_call.py`
- `backend/SINGLE_CALL_HANDOFF.md`

`coach_tools.py` and all its interfaces remain unchanged; no interface coordination was necessary.
The existing `rendered_explanation` helper is left intact for its owner but is no longer imported by orchestration.
Natural-language/privacy work, shared tests, frontend, ledger, transport and shared status files were not edited.

Integrate the implementation commit above and this handoff commit after review; this branch has not been merged.
When combining with the other backend agent's work, retain its routing/validation/privacy changes while removing
the explanation provider call. Keep `facts_for` returning `summary` and all required caveats. Additional facts are
automatically retained by this renderer. No adapter or signature change is required.

Durable cached responses are intentionally not invalidated: old request IDs replay their saved responses without
another paid call. Old in-progress claims retain their existing fallback behavior. Use a new request ID for a new turn.
Do not reset the real ledger or approval state during integration.

The integration owner should update two-call wording in `VERDA_HANDOFF.md`.
Its fact-ordering description and second-call failure discussion are superseded by this handoff.
The smoke script's comment about preventing two paid messages describes duplicate invocations and remains valid.
Those files were outside this agent's ownership and remain untouched. Do not execute the live smoke during integration.

## Verification

Commands were run from the separate worktree with the already-installed Python 3.12.15 interpreter:
`C:/Users/vanal/.codex/worktrees/a308/Junction2026/.venv/Scripts/python.exe`.
No packages or files were changed in that interpreter's worktree.

```powershell
& C:/Users/vanal/.codex/worktrees/a308/Junction2026/.venv/Scripts/python.exe -m unittest backend.test_coach_single_call -v
```

**13 tests passed.** Covers all three approved calculations, exact card amounts and factual text, required caveats,
insufficient history, exactly one provider call/reservation, near-cap persistent accounting, context after restart,
context expiry, browser/customer isolation, explicit/derived-ID cache replay, conflicts, in-flight duplicates,
concurrency, provider/timeouts/validation/calculation failures, disabled configuration and HTTP goal-preview compatibility.
The reduction fixture yields EUR 400.00 baseline, EUR 320.00 hypothetical spending and EUR 80.00 potential reduction;
the 10% follow-up yields EUR 360.00 and EUR 40.00. Transfers and refunds are excluded by the existing Python tools.

```powershell
& C:/Users/vanal/.codex/worktrees/a308/Junction2026/.venv/Scripts/python.exe -m unittest backend.test_coach backend.test_data_coach backend.test_financial backend.test_verda -v
```

**43 tests ran: 32 passed, 10 failed, 1 errored.** All 24 local Coach/data-coach/financial tests passed.
All five ledger tests passed. The remaining failures/error are the unchanged two-call test assumptions listed below.
The original dataset-backed `backend.test_api` and `backend.test_integration` modules were not run for this focused change.
No claim is made that the entire shared suite passes or that real provider behavior has been verified.

The first sandboxed run stalled in Windows asyncio's internal socket-pair creation before asynchronous test execution.
It also exposed an incorrect mock patch target in the new preview test, which was corrected before the passing run.
The stalled processes were stopped and tests reran outside the sandbox with provider traffic still mocked.
An existing Starlette/httpx TestClient deprecation warning was emitted; no dependency changes were made.
`git diff --check` passed, and both changed Python files have all lines shorter than 150 characters.

## Shared tests requiring integration updates

Integration update, 2026-11-14: the items below describe the original branch's failures, not current expectations.
The combined full backend discovery suite now passes all **83 tests**, with paid mode off and mocked provider calls.
Shared fixtures now queue only routing responses; single-call counts and reservations are asserted. The obsolete second-call
timeout test now verifies first-call timeout/no retry. Untrusted model prose is rejected before calculation, and the subsequent
valid request verifies deterministic factual output. Context-expiry and missing-data tests assert zero additional provider
calls/reservations after the local preflight integration. All isolation, non-mutation and accounting checks are retained.

All entries below are in the unchanged `backend/test_verda.py` at the base revision.
Remove the queued `explained()` response from the shared `valid()` helper and other successful mock sequences.
Otherwise that stale response is incorrectly consumed as the next turn's tool selection.

| Test (class prefix abbreviated) | Observed result and required update |
| --- | --- |
| `CoachLLMTests.test_selection_followup_and_minimal_provider_payload` | Error: empty follow-up cards from stale queue. Remove explanation responses; expect two calls for two turns. |
| `CoachLLMTests.test_category_and_comparison_tools` | Failure on the second tool's mode due to stale queue. Queue only tool selections. |
| `CoachLLMTests.test_session_customer_isolation_and_no_cross_customer_followup` | Failure: stale explanation gives `invalid_model_output`. Remove it so the intended context validation executes. |
| `CoachLLMTests.test_privacy_blocking_and_context_expiry` | Same stale-queue failure; keep the context-expiry assertions. |
| `CoachLLMTests.test_missing_usage_restart_reserves_budget_and_wrong_model_freezes` | Wrong-model response is preceded by stale explanation. Remove it; retain freeze/restart checks. |
| `CoachLLMTests.test_completed_duplicates_restart_and_conflict` | Failure: one call, not two. Expect one call before and after duplicate/conflict. |
| `CoachLLMTests.test_provider_errors_retain_reservation_no_retries` | Failure: EUR 0.2804532224, not greater than EUR 0.42. Count two total uncertain calls across the two turns. |
| `CoachLLMTests.test_second_call_timeout_preserves_card_and_reservation` | Obsolete: success is now `llm`. Replace with first-call timeout or assert a second call never occurs. |
| `CoachLLMTests.test_untrusted_explanation_keeps_python_card` | Obsolete: no explanation response is requested, so success has no fallback reason. Assert deterministic Python text instead. |
| `CoachLLMTests.test_total_deadline_duplicate_inflight_and_global_concurrency` | Failure: observed one call, old range was two/three. Remove explanation queue; allow one/two depending on deadline before transport. |
| `CoachRouteTests.test_enabled_http_route_bootstrap_followup_and_nonmutation` | Failure: one call after first turn/replay, not two. Remove explanation responses; expect two after follow-up. |

Keep these tests' isolation, safety, mutation and accounting assertions when updating them; only their two-call
fixtures and expectations need adapting. Shared tests were deliberately not rewritten while the other agent is working.
