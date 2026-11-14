# Coach frontend integration handoff

Date: 14 November 2026. Branch: `codex/verda-coach-ui`.
Implementation commit: `dfe417450244d84d49c0ec6f6e34a41d616b89ba` (this handoff follows separately).
Base: manager-confirmed integration `0e43cbd74cbae8a5698dd4499abcbb5b093e4b61`.
Original UI branch remains at `1f49b0b`; no branches merged and no backend edits.
Manager confirmed exclusive frontend ownership before changes. Independent QA owns its separate QA report.

## Integration retained and reviewed

The verified base already implemented the missing transport and result rendering. This branch reuses it:

- Existing question/scenario payloads and explicit goal creation confirmation are retained.
- Same-origin credentials retain the backend HttpOnly session cookie; no frontend API key or provider client.
- Separate free bootstrap omits conversation_id. Its returned ID is retained in the mounted customer's session.
- Each new message receives a UUID request_id. Explicit retries retain identical IDs and body, without duplicate user bubbles.
- Only session_initialized allows one bounded automatic identical-body replay; no automatic new-ID failures/retries.
- Closing the popup preserves conversation/draft. Customer switch remounts Coach, starts a new conversation and aborts stale work.
- Three Python card types render exact backend amounts independently of llm/rule_based labels, with historical dates.
- Guided category reduction and goal scenarios remain separate. Category-reduction kind=scenario does not open a goal form.

## Candidate changes

- `src/coachSession.js`: explicit clarification, unavailable category/period, session/control and unsupported-topic notices.
- `src/Coach.jsx`: no misleading retry action for concurrency_limit, whose backend receipt can be final for that request.
- `src/CoachResult.jsx`: show comparison baseline date range as well as comparison dates.
- `src/style.css`: carry the single reviewed top/side popup border from UI commit1f49b0b, without a bottom border.
- `qa/check-coach-session.mjs`, `qa/check-coach-cards.cjs`: broaden offline fallback/identity and baseline-date regression checks.
- `qa/verda-popup.html`, `qa/verda-popup.jsx`: explicitly labelled fixture page importing the actual Coach and dialog.
- `qa/verda-popup-360.jpg`, `qa/verda-popup-390.jpg`: mocked browser evidence; values are fixtures, not a live provider result.
- This handoff. No dependencies, financial arithmetic, Home redesign, secrets or customer datasets added.

## Checks actually performed

Passed production build, check-coach-session.mjs, check-coach-cards.cjs, check-home.cjs and git diff --check.
Build retains the existing >500kB bundle warning.
Session tests cover free bootstrap, retained conversation/new turn IDs, identical retries, customer helpers,
abort-ignoring bootstrap, existing goal scenario payload, legacy answers, cookie-expiry bootstrap replay,
provider/budget/control fallbacks without automatic retries. Cookie tests mock transport; they do not prove browser Set-Cookie behavior.
Static card checks cover ranking/remainder, exact monetary display, zero versus null, historical dates and caveats.

Browser fixture checks at360/390px: bootstrap hidden from conversation; follow-up same conversation/new UUID;
network retry identical request body/UUID and single user bubble; fallback still displays dated reduction card;
clarification and missing data notices; in-flight composer/actions disabled; close/reopen retention;
switch customer while an abort-ignoring response is pending, then resolve it: old response stays absent;
new customer bootstraps with a new ID; unknown goal preview remains unavailable, close does not save,
explicit confirmation produces one mocked goal POST and saved response. No actual goal or backend state was changed.

## Safe review and limitations

Fixture URL: http://127.0.0.1:5186/qa/verda-popup.html while this task's isolated Vite process runs.
Its API is an in-memory function with no fetch. Vite's /api proxy deliberately targets closed port127.0.0.1:1.
This URL tests the real UI with mocks, not an integrated data-backed demo. Existing port5178 was not changed or represented as integrated.
The fixture returns fixed card values even for a ten-percent follow-up: it verifies transport identity, not language routing/calculation.
No live provider calls, paid activation, ledger initialization, deployment or main merge performed.

Not tested here: real browser cookie exchange against the verified backend, physical mobile keyboard, live provider response,
full data-backed app with this candidate, or browser tests of every control fallback. Independent QA is reviewing separately.
Manager reports a prior successful backend smoke at0e43cbd; that is not a browser result from this workstream.
Conversation state is in memory and resets on page reload; only prior validated selections are backend context, not full chat memory.
Backend follow-up: concurrency_limit can be cached; UI now explains finality and never changes UUID to bypass it.
No additional backend schema is required for the implemented wiring.

## Full-app follow-up verification (14 November 2026)

Tested exact candidate7a958ebcc3e45a4d670fa83a15fc1dc451e5f0d6; no code regressions found or fixes made.
This supplements the earlier mock-only limits above. A NEW isolated Uvicorn process on127.0.0.1:8026
was launched with COACH_LLM_ENABLED=false explicitly and the supplied synthetic data directory, one worker.
A NEW Vite process on127.0.0.1:5187 targets only8026. Existing servers and paid configuration were not changed.

Browser checks passed at360/390px: populated Home, all four Coach entries, close/reopen retains draft/conversation,
both customers, per-customer conversation clearing, monthly bars and historical-average lines, rule-based answers
with recorded dates, unknown allowances, goal preview/discard and explicit save. Discard left Goals empty;
re-preview and one explicit confirmation created exactly one EUR10 flexible goal for CUST04457.
Direct read-only HTTP verified one goal on CUST04457 and an empty JSON array on CUST00001.
The synthetic goal exists only in this isolated process's memory. No live financial action was performed.
CUST00001 guided September restaurants20% reduction returned225.70/180.56/45.14 EUR with historical dates.

Evidence: qa/full-app-disabled-chart-360.jpg, qa/full-app-disabled-chart-390.jpg,
qa/full-app-disabled-coach-390.jpg. No provider calls/paid activation, no backend edits or main merge.
This verifies UI-to-backend HTTP operation in disabled mode; cookie identity/deduplication enforcement in the paid path,
physical phone keyboards, budget-line editing and weekly chart switching were not additionally exercised here.
The manager's pending backend concurrency fix must be reviewed before changing the current final-result notice.

## Latest eight weeks and Home goals (14 November 2026)

User-approved scope adds Current goals on Home with Add goal opening/focusing the existing three-field goal form.
Actual current-customer names, target amounts and priorities are shown, with an empty/unavailable state.
No saved amount is offered because the GoalInput contract does not support it. No progress/feasibility is invented.
Both Home and Spending weekly charts use the last eight API periods in original chronological order;
monthly charts and full-history detail disclosure remain unchanged. Backend average/target values are untouched.
Changed main.jsx, HomeSummary.jsx, style.css, new chartPeriods.js, check-chart-periods.mjs and check-home.cjs.

Read-only inspection of backend fixf550b26 confirms concurrency_limit can be explicitly retried with identical IDs/body
when the ledger proves no provider call/reservation started. Coach.jsx and coachSession.js now restore that manual Retry
and busy notice; session regression includes concurrency_limit. No automatic retry or new UUID was introduced.
Backend fix was NOT merged into this branch; pairing with f550b26 or newer is needed for transient busy readmission.

Verified on isolated paid-disabled full app5187/8026 at360/390: eight rendered bars in Spending for both customers,
eight in Home, chronological visible ISO labels, unchanged API historical averages445.85/486.95 EUR,
Current goals populated on CUST04457 and empty on CUST00001. Add goal focused name with field visible, then one
explicit EUR12 goal save through the existing form appeared on Home. Other customer's Home stayed empty.
Screenshots: qa/weekly-eight-360.jpg, qa/home-current-goals-360.jpg, qa/home-current-goals-390.jpg.
Build, chart-period selection, Home render, Coach session checks and diff whitespace checks passed.
This local backend does not contain f550b26; its runtime behavior is separately owned/tested by backend and QA.
No provider call, backend edit, new dependency or merge was performed.

## Final pairing smoke

Tested UI767cdd6e6ceb31dd456c5b303c77795a9455d3af against backendf550b266d38c2a2f455650f34fba81d6e8406c38.
Backend source was git-archived to a new temporary directory, not merged. Fresh process8027 explicitly set
COACH_LLM_ENABLED=false with synthetic data and one worker; candidate Vite5188 targets only8027.
Browser390px: July CUST04457 restaurants20% returned95.04/76.03/19.01, then typed follow-up10% returned
95.04/85.54/9.50 with July dates and rule-based label. No unexpected goal form appeared.
Weekly Spending chart had8 bars. Home Add goal saved one explicit EUR8 flexible goal and displayed it.
Browser360px: switched to CUST00001, empty conversation and Home goals; context-free10% follow-up asked
for clarification instead of reusing the first customer's July context. Screenshot: qa/paired-disabled-followup-390.jpg.
No critical pairing blocker found. Paid-path concurrency recovery remains independently QA-tested, not
recreated via provider calls here. All live tests in this workstream used paid-disabled mode.
Final paired preview: http://127.0.0.1:5188 (5187 uses the older backend,5186 is mock-only).

## Demo questions follow-up (14 November 2026)

Manager-assigned branch: `codex/demo-coach-prompts-ui`, based on `dc40848a898133ce477ac9138981cd5527dd36cb`.
Implementation commit: `709889da3294f8c9469a9ab412a4bb5c3331d4d2`; this handoff is committed separately.
Took over the manager-designated `verda-manual-ui` checkout and preserved/finished its partial frontend work.
No other worktrees, backend files, provider configuration, ledger, or server processes changed.

Changed files:
- `src/DemoQuestions.jsx`: customer-scoped read-only question loading, loading/error note, and explicitly labelled Demo questions.
- `src/demoQuestions.js`: validates up to three server-supplied prompts; gates the contextual reduction follow-up.
- `src/Coach.jsx`: sends selected questions through the existing guarded Coach path and offers What about 10% instead?
  only on the latest usable reduction response, with no pending retry or error. Older cards cannot offer stale context.
- `src/style.css`: four small rules for the disclosure, reusing the existing button layout and design.
- `qa/check-demo-questions.mjs`: mock-only loading, customer scope, validation, send/retry identity and follow-up eligibility checks.
- `UI_COACH_HANDOFF.md`: this appended record; prior evidence above is preserved.

Explicit `.jsx` and `.js` imports fix the Windows basename collision between DemoQuestions and demoQuestions.
The GET contract is `/api/customers/{id}/coach-demo-prompts` returning `{questions: [{id,label,question}],note}`.
It does not submit questions. Clicking a suggestion or the 10% button creates a normal new user turn through the existing
cookie/conversation/request-ID helper. Existing in-flight guard, manual identical-body retries, Python cards, historical dates,
question/scenario behavior and goal confirmation are unchanged. No financial calculations or canned amounts were added.
Backend `demo_guidance` responses render their ordinary help text with the existing rule-based label; no AI claim is added.

Checks actually run and passed, from frontend:
- `node qa/check-demo-questions.mjs`
- `node qa/check-coach-session.mjs`
- `node qa/check-coach-cards.cjs`
- `node node_modules/vite/bin/vite.js build` (npm.cmd unavailable in this shell; same Vite build entry point)
- `git diff --check`

Build retains the pre-existing bundle-over-500kB warning. No dependencies or lockfiles changed.
No browser interaction or responsive-layout verification was performed for these new buttons in this pass.
The new endpoint is owned by backend branch `codex/coach-backend-readiness`; see its `backend/DEMO_PROMPTS_HANDOFF.md`.
The existing manual backend on 8031 needs a USER restart to load that endpoint. This task did not contact or restart it.
The existing frontend on 5193 points at this checkout and may hot-reload source changes; it was not started/restarted here.
No live provider requests, paid activation, synthetic goal writes, merges, or deployment were performed.
