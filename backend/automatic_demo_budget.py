"""Automatic retrospective cash-flow scenario with explicit app policies, never current affordability."""
from datetime import date
from decimal import Decimal, ROUND_DOWN

from .data_coach import INCOME_TYPES, complete_windows, in_window, total_amount
from .financial import PAYMENTS, PRIORITIES, money, spending_rows


def automatic_budget(customer, goals, as_of=None):
    checked = as_of or date.today()
    windows = complete_windows(customer, "month", checked)[-3:]
    rows = customer.get_transactions()
    earnings = rows[(rows.tx_amount_eur > 0) & rows.transaction_type.isin(INCOME_TYPES)]
    spending = spending_rows(customer)
    # Unrecognised debits can be essential obligations. Never quietly omit them from a numeric estimate.
    excluded_movements = {"transfer", "investment_deposit", "refund"}
    unknown_debits = rows[(rows.tx_amount_eur < 0) & ~rows.transaction_type.isin(PAYMENTS | excluded_movements)]
    missing = []
    if len(windows) < 3:
        missing.append("three_complete_recorded_months")
    for window in windows:
        if not in_window(unknown_debits, window).empty:
            missing.append(f"unclassified_debit_evidence:{window}")
        if in_window(earnings, window).empty:
            missing.append(f"income_evidence:{window}")
        if in_window(spending, window).empty:
            missing.append(f"spending_evidence:{window}")
    covered_days = sum((w.end_time.date() - w.start_time.date()).days + 1 for w in windows)
    result = {
        "customer_id": customer.customer_id, "currency": "EUR", "label": "Extra spending estimate",
        "status": "needs_goal" if not goals else "insufficient_data" if missing else "estimated",
        "action": "create_goal" if not goals else None, "mode": "historical_demo", "as_of": str(checked),
        "source_period": {"start": str(windows[0].start_time.date()), "end": str(windows[-1].end_time.date())} if windows else None,
        "period_count": len(windows), "covered_days": covered_days, "confidence": "low",
        "daily_eur": None, "weekly_eur": None, "monthly_extra_eur": None, "income_eur": None,
        "protected_spending_eur": None, "surplus_eur": None, "deficit_eur": None, "reserve_target_eur": None,
        "reserve_contribution_eur": None, "reserve_shortfall_eur": None, "goal_budget_eur": None,
        "goal_allocated_eur": None, "goal_allocations": [], "missing_inputs": missing,
        "policy": {"reserve_income_percent": 10, "goal_surplus_percent": 50,
                   "basis": "App demo assumptions, not bank policy or customer preferences."},
        "limitations": [
            "Historical monthly cash-flow scenario: extra spending above the protected usual spending baseline, not today's affordability.",
            "All recorded purchases, housing and utilities are protected, including groceries, irregular and uncertain categories.",
            "Recorded coverage may omit accounts, essentials or debt. Active debt and current reserve adequacy are unknown.",
            "Reserve contribution builds a hypothetical reserve; it does not establish a funded emergency reserve.",
            "No balance is added to income. Transfers, investments and refunds are excluded; mortgage approvals are not active debt.",
            "No future income guarantee, payment timing or goal completion time is inferred. Starting cash is never repeated.",
            "Goals are treated as remaining targets with no known prior progress. Nothing is saved or automatically modified.",
        ],
    }
    if not goals or missing:
        return result
    income = money(sum((total_amount(in_window(earnings, w), 1) for w in windows), Decimal(0)) / 3)
    baseline = money(sum((total_amount(in_window(spending, w)) for w in windows), Decimal(0)) / 3)
    surplus = max(Decimal(0), income - baseline)
    reserve_target = money(income * Decimal("0.10"))
    reserve = min(surplus, reserve_target)
    goal_budget = ((surplus - reserve) * Decimal("0.50")).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
    remaining = goal_budget
    allocated = Decimal(0)
    for goal in sorted(goals, key=lambda g: PRIORITIES[g.priority]):
        target = money(goal.amount_eur)
        value = min(remaining, target)
        remaining -= value
        allocated += value
        result["goal_allocations"].append({"goal_id": goal.id, "priority": goal.priority,
                                           "target_eur": float(target), "allocated_eur": float(value), "completion_periods": None})
    extra = surplus - reserve - allocated
    daily = (extra * 3 / covered_days).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
    result.update(daily_eur=float(daily), weekly_eur=float(min(extra, daily * 7)), monthly_extra_eur=float(extra),
                  income_eur=float(income), protected_spending_eur=float(baseline), surplus_eur=float(surplus),
                  deficit_eur=float(max(Decimal(0), baseline - income)), reserve_target_eur=float(reserve_target),
                  reserve_contribution_eur=float(reserve), reserve_shortfall_eur=float(reserve_target - reserve),
                  goal_budget_eur=float(goal_budget), goal_allocated_eur=float(allocated))
    return result
