# Curated Coach demo questions

Backend branch: codex/coach-backend-readiness. Built on QA fixes f550b26.
This is labelled demo guidance and real Python calculation, not simulated AI success or fabricated financial results.

## API

GET /api/customers/{id}/coach-demo-prompts returns:
`{questions: [{id, label, question}], note}`. Unknown demo customers remain 404.
No provider call, goal/assumption mutation, ledger claim or spending reservation occurs on this GET.

The question list is bounded to three entries:
- overview: category spending in the latest full recorded month, with an explicit YYYY-MM date.
- comparison: overall monthly comparison, only when at least two full recorded months are available.
- restaurants: 20% hypothetical reduction in the latest full month with actual restaurant observations.
  This can differ from the overview month. Missing restaurant observations omit this question; no zero is invented.
Empty/partial-only coverage returns an empty list and an explanatory note. Calendar coverage does not prove all records are present.
Question strings contain only approved generic categories, explicit dates and fixed scenario percentages; no raw records or identifiers.

The existing Coach route also recognizes a small exact list of broad demo intents, including:
- How can I save money?
- Where can I save money?
- From what categories would be easy to save from?
- What categories can I save on?

These return local guidance with kind=help, mode=rule_based, fallback_reason=demo_guidance, empty cards/rows.
Guidance passes the existing conversation/identity gates. In provider-capable mode it stores a normal request receipt,
but no provider call or reservation occurs. In disabled mode it uses the bounded local receipt store.
Identical replies replay; changed bodies or browser/customer mismatches are rejected. Prior financial context is retained.
They invite the user to choose a demo question, protect essentials/reserves, and do not claim that large categories are easy to cut.
Matching normalizes case, whitespace and trailing sentence punctuation only. Unknown/sensitive suffixes are not removed into a match.
Actual calculations still use the ordinary Coach path, its existing request identities, Python tools and provider gates.
A selected demo question can make one provider call when the user enables paid mode; broad scripted guidance makes none.

## UI pairing and verification

The existing UI chat owns codex/demo-coach-prompts-ui in the verda-manual-ui worktree.
UI labels the buttons Demo questions, sends the full selected question through the normal conversation path, and does not auto-send.
A 10% follow-up is offered only with current validated reduction context; it is not a cold-start prompt from this endpoint.
No frontend work is committed by this backend branch. No branches are merged.

backend/test_demo_prompts.py contains nine focused tests for actual Python calculations, dated restaurant selection,
empty/partial periods, omitted unavailable options, read-only GET/404 and guidance avoiding provider calls/reservations
while preserving ownership, replay and conflict checks.
Final regression result after identity review: **107 tests passed**. No live Coach requests were made by this workstream.
The running manual backend must be restarted by the user to load this endpoint; source changes do not hot-reload that paid process.
