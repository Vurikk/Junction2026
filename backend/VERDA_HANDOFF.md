# Verda Coach integration and reviewed smoke procedure

Status: implemented and mocked; paid mode has NOT been activated and no real provider call has been made.
The user changed the cumulative spending limit from USD 1 to **EUR 1.00** on 2026-11-14.
No frontend files, allowance policy, goals or existing data-coach contracts are changed.

## Verified model, currency and conservative token bound

- Exact supported `VERDA_MODEL`: `deepseek-4-1-flash-1017`.
- User's Verda Console screenshot shows **EUR 0.1336 input / EUR 0.5346 output per million tokens** for DeepSeek 4.1 Flash 1017.
  The currency symbol is euro; the originally reported USD denomination was incorrect. No FX conversion is performed.
- [Official model documentation](https://docs.verda.com/inference/models/deepseek-4-1-flash-1017/)
  identifies this model and its 1,048,576-token context and optional reasoning.
- [Verda compatibility documentation](https://docs.verda.com/inference/openai-compatibility/)
  defines `max_tokens` as the combined reasoning/output limit. Requests use `reasoning_effort: "none"` and `max_tokens: 256`.
- [Verda model API documentation](https://docs.verda.com/inference/models/) explains that Console prices are in account currency.
  Public USD prices are not substituted for the screenshot's EUR tariff.

Configuration must match that exact model and approved endpoint. Unknown models/prices/bounds fail closed.
Before any paid activation, review the Console prices again; approval lasts 24 hours and renewal never resets the ledger.

## Configuration and single paid deployment

Read from the PowerShell session that launches Uvicorn:

| Variable | Required value / behavior |
| --- | --- |
| `VERDA_INFERENCE_API_KEY` | Existing secret; backend only, never printed, returned, logged or saved by this code |
| `VERDA_BASE_URL` | `https://inference.verda.com/v1` (root `https://inference.verda.com` also accepted) |
| `VERDA_MODEL` | Exact ID above; no fallback to another model |
| `COACH_LLM_ENABLED` | Only literal `true` (case-insensitive) requests paid mode; default disabled |
| `COACH_LLM_BUDGET_EUR` | Explicit `1.00`, or a lower positive cent amount; maximum EUR 1 |
| `COACH_LLM_BUDGET_USD` | Read for migration detection only; never treated as euros or used to authorize calls |

The agent terminal cannot inherit variables set in a different PowerShell session. Never paste the API key into chat or commands here.
Adding `COACH_LLM_ENABLED=true` alone is insufficient: paid mode also requires the reviewed deployment and existing ledger below.

State is fixed outside all worktrees at `%LOCALAPPDATA%/SBankCoach/.coach_llm/` on Windows
(or `~/.local/share/SBankCoach/.coach_llm/` where LOCALAPPDATA is absent):

- `approval.json`: exact model, EUR rates, cap, token bounds, designated host fingerprint, review expiration.
- `usage.sqlite3`: cumulative reservations/charges, durable idempotency records and validated conversation selections.
- `instance.lock`: OS process lock; only one paid worker can use this deployment at a time.
- `smoke.json`: the controlled smoke's session cookie and request IDs, so repeating the command reuses the same request.

The app never initializes a ledger on startup. Missing/corrupt/mismatched state returns a free fallback.
Setup refuses to overwrite/reset an existing ledger, change its cap or migrate its identity silently.
A copied approval fails on a different host. All checkouts on the designated host use this same canonical state location.
Run **one Uvicorn worker** and one designated paid backend; other PCs must call that backend, never initialize independent paid ledgers.
SQLite is not a cross-PC account-wide billing service: independent operator-created deployments or Playground spending are outside this cap.
Do not copy the API key/approval to other PCs, delete the ledger, or reinitialize under another OS user to regain budget.
Private state and SQLite sidecars are gitignored; no raw records or prompts are persisted in this state.

## Budget, transport and request controls

Every provider call first atomically reserves its worst-case cost using `BEGIN IMMEDIATE` and integer pico-euros.
Input reservation is the **entire documented model context**, not an estimated chars/token count. This covers user text,
context, system messages, tools, aggregates, schema serialization and chat-template overhead. Output reserves all 256 allowed tokens.
At the reviewed rates, the single call per message reserves EUR **0.1402266112** before execution.
Actual complete token usage reconciles the reservation down; cached input is conservatively charged at the full input rate.
Missing/malformed usage, non-200 responses, disconnects, timeouts and crashes keep their full reservations.
Unpriced response models or usage exceeding reviewed bounds freeze subsequent spending for review.
No blind refund on errors, no daily/customer reset, no new ledger on restart, and no retries/redirects inside the provider client.

Limits: at most **one call per message**, **256 tokens per call**, **15 seconds total**, **one active message**,
**four new paid-path request attempts per browser session/minute**, and **twelve globally/minute**.
Rate receipts, request claims and reservations survive restarts. Byte limits bound outgoing payloads and incoming responses.
A crash after claiming a request leaves it in progress; replay falls back without another paid call. Manual review may be needed.
There is no explanation provider call; successful calculations produce their Python card and deterministic explanation locally.

## Privacy and grounding

The sole call can select exactly one of `category_spending`, `spending_comparison`, `category_reduction`.
Pydantic rejects extra arguments, invalid types, dates and percentages. Category/date/percentage must also match the
sanitized question or the same conversation's previous validated selection. No arbitrary function, URL, code or write tool exists.
Ambiguous selections and unsupported category/period calculations are checked locally before a paid request. They return
clarification or missing-data fallback without a provider call or reservation; valid requests still require model selection validation.

The language layer supports a constrained English financial vocabulary, dates and percentages. It rebuilds the question as
canonical JSON containing only intent, categories, period, dates, date_mode and percentages; original prose is never forwarded.
Names, IDs, email addresses, account details, URLs, arbitrary amounts, pasted data and uncertain language remain local.
The semantic projection, not a claim that regex identifies all personal information, defines the outbound boundary.
Finnish and unrestricted free-form language are not supported. See LANGUAGE_HANDOFF.md for examples and limitations.

Only canonical request slots and validated routing context go to Verda. Calculated financial facts are rendered locally.
No customer/account/goal IDs or goal names, transaction rows, merchant data, classifications, assumptions or full transcripts are sent.
Conversation context is only the previous validated tool selection; it expires after 30 minutes and is scoped to browser session/customer.
At most 32 conversation IDs are accepted per browser session. Durable request receipts remain for restart-safe deduplication.

Python renders every explanation with the summary first and all required coverage/hypothetical caveats. Model prose is rejected.
`mode: "llm"` means an LLM selected a validated tool and its calculation succeeded, not that the model generated financial advice.
Cards remain independent of their Python-rendered explanation. Provider failures use the local rule-based fallback.

## Additive Coach contract for the UI owner

`POST /api/customers/{id}/coach` still accepts `question` and optional existing goal `scenario`.
Adds optional `conversation_id` and `request_id`, both UUID strings (invalid UUIDs return 422).
Existing `kind`, `text`, `rows`, and goal-preview `preview`/`baseline`/`analysis` remain present with their existing roles.
Goal previews, goal/allowance questions, current balances and mortgages use the existing local engine, never Verda.

Every HTTP Coach response additionally contains:

```text
mode: "llm" | "rule_based"
fallback_reason: string | null
conversation_id: UUID string
request_id: UUID string
cards: [{type: "category_spending" | "spending_comparison" | "category_reduction", data: object}]
```

`cards` is empty when no approved function completed. A locally validated calculation remains present with
`mode: "rule_based"` if provider/timeout/budget/billing gates fail after preflight, or durable response caching fails.
Model-output validation failures do not expose the candidate card. Render valid returned cards independently of the mode label.
Card `data` fields are exact allowlists, not the full source endpoint objects:

| Card type | Data fields |
| --- | --- |
| category_spending | currency, category, period, source_period {start,end}, spending_eur |
| spending_comparison | currency, period, status, comparison, baseline, difference_eur, coverage |
| category_reduction | currency, category, period, source_period, reduction_percent, and the three amounts listed below |

For a category-spending breakdown, `category: "all"` adds up to five `categories` entries (`category`, `spending_eur`)
and `other_spending_eur`, the sum outside the displayed top five. Displayed amounts plus remainder equal `spending_eur`.
The generic displayed category `other` groups unknown source labels; it is distinct from the undisplayed remainder.

Reduction amount fields: `baseline_spending_eur`, `hypothetical_spending_eur`, `potential_reduction_eur`.
Comparison nested objects match `/spending-comparison`; reduction amounts/dates match `/category-reduction`.
Card currency is EUR. Dates are inclusive ISO dates, gross spending excludes transfers/refunds, and coverage is not guaranteed.
Category names normalize to lowercase. No goal impact, goal mutation, live balance or allowance progress is inferred.

Session/retry workflow:

1. Send an initial Coach request using same-origin credentials. It sets an HttpOnly, SameSite=Strict `coach_session` cookie
   scoped to `/api` (Secure over HTTPS). In paid-ready mode the first request returns `session_initialized`, with no provider call.
2. Reuse the returned `conversation_id`, retain the cookie, and assign one UUID `request_id` per new user message.
   Only with a supplied conversation ID can a request enter the paid path; otherwise it returns `conversation_required` for free.
3. Keep those IDs and the body identical for network retries. Completed duplicates return the saved result; concurrent duplicates
   return `request_in_progress`; reusing a request ID with a different body/conversation returns `request_conflict`.
4. A new follow-up uses the same conversation and a NEW request ID. For example, "What about 10%?" keeps category/month.
5. On customer change, use a NEW conversation ID. Reusing another customer's or browser's conversation returns `conversation_mismatch`.

If request_id is omitted with a stable conversation ID, the backend derives one deterministically from conversation/question;
identical questions return their previous result. Supply a new explicit ID for a deliberately new turn.
Legacy clients that omit conversation IDs remain usable through the free rule-based path. No frontend changes were made here.

Safe fallback reasons (codes only; provider messages/credentials are never returned):

- Setup: `disabled`, `missing_configuration`, `euro_budget_required`, `invalid_budget`, `review_required`,
  `unverified_model`, `unapproved_endpoint`, `deployment_mismatch`, `pricing_review_expired`, `instance_busy`, `ledger_mismatch`.
- Session/control: `session_initialized`, `conversation_required`, `conversation_mismatch`, `session_limit`,
  `request_conflict`, `request_in_progress`, `duplicate_call`, `rate_limited`, `concurrency_limit`.
- Processing: `privacy_blocked`, `goal_preview`, `unsupported_topic`, `clarification_needed`, `unsupported_period_or_category`,
  `invalid_model_output`, `context_limit`, `timeout`, `provider_error`, `ledger_unavailable`, `budget_exhausted`, `billing_uncertain`.

Fallbacks are normal HTTP 200 Coach responses. Existing unknown-customer and input validation errors remain 404/422.
Treat the free session bootstrap separately from a new paid user turn; do not retry other failures automatically with a new request ID.

## Review and one controlled live smoke test — NOT executed by the agent

After manager review, in the SAME configured PowerShell session on the ONE designated backend computer:

```powershell
$env:COACH_LLM_BUDGET_EUR = '1.00'
# Existing VERDA_INFERENCE_API_KEY stays in this terminal; do not print it.
# Verify existing VERDA_MODEL equals deepseek-4-1-flash-1017 and VERDA_BASE_URL matches the documented endpoint.
.venv/Scripts/python.exe -m backend.verda_setup --show-host
```

Record/approve that host fingerprint. Recheck the EUR prices in the Console, then run (replace the placeholder):

```powershell
.venv/Scripts/python.exe -m backend.verda_setup --approve-paid --designated-host APPROVED_HOST_FINGERPRINT --confirm-eur-prices 0.1336 0.5346
$env:COACH_LLM_ENABLED = 'true'
.venv/Scripts/python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8011 --workers 1
```

Use the existing `SBANK_DATA_DIR` for the supplied datasets. Do not start another paid worker or stop the interactive demo without coordination.
In another terminal, from this checkout, the **one controlled smoke command after review** is:

```powershell
.venv/Scripts/python.exe -m backend.verda_smoke --port 8011 --confirm-paid
```

It bootstraps a browser session for free, then submits one message about Restaurants in July 2026 for CUST04457 at 20% reduction.
Expected card: baseline EUR 95.04, hypothetical EUR 76.03, potential reduction EUR 19.01. Maximum one paid provider call.
The script saves its session/request identity before the paid request; repeating the command replays that identity, not a new paid turn.
It prints only mode, safe fallback reason and aggregate cards. A fallback is not automatically retried with new IDs.
Inspect cumulative reserved/charged euros using `python -m backend.verda_setup --status` with COACH_LLM_BUDGET_EUR still set.
To disable after review/testing, stop that instance and relaunch with `COACH_LLM_ENABLED=false`; retain the ledger unchanged.

## Verification

Normal tests force paid mode off or inject httpx.MockTransport, even if launched from the configured terminal.
No test contacts Verda, initializes a real approval, or uses the real key. Synthetic keys in tests are fixed dummy strings.
Run the existing modules plus `backend.test_verda` with the original datasets available:

```powershell
.venv/Scripts/python.exe -m unittest discover -s backend -p "test_*.py" -v
```

Original delivery: 49 tests passed. Combined integration on 2026-11-14: **83 tests passed** with paid mode forced off,
both original datasets and mocked provider transport, including language, single-call and routing regression coverage.
Coverage includes all three selections, follow-up preservation, browser/customer isolation, privacy rejection,
invalid tools/arguments/numerical prose, errors/timeouts, deterministic cards surviving provider/budget failure, concurrent near-cap reservations,
restart persistence, missing usage, model/bound violations, OS instance locks, global/session limits, duplicates and legacy compatibility.
Real provider behavior remains unverified until the single controlled live smoke test is reviewed and explicitly run.
