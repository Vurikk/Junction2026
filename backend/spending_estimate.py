"""Read-only cash-only estimates, separate from confirmed manual plans."""
from datetime import date, timedelta
from decimal import Decimal, ROUND_DOWN

from .data_coach import complete_windows, coverage, in_window, recorded_balances, total_amount
from .financial import income, money, plan, spending_rows

LABELS = {
    "available_funds_eur": ("Money available now", "Confirm accessible cash; recorded balances are not current funds."),
    "emergency_reserve_eur": ("Money to keep in reserve", "Choose money to protect; history cannot determine this preference."),
    "upcoming_essential_bills_eur": ("All bills due", "Confirm the TOTAL due in this horizon, not a prorated monthly average."),
    "additional_essential_bills_eur": ("Any other bills due?", "Historical scenario: add missing obligations, or explicitly enter 0."),
    "everyday_spending_eur": ("Everyday living costs", "Protect living costs before setting money aside for goals."),
}


def rate_observation(rows, windows, days):
    count = sum(len(in_window(rows, w)) for w in windows)
    covered_days = sum((w.end_time.date() - w.start_time.date()).days + 1 for w in windows)
    total = sum((total_amount(in_window(rows, w)) for w in windows), Decimal(0))
    value = money(total * days / covered_days) if count and covered_days else None
    return {"value_eur": None if value is None else float(value), "source": "historical_rate", "confidence": "low",
            "source_period": {"start": str(windows[0].start_time.date()), "end": str(windows[-1].end_time.date())}
            if windows else None, "observations": count, "covered_days": covered_days, "horizon_days": days,
            "formula": "recorded total / covered calendar days * horizon days", "confirmed": False}


def estimate(customer, payload, goals, manual_assumptions, as_of=None):
    checked = as_of or date.today()
    bounds = coverage(customer)
    historical = payload["mode"] == "historical"
    balances = recorded_balances(customer, checked)
    recorded_at = balances["total_recorded_at"]
    reference = checked
    if historical:
        raw_reference = recorded_at[:10] if recorded_at else bounds["recorded_end"]
        reference = date.fromisoformat(raw_reference) if raw_reference else None
    windows = complete_windows(customer, "month", min(reference or checked, checked) + timedelta(days=1))
    outgoing = spending_rows(customer)
    days = payload["horizon_days"]
    bills = rate_observation(outgoing[outgoing.transaction_type.isin({"housing_payment", "utilities_payment"})], windows, days)
    purchases = rate_observation(outgoing[outgoing.transaction_type == "purchase"], windows, days)
    inputs, missing = {}, []

    def put(field, value, source, confidence="low"):
        inputs[field] = {"value_eur": None if value is None else float(money(value)), "source": source, "confidence": confidence}
        return None if value is None else money(value)

    def user(field):
        return put(field, payload.get(field), "user", "user_provided")

    funds = user("available_funds_eur")
    if funds is None and historical and recorded_at and reference <= checked:
        funds = put("available_funds_eur", balances["simultaneous_total_eur"], "recorded_balance")
    if funds is None:
        missing.append("available_funds_eur")
    reserve = user("emergency_reserve_eur")
    if reserve is None:
        missing.append("emergency_reserve_eur")
    essentials = user("upcoming_essential_bills_eur")
    if essentials is None and historical and bills["value_eur"] is not None:
        addendum = user("additional_essential_bills_eur")
        if addendum is None:
            missing.append("additional_essential_bills_eur")
        else:
            essentials = put("upcoming_essential_bills_eur", money(bills["value_eur"]) + addendum, "historical_rate_plus_user")
    elif essentials is None:
        missing.append("upcoming_essential_bills_eur")
    everyday = user("everyday_spending_eur")
    if everyday is None:
        everyday = put("everyday_spending_eur", purchases["value_eur"], "historical_rate")
    contribution = user("voluntary_goal_contribution_eur")
    earmarked = contribution is not None and contribution > 0
    if contribution is None:
        contribution = put("voluntary_goal_contribution_eur", 0, "policy")
    if earmarked and goals and everyday is None:
        missing.append("everyday_spending_eur")
    fields = []
    for field in missing:
        suggestion = bills["value_eur"] if field == "upcoming_essential_bills_eur" else None
        fields.append({"field": field, "label": LABELS[field][0], "reason": LABELS[field][1], "suggested_value_eur": suggestion})
    result = {
        "customer_id": customer.customer_id, "currency": "EUR", "mode": payload["mode"], "as_of": str(checked),
        "reference_date": str(reference) if reference else None, "horizon_days": days, "status": "insufficient_data" if missing else "estimated",
        "daily_eur": None, "weekly_eur": None, "confidence": "low", "missing_inputs": missing, "missing_fields": fields,
        "inputs": inputs, "observations": {"bills": bills, "everyday_purchases": purchases, "balances": balances,
                                             "income": income(customer)},
        "allocations": [], "savings_capacity_eur": None, "shortfall_eur": None,
        "manual_plan_available": plan(manual_assumptions, goals)["status"] == "estimated",
        "goal_policy": "Goals receive the explicit contribution in priority order." if earmarked else
                       "No money set aside for goals in this estimate.",
        "limitations": [
            "Historical scenario only; not today's affordability." if historical else "Cash-only estimate using user-provided current funds.",
            "Future income is excluded, including recurring income; income already in balances is never added again.",
            "Bill references are prorated historical averages, not payment dates. Current mode requires actual total bills due.",
            "Confirm bills can be covered before spending; no intra-horizon payment timing is modeled.",
            "Recorded coverage may omit accounts or payments. Review bills and everyday purchases for overlap.",
            "No mortgage application is active debt. Food is not added separately to purchases.",
            "Nothing is saved; confirmed manual plans and goals are unchanged. Starting cash is never repeated.",
        ],
    }
    if missing:
        return result
    remainder = funds - reserve - essentials
    allocation_total = Decimal(0)
    if everyday is not None:
        calculated = plan({"available_funds_eur": max(Decimal(0), funds), "confirmed_income_eur": 0,
                           "upcoming_essential_bills_eur": essentials + max(Decimal(0), -funds),
                           "emergency_reserve_eur": reserve, "everyday_spending_eur": everyday,
                           "voluntary_goal_contribution_eur": contribution, "horizon_days": days, "repeat_plan": False}, goals)
        result["allocations"] = calculated["allocations"]
        result["savings_capacity_eur"] = calculated["savings_capacity_eur"]
        allocation_total = sum((money(g["allocated_eur"]) for g in calculated["allocations"]), Decimal(0))
    allowance = max(Decimal(0), remainder - allocation_total)
    daily = (allowance / days).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
    result.update(daily_eur=float(daily), weekly_eur=float(min(allowance, daily * 7)),
                  shortfall_eur=float(max(Decimal(0), -remainder)))
    return result
