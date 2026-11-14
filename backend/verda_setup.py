"""Explicit local review/initialization; never invoked by backend startup and never calls Verda."""

import argparse
import json
import os
import sqlite3
import time
from decimal import Decimal, ROUND_DOWN

from .coach_ledger import GateError, Ledger
from .verda import BASE_URL, INPUT_RATE, MODEL, OUTPUT_RATE, host_identity, identity, state_directory


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--show-host', action='store_true')
    parser.add_argument('--status', action='store_true')
    parser.add_argument('--approve-paid', action='store_true')
    parser.add_argument('--designated-host')
    parser.add_argument('--confirm-eur-prices', nargs=2)
    args = parser.parse_args()
    directory = state_directory()
    if args.show_host:
        print(host_identity())
        return
    try:
        cap = os.environ.get('COACH_LLM_BUDGET_EUR', '')
        if not cap or not Decimal(cap).is_finite() or not Decimal(0) < Decimal(cap) <= Decimal(1):
            raise GateError('Set COACH_LLM_BUDGET_EUR explicitly, at most 1.00; USD configuration is not reused.')
        cap = format(Decimal(cap).quantize(Decimal('0.01'), rounding=ROUND_DOWN), '.2f')
        expected = identity(cap)
        path = directory / 'usage.sqlite3'
        review_path = directory / 'approval.json'
        if args.status:
            print(json.dumps({'currency': 'EUR', 'cap': cap, 'charged_or_reserved': Ledger(path, expected).spent()}))
            return
        if not args.approve_paid or args.designated_host != host_identity():
            raise GateError('Explicit approval and the designated host fingerprint are required.')
        if args.confirm_eur_prices != [INPUT_RATE, OUTPUT_RATE]:
            raise GateError('Confirm the exact reviewed EUR input/output prices; unsupported prices fail closed.')
        if os.environ.get('VERDA_MODEL') != MODEL:
            raise GateError('VERDA_MODEL must exactly match deepseek-4-1-flash-1017.')
        if os.environ.get('VERDA_BASE_URL', '').rstrip('/') not in {BASE_URL, 'https://inference.verda.com'}:
            raise GateError('VERDA_BASE_URL must be the reviewed Verda inference endpoint.')
        if review_path.exists():
            previous = json.loads(review_path.read_text(encoding='utf-8'))
            if previous['identity'] != expected:
                raise GateError('Existing deployment identity/cap differs. No reset or increase is allowed.')
            Ledger(path, expected).spent()  # A missing ledger with an approval file fails; never recreates it.
        elif path.exists():
            Ledger(path, expected).spent()  # Recover review only; preserve every existing charge/reservation.
        else:
            Ledger.initialize(path, expected)
        review = {'identity': expected, 'single_paid_host': True, 'expires_at': time.time() + 86400}
        temporary = directory / 'approval.pending'
        temporary.write_text(json.dumps(review), encoding='utf-8')
        temporary.replace(review_path)
        print('Review recorded for this host for 24 hours. Existing ledger preserved. No provider call made.')
        print('Only this designated host may hold the paid deployment. Other PCs must use its backend, not create ledgers.')
    except (GateError, OSError, sqlite3.Error, ArithmeticError, ValueError, KeyError):
        parser.exit(2, 'Review/status failed: check non-secret model, EUR budget, host, rates and existing ledger. Nothing was reset.\n')


if __name__ == '__main__':
    main()
