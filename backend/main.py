"""Local demo API. Financial calculations stay in Python; no LLM is connected."""

import os
from contextlib import asynccontextmanager
from decimal import Decimal
from typing import Literal
from uuid import uuid4

import pandas as pd
from fastapi import FastAPI, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from .data_test import DATA_DIR, load_customers
from .financial import history, income, plan, PRIORITIES


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CustomerSummary(Model):
    customer_id: str
    customer_age: int | None
    customer_postal_code: str | None
    months: list[str]
    has_mortgage_data: bool


class SpendingPoint(Model):
    date: str
    amount_eur: float


class SpendingSummary(Model):
    customer_id: str
    month: str
    currency: Literal["EUR"] = "EUR"
    spending_eur: float
    average_daily_eur: float
    daily: list[SpendingPoint]
    excluded_transaction_count: int
    note: str


class Allocation(Model):
    goal_id: str
    allocated_eur: float | None
    completion_periods: int | None
    feasibility: Literal["unknown", "funded", "conditional", "not_funded_in_horizon"]


class Budget(Model):
    customer_id: str
    status: Literal["insufficient_data", "estimated"]
    daily_eur: float | None = None
    weekly_eur: float | None = None
    missing_inputs: list[str]
    confidence: Literal["unknown", "user_confirmed_assumptions"]
    assumptions: dict
    allocations: list[Allocation]
    savings_capacity_eur: float | None
    shortfall_eur: float | None


class GoalInput(Model):
    name: str = Field(min_length=1, max_length=100, pattern=r"\S")
    amount_eur: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    priority: Literal["critical", "important", "flexible"]


class Goal(GoalInput):
    id: str
    customer_id: str


class GoalAnalysis(Budget):
    ordered_goal_ids: list[str]
    total_target_eur: str
    explanation: str


class MortgageApplication(Model):
    mortgage_customer_id: str
    final_decision: str | None
    final_requested_loan_eur: float | None
    monthly_payment_eur: float | None = None


class Mortgages(Model):
    customer_id: str
    applications: list[MortgageApplication]
    note: str


@asynccontextmanager
async def lifespan(app):
    customers = load_customers(os.environ.get("SBANK_DATA_DIR", DATA_DIR))
    app.state.customers = {customer.customer_id: customer for customer in customers}
    app.state.assumptions = {c.customer_id: Assumptions().model_dump(mode='json') for c in customers}
    app.state.goals = {customer.customer_id: [] for customer in customers}
    yield


app = FastAPI(title="S-Bank Financial Coach", version="0.1.0", lifespan=lifespan)


def customer_for(request, customer_id):
    customer = request.app.state.customers.get(customer_id)
    if customer is None:
        raise HTTPException(404, "Unknown demo customer")
    return customer


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/customers", response_model=list[CustomerSummary])
def customers(request: Request):
    return [
        {**customer.get_profile(), "months": customer.get_months(), "has_mortgage_data": customer.has_mortgage_data()}
        for customer in request.app.state.customers.values()
    ]


@app.get("/api/customers/{customer_id}/spending", response_model=SpendingSummary)
def spending(request: Request, customer_id: str, month: str | None = Query(None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$")):
    customer = customer_for(request, customer_id)
    month = month or customer.get_months()[-1]
    if month not in customer.get_months():
        raise HTTPException(404, "No recorded transactions for this month")
    rows = customer.get_transactions(month)
    # Explicit payment types only: transfers/investments/unknown types never become spending.
    payment_types = {"purchase", "utilities_payment", "housing_payment"}
    included = rows["transaction_type"].isin(payment_types) & (rows["tx_amount_eur"] < 0)
    outgoing = rows[included]
    daily = outgoing.groupby(outgoing["tx_date"].dt.strftime("%Y-%m-%d"))["tx_amount_eur"].sum().mul(-1)
    dates = pd.date_range(f"{month}-01", periods=pd.Period(month).days_in_month)
    points = [{"date": day.strftime("%Y-%m-%d"), "amount_eur": round(float(daily.get(day.strftime("%Y-%m-%d"), 0)), 2)}
              for day in dates]
    total = round(sum(point["amount_eur"] for point in points), 2)
    return {
        "customer_id": customer_id, "month": month, "spending_eur": total,
        "average_daily_eur": round(total / len(points), 2), "daily": points,
        "excluded_transaction_count": int((~included).sum()),
        "note": "Recorded purchases, utilities and housing outflows only. Transfers and other types excluded; refunds not netted."
    }


@app.get("/api/customers/{customer_id}/budget", response_model=Budget)
def budget(request: Request, customer_id: str):
    customer_for(request, customer_id)
    return {"customer_id": customer_id, **plan(request.app.state.assumptions[customer_id], request.app.state.goals[customer_id])}


@app.get("/api/customers/{customer_id}/goals", response_model=list[Goal])
def goals(request: Request, customer_id: str):
    customer_for(request, customer_id)
    return request.app.state.goals[customer_id]


@app.post("/api/customers/{customer_id}/goals", response_model=Goal, status_code=201)
def create_goal(request: Request, customer_id: str, payload: GoalInput):
    customer_for(request, customer_id)
    goal = Goal(**payload.model_dump(), id=str(uuid4()), customer_id=customer_id)
    request.app.state.goals[customer_id].append(goal)
    return goal


@app.get("/api/customers/{customer_id}/goal-analysis", response_model=GoalAnalysis)
def analyze_goals(request: Request, customer_id: str):
    customer_for(request, customer_id)
    ordered = sorted(request.app.state.goals[customer_id], key=lambda goal: PRIORITIES[goal.priority])
    return {
        "customer_id": customer_id, **plan(request.app.state.assumptions[customer_id], ordered),
        "ordered_goal_ids": [goal.id for goal in ordered],
        "total_target_eur": str(sum((goal.amount_eur for goal in ordered), Decimal("0.00"))),
        "explanation": "Required payments and reserves come first. Completion estimates assume explicitly confirmed repeating capacity."
    }


@app.get("/api/customers/{customer_id}/mortgages", response_model=Mortgages)
def mortgages(request: Request, customer_id: str):
    customer = customer_for(request, customer_id)
    records = customer.get_mortgages()
    applications = []
    for _, row in records.iterrows():
        applications.append({
            key: None if pd.isna(row.get(key)) else row.get(key)
            for key in ("mortgage_customer_id", "final_decision", "final_requested_loan_eur")
        })
    return {"customer_id": customer_id, "applications": applications,
            "note": "Application records only; these do not establish an active loan or monthly repayments."}



class Assumptions(Model):
    available_funds_eur: Decimal | None = Field(None, ge=0, max_digits=12, decimal_places=2)
    confirmed_income_eur: Decimal | None = Field(None, ge=0, max_digits=12, decimal_places=2)
    upcoming_essential_bills_eur: Decimal | None = Field(None, ge=0, max_digits=12, decimal_places=2)
    emergency_reserve_eur: Decimal | None = Field(None, ge=0, max_digits=12, decimal_places=2)
    everyday_spending_eur: Decimal | None = Field(None, ge=0, max_digits=12, decimal_places=2)
    voluntary_goal_contribution_eur: Decimal | None = Field(None, ge=0, max_digits=12, decimal_places=2)
    weekly_budget_eur: Decimal | None = Field(None, ge=0, max_digits=12, decimal_places=2)
    monthly_budget_eur: Decimal | None = Field(None, ge=0, max_digits=12, decimal_places=2)
    horizon_days: int = Field(30, ge=1, le=366)
    repeat_plan: bool = False


@app.get("/api/customers/{customer_id}/assumptions", response_model=Assumptions)
def get_assumptions(request: Request, customer_id: str):
    customer_for(request, customer_id)
    return request.app.state.assumptions[customer_id]


@app.put("/api/customers/{customer_id}/assumptions", response_model=Assumptions)
def set_assumptions(request: Request, customer_id: str, payload: Assumptions):
    customer_for(request, customer_id)
    request.app.state.assumptions[customer_id] = payload.model_dump(mode="json")
    return payload


@app.get("/api/customers/{customer_id}/spending-history")
def spending_history(request: Request, customer_id: str, period: Literal["week", "month"] = "month"):
    customer = customer_for(request, customer_id)
    key = "weekly_budget_eur" if period == "week" else "monthly_budget_eur"
    return history(customer, period, request.app.state.assumptions[customer_id][key])


@app.get("/api/customers/{customer_id}/income")
def income_analysis(request: Request, customer_id: str):
    return income(customer_for(request, customer_id))
