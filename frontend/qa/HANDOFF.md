# S-mobiili-inspired coaching UI

## Latest feature: guided category reduction in Coach

Coach now offers **Explore spending less**. Monthly history supplies complete elapsed months and
their own category options. Unknown/uncategorized entries are excluded. Restaurants is the editable
default only when present; otherwise the first observed category is selected. Percentage starts at 20
and accepts 0–100 with two decimal places. The backend remains the authority on period eligibility.

POST `/category-reduction` receives the explicit category, month start, monthly period and percentage.
All displayed financial amounts come from its response. Result shows recorded and hypothetical spending,
potential reduction and source dates. Nothing is saved; goal timing remains unavailable.
Home and the existing goal preview/confirmation flow are unchanged.

Inputs clear old results. AbortController plus a request revision guard prevents late results after
edits or unmount/customer switches, even if the request provider ignores abort. An immediate request
lock and disabled button prevent duplicate submissions. Missing-history and preview errors have retry.

### Automated verification

- `node frontend/qa/check-reduction.mjs`: PASS against the real running backend on 8018.
  Option fixtures cover partial/current/empty months, unsupported categories, fallback selection and
  percentage validation. Real HTTP checks cover both profiles, repeatability, 0/20/100%, absent category
  404, invalid percentage/partial period 422, and unchanged goals/assumptions/budgets for both customers.
- Exact 20% examples returned by Python and also observed in the browser:
  CUST04457, August 2026 Entertainment: 87.46 baseline, 69.97 hypothetical, 17.49 reduction.
  CUST00001, September 2026 Restaurants: 225.70 baseline, 180.56 hypothetical, 45.14 reduction.
  Restaurants is absent from CUST04457's latest complete month; no category is assumed to exist.
- Frontend production build: PASS. Existing >500 kB bundle warning remains. No new dependencies.

### Manual browser verification

- Both real profiles completed a scenario and displayed the exact API amounts above.
- Actual CSS widths 360/390; document widths 345/375 including scrollbar space, no horizontal overflow.
  Screenshots: `reduction-360.jpg` and `reduction-390.jpg` (real backend, not fixtures).
- 0% displayed zero reduction and unchanged hypothetical spending; 100% displayed zero hypothetical
  spending. 101% was rejected by native input validity. Edits removed the prior result.
- Changing category/month refreshed options and cleared results. Switching customers removed the
  old panel/results. The second profile reopened with its own latest month and supported category.
- `qa/reduction-harness.html` is a local Vite-only fixture page, not a production entry point.
  Browser checks exercised 404, 422, network error/retry, empty history, history-load failure/retry,
  disabled duplicate submission, and deliberately late responses after input edit/customer switch.
  Delayed fixtures ignore abort deliberately; neither late response appeared. These are manual
  controlled-fixture checks, not automated browser tests or real network-outage checks.
- Existing goal preview and explicit confirmation worked; the confirmed test goal appeared in Goals.
  The named `Reduction regression test` goal remains only in the currently running backend memory.

Remaining limits: no physical-device/screen-reader checks, no delayed real-network interception,
no general natural-language scenario parsing. Goal impact stays null by backend design; no blocker
for this guided monthly interaction. Preview remains on 5178 with the current backend on 8018.

## Latest visual follow-up: combined card

Per direct user feedback, Balance, Financial coach and Safe to spend now share one white card.
Coach and allowance share an inner green surface. Ask Coach is compact with a four-point star.
Visible balance label is simply Balance. Historical dates, source caveats and structured comparison
text remain accessible in the collapsed Details section rather than the default summary.
The neutral usage track and estimated label remain honest; no financial semantics changed.
The star is visual styling; Coach still explicitly identifies its rule-based implementation.

Production build and `node frontend/qa/check-home.cjs` pass. Browser checked at actual CSS widths
360/390 with no horizontal overflow, and the smaller Ask Coach button opens the prefilled Coach.
Updated Home screenshots show the combined card; `home-chart-390.jpg` documents the prior layout
and is retained only as earlier-pass evidence. Both-profile and confirmation tests from the data
integration pass below were not repeated for this presentation-only grouping change.

## Current handoff: data-backed compact Home (14 November 2026)

Implemented after the PM merged `origin/main` b9a6e39 into this UI branch (merge b30f56c).
This section supersedes the older Home mappings and missing-balance blocker below.

- Home reads `/recorded-balances`, labels the amount Recorded balance and shows its as-of date.
  Null simultaneous totals display individual observed accounts; no client summation or assumptions substitution.
- Tinted Coach card has a short status headline and one dated spending sentence from `/spending-comparison`.
  Prior baseline/difference/limitations are optional details. Ask Coach is a full-width button into category exploration.
  Existing chat averages have older semantics, so Home does not source its comparison from raw chat text.
- Today/Week chooses backend daily/weekly estimates. The horizontal track is neutral with no filled fraction,
  progressbar role or percentage; usage is explicitly unavailable. Estimate context includes everyday costs.
- A separate compact historical bar chart appears below the allowance, with average/optional target lines.
  Spending retains the full existing charts. Goals stay secondary, with no saved-progress claim.
- `/planning-suggestions` supplies optional historical review context, dates, confidence and limitations.
  No input is automatically copied, scaled or confirmed; food/everyday overlap is called out.
  All six inputs and full-object confirmation semantics remain intact.
- Restarted the isolated backend from this merged checkout on 8018. UI preview stays available on 5178.
  Restart after testing cleared temporary goals and zero-valued test assumptions.

Verification in this pass:

- Final production build: PASS, 413 modules; existing >500 kB bundle warning remains.
- `node frontend/qa/check-home.cjs`: PASS. Uses installed esbuild/React, no added dependencies.
  Rendering fixtures cover null/zero balance and allowance, separate accounts with missing observations,
  above/below/equal comparisons and absence of invented progress semantics.
- Live browser: both real synthetic profiles showed their own historical balance/date and structured comparison.
  Actual CSS viewport widths 360/390, document widths 345/375 with scrollbar; no horizontal overflow.
- Today/Week retained unknown values; six explicitly entered zeros produced EUR 0.00 in both selections.
  Historical suggestions displayed while inputs stayed blank before confirmation.
- Saved test period 45, repeat=true and targets 70/300; resaved with Advanced collapsed.
  API readback verified every advanced value survived. Recorded balance was not replaced by available funds=0.
- Ask Coach opened a prefilled category question and returned real categories.
  Goal preview required confirmation; confirmed test goal appeared in Goals.
  Home View all opened Spending with bars, average and categories.
- Stopped backend and reloaded: fetch error, unavailable balance/comparison/allowance and disabled planning action.
  Restarted and pressed Retry: new endpoint data recovered.
- Updated `home-360.jpg`, `home-390.jpg`; added `home-chart-390.jpg` showing the distinct historical chart.

Not verified in browser: synthetic multi-account/zero-bank-balance cases (covered by rendering fixtures),
individual-endpoint failure injection, physical devices, screen reader operation or delayed-request races.
No backend code/tests or financial policy changed. The test harness initially failed due to a missing module
filename; that harness issue was fixed and its final run passes.

Remaining API/product requests:

1. A meaningful allowance fill requires a backend-defined same-period denominator and consumed/remaining amount,
   with period start/end, as-of timestamp, confirmed baseline and unknown/zero semantics. Current allowance values
   alone cannot provide a usage fraction. UI intentionally shows no actual-progress fill.
2. Conversational plan negotiation and goal-timeline impact remain absent. Historical suggestions require review.
3. `/category-reduction` now exists, but this Home-focused change does not add its explicit category/period form.
   Coach copy distinguishes the existing keyword chat from that unwired calculator. It must not imply the backend
   lacks category reduction or promise goal impact (the endpoint returns null goal_impact).

## Follow-up: simplified Home (14 November 2026)

Supersedes the original Home mapping below. Home now presents one vertical surface:
Balance / Not available, Financial coach overview, text-only estimated day/week allowance,
then the Spending link. Goals are a secondary text action. Existing planning disclosures remain.
The balance is never sourced from spending or available funds. Coach overview uses the existing
read-only Coach POST with `Spending vs historical average`; its dated response is shown verbatim.
Missing comparison data gets a brief unavailable fallback. No new backend contract or calculations.

Follow-up verification: production build and diff check passed. Both customers showed their own
dated comparison, unavailable bank balance and unavailable allowances. Checked actual CSS widths
360/390 (scroll widths 345/375) without overflow. Replaced Home screenshots with these captures.
Home Ask Coach prefilled the comparison question and submission returned the backend explanation.
Created a Flexible test goal before planning and observed saved success. Home Spending link opened
the existing bar chart. The transient comparison fallback was observed during customer loading.
The test goal `UI follow-up test` remains only in the currently running local backend's memory.
Preview confirmation/advanced-field preservation were verified in the earlier pass below and were
not rerun for this Home-only follow-up. No physical-device or comparison-only failure injection.

Backend blockers: bank balance needs a contract with amount, currency, timestamp and clear current
versus historical semantics. Conversational budget planning, confirmed historical rent/food suggestions,
and category-reduction scenarios remain unsupported; no wizard or negotiation controls were added.
The existing Coach comparison supports Home today; a dedicated summary endpoint is optional.

Branch: `codex/s-mobiili-ui`. Base: `main` at `65e4e80`.
Implemented 14 November 2026. No backend edits, dependencies, main merge or deployment.

## Screen mapping

The supplied Home/Bank/Me references inform the white header, mint background,
green section headings, white cards, row actions, outline icons and fixed bottom navigation.
The goal references inform simple fields and a full-width green action, without copying
investment forecasts, screenshot balances, risk sliders or unsupported banking controls.

- Home prioritizes dated recorded spending, category/comparison routes into Coach, then allowances.
- Spending retains week/month bars and horizontal historical-average/optional chart-target lines.
  Latest-period categories are visible; historical periods and heuristic baskets remain expandable.
- Coach has English keyword suggestions, explicit rule-based labeling and existing goal previews.
  Home actions prefill the relevant question; the user submits it or chooses a suggested question.
- Goals remain optional and require only name, amount and Critical/Important/Flexible priority.
- Planning starts collapsed. Advanced period, chart targets and repetition also start collapsed.
  All inputs remain mounted in the form and are serialized in the full assumptions PUT.
  Blank and zero remain distinct. Hiding the form does not enable an unknown allowance.
- Account/mortgage information is secondary and collapsed. The concept disclaimer is always visible.

Goal-save success now remains visible if the follow-up explanation fails, in Goals and Coach.
This failure-path change was reviewed in source, but an analysis-only failure was not injected.

## Actual verification

Used an isolated backend on loopback port 8018 with existing local synthetic data and Vite on 5178.
Test-only goals/assumptions existed only in that process and were cleared by restarting it.

- `npm.cmd run build --prefix frontend`: PASS after final changes, 412 modules.
  Existing bundle warning remains: approximately 619 kB minified JavaScript.
- `git diff --check`: PASS.
- Actual CSS viewport widths checked through browser DOM: 360 and 390 pixels.
  Document scroll widths were 347 and 377 (scrollbar space); no horizontal overflow observed.
  Home and Spending visually inspected at both widths; Goals/Coach/planning interacted with at mobile widths.
  Fixed navigation stayed usable; scrolling reached forms and their actions.
- Both customers loaded real spending responses. Customer switch cleared goal view;
  a goal created for CUST04457 was absent for CUST00001.
- Created an Important goal before entering any planning inputs: saved successfully.
- Coach scenario: previewed a Critical goal with unavailable allowances, edited its name,
  verified confirmation disappeared, previewed again, and explicitly confirmed creation.
- Coach historical-average suggestion returned the backend's dated comparison explanation.
- Week/month chart switching worked; saved test chart targets appeared as 70/300 respectively.
- Full-object preservation: saved a test 45-day plan, repeat=true, both targets, accessible funds=0,
  and other amounts blank. Saved again with Advanced collapsed. GET assumptions retained every
  advanced field, explicit zero and nulls. Allowances remained unavailable.
- Stopped backend and reloaded: visible error, unavailable values and Retry.
  Restarted backend and pressed Retry: real spending/customer data recovered.

Screenshots are viewport captures of the real local UI, not mockups:
`home-360.jpg`, `home-390.jpg`, `spending-390.jpg`, `coach-390.jpg`.
The desktop browser scales its capture; filenames identify verified CSS viewport widths,
not JPEG pixel dimensions. Full-page capture cropped incorrectly, so viewport captures are supplied.

Not verified: physical phones, Safari, screen reader walkthrough, delayed-request races,
ambiguous POST failures, analysis-only HTTP failure, preview discard and switch during an in-flight save.
No backend test suite was rerun because backend code/calculations are unchanged.
No automated frontend test dependency was added; the checks above are browser walkthrough evidence.

## Backend/product requests

Reported to the project manager chat before implementation:

1. A read-only category-reduction scenario remains needed for the full core journey.
   Request a dated baseline, explicit category/period, Python-calculated reduction, uncertainty,
   and conditional goal/allowance impact without double-counting. No UI reduction control is exposed.
2. A dedicated additive spending-comparison summary would support comparison directly on Home.
   The existing Coach comparison remains available now; no arithmetic was moved into JavaScript.
3. General natural-language interpretation is absent. The UI honestly calls this rule-based;
   a future LLM must consume only necessary aggregated summaries and never write goals.

Ownership notice sent to the prior frontend chat and project manager before editing.
Changes are limited to `frontend/src/main.jsx`, `Coach.jsx`, `Icon.jsx`, `style.css` and this QA directory.
