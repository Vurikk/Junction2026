# Guided savings and goal conversations

Backend branch codex/coach-backend-readiness; UI branch codex/demo-coach-prompts-ui. No merges.

## Why
The prior free-text router demanded complete category/date/percent inputs and could not carry arbitrary clarifications.
Guided coaching supplies clear choices, retains dated context in the browser and uses existing Python finance data.
The app must label it Guided coaching, without pretending a model generated these conversations.

## Backend
- New GET savings-opportunities contract in API.md provides the same bounded calculation as the existing local savings answer.
- Month is explicit or visibly defaults to the latest full recorded month. Missing/partial data never silently substitutes.
- Fixed candidate scope: restaurants, entertainment and travel purchases. Necessary meals/travel may not be reducible.
- User chooses a category and percentage; Python supplies every amount. No state writes or provider calls.
- Goal-analysis explains the existing plan: protected bills/reserve, critical-first allocation, conditional repeating capacity,
  missing inputs and unknown actual progress. Historical reductions never get added to future capacity or saved balances.
- Actual goal creation remains the existing explicit preview/confirm flow. No changes to formulas, paid transport or ledger.

## Manual walkthrough
1. Open Coach and choose What could I save on? Read the displayed recorded month and candidate limitations.
2. Choose a category, compare 10%/20%, and explore whether that change is realistic. Necessary spending stays protected.
3. Choose Could this help my goals? Inspect confirmed-plan analysis; do not present hypothetical cuts as cash already available.
4. With no goals, use Preview a new goal and confirm only if desired. With missing plan inputs, confirm them on Home.
5. Review priorities and the difference between funded-in-horizon and conditional-on-repeat outcomes.

## Limitations
Guided choices are curated, not unrestricted natural-language understanding. Categories and historical coverage are limited.
No connection from a historical category cut to the future planning horizon is established, so goal benefit is not quantified.
Existing goals/assumptions are in memory; new isolated backend processes start with empty user state.
No paid requests are used for verification. The existing cumulative euro ledger must remain untouched.

Verification: 119 backend tests passed. Independent offline HTTP QA found no blocker in exclusions, date/percentage handling, privacy, state immutability or goal priority/repeat semantics. Preview backend8032 and frontend5194 are loopback only with paid mode disabled; existing servers were left untouched.

Plan persistence update: preview8032 now configured with SBANK_PLAN_STATE_PATH=C:/Users/vanal/AppData/Local/SBankCoach/plans.sqlite3. Existing nonempty confirmed inputs migrated, unknown defaults not marked saved; existing goals restored across this deployment but remain in-memory. Latest full backend suite:127 tests pass, including restart survival, customer isolation and invalid-save preservation. No billing ledger accessed or reset.
