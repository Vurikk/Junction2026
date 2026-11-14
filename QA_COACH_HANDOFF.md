# Independent Coach integration QA

Date: 14 November 2026 (Europe/Helsinki). Owner: independent QA.
Latest disposition: see the appended `f550b26` fix verification; all three targeted backend gates now pass on that hash.
Original recommendation at `0e43cbd`: **NO-GO for claiming the full acceptance matrix passes.**
Disabled-mode date handling and language fallback need backend disposition. Concurrency rejection remains cached.
The final UI candidate passes the bounded mocked checks below; this is not certification of a deployed paid application.

## Versions and coordination

- Backend/integration: `codex/verda-integration`, `0e43cbd74cbae8a5698dd4499abcbb5b093e4b61`.
- Final UI: `codex/verda-coach-ui`, `7a958ebcc3e45a4d670fa83a15fc1dc451e5f0d6`.
  Implementation: `dfe417450244d84d49c0ec6f6e34a41d616b89ba`.
- QA branch: `codex/qa-coach-integration`, based on integration `0e43cbd`; only this new file is owned/changed.
- Manager confirmed branches, ownership and that no pre-existing frontend URL was certified safe.
  UI owner supplied the isolated final-candidate fixture URL and final hash. No other checkout was switched.
- Read repository AGENTS.md, backend/API.md, backend/VERDA_HANDOFF.md,
  docs/VERDA_INTEGRATION_REVIEW.md, frontend/qa/HANDOFF.md, frontend/qa/VERDA_UI_HANDOFF.md,
  manager INTEGRATION_HANDOFF.md and final frontend/UI_COACH_HANDOFF.md.
  Incidental website links in the task were interpreted as the named repository documents.

## Safety and execution setup

No active paid backend, live Verda test, approval setup, actual provider key or canonical ledger was used.
Python processes explicitly used `COACH_LLM_ENABLED=false` and `PYTHONDONTWRITEBYTECODE=1`.
Existing mocked tests inject fake-key providers with httpx.MockTransport and disposable temporary test ledgers.
Those test ledgers are not the designated deployment ledger. No datasets/configuration/existing tests were changed.

- Backend checks ran in the QA checkout with the already installed root `.venv/Scripts/python.exe`.
- Actual base UI browser: `http://127.0.0.1:5189`, bundled from integration source into memory using installed esbuild.
  Its only API proxy was the QA-owned `127.0.0.1:8029` server, running integration FastAPI with paid mode disabled.
  `backend.main.load_customers` was patched in memory to return `test_data_coach.fixture()` for the two profile IDs.
  These are synthetic fixture histories, not the original customer datasets. No source files were written for the servers.
- Final candidate browser: `http://127.0.0.1:5186/qa/verda-popup.html`, supplied by UI owner.
  Inspected fixture source: imports actual Coach/Dialog and uses an in-memory API function, no fetch/provider calls.
  Values are fixed fixtures; in particular a 10% follow-up still returns its fixed 20% card.
  This is a harness limitation, not a reported calculation bug.
- Existing port 5178 and the designated paid endpoint were not used.
- Rendering checks initially hit sandbox esbuild directory-access errors, then passed with approved read-only execution.
  No dependency installation, lockfile change or Git safety configuration change was made.

## Observed bugs

### QA-01 — P1: disabled mode substitutes stale history for “last month”

Affected: backend `0e43cbd`; final UI `7a958eb` has no backend changes, so it does not resolve this.
Observed both through direct service execution and the actual base app browser against the isolated disabled backend.

Reproduce:

1. Run the disabled service against `backend.test_data_coach.fixture()` (shared executable probe below).
2. Ask `How much did I spend on restaurants last month?` on 14 November 2026.
3. Inspect the returned text/cards, or submit the same question in the isolated actual app.

Expected: resolve October 2026; report unavailable records or request a dated historical period.
Never replace the requested period with the latest available month without explaining the mismatch.

Actual: `fallback_reason=disabled`, `kind=categories`, no cards, text:
`Recorded categories for 2024-05 (partial month). Transfers and refunds excluded.`
It continues that no included payments exist for the requested category in that month.
The displayed source month is visible, but the app never explains that it did not answer the requested calendar month.
This is stale period substitution, not an invented numeric result.

Contrast independently observed with an injected mock provider: the same question returns
`unsupported_period_or_category`, asks for another recorded month/week, and makes zero provider calls.
Source mechanism: `CoachLLM.respond` returns the legacy baseline before canonical date validation when provider is absent.

### QA-02 — P2: disabled fallback loses category clarification and reduction continuity

Affected: backend `0e43cbd`; unchanged by final UI candidate. Same disabled fixture setup as QA-01.

Reproduce these turns using one conversation ID:

1. `What if I reduce restaurants in April 2024 by 20%?`
2. `What about 10% instead?`
3. Separately ask `Food` without a previous validated category selection.

Expected: a dated reduction or an explicit unavailable-feature explanation; follow-up retains intended category/date
when supported. `Food` asks whether groceries or restaurants are intended.

Actual: first turn says `Enter a goal name, amount and priority below to preview it. Nothing is saved.`
Follow-up and `Food` both say `Ask about categories, averages, allowances, goals, or a what-if goal.`
All return `disabled`, no cards. The first turn offers unrelated goal guidance; no goal form was actually opened or saved.
The `Food` generic-help result was also observed in the actual browser. Reduction/10% failure was observed at service level.

With an injected mock provider, the exact follow-up `What about 10% instead?` independently returned restaurants,
1–30 April 2024, baseline EUR 400.00, hypothetical EUR 360.00, reduction EUR 40.00.
Fresh-conversation `Food` returned `Do you mean groceries or restaurants?` with zero provider calls.
Therefore this is specifically missing disabled-path behavior, not evidence that the paid routing path fails.

### QA-03 — P2: concurrency rejection is permanently replayed for the same request

Affected backend: `0e43cbd`, unchanged by UI `7a958eb`.
Integration UI `0e43cbd` additionally offers a misleading Retry answer action.
Final UI removes that action for `concurrency_limit` and explains finality; backend recovery remains unresolved.

Reproduce with the mocked test harness (executable probe below):

1. Hold request A inside its mocked provider using an asyncio Event.
2. Send request B from another browser/conversation with a fixed request UUID.
3. B returns `concurrency_limit`; release A and wait for A to finish successfully.
4. Retry B with exactly its original body/conversation/request UUID.

Expected: a transient busy rejection should permit an identical retry after capacity becomes available,
without creating duplicate work or requiring a new identity to bypass deduplication.

Actual: retry returns the identical cached `concurrency_limit` response; provider-call count remains 1.
This demonstrates stuck recovery, not duplicate billing. Do not work around it with automatic new UUIDs.
`respond` claims B before checking the global lock, then `ledger.finish` saves the rejection;
`ledger.claim` returns that saved response on retry. Manager has been informed; backend disposition is pending.

## Reproduction commands (no implementation/test edits)

From the QA checkout in PowerShell, use the existing installed Python interpreter:

```powershell
$env:COACH_LLM_ENABLED = 'false'
$env:PYTHONDONTWRITEBYTECODE = '1'
$qaPython = 'C:/!Study/Ohjelmointi/JunctionGit2026/Junction2026/.venv/Scripts/python.exe'
@'
import asyncio, json
from uuid import uuid4
from backend.coach_llm import CoachLLM
from backend.coach import answer
from backend.financial import history, plan
from backend.test_data_coach import fixture
from backend.test_coach_single_call import SingleCallTests, envelope

async def main():
    customer = fixture()
    service = CoachLLM()
    conversation = str(uuid4())
    questions = [
        'How much did I spend on restaurants last month?',
        'What if I reduce restaurants in April 2024 by 20%?',
        'What about 10% instead?',
        'Food',
    ]
    for question in questions:
        baseline = answer(question, plan({}, []), [], history(customer, 'month'))
        result = await service.respond(customer, question, conversation, str(uuid4()), 'qa', baseline)
        print(json.dumps({'question': question, 'reason': result['fallback_reason'],
                          'text': result['text'], 'cards': result['cards']}))
    test = SingleCallTests()
    await test.asyncSetUp()  # MockTransport, fake key, temporary test ledger only.
    try:
        test.queue.append(envelope())
        test.release = asyncio.Event()
        first = asyncio.create_task(test.ask())
        await test.started.wait()
        request_id, conversation = str(uuid4()), str(uuid4())
        args = dict(request_id=request_id, conversation=conversation, session='second-browser')
        blocked = await test.ask(**args)
        test.release.set()
        await first
        retried = await test.ask(**args)
        print(json.dumps({'initial': blocked['fallback_reason'], 'retry': retried['fallback_reason'],
                          'identical': blocked == retried, 'mock_provider_calls': len(test.requests)}))
    finally:
        await test.service.close()
        test.tmp.cleanup()
asyncio.run(main())
'@ | & $qaPython -
```

Observed concurrency output: initial/retry both `concurrency_limit`, identical `true`, mock_provider_calls `1`.

## Independently executed checks

Backend command at `0e43cbd`, with the disabled environment above:

```powershell
& $qaPython -m unittest backend.test_coach_language backend.test_coach_routing `
  backend.test_coach_single_call backend.test_verda -v
```

**53 tests passed.** These cover synthetic/mock execution, not live Verda.
Tests include exact Python reduction, language/date grounding, provider error/timeout/budget fallbacks,
duplicate/in-flight/restart handling, cookie/bootstrap API contract, isolation, privacy and reservation controls.
Additional independent probes found QA-01/02/03 despite the suite passing.

Independently ran existing frontend checks on both integration and final UI source:

```text
node frontend/qa/check-coach-session.mjs
node frontend/qa/check-coach-cards.cjs
node frontend/qa/check-home.cjs
```

All passed on both versions. Installed root dependencies were reused via NODE_PATH where required.
No fresh Vite production build was run by QA; the UI owner's build pass is separate evidence.

| Acceptance area | Actual independent observation | Scope/limit |
| --- | --- | --- |
| Existing app layout/customer switching | Base Home/chart/popup rendered; switching profile cleared old chat | Actual React app, disabled synthetic backend |
| Close/reopen and Escape | Messages survived reopen; Escape closed and returned focus to opener | Base app and candidate fixture |
| Mobile layout | CSS width 390, height 740; candidate width 360, height 450; no horizontal overflow | Emulated viewport, not physical keyboard |
| Session bootstrap | Log showed one hidden bootstrap then original question once | Candidate mock browser; cookie behavior covered in backend API tests |
| Conversation continuity | Follow-up retained conversation ID with a new request UUID | Candidate mock browser |
| Retry identity | Network failure then explicit retry produced identical body/UUID and one user bubble | Candidate mock browser |
| Exact 10% follow-up | April restaurants 400/360/40 and original dated period preserved | Independent backend mock probe; fixture browser amounts deliberately fixed |
| Food ambiguity | Fresh mock-provider service clarified groceries/restaurants without a call | Disabled-mode failure QA-02 |
| Last month | Mock-provider service refused stale data without a call | Disabled-mode failure QA-01 |
| Result amounts/source dates | 95.04/76.03/19.01 and July 1–31 visible; Python values verified separately | Browser fixture display plus backend calculations, not live smoke |
| Top-five/remainder and null/zero | Existing rendering and backend aggregation assertions passed | Static/synthetic checks, not fresh browser ranking walkthrough |
| Provider failure | Rule-based notice and dated card remained visible after network retry | Candidate browser provider_error fixture |
| Timeouts/budget/malformed provider | Mocked backend tests passed; session notice checks passed | Not individually exercised in browser |
| Missing data | Candidate displayed no matching period plus unavailable category/period notice | Browser fixture, not a real missing-data query |
| Duplicate submissions | Pending composer/actions disabled; backend duplicate tests added no calls | Browser delayed fixture and mocked backend |
| Late customer response | Switched customer, resolved abort-ignoring response; old answer absent | Candidate browser; next customer got a new bootstrap/conversation |
| Goal mutation | Reduction did not open goal form; fixture saved-goals count remained zero | Actual goal confirmation/save not independently exercised in browser |
| Provider privacy | Canonical payload assertions and sensitive-paste rejection passed | Mock capture: no raw prose/customer IDs/browser IDs/transaction records in model body |

Privacy qualification: provider authentication necessarily uses a key in its transport authorization header.
The verified privacy boundary concerns model message/tool payloads, not a claim that authentication needs no key.
No actual secret was read, printed or tested. Mock bodies and source allowlists provide bounded evidence,
not an exhaustive proof for every possible user string or future provider behavior.

## Untested / separate recorded evidence

- No fresh live provider execution. User-recorded smoke at `0e43cbd`: CUST04457, restaurants, July 2026,
  20% reduction, baseline EUR 95.04, hypothetical EUR 76.03, reduction EUR 19.01. Not repeated by QA.
- No browser-to-paid-backend cookie exchange, HTTPS/Secure-cookie deployment, cross-PC proxy or live cookie expiry.
- No full original-dataset suite rerun. Prior 83-test integration pass belongs to earlier reported evidence.
- Final candidate browser coverage uses the popup harness; the full app browser run used base `0e43cbd`.
  Diff inspection confirms main.jsx unchanged in candidate, but that is not a combined end-to-end run.
- No physical mobile keyboard, screen-reader audit, exhaustive Tab/Shift+Tab trap, all popup entry variants,
  or independent scroll-restoration verification.
- No independent real goal save, preview edit/discard lifecycle, post-save analysis failure, full planning-form
  preservation or configured chart target-line browser walkthrough in this pass.
- No backend fix was attempted; no merge, deployment or ledger reset is included.

Manager received the reproduced findings and bounded browser evidence. Keep the UI candidate available for mock demos,
but do not describe disabled fallback as having the same date/language behavior as the validated mock-provider path.

## Follow-up: independent runtime-fix verification at f550b26

Exact backend: `origin/codex/coach-backend-readiness`, `f550b266d38c2a2f455650f34fba81d6e8406c38`.
The earlier readiness commit `1039567` contained tests/documentation only; it was not treated as a fix.
Original findings and evidence above are preserved and apply to `0e43cbd`.

**QA-01, QA-02 and QA-03: PASS / fixed for the tested backend hash.**
Recommendation: **conditional GO for a bounded paid-disabled/mock demo**, subject to a smoke check of the actual
final UI/backend pairing. This does not claim the full original acceptance matrix or live deployment is verified.

### Isolation and commands

Reviewed the runtime diff, new local state implementation, browser-contract tests and QA regression tests.
Exported exact commit bytes with `git archive --format=zip f550b266d38c2a2f455650f34fba81d6e8406c38`
into a disposable temporary source directory using Python zipfile. No other agent checkout was changed,
and no runtime files were copied into or committed on the QA branch.
The same installed interpreter was used with paid mode disabled and bytecode writes disabled.

```powershell
$env:COACH_LLM_ENABLED = 'false'
$env:PYTHONDONTWRITEBYTECODE = '1'
# Run from the exported f550b26 source directory with the previously defined $qaPython.
& $qaPython -m unittest backend.test_coach_language backend.test_coach_routing `
  backend.test_coach_single_call backend.test_verda backend.test_coach_browser_contract `
  backend.test_coach_qa_regressions -v
```

**68 tests passed**, 5.110 seconds reported by unittest. A Starlette/httpx deprecation warning remains;
it did not fail any check. No live provider, canonical ledger, real key or original dataset was accessed.

### Additional independent probes, beyond running the author's tests

Executed inline Python from the exported source, importing the same fixture and mocked harness used in the original reproduction.
For local checks, patched `backend.coach_tools.today_local` to `date(2026, 11, 14)` and patched
`Ledger.transaction` to raise `AssertionError('paid ledger accessed')` on any access.
Constructed a fresh `CoachLLM(unavailable_reason=reason)` and conversation for each of:
`disabled`, `missing_configuration`, `review_required`, `pricing_review_expired`, `ledger_unavailable`.
These inject service-unavailability reasons; they do not claim to test every environment configuration parser.

For **each of those five reasons**, actual results were:

1. `How much did I spend on restaurants last month?` returned `unsupported_period_or_category`, empty cards/rows.
   No substitution to the fixture's latest May 2024 records.
2. `Food` returned exactly `Do you mean groceries or restaurants?`.
3. `What if I reduce restaurants in April 2024 by 20%?`, then `What about 10% instead?`, returned restaurants,
   `source_period={start:2024-04-01,end:2024-04-30}`, baseline 400, hypothetical 360, potential reduction 40.
4. No paid-ledger guard fired. Local results remain rule-based; provider setup is not needed for these calculations.

Concurrency probe independently repeated the original held-request reproduction, with two queued mock envelopes:

1. Hold A in MockTransport using an Event; B with a fixed request ID returns `concurrency_limit`.
2. Release/await A; reset the Event; retry B with its original request/conversation/session.
3. While B is held, identical B returns `request_in_progress`; a changed question with B's ID returns `request_conflict`.
4. Release B: it succeeds with `mode=llm` from mocked tool selection.
5. Completed B replay is identical. Total mocked provider requests are exactly **2**, one for A and one for B.

Observed summary:

```json
{"busy":"concurrency_limit","recovered":"llm","inflight":"request_in_progress",
 "conflict":"request_conflict","total_mock_calls":2,"completed_replay":"identical"}
```

The new regression suite additionally passed restart readmission, no readmission when any call record exists,
rate-limit rechecking, local context expiry/bounds/isolation, request conflict and nonmutation checks.
Reviewed browser-contract tests use FastAPI TestClient with HTTPS URL semantics and mocked transport:
cookie attributes/bootstrap, cookie-loss isolation, and failure replay after restart all passed.
These are HTTP-boundary tests, not a new browser-to-deployed-backend run.

### Remaining limits and coordination

- The `7a958eb` UI removed the concurrency retry button and describes the rejection as final.
  The fixed backend now allows safe same-ID readmission, so that wording/recovery affordance is stale for the new pairing.
  This does not cause duplicate calls; backend recovery is verified through direct requests only.
  Manager informed. No frontend changes made by QA.
- UI owner separately reported full-app paid-disabled checks at `7a958eb`: mobile layouts, popup entries,
  both profiles, charts, preview/discard and one explicit goal save. These remain owner-reported evidence,
  not independent QA results. The owner then announced additional weekly-chart/Home-goal changes;
  their incoming commit is outside this backend verification.
- No new browser work duplicated the UI owner's checks. No fresh production build, full original-data suite,
  physical keyboard, live provider or combined final-candidate deployment check was performed here.
- No merge or paid activation performed. Manager received exact hash, PASS evidence and conditional recommendation.

## Follow-up: Safe to spend backend verification at 86d657f

Exact local backend commit: `86d657f4bff79a7d281fe1539cf2d426a2bb9b86`,
branch `codex/data-backed-spending-estimate`, based on verified `f550b26`.
Verdict: **bounded backend PASS; conditional GO pending the actual UI pairing checks.**
This is a read-only cash-only estimate, not proof of current bank liquidity or complete transaction coverage.
Backend branch publication status is separate from this local commit verification.

### Early findings and disposition

- Contract review flagged prorated historical rent as insufficient protection for a bill due tomorrow.
  Manager/backend accepted the correction: current mode always requires confirmed TOTAL upcoming bills,
  alongside current accessible funds and reserve. Additional-bills zero cannot replace the total.
  Historical rates remain dated reference/scenario evidence, not upcoming payment dates.
- On the uncommitted draft, independently reproduced `TypeError: fromisoformat: argument must be str`
  for historical mode with empty transaction coverage. Reproduction: create `fixture()`, replace its
  `_transactions` with `.iloc[0:0].copy()`, then request historical estimate.
  Fixed and verified in `86d657f`: HTTP 200, insufficient_data, reference_date/daily allowance null.
  Constructing `fixture(records=[])` fails in the fixture constructor itself; that was not counted as an application bug.

### Exact execution and results

Exported `86d657f` through `git archive` into a separate temporary directory; did not switch or edit another checkout.
Read backend/SPENDING_ESTIMATE_HANDOFF.md, route input validation, estimate implementation and tests.
Used the existing interpreter with `COACH_LLM_ENABLED=false`, `PYTHONDONTWRITEBYTECODE=1`, and no SBANK_DATA_DIR.

```powershell
& $qaPython -m unittest backend.test_spending_estimate backend.test_financial backend.test_data_coach `
  backend.test_coach_language backend.test_coach_routing backend.test_coach_single_call backend.test_verda `
  backend.test_coach_browser_contract backend.test_coach_qa_regressions -q
```

Result: **94 tests run, 93 passed, 1 skipped**, no failures (5.715 seconds).
Skipped: original-dataset estimate check requiring SBANK_DATA_DIR. No original-dataset verification claimed.
Prior Coach fixes remain covered and passing. Only existing deprecation/debug timing notices were emitted.

Additional independent FastAPI TestClient probes used two synthetic profiles: ordinary fixture CUST04457,
and CUST00001 with its transaction frame emptied. Patched `Ledger.transaction` to raise on any paid-ledger access.
Set a nonzero confirmed plan only on the first profile: funds 1234, income 99, bills 200, reserve 300,
everyday 50, contribution 150, horizon 45, repeat true, weekly/monthly chart targets 77/333.
Created three isolated test goals in flexible/critical/important insertion order, each EUR 200.
These mutations were in disposable TestClient memory only, not an existing backend or dataset.

Observed assertions passed:

| Gate | Independent observation |
| --- | --- |
| Default current unknown | Both profiles return null daily allowance despite first profile's recorded history |
| Due-rent protection | Funds 1000, reserve 100, TOTAL bills 700, 7 days gives weekly 199.99 (daily 28.57 in suite) |
| No unknown-to-zero | Omitting each of funds/reserve/total bills returns null and its missing field, even with additional bills 0 |
| Input safety | Negative funds/reserve/bills/everyday/contribution each return 422 for both profiles |
| Future income | Supplying confirmed_income_eur to the new endpoint returns 422; this cash-only contract does not accept it |
| Empty historical coverage | HTTP 200 with null reference_date/daily allowance; draft exception no longer occurs |
| Goal protection/priority | Funds 1000, reserve 200, bills 400, everyday 100, contribution 300 allocates 200/100/0 by priority |
| No repeated starting cash | All estimate goal completion_periods remain null; daily allowance 14.28 in that goal case |
| Manual-plan preservation | Full assumptions/goals/budget JSON equal before/after estimate GET/POST for both profiles |
| Customer independence | First manual_plan_available true; second false; second profile's blank plan remains unchanged |
| No paid ledger | The access guard never fired during these HTTP probes |

The initial independent probe incorrectly expected HTTP 200 for goal creation, whose existing contract returns 201.
Correcting that QA assertion yielded the results above; no application change was needed.

The existing estimate tests additionally passed calendar-day scaling (not a fixed 30-day divisor), transfer exclusion,
asynchronous/missing historical balance handling, balance-reference dating, explicit zero, shortfall and no-repeat checks.
Source review confirms income is response evidence only, no mortgage application is read as a debt obligation,
and all arithmetic uses Python. Mortgage application data are not an independent debt-verification source.

### Remaining pairing conditions

- UI must visibly distinguish historical scenarios/current user-provided estimates, show dates and uncertainty,
  and disclose the default no-earmark policy beside the result; existing critical goals are not automatically funded.
- UI must prefer a complete confirmed manual budget without silently overwriting partial or hidden plan fields.
- Customer switching and late responses must not display another profile's estimate.
- These new UI behaviors and actual paired browser execution belong to the UI owner's independent workstream;
  QA has not claimed a browser pass for them here. Original customer datasets and physical keyboard also remain untested by QA.
- No merge, provider call, paid activation, canonical-ledger access, or implementation/test/configuration edit by QA.

## Follow-up: paired Safe to spend browser spot-check

UI candidate `88e05cc4715c46b16d3e5153df33938a2574ea41`, backend `86d657f4bff79a7d281fe1539cf2d426a2bb9b86`.
UI owner supplied its isolated paid-disabled pairing: frontend `http://127.0.0.1:5189` to backend `127.0.0.1:8028`.
This port 5189 is the owner's new pairing, not the earlier QA memory-only server, which was stopped previously.
No Coach/provider requests were submitted during this estimate walkthrough.

Independent browser observations:

1. Loaded CUST04457 Home: historical Balance existed, but Safe to spend remained Not available.
   Visible copy said cash-only estimate, future income excluded, dated seven-day period,
   and `No money set aside for goals in this estimate.`
2. Complete the estimate showed the three blank fields. Historical bill references carried source dates
   and explicitly said they are not a due-date schedule; the full amount actually due must be confirmed.
3. Entered funds 1000 and total bills 700 with reserve blank; submitted. Allowance stayed Not available.
4. Entered reserve 100 and submitted: daily EUR 28.57. Week toggle showed EUR 199.99.
5. Changed to CUST00001: old estimate disappeared during loading; loaded result was Not available with no-earmark copy.
6. Returned to CUST04457: estimate again Not available. No sample preview amount persisted across profile remount.
   No goal or confirmed-plan save was performed; the tab was left with a blank estimate.

Independently ran `check-safe-spend.cjs` and `check-home.cjs`: both passed.
SafeToSpend source hash matched the named commit (`beeb2814a8fb26025df6db075178dac02c86bf8a`).
Static checks cover unknown/zero distinction, manual-plan precedence and absence of invented usage progress.

**Bounded paid-disabled demo GO for this exact pair**, combining the verified backend gates and this browser spot-check.
Not an exhaustive UI certification: delayed-response races, physical keyboard, new mobile dimensions,
historical-mode browser flow and live manual-plan precedence were not independently repeated in this follow-up.
The UI owner's broader tests remain separately attributed. No new critical issue was observed in this bounded pass.

## Follow-up: automatic historical goal-driven budget at c349d65

Backend: `c349d6555aa192aaede3db11b0ecbd60ef226b95`, `codex/data-backed-spending-estimate`.
**Independent bounded backend PASS.** Conditional demo GO requires the new UI to identify historical EXTRA headroom
above usual spending, app policies, source dates and uncertainty. This is not current affordability or a funded reserve.
This automatic default supersedes the earlier manual-default product direction; the cash-only endpoint remains intact.
No new automatic-UI browser pass is claimed by this QA section.

### Policy and pre-commit review

Manager approved a retrospective three-month policy: protect all included recorded spending, then contribute up to
10% of average income toward a hypothetical reserve; allocate 50% of remaining surplus to goal targets by priority.
Only actual capped allocations are deducted; unused goal budget returns to extra headroom.
No goals produces needs_goal; absence of required evidence produces null, not a forced numeric demonstration.

QA flagged the initial draft's silent exclusion of unexpected negative transaction types. Final source now blocks
numeric results with `unclassified_debit_evidence:YYYY-MM`; only documented transfer/investment_deposit/refund
exclusions remain. Unknown categories on ordinary purchases remain protected spending.
QA also flagged an author's two-profile test using duplicate IDs; final independent HTTP checks used distinct IDs
and materially different histories. Neither issue was fixed by QA; application ownership stayed with Agent2.

Reviewed backend/AUTOMATIC_BUDGET_HANDOFF.md and exact implementation from an immutable git archive of c349d65.
Same installed Python interpreter; COACH_LLM_ENABLED=false and PYTHONDONTWRITEBYTECODE=1 throughout.

```powershell
# In exported c349d65 source, initially without SBANK_DATA_DIR:
& $qaPython -m unittest backend.test_automatic_demo_budget backend.test_spending_estimate `
  backend.test_financial backend.test_data_coach -q
# Then with SBANK_DATA_DIR pointing read-only at the existing original local backend/Data directory:
& $qaPython -m unittest backend.test_automatic_demo_budget.RealAutomaticTests `
  backend.test_spending_estimate.RealDemoEstimateTests -q
```

First command: 34 tests run, 32 passed and 2 dataset-dependent tests skipped (0.996 seconds).
Second command: both skipped tests independently rerun with supplied data and passed (11.754 seconds).
The real-profile automatic check independently recalculates monthly income/spending from rows inside the returned
period for both supplied demo profiles; it checks three-month eligibility and no-goal null results.
No raw records were printed or copied into this report, and no datasets were modified.
No broad Coach suite rerun: delta from the previously verified estimate backend adds only a new module/GET route/tests/docs.
Existing Coach runtime is unchanged in this commit; the separate incoming demo-prompts branch is not included here.

### Independent adversarial probes

Constructed a fresh synthetic fixture, without using the author's automatic-budget customer factory:
January–March 2024 each have salary 1000, housing payment 300, grocery purchase 200 and uncertain-category purchase 100.
Large positive transfers/refunds, investment deposits and very large account balances were also present.
An April 1 boundary record brackets three complete months (91 days). None of those movement/balance amounts inflated headroom.
Patched Ledger.transaction to raise on any paid-ledger access; guard never fired.

| Case | Independently observed result |
| --- | --- |
| Large critical goal | Income 1000, protected spending 600, reserve 100, actual goal allocation 150, extra 150/month, 4.94/day, 34.58/week |
| Goal target only 20 | Allocation 20; unused goal capacity returned: extra 280/month, 9.23/day, 64.61/week |
| Priority and stable ties | Critical targets 60/60 allocated first in insertion order, important 30, flexible 0 |
| Spending 950 | Reserve contribution 50, reserve shortfall 50, goals/headroom 0 |
| Spending 1000 | Reserve shortfall 100, goals/headroom 0, deficit 0 |
| Spending 1100 | Deficit 100, reserve shortfall 100, goals/headroom 0 |
| No goals | needs_goal, no forced numeric estimate |
| Unknown negative types | bank_fee, debt_payment and negative salary each block with dated unclassified-debit reason |
| Missing February evidence | Removing salary or included spending blocks with the respective dated missing reason |
| Zero recorded salary / partial coverage | insufficient_data, not inferred zero income or fabricated extra money |

Separate TestClient checks loaded distinct synthetic CUST04457 and CUST00001 histories.
First profile produced monthly extra 150; second had spending 1100 and reported deficit 100.
Set a nonzero manual plan only on the first profile (45 days, repeat true, weekly/monthly targets 77/333),
and created isolated test goals through the existing 201 POST contract. Before/after assumptions, goals and budget
JSON were identical for both customers after automatic GET requests. No persistent or running-demo state was changed.

### Compatibility and remaining limits

Read incoming friend handoffs without merging or replacing local work:
backend7170c21 has demo prompts but not local spending-estimate routes; UI3ef0553 branches before SafeToSpend and newer
chart changes. Their additions require deliberate integration, not replacing the local trees wholesale.
Friend QA27603ea is separate attributed evidence, including its corrected guidance identity bypass on7170c21;
its root QA_COACH_HANDOFF.md must not overwrite this independently maintained report.
No test pass for a combined friend/local tree is claimed.

The automatic UI must show no-goal CTA, historical dates, extra-above-usual semantics and explicit 10%/50% app-policy disclosure.
Reserve-building is not proof of reserve adequacy; active debt/current funds/payment timing remain unknown.
The UI owner's incoming automatic pairing, delayed response isolation and responsive behavior are not independently verified here.
Manager received the bounded backend PASS; no merges, provider calls, paid activation or code changes by QA.
