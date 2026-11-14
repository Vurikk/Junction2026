# Independent QA: curated Coach demo questions

Date: 14 November 2026 (Europe/Helsinki).
Disposition: **QA-DEMO-01 reproduced on 13a2523; fixed and independently verified on 7170c21.**
The initial no-blocker assessment of 13a2523 was withdrawn.
This is not a full browser or paid-deployment acceptance result.

## Scope, versions and coordination

The coordinating backend chat reassigned this pass to urgent curated-demo verification,
with offline mocks only and immediate blocker reporting. Results were sent back to that chat.

- Final backend: `codex/coach-backend-readiness`, `7170c2144ffb2fdb987e25ed4f6756105f2f468d`.
  Initial dated-data checks used `13a252362f6b84149bc63e4bf8ed51245cb9a4ad`; identity correction is verified below.
- UI implementation: `codex/demo-coach-prompts-ui`, `709889da3294f8c9469a9ab412a4bb5c3331d4d2`.
- UI final handoff: `3ef0553a3d0041721a7563dda59a4aa7211afcce`; only documentation differs from implementation.
- QA: `codex/qa-coach-verification`, based on `0e43cbd74cbae8a5698dd4499abcbb5b093e4b61`.
  Only this new handoff is changed. No other agent's checkout was switched.
- Coordinated manual frontend/backend ports are 5193/8031. **Neither was contacted.**
  The coordinator says the running backend still has older code and requires a user restart.
  That runtime status is reported coordination evidence, not independently observed here.
- Read AGENTS.md, backend/API.md, backend/VERDA_HANDOFF.md, backend/DEMO_PROMPTS_HANDOFF.md,
  backend/BACKEND_READINESS_HANDOFF.md, backend/QA_FIX_HANDOFF.md,
  frontend/UI_COACH_HANDOFF.md and the earlier frontend/qa handoffs.
  No separate current INTEGRATION_HANDOFF.md was found; direct coordination supplied scope and ports.
- The earlier report on `origin/codex/qa-coach-integration` remains unchanged.
  Its previous bugs/fix verification are historical evidence, not newly reproduced claims in this report.

## Actual execution and results

All Python commands explicitly set `COACH_LLM_ENABLED=false` and `PYTHONDONTWRITEBYTECODE=1`.
No live provider, actual API key, deployment ledger, paid setup, configuration change or dataset write occurred.
The final nine-test demo suite creates disposable temporary test ledgers; it does not access the deployment ledger.
Python used the existing a308 worktree's `.venv/Scripts/python.exe` and imported the backend under review read-only.
Async tests stalled inside the sandbox; those QA-owned processes were interrupted. The same tests passed outside it.
The existing Starlette/httpx deprecation warning did not fail checks.

### Automated checks independently rerun

`python -B -m unittest backend.test_demo_prompts backend.test_coach_language backend.test_coach_routing`
from the backend checkout: **27 tests passed** (1.204 seconds reported by unittest).
Providers/ledgers used by those tests are mocks; the HTTP tests use synthetic customers and TestClient.

These observed passes cover:

- Six demo tests: supported dated prompts and exact fixture amounts, earlier restaurant month selection,
  empty/partial history, one month without restaurants, read-only GET/404, and local scripted guidance.
- Language/date checks: exact 10% follow-up context, Food ambiguity, relative-date rejection of stale history,
  invalid model selections, sensitive prose rejection and canonical outbound payloads.
- Routing checks: local missing-data/clarification, Python card retained on provider error,
  appropriate weekly/category routing and validated follow-up context.

From the final UI checkout, all four existing offline commands passed:

```text
node frontend/qa/check-demo-questions.mjs
node frontend/qa/check-coach-session.mjs
node frontend/qa/check-coach-cards.cjs
node frontend/qa/check-home.cjs
```

These exercise read-only suggestion loading, customer-scoped request paths, malformed suggestion filtering,
bootstrap, conversation/new-turn IDs, identical-body retry, abort guards and fallback transport behavior.
Static rendering checks verify exact card amounts, source/baseline dates, zero versus unknown,
historical/hypothetical caveats and Home's existing null/zero presentation.
They are not browser click, responsive-layout or actual cookie-persistence tests.

### Independent supplied-data probes beyond the existing tests

Loaded the existing supplied synthetic datasets read-only through `load_customers(data_directory)`.
For each customer, constructed a fresh `CoachLLM()` with no provider, one UUID conversation and fixed local session.
Called `demo_prompts(customer)`, then submitted each returned question directly to `respond` with a new request UUID.
All three prompts returned calculated cards with `mode=rule_based`.

| Customer | Overview month / total EUR | Restaurant period | 20% baseline / hypothetical / reduction EUR |
| --- | --- | --- | --- |
| CUST04457 | August 2026 / 1974.07 | July 2026 | 95.04 / 76.03 / 19.01 |
| CUST00001 | September 2026 / 1878.66 | September 2026 | 225.70 / 180.56 / 45.14 |

Both monthly comparison prompts returned dated comparison and baseline objects.
CUST04457's overview month has no restaurant observations; its restaurant prompt correctly selected July instead.
No amount is embedded in the prompt beyond the chosen scenario percentage.

After each restaurant answer, sent `What about 10% instead?` with the same conversation and a new request ID:

- CUST04457: restaurants, 2026-07-01 through 2026-07-31, 95.04 / 85.54 / 9.50 EUR.
- CUST00001: restaurants, 2026-09-01 through 2026-09-30, 225.70 / 203.13 / 22.57 EUR.
- Repeating each identical request ID/body produced an equal response.
- In a fresh conversation, `Food` returned `clarification_needed`, empty cards, for each customer.
- With `backend.coach_tools.today_local` patched to `date(2026, 11, 14)`, `Restaurants last month`
  returned `unsupported_period_or_category`, empty cards, for each customer; no historical month was substituted.

Independent guidance probe used a provider containing `AsyncMock.complete` and `Mock` ledger:
`How can I save money?` and ` WHERE COULD I CUT SPENDING!!! ` returned `rule_based` / `demo_guidance`.
The provider was never awaited and ledger.mock_calls remained empty.
`demo_guidance('How can I save money? My account is private', fixture())` returned None;
the sensitive suffix was not stripped into an accepted guide intent.

### Follow-up button and duplicate-work review

Observed source at UI `709889d` offers the 10% button only on the latest message when
`canFollowUpReduction(item)` succeeds and neither error nor retry is pending.
The helper requires a conversation ID and a reduction card with an allowed outcome.
Cold-start, category-spending, missing conversation, clarification, pending request and ledger-error cases
were exercised by the passing helper tests. Suggestion/follow-up clicks route to existing `ask`,
which has the synchronous pending guard and creates a normal turn; explicit retry retains that turn.
No automatic suggestion POST is present: loading uses GET and sending requires its click handler.
Actual rapid browser double-clicks and switch-during-fetch behavior were not independently exercised in this pass.

## Reproduction

Use the backend and UI hashes above in isolated checkouts; do not use the manual paid ports.
Run the listed tests with paid mode false. The independent aggregate probe can be reproduced without any server:

```python
import asyncio
from uuid import uuid4
from backend.data_test import load_customers
from backend.demo_prompts import demo_prompts
from backend.coach_llm import CoachLLM

async def verify(data_directory):
    for customer in load_customers(data_directory):
        coach, conversation = CoachLLM(), str(uuid4())
        for prompt in demo_prompts(customer)['questions']:
            response = await coach.respond(customer, prompt['question'], conversation,
                                           str(uuid4()), 'qa-offline', {'kind': 'help'})
            assert response['mode'] == 'rule_based' and response['cards']
            if prompt['id'] == 'restaurants':
                request = str(uuid4())
                args = (customer, 'What about 10% instead?', conversation, request, 'qa-offline', {'kind': 'help'})
                followup = await coach.respond(*args)
                assert followup == await coach.respond(*args)
                data = followup['cards'][0]['data']
                assert data['source_period'] == response['cards'][0]['data']['source_period']
                assert data['category'] == 'restaurants' and data['reduction_percent'] == 10
# asyncio.run(verify(existing_synthetic_data_directory))
```

## Bugs, limitations and recorded evidence

### QA-DEMO-01 — P2: scripted guidance bypasses ownership and request conflict checks

Affected branch/commit: `codex/coach-backend-readiness`, `13a2523`.
Reported by the coordinating reviewer after the initial bounded checks; independently reproduced here.
Cause: `demo_guidance` returns before session/ownership/receipt validation in `CoachLLM.respond`.

Reproduction using only mocks:

1. Load `backend/coach_llm.py` from exact `13a2523` with `git show` and execute it in a backend package namespace.
2. Construct CoachLLM with a fake provider whose ledger.conversation raises `GateError('conversation_mismatch')`.
3. Submit `How can I save money?` with explicit conversation/request UUIDs and another browser session.
4. Repeat with conversation returning None and ledger.claim raising `GateError('request_conflict')`.

Expected: respective `conversation_mismatch` / `request_conflict` guard response, without provider work.
Actual: both return `demo_guidance`; ledger.mock_calls is empty, so neither guard runs.
Also reproduced without mocked guards using `CoachLLM()` and its in-memory disabled state:
first calculate `Reduce restaurants in April 2024 by 20%` in browser A;
reuse its request ID for `How can I save money?`, then submit guidance in browser B with A's conversation.
Both incorrectly return `demo_guidance` instead of conflict/mismatch.
This violates the additive request/ownership contract. No paid call or raw-data disclosure was observed.
The zero-ledger guidance observation above documents the defective old implementation, not a requirement for the fix.
Guidance POST must keep identity receipts while making no provider call or spending reservation;
the suggestion GET remains ledger-free. Backend owner corrected this; no QA implementation edits were made.

### Corrected-source verification

Reran the same three backend modules after the fix: **30 tests passed** in 2.423 seconds,
including nine demo tests. Newly added tests cover replay, changed guide/calculation bodies,
browser/customer ownership, context retention, and zero provider calls/spending reservations.
The fake provider's complete method fails if called; temporary ledgers contain identity receipts, no call records.

Independent probe, without using the author's test methods:

1. In disabled mode, calculate April restaurants 20% with a fixed conversation and request ID.
2. Reuse that request ID for guidance: now `request_conflict` (PASS).
3. Send guidance with that conversation from another browser: now `conversation_mismatch` (PASS).
4. Send guidance with a fresh ID from the original browser; identical replay returns the same response (PASS).
5. Send `What about 10% instead?`: April restaurants remains selected; potential reduction EUR 40 (PASS).
6. Repeat the mocked failing-guard probe described above: conflict/mismatch both returned, provider never awaited (PASS).

Verified source blob IDs before owner commit:
`coach_llm.py`: `dcde520a465fe1a3791febaaabec8ee4cf4c9630`;
`test_demo_prompts.py`: `64a662f4e30d2301cdb84dcd140323faeb833523`.
Both blob IDs exactly match final committed `7170c2144ffb2fdb987e25ed4f6756105f2f468d`.
Final bounded disposition: QA-DEMO-01 resolved; no remaining reproduced blocker for the offline-tested pair
`7170c21` backend / `3ef0553` UI. Browser/deployment limits below still apply.
This verification supersedes the initial guidance zero-ledger/no-blocker result, not the dated amount checks.

Untested independently in this urgent pass: new-button browser layout at mobile widths, actual suggestion clicks,
browser customer switching, real cookie bootstrap, delayed browser races, rapid duplicate browser submissions,
all timeout/budget notices visually, a full paired deployed frontend/backend, physical keyboards and live Verda behavior.
The frontend helper/static tests support these contracts only at their stated boundaries.
The coordinator's final 107-test full-suite pass and UI owner's production build are recorded handoff evidence;
this pass did not independently rerun those broader checks.

Prior authorized live smoke at `0e43cbd`: CUST04457, restaurants, July 2026, 20%,
95.04 / 76.03 / 19.01 EUR. This remains supplied historical evidence; no live smoke was repeated.
The matching amounts above were independently recalculated locally by Python with the provider absent.
No merges, paid activation or changes outside this QA handoff were made by this pass.

## Follow-up: guided savings and goal analysis

Date: 14 November 2026. Reassigned read-only backend verification by the coordinating chat.
Scope: working tree `verda-live-smoke/Junction2026` on `codex/coach-backend-readiness`, base `0c71d8a`,
including the new savings-opportunities endpoint and expanded goal explanation. UI was intentionally not inspected while in flight.

**Result: PASS for the bounded checks below; no concrete bug reproduced.**
These checks apply to the observed working-source blobs, not an unobserved deployment:

| File | Git blob verified before and after independent probes |
| --- | --- |
| backend/savings_demo.py | aea1f727ec0f8ab150fca726f334897c7b1d5a3d |
| backend/main.py | ae8d5e928c297020614d948ba67ae07ac85df157 |
| backend/coach.py | 61bfc2180df7fb62ea67f6e1776fac0d8f2db7f4 |

### Independent HTTP probes

Used a new in-process FastAPI TestClient with `load_customers` patched to synthetic fixtures.
Paid mode was explicitly false, `app.state.coach_llm.provider` was None, and both `Ledger.transaction`
and `VerdaClient.complete` were patched to raise if touched. Neither guard fired.
No existing server, external dataset, raw customer output, credential or actual ledger was accessed.
Fixture goals/assumptions were assigned only within the disposable TestClient state to exercise analysis;
there were no writes to an existing application or source files.

Savings fixture: coverage from 2024-04-01 through partial May (2024-05-15).
April purchases: restaurants EUR 100, entertainment EUR 50, travel EUR 200.
Additional exclusion sentinels included housing payments labelled Restaurants, utilities payments labelled Travel,
negative transfers, positive and negative refunds, unknown/null categories, groceries and positive purchases.
These excluded entries deliberately had much larger amounts than the included purchases.

Expected versus actual (all matched):

- GET savings-opportunities with explicit April and 10% returned only travel/restaurants/entertainment,
  with reductions EUR 20/10/5 and baselines EUR 200/100/50; none of the sentinel amounts entered the totals.
- 0%, 20%, 33.33% and 100% reruns retained 2024-04-01 through 2024-04-30 and matched Decimal rounding.
  At 33.33%, reductions were EUR 66.66/33.33/16.66; at 100%, all hypothetical amounts were zero.
- Omitting month selected April, the latest full recorded month, rather than partial May.
- Explicit May, January 2023 and October 2026 returned `unavailable_period`, null source period and empty candidates.
  No older month was substituted.
- Empty and partial-only histories returned unavailable_period. A full April containing only groceries returned
  `no_candidates` with April dates, keeping absence of eligible observations distinct from an unavailable period.
- Months `2024-13`, `2024-00`, `2024-4`, `last month`, `2024-04-01` and the empty string returned 422.
  Percentages -1, 101, NaN, Infinity, 10.001 and abc returned 422. Unknown customer returned 404.
- Deep comparison confirmed all savings GETs left goals and assumptions unchanged;
  pandas frame equality confirmed transactions were unchanged.

Goal-analysis fixture deliberately inserted flexible before critical and important goals (EUR 200 each).
Six missing planning inputs produced insufficient data, null capacity/allocations/completion times,
and wording that feasibility cannot yet be determined.
With EUR 1000 accessible funds, zero additional income, EUR 400 bills, EUR 200 reserve,
EUR 100 everyday costs and EUR 300 voluntary contribution, a 30-day plan allocated
critical/important/flexible EUR 200/100/0, independent of insertion order.

- repeat_plan=false: completion periods all null; only the fully funded critical target was described as fitting.
- repeat_plan=true: completion periods 1/2/2; unfunded targets were explicitly conditional on repeated contribution/capacity.
- Reducing accessible funds to EUR 100 produced EUR 500 shortfall, zero allocations, no completion periods,
  and no conditional-completion promise despite repeat_plan=true.
- Text states saved progress is unknown and historical cuts have not been added to capacity.
  GET goal-analysis left the seeded goals and confirmed assumptions unchanged in both repeat configurations.

### Existing regression checks independently rerun

With paid mode false and bytecode writes disabled:

```text
python -B -m unittest backend.test_guided_coach backend.test_savings_demo backend.test_coach backend.test_financial
```

**22 tests passed**, 0.444 seconds reported by unittest. The savings identity test uses a disposable temporary ledger,
mock provider and zero spending/call assertions; it never accesses the deployment ledger.
These checks additionally cover ties, tiny amounts, sensitive suffixes, no-goal copy and zero contribution/capacity.
The installed Starlette/httpx deprecation warning remains non-failing.

To reproduce the independent HTTP checks, patch load_customers with the fixture described above, construct TestClient(app),
and GET `/api/customers/{fixture_id}/savings-opportunities?month=2024-04&reduction_percent=10`.
Repeat the listed month/percentage variants and compare state before/after. Seed the stated goal/assumption values
in that client's disposable app.state, then GET `/goal-analysis` for each repeat/shortfall case.
Keep the provider/ledger failure guards active throughout.

Not tested in this follow-up: in-flight UI changes, actual guided-dialogue clicks/layout, production routing,
real datasets, paid-provider behavior, or a full-suite/build rerun. No claim is made for those cases.
No implementation, existing tests, configuration, datasets or shared server processes were modified by QA.
