"""Approved read-only tools, privacy projection, and Python-rendered factual explanations."""

import calendar
import json
import re
import unicodedata
from datetime import date
from decimal import Decimal
from typing import Literal

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .coach_ledger import GateError
from .data_coach import category_reduction, complete_windows, in_window, period_dates, spending_comparison, total_amount
from .financial import spending_rows

CATEGORY_ALIASES = {
    'restaurants': {'restaurants', 'restaurant', 'dining', 'eating'},
    'groceries': {'groceries', 'grocery'}, 'housing': {'housing', 'rent'}, 'utilities': {'utilities', 'utility'},
    'transportation': {'transportation', 'transport'}, 'entertainment': {'entertainment'}, 'health': {'health'},
    'lifestyle': {'lifestyle'}, 'home & tech': {'home', 'tech'}, 'travel': {'travel'},
}
MONTHS = {name.lower(): index for index, name in enumerate(calendar.month_name) if name}
WORDS = set(('a an the i me my we our you your it its is was are were be been do did does can could would should will '
             'have has had how what about if and or of on in for to from with without by at than as this that these those '
             'please tell show explain compare compared comparison spending spend spent category categories average historical '
             'recorded reduce reduced reduction reducing less more cut change percent per month monthly week weekly latest '
             'last previous period usual same instead only again much money out s').split())
WORDS |= set(MONTHS) | set().union(*CATEGORY_ALIASES.values())


def sanitize_question(question):
    value = unicodedata.normalize('NFKC', question).lower().strip()
    if not value.isascii() or len(value) > 500 or any(c in value for c in '\r\n\t{}[]<>/@\\:='):
        raise GateError('privacy_blocked')
    # Only a small English financial vocabulary plus dates/percentages can leave the server.
    # Unknown prose/names/identifiers are blocked, not optimistically redacted.
    words = set(re.findall(r'[a-z]+', value))
    if not words <= WORDS:
        raise GateError('privacy_blocked')
    residual = re.sub(r'\b\d{4}-\d{2}(?:-\d{2})?\b', '', value)
    residual = re.sub(r'(?<!\w)-?\d{1,3}(?:\.\d{1,2})?\s*(?:%|percent\b)', '', residual)
    if words & set(MONTHS):
        residual = re.sub(r'\b(?:19|20)\d{2}\b', '', residual)
    if re.search(r'\d', residual):
        raise GateError('privacy_blocked')
    return value


class Arguments(BaseModel):
    model_config = ConfigDict(extra='forbid')


class ComparisonArgs(Arguments):
    period: Literal['week', 'month']


class CategoryArgs(ComparisonArgs):
    category: str = Field(min_length=1, max_length=100)
    period_start: date


class ReductionArgs(CategoryArgs):
    reduction_percent: Decimal = Field(ge=0, le=100, max_digits=5, decimal_places=2)


ARGUMENTS = {'category_spending': CategoryArgs, 'spending_comparison': ComparisonArgs, 'category_reduction': ReductionArgs}
TOOLS = [{'type': 'function', 'function': {
    'name': name, 'description': 'Read-only historical ' + name.replace('_', ' ') + '; use explicit dates or prior context.',
    'parameters': model.model_json_schema(),
}} for name, model in ARGUMENTS.items()]


def routing_context(customer, prior):
    latest = {}
    for period in ('week', 'month'):
        windows = complete_windows(customer, period)
        latest[period] = period_dates(windows[-1]) if windows else None
    return {'previous_selection': prior, 'latest_complete_periods': latest, 'approved_categories': list(CATEGORY_ALIASES)}


def selection(message, question, prior, customer):
    try:
        calls = message.get('tool_calls')
        if message.get('content') not in (None, '') or not isinstance(calls, list) or len(calls) != 1:
            raise GateError('invalid_model_output')
        call = calls[0]
        if call.get('type') != 'function':
            raise GateError('invalid_model_output')
        function = call['function']
        name = function['name']
        if name not in ARGUMENTS or not isinstance(function['arguments'], str) or len(function['arguments']) > 1200:
            raise GateError('invalid_model_output')
        args = ARGUMENTS[name].model_validate_json(function['arguments']).model_dump(mode='json')
    except (KeyError, TypeError, ValidationError):
        raise GateError('invalid_model_output') from None
    words = set(re.findall('[a-z]+', question))
    if ('%' in question or words & {'percent', 'reduce', 'reduced', 'reduction', 'reducing', 'cut'}) and name != 'category_reduction':
        raise GateError('invalid_model_output')
    if name == 'spending_comparison':
        expected = 'week' if words & {'week', 'weekly'} else 'month'
        if args['period'] != expected:
            raise GateError('invalid_model_output')
        return {'name': name, 'arguments': args}
    category = args['category'].strip().casefold()
    mentioned = [key for key, aliases in CATEGORY_ALIASES.items() if words & aliases]
    old = (prior or {}).get('arguments', {})
    if category not in CATEGORY_ALIASES or category not in (mentioned or [old.get('category')]):
        raise GateError('clarification_needed')
    dates = [d if len(d) == 10 else d + '-01' for d in re.findall(r'\b\d{4}-\d{2}(?:-\d{2})?\b', question)]
    for month, year in re.findall(r'(' + '|'.join(MONTHS) + r')\s+((?:19|20)\d{2})\b', question):
        dates.append(f'{year}-{MONTHS[month]:02d}-01')
    expected_period = 'week' if words & {'week', 'weekly'} else 'month' if dates or words & {'month', 'monthly'} else old.get('period')
    if args['period'] != expected_period:
        raise GateError('clarification_needed')
    if 'latest' in words:
        windows = complete_windows(customer, args['period'])
        dates = [period_dates(windows[-1])['start']] if windows else []
    if args['period_start'] not in (dates or [old.get('period_start')]):
        raise GateError('clarification_needed')
    if name == 'category_reduction':
        values = re.findall(r'(-?\d{1,3}(?:\.\d{1,2})?)\s*(?:%|percent\b)', question)
        expected_values = [Decimal(v) for v in values] if values else [old.get('reduction_percent')]
        if not any(v is not None and Decimal(str(v)) == Decimal(args['reduction_percent']) for v in expected_values):
            raise GateError('clarification_needed')
    args['category'] = category
    return {'name': name, 'arguments': args}


def run_tool(customer, selected):
    name, args = selected['name'], selected['arguments']
    try:
        if name == 'spending_comparison':
            result = spending_comparison(customer, args['period'])
            data = {key: result[key] for key in ('currency', 'period', 'status', 'comparison', 'baseline', 'difference_eur', 'coverage')}
        elif name == 'category_reduction':
            result = category_reduction(customer, **{**args, 'period_start': date.fromisoformat(args['period_start'])})
            data = {key: result[key] for key in ('currency', 'category', 'period', 'source_period', 'reduction_percent',
                                                'baseline_spending_eur', 'hypothetical_spending_eur', 'potential_reduction_eur')}
        else:
            window = pd.Period(args['period_start'], freq='W-SUN' if args['period'] == 'week' else 'M')
            if window not in complete_windows(customer, args['period']) or str(window.start_time.date()) != args['period_start']:
                raise ValueError('Invalid period')
            rows = in_window(spending_rows(customer), window)
            rows = rows[rows.category.fillna('').str.strip().str.casefold() == args['category']]
            if rows.empty:
                raise LookupError('No observations')
            data = {'currency': 'EUR', 'category': args['category'], 'period': args['period'],
                    'source_period': period_dates(window), 'spending_eur': float(total_amount(rows))}
    except (ValueError, LookupError):
        raise GateError('unsupported_period_or_category') from None
    return {'type': name, 'data': data}


def facts_for(card):
    data = card['data']
    facts = {'coverage': 'Recorded coverage may be incomplete. Transfers and refunds are excluded.'}
    if card['type'] == 'spending_comparison':
        point, baseline = data['comparison'], data['baseline']
        if not point or not baseline:
            facts['summary'] = 'There is insufficient full-period history for a comparison.'
        else:
            facts['summary'] = (f"{point['start']} to {point['end']}: EUR {point['spending_eur']:.2f} recorded spending; "
                                f"prior-period average EUR {baseline['average_spending_eur']:.2f}; {data['status']} average.")
    else:
        window = data['source_period']
        dates = f"{window['start']} to {window['end']}"
        if card['type'] == 'category_reduction':
            facts['summary'] = (f"{data['category']} ({dates}): EUR {data['baseline_spending_eur']:.2f} recorded; "
                                f"at {data['reduction_percent']:g}% reduction, EUR {data['hypothetical_spending_eur']:.2f} hypothetical; "
                                f"EUR {data['potential_reduction_eur']:.2f} potential spending reduction.")
            facts['hypothetical'] = 'This is not actual savings. Goals and confirmed inputs are unchanged; goal impact is unknown.'
        else:
            facts['summary'] = f"{data['category']} ({dates}): EUR {data['spending_eur']:.2f} recorded spending."
    return facts


def rendered_explanation(message, facts):
    try:
        if message.get('tool_calls'):
            raise ValueError()
        result = json.loads(message['content'])
        keys = result['fact_ids']
        if set(result) != {'fact_ids'} or not isinstance(keys, list) or not 1 <= len(keys) <= len(facts):
            raise ValueError()
        if any(not isinstance(k, str) or k not in facts for k in keys) or len(keys) != len(set(keys)) or 'summary' not in keys:
            raise ValueError()
    except (ValueError, TypeError, KeyError):
        raise GateError('invalid_model_output') from None
    # Required caveats cannot be omitted by a model. No model-generated financial numeral or free prose is returned.
    ordered = keys + [key for key in facts if key not in keys]
    return ' '.join(facts[key] for key in ordered)
