"""Persistent accounting and idempotency. Never store prompts, API keys or raw records."""

import json
import sqlite3
import time
from contextlib import closing, contextmanager
from decimal import Decimal, ROUND_CEILING
from pathlib import Path

SCALE = 1_000_000_000_000  # Integer pico-euros; rounding never understates cost.


class GateError(Exception):
    """A public, fixed reason code, never a provider message."""


def units(value):
    return int((Decimal(str(value)) * SCALE).to_integral_value(rounding=ROUND_CEILING))


def cost(input_tokens, output_tokens, input_rate, output_rate):
    return units((Decimal(input_tokens) * Decimal(input_rate) + Decimal(output_tokens) * Decimal(output_rate)) / 1_000_000)


class Ledger:
    def __init__(self, path, identity):
        self.path = Path(path).resolve()
        self.identity = identity

    @classmethod
    def initialize(cls, path, identity):
        """Explicit operator action only. Refuse to overwrite or reset an existing ledger."""
        path = Path(path).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb'):
            pass
        ledger = cls(path, identity)
        with closing(sqlite3.connect(path)) as db:
            db.executescript('''
                CREATE TABLE settings (id INTEGER PRIMARY KEY CHECK(id=1), identity TEXT NOT NULL, frozen INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE calls (key TEXT PRIMARY KEY, reserved INTEGER NOT NULL, charged INTEGER NOT NULL,
                                    input_bound INTEGER NOT NULL, output_bound INTEGER NOT NULL, state TEXT NOT NULL);
                CREATE TABLE requests (key TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, session TEXT NOT NULL,
                                       created REAL NOT NULL, response TEXT);
                CREATE TABLE conversations (id TEXT PRIMARY KEY, owner TEXT NOT NULL, customer TEXT NOT NULL,
                                            updated REAL NOT NULL, context TEXT NOT NULL);
            ''')
            db.execute('INSERT INTO settings(id, identity) VALUES(1, ?)', (json.dumps(identity, sort_keys=True),))
            db.commit()
        return ledger

    @contextmanager
    def transaction(self):
        # mode=rw is essential: deleting or moving the ledger must never reset the budget.
        db = sqlite3.connect(self.path.as_uri() + '?mode=rw', uri=True, timeout=0.1)
        try:
            db.execute('BEGIN IMMEDIATE')
            setting = db.execute('SELECT identity, frozen FROM settings WHERE id=1').fetchone()
            if not setting or json.loads(setting[0]) != self.identity:
                raise GateError('ledger_mismatch')
            yield db, bool(setting[1])
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def reserve(self, key, input_bound, output_bound):
        amount = cost(input_bound, output_bound, self.identity['input_rate'], self.identity['output_rate'])
        with self.transaction() as (db, frozen):
            if frozen:
                raise GateError('billing_uncertain')
            if db.execute('SELECT 1 FROM calls WHERE key=?', (key,)).fetchone():
                raise GateError('duplicate_call')
            used = db.execute('SELECT COALESCE(SUM(charged), 0) FROM calls').fetchone()[0]
            if used + amount > units(self.identity['cap_eur']):
                raise GateError('budget_exhausted')
            db.execute('INSERT INTO calls VALUES(?, ?, ?, ?, ?, ?)',
                       (key, amount, amount, input_bound, output_bound, 'reserved'))

    def reconcile(self, key, usage):
        """Missing/error usage retains the full reservation. Never assume unbilled errors."""
        if not isinstance(usage, dict):
            return
        prompt, completion, total = (usage.get(k) for k in ('prompt_tokens', 'completion_tokens', 'total_tokens'))
        if any(type(v) is not int or v < 0 for v in (prompt, completion, total)) or total != prompt + completion:
            return
        # Reasoning is included in completion_tokens by the reviewed Verda contract.
        reasoning = usage.get('completion_tokens_details', {})
        if not isinstance(reasoning, dict) or reasoning.get('reasoning_tokens', 0) not in range(completion + 1):
            return
        violation = False
        with self.transaction() as (db, _):
            row = db.execute('SELECT reserved, input_bound, output_bound, state FROM calls WHERE key=?', (key,)).fetchone()
            if not row or row[3] != 'reserved':
                return
            actual = cost(prompt, completion, self.identity['input_rate'], self.identity['output_rate'])
            if prompt > row[1] or completion > row[2] or actual > row[0]:
                db.execute('UPDATE settings SET frozen=1 WHERE id=1')
                db.execute('UPDATE calls SET charged=?, state=? WHERE key=?', (max(actual, row[0]), 'over_bound', key))
                violation = True
            else:
                db.execute('UPDATE calls SET charged=?, state=? WHERE key=?', (actual, 'reconciled', key))
        if violation:
            raise GateError('billing_uncertain')

    def conversation(self, conversation_id, owner, customer):
        now = time.time()
        with self.transaction() as (db, _):
            row = db.execute('SELECT owner, customer, updated, context FROM conversations WHERE id=?', (conversation_id,)).fetchone()
            if row:
                if row[:2] != (owner, customer):
                    raise GateError('conversation_mismatch')
                return json.loads(row[3]) if now - row[2] <= 1800 else None
            count = db.execute('SELECT COUNT(*) FROM conversations WHERE owner=?', (owner,)).fetchone()[0]
            if count >= 32:
                raise GateError('session_limit')
            db.execute('INSERT INTO conversations VALUES(?, ?, ?, ?, ?)', (conversation_id, owner, customer, now, 'null'))
        return None

    def claim(self, key, fingerprint, session):
        now = time.time()
        with self.transaction() as (db, _):
            row = db.execute('SELECT fingerprint, response FROM requests WHERE key=?', (key,)).fetchone()
            if row:
                if row[0] != fingerprint:
                    raise GateError('request_conflict')
                if row[1] is None:
                    raise GateError('request_in_progress')
                cached = json.loads(row[1])
                # Only a proven-unstarted busy rejection may be readmitted. Keep its original fingerprint.
                prefix = key + ':'
                called = db.execute('SELECT 1 FROM calls WHERE key=? OR substr(key, 1, ?)=? LIMIT 1',
                                    (key, len(prefix), prefix)).fetchone()
                if (cached.get('fallback_reason') != 'concurrency_limit' or cached.get('mode') != 'rule_based'
                        or cached.get('cards') or called):
                    return cached
            recent = db.execute('SELECT session FROM requests WHERE created>? AND key<>?', (now - 60, key)).fetchall()
            if len(recent) >= 12 or sum(r[0] == session for r in recent) >= 4:
                raise GateError('rate_limited')
            if row:
                db.execute('UPDATE requests SET response=NULL, created=? WHERE key=?', (now, key))
            else:
                db.execute('INSERT INTO requests VALUES(?, ?, ?, ?, NULL)', (key, fingerprint, session, now))
        return None

    def finish(self, key, response, conversation_id, context=None):
        with self.transaction() as (db, _):
            db.execute('UPDATE requests SET response=? WHERE key=?', (json.dumps(response), key))
            if context is not None:
                db.execute('UPDATE conversations SET context=?, updated=? WHERE id=?',
                           (json.dumps(context), time.time(), conversation_id))

    def freeze(self):
        with self.transaction() as (db, _):
            db.execute('UPDATE settings SET frozen=1 WHERE id=1')

    def spent(self):
        with self.transaction() as (db, _):
            return db.execute('SELECT COALESCE(SUM(charged), 0) FROM calls').fetchone()[0] / SCALE
