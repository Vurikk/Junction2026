# Coach language handoff

Base: c3da04b6bb8ce453ce9d6c5f3f899adc77e8190c
Branch: codex/coach-language
Implementation commit: d718cab8c3e27d46d269f5d042e06436c2a098da
Status: implemented and verified; no paid calls, activation or merges.
Final verification on 2026-11-14: **62 backend tests passed**, including **13 focused language tests**.
The subsequent documentation-only commit records this implementation hash and the review handoff.

## Contract recorded before implementation

The seven imported names and their call signatures remain unchanged. sanitize_question still returns a string,
but the string is rebuilt from approved semantic slots, never the original user prose. selection validates that
canonical request against the proposed tool arguments. Existing single-category cards remain unchanged.

For the requested bounded ranking, category_spending accepts the reserved category value `all` using its existing
string argument. Its card retains type=category_spending, currency, period, source_period and spending_eur, and adds
categories (up to five {category, spending_eur} entries) plus other_spending_eur. Python calculates and ranks totals.
Unknown dataset category labels are collapsed locally to `other`; merchant/free-text labels never reach the provider.
The category=all card is a dated recorded breakdown, not a recommended budget. Consumers can always use facts_for.
No changes are required to coach_llm.py's function calls or existing tool-to-kind mapping.

Undated overall breakdowns use the latest complete recorded month and explicitly label it in Python facts.
Single-category questions need an explicit period or validated prior context. Relative `last month/week` resolves
against the current Europe/Helsinki calendar and fails if that exact period is unavailable. Existing comparison
supports only the latest complete recorded period; incompatible explicit/relative comparison dates require clarification.

The orchestration owner should note that the base service labels all sanitizer exceptions privacy_blocked and its
clarification message is generic. Ambiguities are retained as canonical requests and rejected with clarification_needed
by selection; a model's missing/invalid tool call cannot override that check. No fallback-policy changes here.

## Implemented language boundary

`sanitize_question` returns a canonical JSON **string** with exactly these fields:
`intent`, `categories`, `period`, `dates`, `date_mode`, `percentages`.
Only enum-like intent/category values, validated ISO calendar dates and bounded-format percentages are projected.
The provider never receives the original sentence, accepted filler words, names, IDs, pasted records or arbitrary strings.
The caller can continue placing this string in its existing `question` field without changing function signatures.

The local vocabulary gate is deliberately conservative, but is not the privacy guarantee by itself. Regex and vocabulary
cannot prove that arbitrary text contains no personal information. Privacy relies on rejecting uncertain input and rebuilding
only the small reviewed financial representation; residual numbers, unknown words, record syntax and unknown context fields
are never copied through. A user can still express private information using an allowed financial date/category/percentage;
this is not a universal PII classifier and should not be advertised as one. No names, arbitrary identifiers or raw records
have an outbound field. Allowed dates are needed to identify the requested financial period.

Routing context contains only validated prior tool arguments, latest complete period bounds, approved generic categories,
and `calendar_today` in Europe/Helsinki. Extra prior-argument fields invalidate that context; extra top-level fields are dropped.
All provider-selected tool names and arguments must match the locally interpreted request. A provider cannot change the
category, date, percentage or operation, add arguments, invoke a write tool, or turn ambiguous food into a guessed category.

## Supported questions

- Overall recorded category breakdown: “Where does most of my money go?”, “What are my biggest expenses?”,
  “How are my expenses split?”, “Show my spending by category.” Without dates or prior dated context, this explicitly uses
  the latest complete recorded month. With validated prior context, its period is retained. Python states the exact date range.
- Single category: “How much did I spend on eating out in April 2024?”, “Show my dining costs for 2024-04.”
- Overall comparison: “How does my monthly spending compare with usual?”, “Compare my overall spending.”
  This reuses the existing latest-complete-period versus earlier-period average calculation.
- Reduction: “What if I reduce restaurant spending in April 2024 by 20%?”,
  “Could I cut back on dining out by 20 percent during Apr 2024?”, “Lower restaurant expenses by 20% in 2024-04.”
- Follow-up: “What about 10% instead?”, “Could I cut that by 10 percent?”, “And with 10% less?”
  Category and dated period must come from validated prior context; an explicit new date overrides that context.
- “Could I spend less on food?” is accepted as a financial request but requires clarification unless prior context resolves
  groceries versus restaurants, period and reduction percentage. An unrelated housing context cannot resolve food.
- “What if I reduce restaurant spending by 20%?” requires a recorded period or a validated prior period.

English month names/abbreviations with year and ISO YYYY-MM / YYYY-MM-DD are supported. Weeks use Monday starts.
`last month` and `last week` refer to the actual preceding Helsinki calendar periods, including year rollover.
Missing coverage for that exact period fails locally; stale historical data is never silently substituted.
`latest recorded month/week` explicitly opts into historical coverage. Partial periods remain unsupported.

## Card and ranking semantics

Single-category and comparison cards retain their existing shapes. Only category=all adds the bounded breakdown fields:

```json
{
  "type": "category_spending",
  "data": {
    "currency": "EUR",
    "category": "all",
    "period": "month",
    "source_period": {"start": "2024-04-01", "end": "2024-04-30"},
    "spending_eur": 28.07,
    "categories": [
      {"category": "other", "spending_eur": 7.01},
      {"category": "travel", "spending_eur": 6.01},
      {"category": "health", "spending_eur": 5.01},
      {"category": "utilities", "spending_eur": 4.01},
      {"category": "housing", "spending_eur": 3.01}
    ],
    "other_spending_eur": 3.02
  }
}
```

These are synthetic test aggregates, not demo customer data. `other` is a group of unrecognized category labels.
`other_spending_eur` is the sum of groups outside the top five, including `other` if it does not make the top five.
Displayed categories plus that remainder equal spending_eur. Ranking uses descending Decimal totals, with category-name
ordering for ties. Existing spending_rows/total_amount exclusions and rounding are reused; no financial formulas changed.
No spending produces an empty categories list and zero total, with the existing incomplete-coverage caveat.
No amount is interpreted as future income, confirmed savings, a new allowance, or a goal mutation.

## Limits and coordination notes

- English is a constrained financial language, not unrestricted chat. Unknown words, merchant-specific questions, free-text
  personal details, arbitrary monetary amounts and pasted transactions stay local. **Finnish is not supported**, including
  unaccented Finnish; safe Finnish interpretation needs a separate language review and tests.
- Missing years, multiple dates/categories/percentages, mixed weekly/monthly requests, current/future periods, negation,
  percentage points, increases, and “reduce to 20%” require clarification or local rejection. Unsupported wording may be
  rejected even when harmless; the backend does not guess how to strip potentially sensitive text.
- Comparison remains overall spending for the latest full recorded period. Category-specific comparison or other requested
  comparison periods require clarification; no comparison API or financial formula changed.
- The base orchestrator's clarification text is generic. It does not yet ask specifically “groceries or restaurants?”
  Its pre-existing rule-based dispatch may intercept weekly wording as an allowance question. The language layer cannot
  override that without changing another owner's file; use explicit monthly examples for the current end-to-end demo.
- Ambiguity is checked before validating the returned model call. With the base orchestrator, that still happens after
  the routing call. Unknown/sensitive vocabulary is rejected by sanitize_question before any provider request.
- Existing fallback policy, ledger, EUR 1 cap and transport were not changed. The base two-call orchestrator remains in
  this branch; the other agent owns its replacement. The focused outbound test mocks both possible calls without requiring
  a fixed call count. facts_for still returns a dict of Python-authored fact strings and rendered_explanation remains available.
- No provider behavior or unconstrained model language quality was tested live. All paid traffic was mocked; paid mode is off.

## Verification

Commands from the backend checkout (with the existing local demo dataset path configured for the full suite):

```powershell
.venv/Scripts/python.exe -m unittest backend.test_coach_language -v
.venv/Scripts/python.exe -m unittest discover -s backend -p 'test_*.py' -q
```

Focused coverage: 13 tests with varied paraphrase subcases; category spending, overall comparisons, reduction, dated follow-ups,
food ambiguity, invalid/multiple dates, real-calendar relative dates, partial history, zero spending, Decimal ranking/remainder,
unknown-label privacy, tainted prior context, pasted identifiers/records, prompt injection, unsupported tools/arguments,
no source mutation, and mocked outbound projections. Existing shared tests are unchanged.
