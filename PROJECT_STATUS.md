# Project status — S-Bank Financial Coach

Reviewed: 14 November 2026. Repository baseline: `main` at `5ecf8a4`.
Scope: source, API documentation, tests and worktree inventory; no browser usability verification in this audit.
Only planning documentation changed. No agents launched, branches merged or application code edited.

## Product vision

A simple mobile web demo that immediately explains where money goes, spending versus usual,
estimated spending room, and realistic savings goals. Ordinary language and trustworthy numbers come first.
Python owns calculations. Protect essentials and reserves, exclude transfers, and keep missing information unknown.
Coach is rule-based. Mortgage approval is not proof of an active loan. Goals change only after user confirmation.
Use synthetic banking data automatically wherever supported; never ask users to retype available information.
Historical observations and suggestions must remain distinguishable from confirmed future facts.

Challenge context supplied by the user: conversational exploration, plain-language education, what-if scenarios,
and three spending baskets are central. Mobile is the target; open-data benchmarks and multi-bank views are optional.
Mentor feedback prioritizes extremely simple explanations. Do not shame users or equate lower spending with actual savings.
The attached earlier brainstorming contains illustrative balances/progress and deadlines, not verified data or accepted scope.
Proposed demo story: understand spending → ask why → try reducing one category → see conditional impact on a goal.
Product clarification: the core is AI-assisted understanding of money consumption, not another savings-goal product.
The user reports S-mobiili already has Säästäjä; goals support explanations and scenarios rather than define the whole app.
Spending exploration must work without creating a goal. The goal-first journey below applies only to goal planning.
UI direction: closely reproduce the S-mobiili visual structure from user-provided screenshots, then integrate our Coach.
Latest requested Home layout: Balance → Financial coach overview → text-only estimated spending allowance
→ See where it went. Keep charts on Spending and goals secondary. UI refinement sent to the existing UI agent.
Never relabel spending_eur as Balance; missing balance/comparison contracts require honest unavailable states.
Conversational budget planning with embedded goals is proposed, not implemented or fully specified.
Reuse supported rent/food history, but mortgage applications cannot establish repayments; ask only necessary follow-ups.
UI agent reports screenshots received; do not treat screenshot amounts as customer data.
Present the result as a Junction concept/demo, not an official production banking app.
Show the three baskets in plain language (regular bills, unexpected essentials, everyday spending), with uncertainty visible.
Do not label all everyday spending as unnecessary. Keep technical classification evidence in optional details.

## Working agreement

This chat is the primary product/planning contact: challenge unnecessary complexity, inspect code before proposing
changes, prepare workstream prompts and review completed diffs before recommending integration.
Maintain this document; do not edit application code without an explicit request or merge without approval.
Do not launch agents unless requested. Review repository/worktree state on demand, not through claimed continuous monitoring.
For work across PCs, handoffs should identify the GitHub branch, base commit, changed contract and test evidence.
UI workstream reports started on codex/s-mobiili-ui from 65e4e80, with screenshots received.
It owns frontend/src/main.jsx, frontend/src/Coach.jsx and frontend/src/style.css, plus a separate handoff document.
This chat owns PROJECT_STATUS.md. No agent launched from this chat; branch changes have not yet been reviewed.
Ownership clarification: codex/s-mobiili-ui is the LOCAL UI agent, not the friend's remote agent.
The friend's agent on the second PC is assigned backend data/Coach work on codex/data-backed-budget.
Do not assign competing backend implementation to local Agent 2 while the friend owns that work.
Local UI handoff commit: 1fe7eaf (not merged). Build/mobile checks are agent-reported, not a completed PM review.
Immediate backend priorities: expose dated recorded balances, a structured spending comparison and data-derived
planning suggestions with missing-input explanations. Preserve confirmed planning semantics and existing API callers.
After these unblock Home, implement the read-only category-reduction scenario. No frontend edits in this workstream.
Home chart placement needs UI follow-up: text-only allowance does not prohibit a separate spending chart on Home.
UI work should use a separate branch, preserve agreed API contracts and avoid backend edits without coordination.
Before its implementation handoff, provide reference screenshots and a shared base commit; review its diff before integration.
Coordinate ownership of main.jsx, Coach.jsx and style.css to avoid overlapping UI changes across workstreams.

## Demo deadline and scope

User reports approximately 14 hours remaining at this planning update; exact submission time is not established.
Mentors explicitly want more than charts/visual analysis. They did not specify whether a real LLM is required.
Deliver one complete interaction: see spending → ask why → simulate a category reduction → understand the effect.
Explain recorded category changes, not invented reasons or personal motives. Goals are an optional continuation.
Proposed time budget from this update: 1 hour for data/contract decisions and UI handoff, 7 hours for implementation,
3 hours for integration and mobile checks, and 3 hours for fixes and demo rehearsal. These are targets, not scheduled jobs.
Limit UI replication to screens needed by that journey; do not rebuild unrelated banking functionality.
A small real-LLM interpretation/explanation layer is desirable for open questions if time permits, with Python calculations
and deterministic fallback. Do not let provider integration block the working scenario or mislabel the fallback as an LLM.
UI handoff is underway: spending-first Home, Spending, rule-based Coach, optional Goals and collapsed full-object planning.
UI agent requests dedicated contracts for dated comparison and category-reduction what-if; these remain unimplemented.
It will not expose unsupported reduction controls. No conflicting frontend ownership is assigned in this chat.
The data audit remains the first backend task and should be bounded to the decisions needed by this demo.

## Completed features

- Two synthetic customer profiles with isolated in-memory goals and confirmed planning inputs.
- Weekly/monthly spending bars with optional horizontal average and user-set target lines.
- Python daily/weekly allowance, essential/reserve protection and three-priority goal allocation.
- Goal creation already requires only name, amount and priority; analysis follows creation.
- Conditional completion estimates require explicit repeat-capacity confirmation.
- Rule-based Coach: category/average explanations and read-only goal previews with explicit save confirmation.
- Mortgage application availability without invented repayments; unknown balances remain unavailable.
- API and real-HTTP tests cover both customers, exclusions, validation, priorities and preview non-mutation.

## Audit findings and simplification decision

The problem is the Home planning form, not the three-field goal form (`frontend/src/main.jsx`).
Home exposes eight monetary inputs, a period field and two checkboxes before users understand their goal.
Its terms (accessible funds, voluntary contribution, repeating capacity) demand unnecessary financial knowledge.
An unavailable account balance receives the strongest visual emphasis. Categories are buried in expanded history;
the plain-language comparison with usual spending is only available through Coach.

Recommended journey: **Create goal → Goal saved → Check my plan → Short confirmation → Estimate**.
Goal creation must work without a plan. Keep detailed assumptions collapsed and accessible after creation,
with a secondary Home action for people who only want a spending estimate.
The previous proposal to collect all six amounts in three steps is superseded by a data-first review.
First map source data and existing summaries to these information needs:

1. Money available: money accessible now; additional income expected during the displayed period.
2. Money to protect: essential bills; emergency money to leave untouched.
3. Living and saving: everyday costs; maximum amount to put toward goals.

Use a visibly stated 30-day default for new plans; preserve an existing plan's period.
Put period editing, repeat confirmation and chart targets in optional Advanced settings.
Keep repeat confirmation false for new plans. A collapsed field must never silently reset a saved value.
Explain that income excludes money already held and everyday costs exclude bills already entered.
Allow “I don't know”; return an unavailable estimate and the specific next missing input, never an assumed zero.
Show one final review/confirmation before saving inputs. Allowances include everyday costs, not just spare spending.
Use supported historical suggestions now where useful, with dates and explicit confirmation before treating them as future inputs.
The existing income endpoint already returns historical totals and recurring candidates, but the frontend does not call it.
Do not promise automatic prefilling for either customer until source coverage and candidate quality have been checked.
Loader inspection confirms Customer.get_account_balances() exposes latest recorded per-account balance_after_eur
with timestamps. These are historical balances, not necessarily current funds; the current UI/API does not expose them.
A clearly dated historical demo snapshot is an option to investigate, not permission to label old balances as current.
Remove the large Home form in the UI redesign; retain optional planning access until a reviewed replacement exists.
Removing the form alone does not enable allowances: the current engine still requires its six confirmed inputs.

Do not remove the six engine inputs merely to shorten the screen: all six currently gate calculations.
Changing that policy requires a separately reviewed financial model and API contract.
Optional existing savings is not supported by GoalInput; defer it rather than subtracting savings in JavaScript
or double-counting money that is also in accessible funds/reserves. No progress bars without a defined saved balance.

## Current priorities and proposed workstreams (maximum three)

UI ownership is active as reported above; backend/Coach assignments below remain proposed. Execute the data audit first.

### 1. Data-first planning, then a minimal goal-first review

Owner: backend/data workstream first, then friend's external UI agent; financial Coach reviews explanation wording.

Acceptance criteria:
- Create a goal with three fields and no planning prerequisites; show saved success before offering analysis.
- First document, for both profiles, which planning inputs are observed, reasonably estimable, user preferences or unavailable.
- Include source fields, date coverage and limitations without copying raw customer records into documentation.
- Reuse supported data automatically; present historical suggestions with their period and basis, not as confirmed future facts.
- Home has a compact estimate/action instead of the full planning form; advanced settings start collapsed.
- Ask only for missing information or confirmation of a suggested future assumption; preserve drafts and saved advanced values.
- Unknown and explicit zero remain distinct; incomplete plans show no numeric allowance or completion date.
- Full-object assumptions PUT happens only after confirmation; cancel does not change server state.
- Existing backend allocations and allowances remain unchanged for identical inputs.
- At 360px and 390px widths, controls remain usable with no horizontal overflow or bottom-navigation obstruction.
- Tests cover creation before planning, cancel, missing/zero inputs, advanced-value preservation and customer switching.

Copy-ready task prompt:
> Investigate priority 1 in PROJECT_STATUS.md before implementation. Inspect the CSV schema, Customer loader,
> income/history endpoints and planning engine for both demo profiles. Produce a concise mapping of each planning input
> to its source, date coverage, confidence and whether it is observed, estimable, a preference or genuinely missing.
> Recommend the minimum user questions and an additive API proposal for labelled suggestions if necessary.
> Separate historical estimates from confirmed future inputs; never infer active mortgages from approvals.
> Do not expose raw records, change application code or merge. Return findings for product review before UI implementation.

### 2. Make spending understandable at a glance

Owner: backend summaries followed by friend's external UI agent; this chat reviews product fit and API compatibility.

Acceptance criteria:
- Home prioritizes recorded spending and estimated allowance; unavailable balance is secondary.
- Spending shows a short category list and a dated above/below/equal-to-average statement without opening details or Coach.
- Python supplies comparison arithmetic; use complete comparable periods and explicitly label incomplete coverage.
- Missing complete periods produce an unavailable comparison; equal spending says “same”, not “above”.
- Keep bar charts and labelled horizontal average/target lines when values exist; never invent a target.
- Advanced basket classifications stay optional; groceries are not presented as automatically safe to cut.
- Add API tests for above/below/equal, no complete periods, partial periods and transfer exclusion.
- Verify both customer profiles and chart labels at mobile widths; update API docs for any additive response fields.

Copy-ready task prompt:
> Implement priority 2 in PROJECT_STATUS.md. Expose a compact category summary and plain-language spending comparison
> on the main spending journey. Reuse financial.py/coach.py logic; keep arithmetic in Python and API changes additive.
> Label the compared historical period and incomplete coverage. Preserve bars, average lines and independent targets.
> Add comparison edge-case tests and mobile UI checks; run the backend suite and frontend build. Do not merge.

### 3. Deliver one useful conversational what-if, with reliable demo interactions

Owner: financial Coach/backend workstream, supported by frontend reliability/QA.

Acceptance criteria:
- Support a read-only category-reduction scenario, such as dining out by 20%, using an explicitly dated historical baseline.
- Python calculates the hypothetical reduction; it is potential spending reduction, not money already saved.
- Show goal-timeline impact only when the confirmed planning model supports it; never count a reduction twice.
- Interpret category and period explicitly; ambiguous requests ask one short clarification rather than silently choosing.
- A real LLM, if added, interprets requests and explains Python results using only necessary aggregated data.
  It cannot invent financial values, execute arbitrary code or write goals; retain deterministic fallback responses.
- Coach visibly says it provides rule-based demo explanations; no suggestion of an actual LLM or guaranteed advice.
- Successful goal creation remains visibly successful if the subsequent analysis request fails.
- Retrying analysis never resubmits a successful goal POST; ambiguous save failures refresh state before encouraging retry.
- A preview cannot remain confirmable after switching customers or after goals/planning inputs have changed.
- Browser tests cover preview edit/discard/confirm, customer switching during delayed requests and post-save analysis failure.
- Regression tests retain essentials/reserves protection, priority/tie ordering, short horizons and null completion estimates.
- Run the full suite/build and a two-profile mobile demo walkthrough; record results and remaining limitations.

Copy-ready task prompt:
> Design the smallest read-only category-reduction scenario described in priority 3 of PROJECT_STATUS.md.
> Inspect existing Coach routing and financial functions, propose the request/response contract and baseline semantics,
> and tests for missing categories, ambiguous periods, reduction bounds and no double-counted goal capacity.
> Return this design for review before implementation or adding an LLM dependency.
> In the reliability pass, first reproduce UI failure paths with delayed/failed API responses.
> Separate goal-save success from follow-up analysis errors in main.jsx and Coach.jsx, and invalidate previews when
> their underlying customer/plan/goals change. Add a visible rule-based Coach explanation and focused browser tests.
> Preserve explicit goal confirmation and customer isolation. Run all backend tests and the production build.
> Report verified fixes, mobile walkthrough results and unresolved risks. Do not merge.

## Contracts, blockers and review limits

- Inspected frontend calls match backend routes and fields; optional existing savings would currently receive 422.
- Assumptions PUT replaces the complete object: omitted amounts become null. Preserve hidden fields explicitly.
- Source-level risk: creation and follow-up analysis share a catch block, so a saved goal can appear to have failed.
- Source-level risk: Coach updates goals/budget without invalidating a previously held Goals analysis;
  navigating away and creating goals can also leave an old Coach preview available. Browser reproduction is pending.
- No frontend test script currently exists. Production build alone does not verify interaction or mobile layout.
- Current balance, actual goal savings and payment timing are unknown. Estimates require user inputs; state resets on restart.
- The challenge brief and mentor feedback are supplied; a weighted judging rubric is not.
  Conversation, education and what-if exploration must remain core, not optional polish behind a dashboard.
- Worktree inventory includes frontend, backend and Coach branches plus two detached worktrees.
  This audit does not certify their uncommitted changes or recommend integration; review each diff when requested.
- No current implementation blocker; real user confirmations are needed to demonstrate numeric planning honestly.

## Verification and next recommended action

- Frontend production build passed; Vite reports a bundle over 500 kB. Defer splitting unless demo performance suffers.
- Backend verification: all 15 tests passed, including the isolated real-HTTP workflow for both customers.
- Existing coverage: financial protection/priorities, spending/income exclusions, mortgage unknowns,
  both-customer API isolation, read-only analysis/previews and live HTTP planning workflows.
- Additional coverage belongs with the three tasks above; no application or test code was changed in this review.
- Next action: establish the two-profile data-to-planning mapping using the priority 1 investigation prompt,
  then approve the smallest user review flow. Do not build the previous six-field wizard first.
- Decide on a small real LLM layer after the data audit and one deterministic what-if contract; do not build a general agent.
- Defer richer mortgage features, open-data benchmarks, multi-bank support, goal editing and persistence until the core demo is clear.


### Selective optional-plan integration ? 15 November
- Integrated historical form defaults and optional saved-plan storage from backend `991f124` and UI `f811777`.
- Kept automatic goal-based allowance, automatic chart fallback, eight-week history and scripted Coach.
- Corrected remainder preview to send the selected plan horizon; guarded chart-settings focus until the form loads.
- Plan persistence across backend restarts requires `SBANK_PLAN_STATE_PATH`; goals remain session-only.
- Integration is in `codex/scripted-coach`; other UI worktrees and running backend processes are untouched.

- Added Goals six-month projection chart using Python goal-plan allocations, target caps and priority rollover. Preview 5204 refreshed with existing goal restored. Verified 18 tests passed (one dataset check skipped), production build and rendered graph.

- Home estimate now warns yellow at 90�100% of the automatic spending target, red above it, with overage and recorded-month dates. Python comparison; automatic allowance unchanged. Threshold tests/build passed.

- Render deployment prepared: Docker frontend/backend, private 31,448-byte two-customer bundle; parity and static API checks passed. Not deployed. Docker build awaits Render verification.

- Coach now shows six-month hypothetical category saving lines and first-month goal allocation bars. Python owns savings projection; existing goal allocations reused. Ten tests and build passed; both charts visually verified.

- Coach question search restored: local typing suggestions route only to supported deterministic actions. Microphone displays future-feature notice, never records. Build, matching checks and browser flow passed.

- Goal removal added in Goals with Yes, remove / Keep goal confirmation. Customer-scoped DELETE API, automatic chart/allowance refresh; 11 relevant tests and production build passed.
