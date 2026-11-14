"""Small Verda transport. Paid calls require an explicit, host-bound review record."""

import hashlib
import json
import os
import platform
import time
import uuid
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_DOWN
from pathlib import Path

import httpx

from .coach_ledger import GateError, Ledger

MODEL = 'deepseek-4-1-flash-1017'
BASE_URL = 'https://inference.verda.com/v1'
INPUT_RATE = '0.1336'  # EUR / million, user Console screenshot, 2026-11-14.
OUTPUT_RATE = '0.5346'
INPUT_BOUND = 1_048_576  # Full documented model context: includes all serialized input/tool/context tokens.
OUTPUT_BOUND = 256  # Verda documents max_tokens as reasoning + answer combined.
PRICE_SOURCE = 'User Verda Console screenshot reviewed 2026-11-14; rates are EUR, not USD.'


def host_identity():
    return hashlib.sha256((platform.node() + ':' + str(uuid.getnode())).encode()).hexdigest()


def state_directory():
    # One canonical location per host/user, shared by every checkout. Never default inside a worktree.
    root = Path(os.environ.get('LOCALAPPDATA', Path.home() / '.local' / 'share'))
    return root / 'SBankCoach' / '.coach_llm'


def identity(cap='1.00'):
    return {'model': MODEL, 'currency': 'EUR', 'input_rate': INPUT_RATE, 'output_rate': OUTPUT_RATE,
            'input_bound': INPUT_BOUND, 'output_bound': OUTPUT_BOUND, 'cap_eur': cap, 'host': host_identity()}


class InstanceLock:
    """OS lock is released on exit/crash; two workers cannot pay concurrently."""
    def __init__(self, path):
        self.file = open(path, 'a+b')
        try:
            self.file.seek(0)
            if os.name == 'nt':
                import msvcrt
                if not self.file.read(1):
                    self.file.write(b'0')
                    self.file.flush()
                self.file.seek(0)
                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.file.close()
            raise GateError('instance_busy') from None

    def close(self):
        self.file.close()


@dataclass
class Settings:
    key: str = field(repr=False)
    ledger: Ledger
    expires_at: float
    lock: InstanceLock | None = field(default=None, repr=False)


def settings_from_env():
    if os.environ.get('COACH_LLM_ENABLED', '').lower() != 'true':
        raise GateError('disabled')
    # Read the originally requested variable but never interpret USD as euros silently.
    legacy_usd = os.environ.get('COACH_LLM_BUDGET_USD')
    cap = os.environ.get('COACH_LLM_BUDGET_EUR')
    if cap is None:
        raise GateError('euro_budget_required' if legacy_usd else 'missing_configuration')
    try:
        if not Decimal(cap).is_finite() or not 0 < Decimal(cap) <= 1:
            raise GateError('invalid_budget')
        cap = format(Decimal(cap).quantize(Decimal('0.01'), rounding=ROUND_DOWN), '.2f')
        if Decimal(cap) <= 0:
            raise GateError('invalid_budget')
    except ArithmeticError:
        raise GateError('invalid_budget') from None
    key = os.environ.get('VERDA_INFERENCE_API_KEY', '')
    if not key or not os.environ.get('VERDA_MODEL') or not os.environ.get('VERDA_BASE_URL'):
        raise GateError('missing_configuration')
    if os.environ['VERDA_MODEL'] != MODEL:
        raise GateError('unverified_model')
    if os.environ['VERDA_BASE_URL'].rstrip('/') not in {BASE_URL, 'https://inference.verda.com'}:
        raise GateError('unapproved_endpoint')
    directory = state_directory()
    try:
        review = json.loads((directory / 'approval.json').read_text(encoding='utf-8'))
        expected = identity(cap)
        if review['identity'] != expected or review['single_paid_host'] is not True:
            raise GateError('deployment_mismatch')
        if not time.time() < review['expires_at'] <= time.time() + 86400:
            raise GateError('pricing_review_expired')
        ledger = Ledger(directory / 'usage.sqlite3', expected)
        ledger.spent()  # mode=rw verifies schema and identity; never creates/reset files.
        lock = InstanceLock(directory / 'instance.lock')
        return Settings(key, ledger, review['expires_at'], lock)
    except (OSError, ValueError, KeyError, TypeError):
        raise GateError('review_required') from None


class VerdaClient:
    def __init__(self, settings, client=None):
        self.settings = settings
        self.client = client or httpx.AsyncClient(
            timeout=14, follow_redirects=False, trust_env=False, transport=httpx.AsyncHTTPTransport(retries=0),
        )

    async def complete(self, call_key, messages, *, tools=None, deadline):
        if time.time() >= self.settings.expires_at:
            raise GateError('pricing_review_expired')
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise GateError('timeout')
        body = {'model': MODEL, 'messages': messages, 'max_tokens': OUTPUT_BOUND,
                'reasoning_effort': 'none', 'temperature': 0, 'stream': False}
        if tools:
            body.update(tools=tools, tool_choice='required', parallel_tool_calls=False)
        else:
            body['response_format'] = {'type': 'json_object'}
        encoded = json.dumps(body, ensure_ascii=True, separators=(',', ':')).encode()
        if len(encoded) > 24_000:
            raise GateError('context_limit')
        # Reserve the full documented context, not an optimistic chars/token guess.
        self.settings.ledger.reserve(call_key, INPUT_BOUND, OUTPUT_BOUND)
        try:
            if deadline <= time.monotonic():
                raise GateError('timeout')
            async with self.client.stream(
                'POST', BASE_URL + '/chat/completions', content=encoded,
                headers={'Authorization': 'Bearer ' + self.settings.key, 'Content-Type': 'application/json'},
                timeout=remaining,
            ) as response:
                if response.status_code != 200:
                    raise GateError('provider_error')
                chunks = bytearray()
                async for chunk in response.aiter_bytes():
                    chunks.extend(chunk)
                    if len(chunks) > 65_536:
                        raise GateError('invalid_model_output')
            result = json.loads(chunks)
            if not isinstance(result, dict):
                raise GateError('invalid_model_output')
            if result.get('model') != MODEL:
                self.settings.ledger.freeze()
                raise GateError('billing_uncertain')
            self.settings.ledger.reconcile(call_key, result.get('usage'))
            choices = result.get('choices')
            if not isinstance(choices, list) or len(choices) != 1:
                raise GateError('invalid_model_output')
            choice = choices[0]
            if choice.get('finish_reason') not in {'stop', 'tool_calls'} or not isinstance(choice.get('message'), dict):
                raise GateError('invalid_model_output')
            if choice['message'].get('reasoning_content'):
                raise GateError('invalid_model_output')
            return choice['message']
        except httpx.TimeoutException:
            raise GateError('timeout') from None
        except (httpx.HTTPError, ValueError, TypeError, KeyError, AttributeError):
            raise GateError('provider_error') from None

    async def close(self):
        await self.client.aclose()
        if self.settings.lock:
            self.settings.lock.close()
