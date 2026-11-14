# S-Bank Financial Coach — foundation

Minimal FastAPI + React/Vite local demo using the existing two synthetic customers.
The coach uses Python response templates. No LLM, API keys, authentication or database is required.

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
.\.venv\Scripts\python.exe -m unittest backend.test_financial backend.test_coach backend.test_api backend.test_integration -v
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
Category/basket classifications are heuristics. The Coach page offers short deterministic answers and read-only goal previews.
By default, no customer data is sent to external services. Optional Verda mode sends only filtered questions and aggregate facts.
It requires explicit review and a persistent EUR 1 cap; see [backend/VERDA_HANDOFF.md](backend/VERDA_HANDOFF.md).
Bind both servers to loopback for this unauthenticated demo.

## Rule-based coach

Run the backend and frontend as above, then open Coach. Suggested questions cover categories,
historical averages, daily/weekly allowances, goal progress and adding a hypothetical goal.
Category answers show the latest recorded month; averages compare the latest complete month
with the average of complete months. Recorded coverage may be incomplete.
Confirm planning inputs on Home for allowance and goal estimates. Saved progress is unavailable.
Preview a goal with its name, amount and priority; only **Confirm and create goal** saves it.
Preview shows current and hypothetical allowances. Editing any scenario field invalidates its confirmation;
preview again before saving. Switching customers or discarding a preview does not create a goal.
Goal creation also displays a short message from the existing goal-analysis API.

Templates and question routing live in `backend/coach.py`; calculations remain in `backend/financial.py`.
A future language provider can replace the presentation layer without changing the engine.
Run synthetic checks without customer data: `python -m unittest backend.test_financial backend.test_coach -v`.
Run `npm.cmd run build` inside `frontend` to verify the React production build.

If the default ports are occupied, leave the existing servers intact and run the backend on another port,
for example `--port 8011`. In the frontend terminal use:

```powershell
$env:SBANK_API_TARGET='http://127.0.0.1:8011'
npm.cmd run dev -- --port 5174
```

The coach uses English keywords and category names, not general language understanding. Category answers use the latest month;
average answers use complete calendar months. What-if scenarios only add one hypothetical goal; they do not edit goals or income.
Mortgage applications never imply active debt or known repayments. Current balances and saved goal progress remain unknown.
Confirmation creates a goal using the current plan; it does not lock a financial forecast or persist data across restarts.
