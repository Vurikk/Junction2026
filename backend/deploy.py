"""Start the hosted demo using a private, compressed two-customer data bundle."""
import base64
import io
import os
from pathlib import Path
import tempfile
import zipfile

FILES = {'tx_customers_junction.csv', 'tx_junction_transactions.csv',
         'mtg_tx_customer_link_and_final_mtg_infio.csv', 'mtg_negotiation_history.csv'}


def unpack_bundle(source, destination):
    with zipfile.ZipFile(io.BytesIO(base64.b64decode(Path(source).read_text(), validate=True))) as archive:
        if set(archive.namelist()) != FILES:
            raise ValueError('Demo bundle must contain exactly the four expected CSV files')
        if sum(item.file_size for item in archive.infolist()) > 20_000_000:
            raise ValueError('Demo bundle exceeds the two-customer size limit')
        destination = Path(destination)
        destination.mkdir(parents=True, exist_ok=True)
        for name in FILES:
            (destination / name).write_bytes(archive.read(name))
    return destination


if __name__ == '__main__':
    import uvicorn
    source = os.environ.get('SBANK_DEMO_BUNDLE', '/etc/secrets/sbank-demo-data.b64')
    if not os.environ.get('SBANK_DATA_DIR'):
        directory = Path(tempfile.mkdtemp(prefix='sbank-demo-'))
        os.environ['SBANK_DATA_DIR'] = str(unpack_bundle(source, directory))
    uvicorn.run('backend.main:app', host='0.0.0.0', port=int(os.environ.get('PORT', '10000')), workers=1)
