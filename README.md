# S-Bank Financial Coach — foundation

Minimal FastAPI + React/Vite local demo using the existing two synthetic customers.
No LLM, authentication, database or full coaching UI is implemented.

## Requirements and local data

Python 3.11+ and Node.js 20.19+ (or 22.12+). Run commands from the repository root.
Keep these original files in `backend/Data/` (gitignored):

- `tx_customers_junction.csv`
- `tx_junction_transactions.txt` (or `.csv`)
- `mtg_tx_customer_link_and_final_mtg_infio.csv` (original spelling)
- `mtg_negotiation_history.csv`

Alternatively set `SBANK_DATA_DIR` to their directory before starting the backend.
The existing chunked loader retains only `CUST04457` and `CUST00001`; startup scans the transaction file once.
`Customer.py` and its mortgage/history linking remain the source of customer data.
The desktop `DataVisualizer.py` remains available separately with matplotlib installed.

## Run the backend (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Use `py` instead of `python` if your Windows installation provides the Python launcher.
No virtual environment activation is required. Wait for `Application startup complete`.
API: <http://127.0.0.1:8000/api/health>; interactive contracts: <http://127.0.0.1:8000/docs>.
Optional `--reload` reloads code and clears in-memory goals. Use a single worker.

## Run the frontend (second PowerShell terminal)

```powershell
cd frontend
npm.cmd install
npm.cmd run dev
```

Open <http://127.0.0.1:5173>. Vite forwards `/api` to port 8000; no CORS setup is necessary.
On macOS/Linux use `npm` and `.venv/bin/python` instead of the Windows commands above.
The mobile-first UI supports customer switching, weekly/monthly Recharts spending charts with average/target lines,
three goal priorities, goal creation and analysis. On Home, confirm the six planning amounts to calculate allowances.
Optional weekly/monthly chart targets are independent of safe allowances. Mortgage application availability is shown on Home.

## Verify

```powershell
.\.venv\Scripts\python.exe -m unittest backend.test_financial backend.test_api backend.test_integration -v
cd frontend
npm.cmd run build
```

Tests need the local data files. They cover both customers, mortgage missing values, spending exclusions,
budget safety, goal priority/isolation, read-only analysis and validation errors.
The live integration test starts and stops its own isolated Uvicorn process on a free loopback port;
it verifies both customers, confirmed inputs, chart targets and three-priority allocations through real HTTP.
`npm.cmd run preview` serves the production bundle only; production API hosting/proxying is not configured.

## API and financial limits

See [docs/API.md](docs/API.md) for base JSON contracts and [backend/API.md](backend/API.md) for financial planning contracts.
Python calculates financial values. Spending excludes transfers and unknown transaction types.
Safe daily/weekly budgets and goal feasibility remain unavailable until income, essential bills and reserves are established.
Mortgage applications are never treated as active repayment schedules. Goals reset when the backend stops.
Confirmed inputs also reset. Completion estimates require explicitly confirmed repeating capacity; they are conditional.
The model uses aggregate cash across a planning horizon and does not model intra-period liquidity or goal progress.
Category/basket classifications are heuristics. The Coach page remains a placeholder, with no LLM connected.
No customer data is sent to external services. Bind both servers to loopback for this unauthenticated demo.
