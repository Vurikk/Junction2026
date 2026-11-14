# Verda popup integration checks

Integration branch frontend changes only. No paid calls, provider credentials or backend edits by the UI workstream.

## Behavior

- The popup and navigation design are retained. Its heading is neutral; each answer states AI-assisted/Python calculations
  or rule-based explanation from the returned mode. Legacy answers remain labelled rule-based.
- Each mounted customer owns an in-memory session helper. The existing customer key resets it on profile change;
  closing/reopening the popup retains the same conversation, draft and messages.
- The first send performs a free bootstrap without a conversation ID, then sends the original user question once with
  the returned conversation ID and a new request UUID. Bootstrap text is not inserted into the visible conversation.
- Follow-ups reuse the conversation ID. Explicit retry keeps exactly the same request body/UUID and does not add
  a second user message. Successful retry replaces an earlier answer associated with that turn rather than duplicating it.
- Only the explicit free `session_initialized` result triggers one bounded automatic replay with identical body/UUID.
  Provider errors, timeouts, budget/rate limits and conversation mismatch never create automatic new paid turns.
  An expired cookie can produce conversation mismatch because the server binds history to its old browser owner;
  the UI explains that a new profile conversation is needed, rather than bypassing isolation silently.
- Same-origin credentials retain the HttpOnly cookie. Abort-ignoring bootstrap results cannot initiate a paid turn after unmount.
- Three result-card types render exact API values. `category_spending` supports `all`, top categories and remaining categories.
  Historical dates and hypothetical reduction wording remain visible. Null and zero remain distinct.
- A category-reduction result has kind=scenario but no goal preview: it no longer accidentally opens the add-goal form.
  Existing explicit goal preview and creation remain separate and require confirmation.

## Automated verification performed

Commands from this worktree:

```text
node frontend/qa/check-coach-session.mjs
node frontend/qa/check-coach-cards.cjs
node frontend/qa/check-home.cjs
npm.cmd run build --prefix frontend
```

All passed. Session fixtures cover initial bootstrap, follow-up conversation IDs, explicit retry identity,
customer-scoped helpers, abort-ignoring bootstrap, scenario payloads, legacy responses, provider fallback and cookie expiry replay.
Card static rendering covers aggregate ranking/remainder, exact amounts, zero, unknown, dates and caveats.
The production build retains the pre-existing large bundle warning.

The worktree uses a local ignored node_modules junction to the already-installed root frontend dependencies;
no dependencies or lockfiles changed.

## Not verified in this pass

No browser automation, physical mobile keyboard test, actual goal save submission, live Verda smoke or fresh mobile screenshots.
Popup focus/layout/scroll behavior is unchanged from the UI branch, but needs a combined browser smoke after backend integration.
New request tests exercise the session transport directly; they are not a claim of full React/browser interaction coverage.
No paid activation or main merge is included.
