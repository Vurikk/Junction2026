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
