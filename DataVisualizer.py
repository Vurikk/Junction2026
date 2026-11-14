"""Run: python DataVisualizer.py. Requires pandas and matplotlib."""

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.widgets import Button, RadioButtons, Slider

from data_test import load_customers


class DataVisualizer:
    def __init__(self, customers):
        self.customers = {customer.customer_id: customer for customer in customers}
        self.customer = customers[0]
        self.periods = ["MAX"] + sorted({month for customer in customers for month in customer.get_months()})
        self.figure, self.axes = plt.subplots(2, 2, figsize=(14, 9), facecolor="#f5f7fa")
        self.figure.canvas.manager.set_window_title("Customer data")
        self.figure.subplots_adjust(left=0.13, right=0.96, bottom=0.09, top=0.72, hspace=0.6, wspace=0.42)
        self.figure.text(0.06, 0.95, "Customer overview", fontsize=22, weight="bold", color="#18332e")
        self.profile_text = self.figure.text(0.06, 0.91, "", fontsize=11)
        self.totals_text = self.figure.text(0.06, 0.86, "", fontsize=13)
        self.figure.text(
            0.06, 0.025,
            "Money in includes refunds/transfers; money out includes transfers. Mortgage details use all recorded history.",
            fontsize=9, color="#566573"
        )

        self.customer_buttons = RadioButtons(
            self.figure.add_axes([0.74, 0.85, 0.22, 0.1], facecolor="white"), list(self.customers)
        )
        self.customer_buttons.on_clicked(self.change_customer)
        self.month_slider = Slider(
            self.figure.add_axes([0.13, 0.79, 0.57, 0.025]), "Month", 0, len(self.periods) - 1,
            valinit=0, valstep=1, color="#278a73"
        )
        self.month_slider.on_changed(self.redraw)
        self.max_button = Button(self.figure.add_axes([0.82, 0.78, 0.1, 0.045]), "MAX / all dates")
        self.max_button.on_clicked(lambda event: self.month_slider.set_val(0))
        self.redraw()

    def change_customer(self, customer_id):
        self.customer = self.customers[customer_id]
        self.redraw()

    def redraw(self, value=None):
        period = self.periods[int(self.month_slider.val)]
        month = None if period == "MAX" else period
        customer = self.customer
        transactions = customer.get_transactions(month)
        received = customer.get_total_received(month)
        spent = customer.get_total_spent(month)
        self.month_slider.valtext.set_text(period)
        self.profile_text.set_text(
            f"{customer.customer_id}  |  Age: {customer.age}  |  Postal code: {customer.postal_code}"
        )
        self.totals_text.set_text(
            f"Money in: EUR {received:,.2f}     Money out: EUR {spent:,.2f}     Net: EUR {received - spent:,.2f}"
        )
        for ax in self.axes.flat:
            ax.clear()
            ax.set_facecolor("white")
            ax.spines[["top", "right"]].set_visible(False)

        categories_ax, flow_ax, balance_ax, mortgage_ax = self.axes.flat
        spending = customer.get_spending_by_category(month).sort_values()
        if spending.empty:
            self.show_empty(categories_ax, "No outgoing transactions in this period.")
        else:
            labels = ["Uncategorised" if pd.isna(name) else str(name) for name in spending.index]
            bars = categories_ax.barh(labels, spending.values, color="#278a73")
            categories_ax.bar_label(bars, fmt="%.0f", padding=3, fontsize=8)
            categories_ax.margins(x=0.2)
            categories_ax.tick_params(axis="y", labelsize=9)
        categories_ax.set_title(f"Outgoing by category - {period}", loc="left", weight="bold")
        categories_ax.set_xlabel("EUR")

        summary = customer.get_monthly_summary()
        if month is not None:
            summary = summary.loc[summary.index == month]
        if summary.empty:
            self.show_empty(flow_ax, "No transactions in this period.")
        else:
            summary[["received", "spent"]].rename(columns={"received": "Money in", "spent": "Money out"}).plot.bar(
                ax=flow_ax, color=["#278a73", "#d77a61"], rot=45, width=0.8
            )
            flow_ax.tick_params(axis="x", labelsize=8)
            flow_ax.set_xlabel("")
            flow_ax.margins(y=0.25)
            flow_ax.legend(frameon=False, fontsize=9)
        flow_ax.set_title("Monthly money in / out", loc="left", weight="bold")
        flow_ax.set_ylabel("EUR")

        if transactions.empty:
            self.show_empty(balance_ax, "No recorded balances in this period.")
        else:
            for account_id, rows in transactions.groupby("bank_account_id"):
                balance_ax.plot(rows["tx_timestamp"], rows["balance_after_eur"], label=account_id, linewidth=1.5, marker=".")
            locator = mdates.AutoDateLocator(minticks=3, maxticks=7)
            balance_ax.xaxis.set_major_locator(locator)
            balance_ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))
            balance_ax.legend(frameon=False, fontsize=8)
        balance_ax.set_title("Recorded account balances", loc="left", weight="bold")
        balance_ax.set_ylabel("EUR")

        self.draw_mortgage(mortgage_ax)
        self.figure.canvas.draw_idle()

    @staticmethod
    def show_empty(ax, message):
        ax.text(0.5, 0.5, message, ha="center", va="center", transform=ax.transAxes, fontsize=10)
        ax.set_xticks([])
        ax.set_yticks([])

    def draw_mortgage(self, ax):
        ax.axis("off")
        ax.set_title("Mortgage application - all dates", loc="left", weight="bold")
        mortgages = self.customer.get_mortgages()
        if mortgages.empty:
            ax.text(0, 0.9, "No linked mortgage application in these files.", va="top", transform=ax.transAxes)
            return

        # The demo customers have at most one application each.
        mortgage = mortgages.iloc[0]
        lines = [f"{mortgage['mortgage_customer_id']}  |  {mortgage['final_decision'].upper()}"]
        fields = {
            "Property price": "final_property_price_eur",
            "Requested loan": "final_requested_loan_eur",
            "Own contribution": "final_equity_amount_eur",
            "Collateral value": "final_collateral_value_eur",
            "Required monthly income": "required_monthly_income_eur"
        }
        for label, field in fields.items():
            value = mortgage.get(field)
            lines.append(f"{label}: EUR {value:,.2f}" if pd.notna(value) else f"{label}: not provided")
        ratio = mortgage.get("lfinal_loan_to_value")
        if pd.notna(ratio):
            lines.append(f"Loan / property value: {ratio:.1%}")
        if pd.notna(mortgage.get("rejection_reason")):
            lines.append(f"Reason: {mortgage['rejection_reason'].replace('_', ' ')}")
        lines.append(f"History: {len(self.customer.get_mortgage_history())} recorded events")
        lines.append("Monthly payment: not provided")
        ax.text(0, 0.98, "\n".join(lines), va="top", transform=ax.transAxes, fontsize=10, linespacing=1.5)

    def show(self):
        plt.show()


if __name__ == "__main__":
    print("Loading the two customers...")
    visualizer = DataVisualizer(load_customers())
    visualizer.show()
