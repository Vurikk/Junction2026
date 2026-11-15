"""Optional local persistence for explicitly confirmed plans, separate from provider billing."""
import json
import sqlite3
from pathlib import Path


class PlanStore:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as db:
            db.execute('CREATE TABLE IF NOT EXISTS plans (customer TEXT PRIMARY KEY, payload TEXT NOT NULL)')

    def load(self, customer):
        with sqlite3.connect(self.path) as db:
            row = db.execute('SELECT payload FROM plans WHERE customer=?', (customer,)).fetchone()
        return json.loads(row[0]) if row else None

    def save(self, customer, payload):
        with sqlite3.connect(self.path) as db:
            db.execute('INSERT INTO plans(customer,payload) VALUES (?,?) '
                       'ON CONFLICT(customer) DO UPDATE SET payload=excluded.payload', (customer, json.dumps(payload)))
