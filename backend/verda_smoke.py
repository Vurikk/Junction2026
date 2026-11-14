"""One explicitly confirmed paid smoke message; persistent request IDs make repeats cached, not new paid work."""

import argparse
import json
from uuid import uuid4

import httpx

from .verda import state_directory


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8011)
    parser.add_argument('--confirm-paid', action='store_true')
    args = parser.parse_args()
    if not args.confirm_paid or not 1 <= args.port <= 65535:
        parser.exit(2, 'After review, supply --confirm-paid and a valid local backend port.\n')
    directory = state_directory()
    if not (directory / 'approval.json').is_file() or not (directory / 'usage.sqlite3').is_file():
        parser.exit(2, 'Review and initialize the designated backend first. No request sent.\n')
    state_path = directory / 'smoke.json'
    endpoint = '/api/customers/CUST04457/coach'
    try:
        with httpx.Client(base_url=f'http://127.0.0.1:{args.port}', timeout=20, trust_env=False) as client:
            if state_path.exists():
                state = json.loads(state_path.read_text(encoding='utf-8'))
                client.cookies.set('coach_session', state['cookie'])
            else:
                bootstrap = client.post(endpoint, json={'question': 'spending categories'})
                bootstrap.raise_for_status()
                initial = bootstrap.json()
                if initial.get('fallback_reason') != 'session_initialized':
                    parser.exit(2, 'Paid configuration not ready; check safe fallback_reason. No paid smoke request sent.\n')
                state = {'cookie': client.cookies['coach_session'], 'conversation_id': initial['conversation_id'],
                         'request_id': str(uuid4())}
                # Exclusive create prevents concurrent smoke invocations creating two paid messages.
                with state_path.open('x', encoding='utf-8') as output:
                    json.dump(state, output)
            response = client.post(endpoint, json={
                'question': 'What if I reduce restaurants in July 2026 by 20%?',
                'conversation_id': state['conversation_id'], 'request_id': state['request_id'],
            })
            response.raise_for_status()
            result = response.json()
            print(json.dumps({key: result.get(key) for key in ('mode', 'fallback_reason', 'cards')}, indent=2))
            if result.get('mode') != 'llm':
                parser.exit(1, 'Smoke returned a safe fallback. Do not erase the ledger or retry with a new ID automatically.\n')
    except (httpx.HTTPError, OSError, ValueError, KeyError):
        parser.exit(2, 'Smoke incomplete. Stored request identity is retained; repeating this command does not create a new paid turn.\n')


if __name__ == '__main__':
    main()
