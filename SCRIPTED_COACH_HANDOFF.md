# Scripted Coach demo

One agent implemented this at the user's request. New Coach never calls an LLM or provider.
Candidate: codex/scripted-coach; backend base1441e0a plus reviewed frontend518b842. No branch merges.
Friend latest work inspected: backend2cc7d04/UIafcc79e/QAfbc27bd. Reused savings_demo.py from2cc7d04.

Six preset questions: savings ranking, category breakdown, goals, comparison, extra spending, everyday tips.
Follow-ups retain exact month/category;10%/20% math in Python. Goal timings explicitly conditional on continuing
the historical monthly allocation from no known saved progress. Zero allocation has unknown completion time.
No free-text LLM input. Dedicated read-only POST guided-coach never touches goals, assumptions or paid ledgers.

Validation:14 tests,13passed/1original-data skip; new3guided tests rerun passed. Includes no-LLM guard,
state preservation, exact amounts, follow-up, missing data, invalid requests and customer isolation.
Production build passed (existing bundle warning). Actual browser savings/follow-up/goals/no-goals verified.
Screenshot frontend/qa/scripted-coach.jpg. Latest replies scroll to their beginning; popup opens expanded.

Preview5200->8040 paid-disabled; copied existing app goals/assumptions from8030, original untouched.
No credentials/ledger/raw dataset copied. Existing data read in place. No push or main merge.

## Monthly category chart

Overview replies now render a horizontal category chart from the existing Python rows: top five plus remainder,
exact EUR labels and recorded month. Other replies keep their existing result format. No financial arithmetic or
LLM path added. Accessible chart description and expandable amount table included; unknown/empty rows remain explicit.
Question menu collapses after each successful answer so the chart fits the mobile popup, with Ask another question to reopen.
Production build/diff checks passed. Actual browser verified August2026 total1974.07 and six bars with exact values,
and question-menu open/close. Screenshot frontend/qa/coach-monthly-categories.jpg. Preview remains5200, no backend restart.
