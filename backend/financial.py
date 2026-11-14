"""Conservative financial summaries. Historical observations never confirm future cash flow."""
from decimal import Decimal, ROUND_DOWN
from math import ceil

import pandas as pd

PAYMENTS = {"purchase", "utilities_payment", "housing_payment"}
PRIORITIES = {"critical": 0, "important": 1, "flexible": 2}


def money(value):
    return Decimal(str(value)).quantize(Decimal("0.01"))


def spending_rows(customer):
    rows = customer.get_transactions()
    return rows[rows.transaction_type.isin(PAYMENTS) & (rows.tx_amount_eur < 0)].copy()


def basket(row):
    if row.transaction_type in {"utilities_payment", "housing_payment"}:
        return "mandatory_regular", "medium", "Payment type suggests a regular essential; confirm with user."
    category = str(row.get("category", "")).lower()
    if category in {"healthcare", "medical", "insurance", "car repair"}:
        return "mandatory_irregular", "low", "Category suggests an irregular essential; confirm necessity."
    if category in {"restaurants", "entertainment", "shopping", "groceries", "dining"}:
        return "discretionary_everyday", "low", "Everyday category; may contain essential purchases."
    return "uncertain", "low", "Insufficient evidence to assign a spending basket."


def history(customer, period, target=None):
    all_rows = customer.get_transactions()
    rows = spending_rows(customer)
    freq = "W-SUN" if period == "week" else "M"
    start, end = all_rows.tx_date.min(), all_rows.tx_date.max()
    periods = pd.period_range(start, end, freq=freq)
    result = []
    for window in periods:
        selected = rows[rows.tx_date.dt.to_period(freq) == window]
        categories = selected.assign(category=selected.category.fillna("unknown")).groupby("category").tx_amount_eur.sum()
        totals = {name: Decimal("0") for name in (
            "mandatory_regular", "mandatory_irregular", "discretionary_everyday", "uncertain"
        )}
        classifications = []
        for _, row in selected.iterrows():
            name, confidence, reason = basket(row)
            amount = money(-row.tx_amount_eur)
            totals[name] += amount
            classifications.append({"category": None if pd.isna(row.get("category")) else row.get("category"),
                                    "basket": name, "amount_eur": float(amount), "confidence": confidence, "reason": reason})
        total = money(-selected.tx_amount_eur.sum())
        result.append({"period": str(window), "start": str(window.start_time.date()), "end": str(window.end_time.date()),
                       "partial": start.date() > window.start_time.date() or end.date() < window.end_time.date(),
                       "spending_eur": float(total), "categories": {str(k): round(-float(v), 2) for k, v in categories.items()},
                       "baskets": {k: float(v) for k, v in totals.items()}, "classifications": classifications,
                       "budget_target_eur": target, "remaining_budget_eur": None if target is None else float(money(target) - total)})
    complete = [r for r in result if not r["partial"]]
    average = round(sum(r["spending_eur"] for r in complete) / len(complete), 2) if complete else None
    return {"customer_id": customer.customer_id, "period": period, "periods": result,
            "historical_average_eur": average, "average_period_count": len(complete), "budget_target_eur": target,
            "confidence": "low", "note": "Average uses full calendar periods inside observed date range, including zero-spend periods. "
            "Coverage is not guaranteed; edge periods are excluded. Gross purchases only; refunds and transfers excluded."}


def income(customer):
    rows = customer.get_transactions()
    # Only explicit income types qualify. Positive transfers and refunds are never income.
    selected = rows[(rows.tx_amount_eur > 0) & rows.transaction_type.isin({"salary", "income", "salary_payment", "pension"})]
    monthly = selected.groupby(selected.tx_date.dt.strftime("%Y-%m")).tx_amount_eur.sum()
    candidates = []
    for kind, group in selected.groupby("transaction_type"):
        dates = group.tx_date.drop_duplicates().sort_values()
        gaps = dates.diff().dt.days.dropna()
        stable = len(group) >= 3 and len(gaps) >= 2 and gaps.between(25, 35).all()
        stable = stable and group.tx_amount_eur.max() <= group.tx_amount_eur.min() * 1.15
        if stable:
            candidates.append({"type": kind, "observations": len(group), "average_payment_eur": round(group.tx_amount_eur.mean(), 2),
                               "confidence": "medium", "confirmed": False, "cadence": "monthly"})
    return {"customer_id": customer.customer_id, "recorded_income_eur": round(float(selected.tx_amount_eur.sum()), 2),
            "monthly": {k: round(float(v), 2) for k, v in monthly.items()}, "likely_recurring": candidates,
            "confidence": "medium" if candidates else "low",
            "note": "Explicit positive income types only. Recurrence is observational, not confirmed future income; "
            "multiple sources cannot reliably be distinguished without payer information."}


def plan(assumptions, goals):
    ordered = sorted(goals, key=lambda g: PRIORITIES[g.priority])
    required = ["available_funds_eur", "confirmed_income_eur", "upcoming_essential_bills_eur", "emergency_reserve_eur",
                "everyday_spending_eur", "voluntary_goal_contribution_eur"]
    missing = [key for key in required if assumptions.get(key) is None]
    result = {"status": "insufficient_data" if missing else "estimated", "daily_eur": None, "weekly_eur": None,
              "missing_inputs": missing, "confidence": "unknown" if missing else "user_confirmed_assumptions",
              "assumptions": assumptions, "allocations": [], "savings_capacity_eur": None, "shortfall_eur": None}
    if missing:
        result["allocations"] = [{"goal_id": g.id, "allocated_eur": None, "completion_periods": None,
                                  "feasibility": "unknown"} for g in ordered]
        return result
    days = assumptions["horizon_days"]
    cash = money(assumptions["available_funds_eur"]) + money(assumptions["confirmed_income_eur"])
    protected = money(assumptions["upcoming_essential_bills_eur"]) + money(assumptions["emergency_reserve_eur"])
    remainder = cash - protected
    capacity = max(Decimal(0), remainder - money(assumptions["everyday_spending_eur"]))
    pool = min(capacity, money(assumptions["voluntary_goal_contribution_eur"]))
    original_pool = pool
    cumulative = Decimal(0)
    for goal in ordered:
        target = money(goal.amount_eur)
        allocated = min(pool, target)
        pool -= allocated
        cumulative += target
        completion = ceil(cumulative / original_pool) if original_pool else None
        result["allocations"].append({"goal_id": goal.id, "allocated_eur": float(allocated),
                                      "completion_periods": completion if assumptions["repeat_plan"] else None,
                                      "feasibility": "funded" if allocated == target else (
                                          "conditional" if original_pool and assumptions["repeat_plan"] else "not_funded_in_horizon")})
    allowance = max(Decimal(0), remainder - (original_pool - pool))
    daily = (allowance / days).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
    result.update(daily_eur=float(daily), weekly_eur=float(min(allowance, daily * 7)),
                  savings_capacity_eur=float(capacity), shortfall_eur=float(max(Decimal(0), -remainder)))
    return result
