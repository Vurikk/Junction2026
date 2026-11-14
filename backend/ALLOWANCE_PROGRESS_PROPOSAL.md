# Spending-allowance bar proposal

Status: proposal for review only, 2026-11-14. No financial policy or existing API contract is changed.
Recommendation for this deadline: keep the confirmed estimate and a neutral track. Do not label it "remaining" yet.
A dated historical replay is possible after explicit scenario confirmation, but is not evidence of money available today.

## 1. Calculation and date semantics

Use a frozen, confirmed plan, not a repeatedly recalculated balance. Call the result **Remaining in plan**,
not current account balance or guaranteed safe-to-spend cash. The engine still requires all six confirmed amounts.

At plan activation, snapshot the inputs and actual goal allocations from the existing Python engine:

- `A = max(0, available funds + additional income - essential bills - reserve - actual goal allocations)`.
- `D = floor_to_cents(A / horizon_days)`, matching the existing daily estimate.
- A day has a nominal allowance `D`; a week has `D * k`, where `k` is calendar days inside both week and plan.
  Sub-cent division residue stays unallocated; do not reconstruct `A` from the rounded daily estimate.
- For each displayed window, let `P` be eligible spending since activation but before that window.
  Starting allowance `B = min(D * k, max(0, A - P))`. This horizon cap prevents earlier spending freeing extra money.
- Let `S` be eligible spending inside the displayed window up to the explicit observation cutoff.
  `remaining = max(0, B - S)`, `overspent = max(0, S - B)`.
- Remaining-fill fraction is `remaining / B` when `B > 0`, clamped to 0-1 and calculated in Python.
  When `B = 0`, fill is null: show zero remaining and any overspend, with a neutral track. Never divide by zero.

Today and Week are two views of the same ledger, not additive pots. Week means Monday-Sunday, clipped to the horizon.
Unused day/week allowance does not roll into a larger next-period nominal allowance. Overspending remains in the horizon ledger.
These are explicit pacing rules proposed for approval, not behavior already supported by `/budget`.

**Which spending counts:** posted negative `purchase` transactions from the covered accounts after activation.
Housing/utilities and other bills already reserved in the essential-bills input must not reduce this pot again.
Purchases already represented in protected bills must also be excluded explicitly; the current model has no such mapping.
The minimum supported case requires confirming this overlap does not exist. Otherwise tracking needs review, not a guessed exclusion.
Transfers, investments, income and refunds do not replenish or consume this purchase envelope; use gross purchases initially.
Unexplained outflows, protected-bill overruns or changed income/goal assumptions require review rather than silently claiming safety.
This is not a bank-balance reconciliation engine; the existing liquidity confirmation remains necessary.

**Anchor:** a confirmed `start_date` at 00:00 in `Europe/Helsinki`, ending at midnight after `horizon_days` calendar days.
Today is the calendar day containing `as_of`; Week is its calendar week. Windows are start-inclusive/end-exclusive.
DST changes hours, not the count of calendar days. No automatic renewal and no Today/Week after the horizon expires.
For live activation mid-day, start tomorrow; don't attach a current balance to today's midnight and subtract earlier purchases.
Existing undated plans are ineligible until a dated opening-funds snapshot is explicitly confirmed.

**Double-counting guard:** opening funds must correspond to the anchor, with covered accounts and a source cutoff/checkpoint.
Never substitute a later closing balance and then deduct earlier transactions, or add income already included in opening funds.
Only transactions after the opening checkpoint and within the plan are counted, once, using stable source identity.
Do not silently refresh opening funds from a newer balance. Replanning is an explicit new version with a new checkpoint;
old deductions are never replayed against its updated opening funds. Goal/input changes invalidate tracking until reviewed.
A live bar also requires a feed completeness watermark through `as_of`; the date of the last transaction is not that watermark.
With unknown completeness, balances, overlap or checkpoint, remaining/fill are null rather than treating missing spending as zero.

## 2. Minimal additive API proposal

Leave `/budget`, `/assumptions`, `/recorded-balances`, comparisons and suggestions unchanged.
Coordinate these proposed names with the UI owner before implementation.

A separate explicit activation action would store the existing confirmed input/goal snapshot plus:
`plan_id`, `start_date`, `timezone`, covered accounts, opening-funds checkpoint and `mode` (`live` or `historical_demo`).
A demo must record that opening funds and future amounts are scenario assumptions, not confirmed current funds.
No GET or suggestion activates a plan. No dates or checkpoints are inferred from an existing assumptions PUT.

Proposed read: `GET /api/customers/{id}/allowance-progress?period=day|week`.
For live mode, the server supplies now; a demo uses its explicitly selected replay cutoff, never today's date.

| Response fields | Meaning |
| --- | --- |
| `plan_id`, `mode`, `status`, `reason` | Status: tracked, historical_demo, unavailable, requires_review, or expired |
| `currency`, `timezone` | EUR and the declared calendar timezone |
| `plan_start`, `plan_end`, `period_start`, `period_end`, `as_of` | ISO timestamps with offsets; exclusive ends |
| `source_complete_through`, `completeness_guaranteed` | Verified source watermark or null; never max transaction date |
| `starting_allowance_eur`, `spent_eur`, `remaining_eur`, `overspent_eur`, `remaining_fraction` | Python results; nullable |

When unavailable/requires-review/expired, do not supply an actionable remaining amount or fill.
The UI can retain the existing `/budget` estimate separately, labelled Estimated per day/week, with a neutral track.
Historical-demo amounts mean "remaining against recorded purchases in this simulation"; show date and incomplete-source notice.
A normal current-day partial interval is valid only with complete ingestion through `as_of`; missing source coverage is different.

## 3. Required choices and historical feasibility

For tracking: confirm the six existing amounts for the same dated horizon, opening accessible funds/checkpoint/accounts,
protection-versus-purchase scope, and liquidity. Do not introduce another mandatory form just to display an estimate.
Reserve and maximum goal contribution remain user preferences; historical observations never confirm them automatically.

Dataset audit: both profiles have one observed account, populated balances/timestamps and matching transaction/timestamp dates.
No duplicate account/timestamp pairs were found, but neither file supplies a stable transaction ID or completeness guarantee.
Merchant ID is not transaction identity. A live incremental ledger therefore needs stronger ingestion support.
A fixed-file replay can process an immutable file snapshot once using its row identity; do not deduplicate by amount/date/merchant.
Source timestamps lack a timezone, so Helsinki interpretation must be declared as a demo assumption.

Both files cover **3-9 August 2026** and contain August purchases (13 and 26 respectively).
This is a possible shared historical week, not proof of seven days of complete records or known opening-midnight funds.
A replay requires an explicitly chosen historical opening-funds scenario and six reviewed scenario inputs; no automatic backfill.
Use only pre-anchor observations to suggest forecasts; later records are replayed spending, not hindsight-confirmed future income.
The user selects a dated replay cutoff. Label it "Demo day: [date]" / "Demo week: 3-9 Aug 2026", never current Today/Week.
The file can support this qualified simulation; it cannot support a trustworthy live remaining-budget bar today.

## 4. Acceptance tests before implementation is released

| Case | Required result |
| --- | --- |
| Zero allowance, no spending | Remaining 0, overspent 0, fraction null; no NaN or division error |
| Zero allowance with purchases | Remaining 0, positive overspend, neutral track |
| B=100, S=120 | Remaining 0, overspent 20, fill 0; no negative width |
| B=100, S=25 | Remaining 75, fill 0.75; day/week reuse the ledger without adding pots |
| Prior spending nearly exhausts horizon | Window starting allowance is capped at unspent horizon funds |
| Partial week/horizon, DST, expiry | Calendar clipping; no automatic renewal or arbitrary seven-day multiplier |
| Missing/delayed source coverage | Remaining/fill null; last recorded transaction is not a completeness watermark |
| Balance includes an earlier purchase | That purchase is not deducted again; later balance cannot silently replace opening funds |
| Bills, transfers, refunds, repeated ingestion | No bill double-deduction, no refund refill, no duplicate transaction counting |
| Purchase/bill overlap or changed plan/goals | Requires review; frozen historical allocation is not silently rewritten |
| Historical replay vs live plan | September/August records never reduce today's allowance; explicit demo dates and assumptions |
| Unknown vs explicit zero; customer isolation | Unknown remains unavailable; zero is valid; previews do not mutate either customer's state |

No implementation or runtime tests were added for this proposal. Existing 28-test evidence covers the unchanged backend only.
