"""Bounded, process-local context for free Coach calculations; never opens the paid ledger."""

from copy import deepcopy
import time

from .coach_ledger import GateError


class LocalCoachState:
    TTL = 1800
    MAX_CONVERSATIONS = 256
    MAX_REQUESTS = 2048

    def __init__(self):
        self.conversations = {}
        self.requests = {}

    def prune(self):
        cutoff = time.monotonic() - self.TTL
        self.conversations = {key: row for key, row in self.conversations.items() if row['updated'] > cutoff}
        self.requests = {key: row for key, row in self.requests.items() if row['updated'] > cutoff}

    def conversation(self, conversation_id, owner, customer):
        self.prune()
        row = self.conversations.get(conversation_id)
        if row:
            if (row['owner'], row['customer']) != (owner, customer):
                raise GateError('conversation_mismatch')
            return deepcopy(row['context'])
        if len(self.conversations) >= self.MAX_CONVERSATIONS or sum(
                row['owner'] == owner for row in self.conversations.values()) >= 32:
            raise GateError('session_limit')
        self.conversations[conversation_id] = {
            'owner': owner, 'customer': customer, 'updated': time.monotonic(), 'context': None,
        }
        return None

    def claim(self, key, fingerprint):
        self.prune()
        row = self.requests.get(key)
        if row:
            if row['fingerprint'] != fingerprint:
                raise GateError('request_conflict')
            if row['response'] is None:
                raise GateError('request_in_progress')
            return deepcopy(row['response'])
        if len(self.requests) >= self.MAX_REQUESTS:
            raise GateError('session_limit')
        self.requests[key] = {'fingerprint': fingerprint, 'response': None, 'updated': time.monotonic()}
        return None

    def finish(self, key, response, conversation_id, context):
        self.requests[key]['response'] = deepcopy(response)
        if context is not None:
            row = self.conversations[conversation_id]
            row.update(context=deepcopy(context), updated=time.monotonic())
