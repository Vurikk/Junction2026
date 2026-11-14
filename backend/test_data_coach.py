"""Synthetic edge cases and HTTP validation; no original datasets needed."""

from copy import deepcopy
from datetime import date
from unittest import TestCase, main
from unittest.mock import patch

import pandas as pd
from fastapi.testclient import TestClient

from backend.Customer import Customer
from backend.data_coach import category_reduction, planning_suggestions, recorded_balances, spending_comparison
from backend.main import Assumptions, app


def fixture(customer_id="CUST04457", records=None):
    if records is None:
        records = [
            ("2024-01-01", "salary", 2000, "income", "one", 2000),
            ("2024-01-15", "purchase", -100, "Restaurants", "one", 1900),
            ("2024-02-15", "purchase", -200, "Restaurants", "one", 1700),
            ("2024-03-15", "purchase", -300, "Restaurants", "one", 1400),
            ("2024-04-15", "purchase", -400, "Restaurants", "one", 1000),
            ("2024-04-16", "transfer", -99999, "Restaurants", "one", 1000),
            ("2024-04-17", "refund", 50, "Restaurants", "one", 1050),
            ("2024-05-10", "transfer", 0, "transfer", "one", 1050),
        ]
    rows = pd.DataFrame(records, columns=["tx_date", "transaction_type", "tx_amount_eur", "category",
                                          "bank_account_id", "balance_after_eur"])
    rows["customer_id"] = customer_id
    rows["tx_timestamp"] = pd.to_datetime(rows.tx_date).dt.strftime("%d%b%y:%H:%M:%S")
    return Customer(customer_id, rows)


class DataCoachTests(TestCase):
    def test_historical_balance_is_not_current_funds(self):
        result = recorded_balances(fixture(), date(2026, 11, 14))
        self.assertEqual(result["simultaneous_total_eur"], 1050)
        self.assertFalse(result["current_balance_known"])
        self.assertEqual(result["accounts"][0]["status"], "historical")
        self.assertGreater(result["accounts"][0]["age_days"], 365)
        same_day = recorded_balances(fixture(), date(2024, 5, 10))["accounts"][0]
        self.assertEqual(same_day["status"], "recorded_today")
        self.assertFalse(same_day["is_current"])

    def test_missing_zero_negative_and_differing_account_dates(self):
        records = [("2024-01-01", "transfer", 0, "transfer", "one", 100),
                   ("2024-01-02", "transfer", 0, "transfer", "one", None),
                   ("2024-01-03", "transfer", 0, "transfer", "two", 0)]
        result = recorded_balances(fixture(records=records))
        self.assertIsNone(result["accounts"][0]["balance_eur"])
        self.assertEqual(result["accounts"][1]["balance_eur"], 0)
        self.assertIsNone(result["simultaneous_total_eur"])
        records[1] = (*records[1][:-1], -10)
        result = recorded_balances(fixture(records=records))
        self.assertEqual(result["accounts"][0]["balance_eur"], -10)
        self.assertIn("different timestamps", result["total_unavailable_reason"])
        records[2] = ("2024-01-02", *records[2][1:])
        self.assertEqual(recorded_balances(fixture(records=records))["simultaneous_total_eur"], -10)

    def test_same_day_different_times_and_missing_columns(self):
        customer = fixture(records=[("2024-01-01", "transfer", 0, "transfer", "one", 10),
                                    ("2024-01-01", "transfer", 0, "transfer", "two", 20)])
        customer._transactions.loc[1, "tx_timestamp"] = pd.Timestamp("2024-01-01T01:00:00")
        self.assertIsNone(recorded_balances(customer)["simultaneous_total_eur"])
        customer._transactions = customer._transactions.drop(columns="balance_after_eur")
        self.assertTrue(all(a["balance_eur"] is None for a in recorded_balances(customer)["accounts"]))

    def test_missing_balance_column_preserves_known_timestamp(self):
        customer = fixture()
        expected_at = recorded_balances(customer, date(2026, 11, 14))["accounts"][0]["recorded_at"]
        customer._transactions = customer._transactions.drop(columns="balance_after_eur")
        result = recorded_balances(customer, date(2026, 11, 14))
        account = result["accounts"][0]
        self.assertEqual(account["recorded_at"], expected_at)
        self.assertIsNotNone(account["age_days"])
        self.assertIsNone(account["balance_eur"])
        self.assertEqual(account["status"], "unavailable")
        self.assertFalse(account["is_current"])
        self.assertIsNone(result["simultaneous_total_eur"])

    def test_comparison_excludes_target_partial_period_and_transfers(self):
        result = spending_comparison(fixture(), "month")
        self.assertEqual(result["comparison"], {"start": "2024-04-01", "end": "2024-04-30", "spending_eur": 400})
        self.assertEqual(result["baseline"]["period_count"], 3)
        self.assertEqual(result["baseline"]["average_spending_eur"], 200)
        self.assertEqual(result["difference_eur"], 200)
        self.assertEqual(result["status"], "above")
        self.assertFalse(result["coverage"]["completeness_guaranteed"])

    def test_insufficient_history_and_elapsed_periods(self):
        customer = fixture(records=[("2024-01-10", "purchase", -10, "food", "one", 10),
                                    ("2024-02-29", "purchase", -20, "food", "one", 20)])
        result = spending_comparison(customer, "month")
        self.assertEqual(result["status"], "insufficient_data")
        self.assertEqual(result["comparison"]["spending_eur"], 20)
        self.assertIsNone(result["baseline"])
        self.assertIsNone(spending_comparison(customer, "month", date(2024, 2, 29))["comparison"])
        result = spending_comparison(fixture(), "month", date(2024, 3, 15))
        self.assertEqual(result["comparison"]["end"], "2024-02-29")

    def test_equal_below_and_empty_interior_weeks(self):
        customer = fixture(records=[("2024-01-01", "purchase", -10, "food", "one", 10),
                                    ("2024-01-14", "purchase", -10, "food", "one", 0)])
        self.assertEqual(spending_comparison(customer, "week")["status"], "equal")
        customer._transactions.loc[1, "tx_amount_eur"] = -5
        result = spending_comparison(customer, "week")
        self.assertEqual(result["status"], "below")
        self.assertEqual(result["difference_eur"], -5)
        result = spending_comparison(fixture(), "week")
        self.assertEqual(result["comparison"]["start"], "2024-04-29")
        self.assertEqual(result["comparison"]["spending_eur"], 0)

    def test_suggestions_keep_observations_preferences_and_confirmation_separate(self):
        assumptions = Assumptions().model_dump(mode="json")
        before = deepcopy(assumptions)
        result = planning_suggestions(fixture(), assumptions)
        self.assertEqual(assumptions, before)
        self.assertEqual(result["observations"]["income"]["average_monthly_eur"], 500)
        self.assertEqual(result["observations"]["food"]["average_monthly_eur"], 250)
        self.assertIsNone(result["observations"]["housing_utilities"]["average_monthly_eur"])
        self.assertEqual(len(result["missing_inputs"]), 6)
        self.assertTrue(all(item["missing_reason"] for item in result["inputs"]))
        assumptions["emergency_reserve_eur"] = "0.00"
        result = planning_suggestions(fixture(), assumptions)
        reserve = next(item for item in result["inputs"] if item["field"] == "emergency_reserve_eur")
        self.assertFalse(reserve["needs_confirmation"])
        self.assertEqual(reserve["kind"], "user_preference")
        self.assertEqual(reserve["confirmed_value_eur"], "0.00")
        self.assertNotIn("emergency_reserve_eur", result["missing_inputs"])

    def test_suggestions_missing_category_leap_boundary_and_excluded_transfers(self):
        customer = fixture(records=[
            ("2023-12-15", "purchase", -999, "Groceries", "one", 0),
            ("2024-01-01", "salary", 1000, "income", "one", 0),
            ("2024-01-02", "housing_payment", -100, "Housing", "one", 0),
            ("2024-01-03", "purchase", -10, "Groceries", "one", 0),
            ("2024-02-01", "salary", 1000, "income", "one", 0),
            ("2024-02-02", "transfer", 9999, "income", "one", 0),
            ("2024-02-03", "investment_deposit", -9999, "Groceries", "one", 0),
            ("2024-02-04", "utilities_payment", -300, "Utilities", "one", 0),
            ("2024-02-29", "purchase", -30, "Groceries", "one", 0),
            ("2024-02-29", "purchase", -50, None, "one", 0),
            ("2024-03-10", "transfer", 0, "transfer", "one", 0),
        ])
        result = planning_suggestions(customer, Assumptions().model_dump(mode="json"))
        observations = result["observations"]
        self.assertEqual(observations["income"]["source_period"], {"start": "2024-01-01", "end": "2024-02-29"})
        for key, expected in [("income", 1000), ("housing_utilities", 200), ("food", 20), ("everyday_purchases", 45)]:
            self.assertEqual(observations[key]["average_monthly_eur"], expected)
            self.assertEqual(observations[key]["period_count"], 2)
            self.assertFalse(observations[key]["confirmed"])
        comparison = spending_comparison(customer, "month")
        self.assertEqual(comparison["comparison"]["spending_eur"], 380)
        self.assertEqual(comparison["baseline"]["average_spending_eur"], 110)
        self.assertEqual(comparison["difference_eur"], 270)

    def test_reduction_bounds_rounding_and_non_mutation(self):
        customer = fixture()
        before = customer.get_transactions()
        for percent, expected in [(0, 0), (20, 80), (100, 400)]:
            result = category_reduction(customer, " restaurants ", "month", date(2024, 4, 1), percent)
            self.assertEqual(result["potential_reduction_eur"], expected)
            self.assertEqual(result["hypothetical_spending_eur"], 400 - expected)
            self.assertIsNone(result["goal_impact"])
        for percent in [-1, 101, "NaN", "Infinity"]:
            with self.assertRaises(ValueError):
                category_reduction(customer, "Restaurants", "month", date(2024, 4, 1), percent)
        pd.testing.assert_frame_equal(before, customer.get_transactions())

    def test_weekly_scenario_and_decimal_rounding(self):
        customer = fixture(records=[("2024-01-01", "purchase", -0.03, "food", "one", 10),
                                    ("2024-01-07", "transfer", -90, "food", "one", 0)])
        result = category_reduction(customer, "food", "week", date(2024, 1, 1), 50)
        self.assertEqual(result["baseline_spending_eur"], 0.03)
        self.assertEqual(result["potential_reduction_eur"], 0.02)
        self.assertEqual(result["hypothetical_spending_eur"], 0.01)
        with self.assertRaises(ValueError):
            category_reduction(customer, "food", "week", date(2024, 1, 2), 20)

    def test_missing_timestamp_and_nonfinite_balance(self):
        customer = fixture()
        customer._transactions.loc[customer._transactions.index[-1], "tx_timestamp"] = pd.NaT
        result = recorded_balances(customer)
        self.assertIsNone(result["accounts"][0]["recorded_at"])
        self.assertIsNone(result["simultaneous_total_eur"])
        customer._transactions["balance_after_eur"] = customer._transactions.balance_after_eur.astype(float)
        customer._transactions.loc[customer._transactions.index[-1], "balance_after_eur"] = float("inf")
        self.assertIsNone(recorded_balances(customer)["accounts"][0]["balance_eur"])


class DataCoachApiTests(TestCase):
    def setUp(self):
        loader = patch("backend.main.load_customers", return_value=[fixture(), fixture("CUST00001")])
        self.addCleanup(loader.stop)
        loader.start()
        context = TestClient(app)
        self.client = context.__enter__()
        self.addCleanup(context.__exit__, None, None, None)

    def test_both_profiles_read_only_endpoints_and_existing_contract(self):
        for key in ["CUST04457", "CUST00001"]:
            base = f"/api/customers/{key}"
            self.client.post(f"{base}/goals", json={"name": "Bike", "amount_eur": "100", "priority": "critical"})
            before = {name: self.client.get(f"{base}/{name}").json() for name in ["goals", "assumptions", "budget"]}
            for resource in ["recorded-balances", "spending-comparison", "spending-comparison?period=week", "planning-suggestions"]:
                response = self.client.get(f"{base}/{resource}")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["customer_id"], key)
            payload = {"category": "restaurants", "period": "month", "period_start": "2024-04-01", "reduction_percent": "20"}
            for _ in range(2):
                response = self.client.post(f"{base}/category-reduction", json=payload)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["potential_reduction_eur"], 80)
            for resource, value in before.items():
                self.assertEqual(self.client.get(f"{base}/{resource}").json(), value)
            self.assertIsNone(before["budget"]["daily_eur"])
            zeros = {key: "0.00" for key in before["budget"]["missing_inputs"]}
            self.assertEqual(self.client.put(f"{base}/assumptions", json=zeros).status_code, 200)
            self.assertEqual(self.client.get(f"{base}/budget").json()["daily_eur"], 0)

    def test_http_validation(self):
        base = "/api/customers/CUST04457"
        payload = {"category": "restaurants", "period": "month", "period_start": "2024-04-01", "reduction_percent": 20}
        invalid = [{"reduction_percent": value} for value in [-1, 101, "NaN", "Infinity", "0.001"]]
        invalid += [{"period": "day"}, {"period_start": "2024-04-02"}, {"period_start": "2024-05-01"},
                    {"period_start": "2024-02-30"}, {"period_start": "2023-01-01"}, {"category": " "}, {"save": True}]
        for changes in invalid:
            with self.subTest(changes=changes):
                self.assertEqual(self.client.post(f"{base}/category-reduction", json={**payload, **changes}).status_code, 422)
        for category in ["missing", "unknown", "housing"]:
            self.assertEqual(self.client.post(f"{base}/category-reduction", json={**payload, "category": category}).status_code, 404)
        for field in payload:
            self.assertEqual(self.client.post(f"{base}/category-reduction", json={k: v for k, v in payload.items() if k != field})
                             .status_code, 422)
        self.assertEqual(self.client.get(f"{base}/spending-comparison?period=day").status_code, 422)
        for path in ["recorded-balances", "spending-comparison", "planning-suggestions"]:
            self.assertEqual(self.client.get(f"/api/customers/unknown/{path}").status_code, 404)
        self.assertEqual(self.client.post("/api/customers/unknown/category-reduction", json=payload).status_code, 404)


if __name__ == "__main__":
    main()
