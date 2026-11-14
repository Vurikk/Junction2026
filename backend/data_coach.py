"""Read-only, dated observations; none of these functions confirm planning inputs."""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pandas as pd

from .financial import money, spending_rows


COVERAGE_NOTE = (
    "Calendar periods inside the recorded date range are not guaranteed complete. "
    "Missing transactions or accounts may understate totals. Transfers and refunds are excluded."
)
INCOME_TYPES = {"salary", "income", "salary_payment", "pension"}
FOOD_CATEGORIES = {"groceries", "restaurants", "dining", "food", "food & groceries", "food & dining"}


def today_utc():
    return datetime.now(timezone.utc).date()


def total_amount(rows, sign=-1):
    """Sum monetary amounts as decimal cents, never binary floating point."""
    return sum((money(value) * sign for value in rows.tx_amount_eur), Decimal("0.00"))


def coverage(customer):
    dates = customer.get_transactions().tx_date.dropna()
    return {
        "recorded_start": str(dates.min().date()) if not dates.empty else None,
        "recorded_end": str(dates.max().date()) if not dates.empty else None,
        "completeness_guaranteed": False,
    }


def complete_windows(customer, period, as_of=None):
    """Only elapsed whole calendar periods bracketed by recorded transaction dates."""
    bounds = coverage(customer)
    if bounds["recorded_start"] is None:
        return []
    freq = "W-SUN" if period == "week" else "M"
    start = pd.Timestamp(bounds["recorded_start"])
    end = pd.Timestamp(min(date.fromisoformat(bounds["recorded_end"]), (as_of or today_utc()) - timedelta(days=1)))
    if end < start:
        return []
    return [window for window in pd.period_range(start, end, freq=freq)
            if window.start_time.date() >= start.date() and window.end_time.date() <= end.date()]


def in_window(rows, window):
    return rows[rows.tx_date.between(window.start_time, window.end_time)]


def period_dates(window):
    return {"start": str(window.start_time.date()), "end": str(window.end_time.date())}


def recorded_balances(customer, as_of=None):
    checked_on = as_of or today_utc()
    rows = customer.get_transactions()
    accounts = []
    # The loader returns the last transaction, even when its balance is missing.
    # Do not silently substitute an older balance for that missing observation.
    if {"bank_account_id", "balance_after_eur", "tx_timestamp"}.issubset(rows.columns):
        latest = customer.get_account_balances()
    else:
        latest = pd.DataFrame()
    ids = rows.bank_account_id.dropna().unique() if "bank_account_id" in rows else []
    for account_id in ids:
        row = latest.loc[account_id] if account_id in latest.index else {}
        raw_balance, timestamp = row.get("balance_after_eur"), row.get("tx_timestamp")
        value = None if pd.isna(raw_balance) else Decimal(str(raw_balance))
        value = money(value) if value is not None and value.is_finite() else None
        timestamp = None if pd.isna(timestamp) else pd.Timestamp(timestamp)
        age = (checked_on - timestamp.date()).days if timestamp is not None else None
        status = "unavailable"
        if value is not None and age is not None:
            status = "historical" if age > 0 else "recorded_today" if age == 0 else "future_dated"
        accounts.append({
            "account_id": str(account_id), "currency": "EUR", "balance_eur": None if value is None else float(value),
            "recorded_at": timestamp.isoformat() if timestamp is not None else None,
            "age_days": age, "status": status, "is_current": False,
        })
    timestamps = {account["recorded_at"] for account in accounts}
    total = None
    reason = "No accounts with recorded balances."
    if accounts:
        if any(account["balance_eur"] is None or account["recorded_at"] is None for account in accounts):
            reason = "At least one account is missing its latest balance or timestamp."
        elif len(timestamps) != 1:
            reason = "Account balances have different timestamps; no simultaneous total is available."
        else:
            total = float(sum((money(account["balance_eur"]) for account in accounts), Decimal("0.00")))
            reason = None
    return {
        "customer_id": customer.customer_id, "currency": "EUR", "checked_on": str(checked_on),
        "current_balance_known": False, "accounts": accounts, "simultaneous_total_eur": total,
        "total_recorded_at": next(iter(timestamps)) if total is not None else None, "total_unavailable_reason": reason,
        "note": "Latest recorded balance_after_eur per observed account, not current accessible funds. "
                "Source timestamps have no declared timezone. checked_on uses UTC; no live balance feed exists.",
    }


def spending_comparison(customer, period, as_of=None):
    windows = complete_windows(customer, period, as_of)
    rows = spending_rows(customer)
    comparison = None
    baseline = None
    difference = None
    status = "insufficient_data"
    if windows:
        comparison = {**period_dates(windows[-1]), "spending_eur": float(total_amount(in_window(rows, windows[-1])))}
    if len(windows) > 1:
        baseline_windows = windows[:-1]
        average = money(sum((total_amount(in_window(rows, w)) for w in baseline_windows), Decimal(0)) / len(baseline_windows))
        baseline = {
            "start": period_dates(baseline_windows[0])["start"], "end": period_dates(baseline_windows[-1])["end"],
            "period_count": len(baseline_windows), "average_spending_eur": float(average),
        }
        difference = money(comparison["spending_eur"]) - average
        status = "above" if difference > 0 else "below" if difference < 0 else "equal"
    return {
        "customer_id": customer.customer_id, "currency": "EUR", "period": period, "status": status,
        "comparison": comparison, "baseline": baseline, "difference_eur": None if difference is None else float(difference),
        "coverage": coverage(customer), "confidence": "low", "note": COVERAGE_NOTE,
        "insufficient_data_reason": (
            "Need at least two elapsed full calendar periods inside recorded coverage." if baseline is None else None
        ),
    }


def monthly_observation(rows, windows, source, limitation, sign=-1):
    selected = [in_window(rows, window) for window in windows]
    count = sum(len(group) for group in selected)
    supported = bool(windows) and count > 0
    return {
        "kind": "historical_estimate", "average_monthly_eur": (
            float(money(sum((total_amount(group, sign) for group in selected), Decimal(0)) / len(windows)))
            if supported else None
        ),
        "source_period": {"start": period_dates(windows[0])["start"], "end": period_dates(windows[-1])["end"]} if windows else None,
        "period_count": len(windows), "observations": count, "source": source,
        "confidence": "low" if supported else "unknown", "confirmed": False,
        "limitations": [COVERAGE_NOTE, limitation, "Calendar-month averages are not amounts for an arbitrary planning horizon."],
        "unavailable_reason": None if supported else "No matching observations in elapsed full calendar months.",
    }


def planning_suggestions(customer, assumptions):
    rows = customer.get_transactions()
    outgoing = spending_rows(customer)
    windows = complete_windows(customer, "month")
    income_rows = rows[(rows.tx_amount_eur > 0) & rows.transaction_type.isin(INCOME_TYPES)]
    food = outgoing[outgoing.category.fillna("").str.strip().str.casefold().isin(FOOD_CATEGORIES)]
    specs = {
        "income": (income_rows, "Positive salary, income, salary_payment, pension types.",
                   "Historical income does not confirm future amount or payment timing.", 1),
        "housing_utilities": (outgoing[outgoing.transaction_type.isin({"housing_payment", "utilities_payment"})],
                              "Negative housing_payment and utilities_payment types.",
                              "May omit essential bills and active debt. Mortgage approvals are not repayments.", -1),
        "food": (food, "Included payment types with categories: " + ", ".join(sorted(FOOD_CATEGORIES)) + ".",
                 "Category labels are heuristic; food is only a subset of everyday costs.", -1),
        "everyday_purchases": (outgoing[outgoing.transaction_type == "purchase"], "Negative purchase type, excluding bill types.",
                               "Purchases may include irregular essentials; review overlap with planned bills.", -1),
    }
    observations = {key: monthly_observation(selected, windows, source, limitation, sign)
                    for key, (selected, source, limitation, sign) in specs.items()}
    requirements = [
        ("available_funds_eur", "current_fact", [],
         "Confirm funds accessible now. Recorded balances are dated observations, not current funds."),
        ("confirmed_income_eur", "future_fact", ["income"],
         "Confirm additional income arriving within the horizon; exclude money already in accessible funds."),
        ("upcoming_essential_bills_eur", "future_fact", ["housing_utilities"],
         "Confirm all essential bills and active debt payments due within the horizon."),
        ("emergency_reserve_eur", "user_preference", [],
         "Choose money to protect in addition to bills; transactions cannot establish this preference."),
        ("everyday_spending_eur", "user_plan", ["everyday_purchases", "food"],
         "Confirm everyday costs for the horizon, excluding bills. Food overlaps purchases; do not add these suggestions."),
        ("voluntary_goal_contribution_eur", "user_preference", [],
         "Choose the maximum contribution to goals during the horizon; history cannot establish this preference."),
    ]
    inputs = [{"field": field, "kind": kind, "confirmed_value_eur": assumptions.get(field),
               "needs_confirmation": assumptions.get(field) is None, "observation_keys": keys,
               "missing_reason": reason if assumptions.get(field) is None else None}
              for field, kind, keys, reason in requirements]
    return {
        "customer_id": customer.customer_id, "currency": "EUR", "coverage": coverage(customer),
        "observations": observations, "inputs": inputs, "horizon_days": assumptions["horizon_days"],
        "missing_inputs": [item["field"] for item in inputs if item["needs_confirmation"]],
        "note": "Read-only suggestions. Nothing is populated or confirmed automatically; the six-input allowance contract is unchanged.",
    }


def category_reduction(customer, category, period, period_start, reduction_percent):
    """Raise ValueError for invalid period and LookupError for missing observations."""
    window = pd.Period(period_start, freq="W-SUN" if period == "week" else "M")
    if window.start_time.date() != period_start:
        raise ValueError("period_start must be Monday for a week or the first day of a month.")
    if window not in complete_windows(customer, period):
        raise ValueError("Use an elapsed full calendar period inside the recorded date range.")
    rows = spending_rows(customer)
    category_key = category.strip().casefold()
    if category_key in {"", "unknown", "uncategorized"}:
        raise LookupError("Choose an explicitly recorded spending category.")
    selected = in_window(rows, window)
    selected = selected[selected.category.fillna("").str.strip().str.casefold() == category_key]
    if selected.empty:
        raise LookupError("No included spending observations for this category and period; absence does not establish zero spending.")
    percent = Decimal(str(reduction_percent))
    if not percent.is_finite() or not 0 <= percent <= 100:
        raise ValueError("reduction_percent must be between 0 and 100.")
    baseline = total_amount(selected)
    reduction = money(baseline * percent / 100)
    return {
        "customer_id": customer.customer_id, "currency": "EUR", "category": category_key, "period": period,
        "source_period": period_dates(window), "reduction_percent": float(percent), "baseline_spending_eur": float(baseline),
        "hypothetical_spending_eur": float(baseline - reduction), "potential_reduction_eur": float(reduction),
        "coverage": coverage(customer), "confidence": "low", "read_only": True, "goal_impact": None,
        "goal_impact_unavailable_reason": "Confirmed plans do not map category spending to their horizon or inputs. "
                                          "Adding this reduction to goal capacity could double-count money.",
        "note": "Hypothetical spending reduction, not actual savings. Goals and confirmed inputs are unchanged. " + COVERAGE_NOTE,
    }
