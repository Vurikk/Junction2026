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
The mobile-first placeholder supports customer switching and shows real recorded spending,
budget availability and linked mortgage availability. Recharts is installed for the next chart implementation.
Goals can currently be created through `/docs`; the screen intentionally provides placeholder goal/chart sections.

## Verify

```powershell
.\.venv\Scripts\python.exe -m unittest backend.test_api -v
cd frontend
npm.cmd run build
```

Tests need the local data files. They cover both customers, mortgage missing values, spending exclusions,
budget safety, goal priority/isolation, read-only analysis and validation errors.
`npm.cmd run preview` serves the production bundle only; production API hosting/proxying is not configured.

## API and financial limits

See [docs/API.md](docs/API.md) for JSON contracts and financial semantics.
Python calculates financial values. Spending excludes transfers and unknown transaction types.
Safe daily/weekly budgets and goal feasibility remain unavailable until income, essential bills and reserves are established.
Mortgage applications are never treated as active repayment schedules. Goals reset when the backend stops.
No customer data is sent to external services. Bind both servers to loopback for this unauthenticated demo.
