# S-mobiili-inspired coaching UI

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
