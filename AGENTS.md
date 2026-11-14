
# S-Bank Financial Coach — Junction 2026

## Goal
Build a mobile-first financial coaching web app inspired by S-mobiili.

The app helps users understand spending, set financial goals,
and learn what they can realistically save or spend.

## Technology
- React + Vite + plain CSS frontend
- Python + FastAPI backend
- Recharts for graphs
- Existing synthetic S-Bank data processing
- External LLM API for natural-language explanations

## Main features
1. Switch between two demo customers.
2. Spending histogram with horizontal average and budget lines.
3. Daily and weekly estimated spending allowance.
4. Goals created with name, amount and priority.
5. Critical goals take priority over flexible savings.
6. AI explains goal feasibility and spending patterns.
7. Mortgage information where supported by the data.

## Financial rules
- Python calculates all financial values.
- Never invent missing financial information.
- Protect essential bills and emergency reserves.
- Do not double-count transfers.
- LLM receives only necessary aggregated financial summaries.
- AI never modifies goals without user confirmation.

## Development rules
- Keep code simple and readable.
- Avoid unnecessary abstractions.
- Keep code lines under 150 characters.
- Reuse existing Python code where practical.
- Keep the frontend mobile-first.
- Run relevant tests after changes.
- Do not modify unrelated files.
- Do not commit secrets or raw customer datasets.
