# Backend readiness for UI integration

Date: 2026-11-14 (Europe/Helsinki).
Owner: existing backend chat. Branch: `codex/coach-backend-readiness`.
Base: `0e43cbd74cbae8a5698dd4499abcbb5b093e4b61` (`origin/codex/verda-integration`).
Original readiness status: compatibility checks passed before the later independent QA findings.
Follow-up: QA-01/02/03 are now fixed on this branch; see [QA_FIX_HANDOFF.md](QA_FIX_HANDOFF.md) for scope and 98-test evidence.
No paid activation or new provider calls during either task.

## Ownership and integration boundary

This branch owns only the new browser-contract regression tests and this handoff unless a concrete backend bug is verified.
Frontend implementation belongs to the UI chat; QA and manager handoffs remain theirs.
No API changes are required to connect this backend. No frontend files, financial policy, ledger or transport changes here.
The current Vite configuration already accepts `SBANK_API_TARGET`, defaulting to `http://127.0.0.1:8000`.
Use frontend `/api` requests through that proxy, with same-origin cookies; do not point browser requests directly at another port.
Avoid switching between localhost and 127.0.0.1 midway through a conversation because browser cookies are host-specific.

## Recorded live evidence, not a new test authorization

The user supplied a successful live smoke screenshot for the base integration:
`mode=llm`, `fallback_reason=null`, CUST04457 restaurants July 2026 at 20% reduction:
baseline EUR 95.04, hypothetical EUR 76.03, potential reduction EUR 19.01.
The screenshot ledger status was EUR 0.0001769058 charged/reserved against the EUR 1 cap.
The supplied smoke script stopped its temporary backend and disabled paid mode afterward.
Do not repeat that smoke or create more live questions without explicit authorization.
The old VERDA_HANDOFF.md statements that live behavior is unverified predate this user-supplied evidence.
Read-only budget status on this verification run still reports EUR 0.0001769058: no additional spend/reservation.

## Browser contract checks

New `backend/test_coach_browser_contract.py` uses synthetic customers, httpx.MockTransport and a disposable ledger:

- HTTPS cookie is HttpOnly, Secure, SameSite=Strict and scoped to `/api`.
- First bootstrap returns session_initialized; a later bootstrap without conversation ID returns conversation_required.
  Neither creates a paid request claim, reservation or provider call.
- If the cookie disappears after a completed turn, the next request establishes a new browser session for free.
  Reusing the old conversation then returns conversation_mismatch; it never repeats the provider call or exposes the old card.
  UI should explain this and offer an explicit new conversation, not silently assign new IDs and resend a paid question.
- A provider-error response with a valid Python card survives a service restart and an identical HTTP retry.
  The cached response and uncertain reservation are preserved; retry makes no extra provider call.

## Local configuration

Existing interpreter: `C:\Users\vanal\.codex\worktrees\a308\Junction2026\.venv\Scripts\python.exe`.
Dataset directory is selected with `SBANK_DATA_DIR`; use the existing supplied local synthetic-data directory.
Never copy data or provider credentials into the checkout or frontend environment.
Preparation and test commands must explicitly set `COACH_LLM_ENABLED=false` even if the parent terminal was configured for Verda.
For UI verification, launch a separate free loopback backend with one worker and point Vite's SBANK_API_TARGET at that port.
Do not stop unrelated servers or reuse an unknown server that might have paid mode enabled.

Example paid-disabled launch from this checkout, after confirming port 8011 is free:

```powershell
$env:COACH_LLM_ENABLED = 'false'
$env:SBANK_DATA_DIR = 'C:\Users\vanal\Documents\junction2\Junction2026\backend\Data'
& 'C:\Users\vanal\.codex\worktrees\a308\Junction2026\.venv\Scripts\python.exe' `
    -m uvicorn backend.main:app --host 127.0.0.1 --port 8011 --workers 1
```

In the UI agent's own frontend terminal set `$env:SBANK_API_TARGET = 'http://127.0.0.1:8011'` before starting Vite.
If that backend port is occupied, choose another free loopback port in both commands. Do not change existing server processes.
This free backend validates connectivity and rule-based UI behavior. LLM success/error UI paths require the existing mocks;
turning paid mode off does not emulate an LLM-selected card. No permanent test server was left running by this task.

## Verification results

- Existing full integration suite: **83 passed** (`unittest discover -s backend -p 'test_*.py' -q`, before adding the new file).
- New browser-contract suite: **3 passed** (`unittest backend.test_coach_browser_contract -v`).
- **86 passing tests across those two runs**; normal tests use mocks or disabled paid mode.
- Actual supplied demo data loaded locally with disabled paid mode; `/api/health` returned ok and Coach returned
  mode=rule_based, fallback_reason=disabled. Provider object was absent.
- Python preflight (no provider) checked both exact restaurant-reduction scenarios:

| Demo customer | Recorded month | Reduction | Baseline EUR | Hypothetical EUR | Potential reduction EUR |
| --- | --- | --- | --- | --- | --- |
| CUST04457 | July 2026 | 20% | 95.04 | 76.03 | 19.01 |
| CUST00001 | September 2026 | 20% | 225.70 | 180.56 | 45.14 |

- No frontend/browser visual verification is claimed here; that belongs to the UI and QA chats.
- No merge, new provider traffic, credential access, raw-data copying, goal/allowance policy change or real ledger reset.
- The installed FastAPI test client emits an existing Starlette/httpx deprecation warning; tests pass. No dependency changes made.
