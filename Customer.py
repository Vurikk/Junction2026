import pandas as pd


class Customer:
    """Customer profile, transactions and optional mortgage application data.

    Load customer_postal_code as a string to preserve leading zeros.
    Month arguments use 'YYYY-MM'. Mortgage records describe applications,
    not confirmed active loans or repayment schedules.
    """

    def __init__(self, customer_id, transactions, customers=None, mortgage_info=None, mortgage_history=None):
        self.customer_id = customer_id
        self.age = None
        self.postal_code = None

        if customers is not None:
            profile = customers[customers["customer_id"] == customer_id]
            if len(profile) > 1:
                raise ValueError(f"Multiple profiles found for customer {customer_id}")
            if not profile.empty:
                row = profile.iloc[0]
                if pd.notna(row["customer_age"]):
                    self.age = int(row["customer_age"])
                if pd.notna(row["customer_postal_code"]):
                    self.postal_code = str(row["customer_postal_code"])

        self._transactions = transactions[
            transactions["customer_id"] == customer_id
        ].copy()

        if self._transactions.empty:
            raise ValueError(f"No transactions found for customer {customer_id}")

        self._transactions["tx_date"] = pd.to_datetime(self._transactions["tx_date"])
        self._transactions["tx_timestamp"] = pd.to_datetime(
            self._transactions["tx_timestamp"], format="%d%b%y:%H:%M:%S"
        )
        self._transactions = self._transactions.sort_values(
            "tx_timestamp", kind="stable"
        ).reset_index(drop=True)

        # Keep applications separate from transactions to avoid duplicate totals.
        self._mortgages = pd.DataFrame(columns=["customer_id", "mortgage_customer_id"])
        if mortgage_info is not None:
            self._mortgages = mortgage_info[
                mortgage_info["customer_id"] == customer_id
            ].copy().reset_index(drop=True)

        self._mortgage_history = pd.DataFrame(columns=["mortgage_customer_id", "timestamp"])
        if mortgage_history is not None:
            if mortgage_info is None:
                raise ValueError("Provide mortgage_info to link mortgage history to this customer.")
            mortgage_ids = self._mortgages["mortgage_customer_id"]
            self._mortgage_history = mortgage_history[
                mortgage_history["mortgage_customer_id"].isin(mortgage_ids)
            ].copy()
            self._mortgage_history["timestamp"] = pd.to_datetime(
                self._mortgage_history["timestamp"], format="%d%b%y:%H:%M:%S"
            )
            self._mortgage_history = self._mortgage_history.sort_values(
                "timestamp", kind="stable"
            ).reset_index(drop=True)

    def get_profile(self):
        """Return basic information; unavailable age or postal code is None."""
        return {
            "customer_id": self.customer_id,
            "customer_age": self.age,
            "customer_postal_code": self.postal_code
        }

    def has_mortgage_data(self, decision=None):
        """Whether applications exist; optionally select 'approved' or 'rejected'."""
        return not self.get_mortgages(decision).empty

    def get_mortgages(self, decision=None):
        """Return all linked application summaries, including rejected ones.

        Optionally filter by final decision: 'approved' or 'rejected'.
        Original source columns are preserved, including lfinal_loan_to_value.
        required_monthly_income_eur is a requirement, not actual income.
        Missing repayment details are not estimated or filled with zeros.
        """
        mortgages = self._mortgages
        if decision is not None:
            if decision not in ("approved", "rejected"):
                raise ValueError("decision must be 'approved' or 'rejected'")
            if not mortgages.empty:
                mortgages = mortgages[mortgages["final_decision"] == decision]
        return mortgages.copy()

    def get_mortgage_history(self, mortgage_customer_id=None):
        """Return application events, oldest first; optionally select one ID.

        Recorded assessment expenses are not necessarily completed payments.
        """
        history = self._mortgage_history
        if mortgage_customer_id is not None:
            history = history[history["mortgage_customer_id"] == mortgage_customer_id]
        return history.copy()

    def get_mortgage_expenses(self, mortgage_customer_id=None):
        """Return recorded expense events, not a monthly repayment estimate."""
        history = self.get_mortgage_history(mortgage_customer_id)
        if history.empty:
            return history
        return history[
            history["expense_type"].notna() | history["expense_amount"].notna()
        ].copy()

    def get_transactions(self, month=None):
        """Return a copy, sorted oldest first; optionally filter by month."""
        transactions = self._transactions
        if month is not None:
            period = pd.Period(month, freq="M")
            transactions = transactions[
                transactions["tx_date"].dt.to_period("M") == period
            ]
        return transactions.copy()

    def get_months(self):
        """List months with transactions, e.g. ['2024-10', '2024-11']."""
        return self._transactions["tx_date"].dt.to_period("M").astype(str).sort_values().unique().tolist()

    def get_account_ids(self):
        return self._transactions["bank_account_id"].unique().tolist()

    def get_transaction_types(self):
        return self._transactions["transaction_type"].dropna().unique().tolist()

    def get_total_spent(self, month=None):
        """Gross money out as a positive number, including outgoing transfers."""
        amounts = self.get_transactions(month)["tx_amount_eur"]
        return round(float(-amounts[amounts < 0].sum()), 2)

    def get_total_received(self, month=None):
        """Gross money in, including refunds and transfers; not just income."""
        amounts = self.get_transactions(month)["tx_amount_eur"]
        return round(float(amounts[amounts > 0].sum()), 2)

    def get_spending_by_category(self, month=None):
        """Gross outflows by category, largest first; refunds are not deducted."""
        transactions = self.get_transactions(month)
        outgoing = transactions[transactions["tx_amount_eur"] < 0]
        return (
            outgoing.groupby("category", dropna=False)["tx_amount_eur"]
            .sum().mul(-1).round(2).sort_values(ascending=False)
        )

    def get_monthly_summary(self):
        """Monthly gross inflows, outflows and net change; empty months omitted."""
        transactions = self._transactions
        summary = transactions.assign(
            month=transactions["tx_date"].dt.to_period("M").astype(str),
            received=transactions["tx_amount_eur"].clip(lower=0),
            spent=-transactions["tx_amount_eur"].clip(upper=0)
        ).groupby("month")[["received", "spent"]].sum()
        summary["net"] = summary["received"] - summary["spent"]
        return summary.round(2)

    def get_account_balances(self):
        """Latest recorded balance per account, with its timestamp."""
        latest = self._transactions.groupby("bank_account_id", sort=False).tail(1)
        return latest.set_index("bank_account_id")[
            ["tx_timestamp", "balance_after_eur"]
        ].copy()
