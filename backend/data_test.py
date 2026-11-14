"""Run beside Customer.py with the original files in a Data folder."""

from pathlib import Path

import pandas as pd

if __package__:
    from .Customer import Customer
else:
    from Customer import Customer


DATA_DIR = Path(__file__).resolve().parent / "Data"
CUSTOMER_IDS = ("CUST04457", "CUST00001")


def load_customers(data_dir=DATA_DIR, chunk_size=100_000):
    """Scan the transaction file in chunks and retain only our two customers."""
    data_dir = Path(data_dir)
    profiles = pd.read_csv(
        data_dir / "tx_customers_junction.csv",
        encoding="utf-8-sig",
        dtype={"customer_postal_code": "string"}
    )
    profiles = profiles[profiles["customer_id"].isin(CUSTOMER_IDS)]

    mortgages = pd.read_csv(
        data_dir / "mtg_tx_customer_link_and_final_mtg_infio.csv",
        encoding="utf-8-sig"
    )
    mortgages = mortgages[mortgages["customer_id"].isin(CUSTOMER_IDS)]

    history = pd.read_csv(data_dir / "mtg_negotiation_history.csv", encoding="utf-8-sig")
    history = history[history["mortgage_customer_id"].isin(mortgages["mortgage_customer_id"])]

    # Accept your .txt filename as well as the repository's original .csv name.
    transaction_path = data_dir / "tx_junction_transactions.txt"
    if not transaction_path.exists():
        transaction_path = data_dir / "tx_junction_transactions.csv"

    selected = []
    with pd.read_csv(
        transaction_path,
        encoding="utf-8-sig",
        parse_dates=["tx_date"],
        dtype={"customer_id": "string", "bank_account_id": "string", "mcc_code": "string"},
        chunksize=chunk_size
    ) as chunks:
        for chunk in chunks:
            matching = chunk[chunk["customer_id"].isin(CUSTOMER_IDS)]
            if not matching.empty:
                selected.append(matching.copy())

    if not selected:
        raise ValueError(f"No transactions found for {CUSTOMER_IDS}")
    transactions = pd.concat(selected, ignore_index=True)

    return [
        Customer(customer_id, transactions, profiles, mortgages, history)
        for customer_id in CUSTOMER_IDS
    ]


def print_customer(customer):
    """Print all available mortgage fields without pandas hiding columns."""
    print(f"\n=== {customer.customer_id} ===")
    print(f"Age: {customer.age} | Postal code: {customer.postal_code}")
    transactions = customer.get_transactions()
    start = transactions["tx_date"].min().date()
    end = transactions["tx_date"].max().date()
    print(f"Transactions: {len(transactions)} | Period: {start} to {end}")
    print(f"Money received: EUR {customer.get_total_received():,.2f}")
    print(f"Money out: EUR {customer.get_total_spent():,.2f}")

    if not customer.has_mortgage_data():
        print("No linked mortgage application in these files.")
        return

    for _, mortgage in customer.get_mortgages().iterrows():
        mortgage_id = mortgage["mortgage_customer_id"]
        print(f"\nMortgage application {mortgage_id} - final summary:")
        for field, value in mortgage.items():
            if pd.notna(value):
                print(f"  {field}: {value}")

        events = customer.get_mortgage_history(mortgage_id)
        print(f"\nEvent history ({len(events)} events; historical details may change):")
        for _, event in events.iterrows():
            print(f"\n  {event['timestamp']} | {event['event_type']}")
            for field, value in event.items():
                if field not in ("mortgage_customer_id", "timestamp", "event_type") and pd.notna(value):
                    print(f"    {field}: {value}")


if __name__ == "__main__":
    print("Loading two customers; scanning the full transaction file may take a moment...")
    with_mortgage, without_mortgage = load_customers()
    print_customer(with_mortgage)
    print_customer(without_mortgage)
