"""Create a private Render secret file; never commit the output."""
import argparse
import base64
import io
from pathlib import Path
import zipfile

import pandas as pd
from .data_test import CUSTOMER_IDS


def package(source, output):
    source = Path(source)
    frames = {}
    for name in ['tx_customers_junction.csv', 'mtg_tx_customer_link_and_final_mtg_infio.csv']:
        frame = pd.read_csv(source / name, dtype=str, keep_default_na=False, encoding='utf-8-sig')
        frames[name] = frame[frame.customer_id.isin(CUSTOMER_IDS)]
    history = pd.read_csv(source / 'mtg_negotiation_history.csv', dtype=str, keep_default_na=False, encoding='utf-8-sig')
    ids = frames['mtg_tx_customer_link_and_final_mtg_infio.csv'].mortgage_customer_id
    frames['mtg_negotiation_history.csv'] = history[history.mortgage_customer_id.isin(ids)]
    tx = source / 'tx_junction_transactions.txt'
    if not tx.exists():
        tx = source / 'tx_junction_transactions.csv'
    selected = []
    with pd.read_csv(tx, dtype=str, keep_default_na=False, encoding='utf-8-sig', chunksize=100_000) as chunks:
        for chunk in chunks:
            selected.append(chunk[chunk.customer_id.isin(CUSTOMER_IDS)])
    frames['tx_junction_transactions.csv'] = pd.concat(selected, ignore_index=True)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, frame in frames.items():
            archive.writestr(name, frame.to_csv(index=False))
    encoded = base64.b64encode(buffer.getvalue())
    if len(encoded) > 1_000_000:
        raise ValueError('Bundle exceeds Render secret file limit')
    Path(output).write_bytes(encoded)
    print(f'Created private two-customer bundle: {len(encoded)} bytes')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('source')
    parser.add_argument('output')
    args = parser.parse_args()
    package(args.source, args.output)
