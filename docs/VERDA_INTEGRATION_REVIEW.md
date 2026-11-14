# Verda integration review

The `codex/verda-integration` branch combines the existing popup UI with
`codex/coach-language` and `codex/coach-single-call`. Main is not modified.

## Scope

- Update shared tests to the single-provider-call contract without removing safety assertions.
- Fix weekly spending being intercepted as allowance and clarify missing scenario inputs locally.
- Connect popup conversation IDs, retry IDs, result cards and honest mode labels.
- Preserve the EUR 1 cumulative budget, provider configuration gates and explicit goal confirmation.

No paid provider calls, approval initialization or real credentials are needed for integration tests.
The current model only selects a validated financial tool. Python renders the explanation.
English financial requests are constrained; unrestricted chat and Finnish remain unsupported.

## Integration checks

Run backend discovery with the existing original data directory supplied by `SBANK_DATA_DIR`,
`COACH_LLM_ENABLED=false`, and the existing virtual environment interpreter.
Run the frontend production build and focused session/retry/card tests.
Provider responses in tests must be mocked, with no real Verda requests.

Verified 14 November 2026: 83 backend tests passed against synthetic fixtures and the original two demo profiles.
Frontend session/retry and result-card checks passed; production build passed with the existing bundle-size warning.
The manager independently reran frontend checks/build; the backend integration agent ran full discovery.
No fresh browser/mobile walkthrough or live Verda smoke test is claimed for this integration.
Cookie expiry preserves customer/session isolation: the UI may request restarting the conversation by switching profiles.

## After integration

Review test evidence before merging into main. On the single designated paid backend host,
follow `backend/VERDA_HANDOFF.md` for explicit EUR-price verification, persistent ledger setup
and one controlled smoke test. A passing mocked suite is not evidence of live provider compatibility.
Do not delete or reset the ledger, silently enable paid mode or create a second paid deployment.
