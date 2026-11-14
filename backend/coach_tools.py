"""Read-only financial tools; outbound language is a projection, never user prose."""

import calendar
import json
import re
import unicodedata
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Literal
from zoneinfo import ZoneInfo

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .coach_ledger import GateError
from .data_coach import category_reduction, complete_windows, in_window, period_dates, spending_comparison, total_amount
from .financial import spending_rows

CATEGORY_ALIASES = {
    'restaurants': {'restaurants', 'restaurant', 'dining', 'eating', 'takeaway', 'takeout'},
    'groceries': {'groceries', 'grocery', 'supermarket', 'supermarkets'},
    'housing': {'housing', 'rent'}, 'utilities': {'utilities', 'utility'},
    'transportation': {'transportation', 'transport', 'commuting'}, 'entertainment': {'entertainment'},
    'health': {'health', 'healthcare'}, 'lifestyle': {'lifestyle'},
    'home & tech': {'home', 'tech', 'technology'}, 'travel': {'travel'},
}
MONTHS = {name.lower(): index for index, name in enumerate(calendar.month_name) if name}
MONTHS.update({name.lower(): index for index, name in enumerate(calendar.month_abbr) if name})
REDUCTION_WORDS = {'reduce', 'reduced', 'reduction', 'reducing', 'cut', 'cutting', 'less', 'lower', 'lowering',
                   'decrease', 'decreased', 'trim', 'trimming', 'save', 'saving', 'savings'}
COMPARE_WORDS = {'compare', 'compared', 'comparison', 'average', 'usual', 'normally', 'versus', 'vs', 'above', 'below'}
RANK_WORDS = {'where', 'most', 'biggest', 'largest', 'highest', 'top', 'main', 'bulk', 'breakdown', 'overview',
              'distribution', 'split', 'rank', 'ranked', 'ranking', 'categories'}
SPEND_WORDS = {'spending', 'spend', 'spent', 'money', 'cost', 'costs', 'expense', 'expenses', 'expenditure',
               'expenditures', 'outgoings', 'payments'}
WORDS = set(('a an the i me my we our you your it its is am was are were be been do did does can could would should will '
             'have has had how what about if and or of on in for to from with without by at than as this that these those '
             'please tell show explain help understand see give find look which when much more historical recorded '
             'category per month monthly week weekly latest last previous period same instead only again out s not '
             'go goes going went all overall total totals biggest mostly compared back over during between year '
             'food up down percent percentage points next today yesterday tomorrow eats takes taking uses used using portion share').split())
WORDS |= set(MONTHS) | set().union(*CATEGORY_ALIASES.values()) | REDUCTION_WORDS | COMPARE_WORDS | RANK_WORDS | SPEND_WORDS


class Arguments(BaseModel):
    model_config = ConfigDict(extra='forbid')


class LanguageRequest(Arguments):
    intent: Literal['category_spending', 'category_reduction', 'spending_comparison', 'clarify']
    categories: list[str]
    period: Literal['week', 'month'] | None
    dates: list[str]
    date_mode: Literal['explicit', 'latest', 'last', 'missing', 'ambiguous']
    percentages: list[str]


def sanitize_question(question):
    """Constrained English extraction, NOT a general PII detector or a regex privacy guarantee.

    Reject unknown vocabulary/record syntax locally. Rebuild only approved intent/category/date/percentage slots;
    no accepted filler, punctuation or original phrasing is sent to the provider.
    """
    value = unicodedata.normalize('NFKC', question).lower().strip().replace('’', "'")
    if not value.isascii() or len(value) > 500 or not re.fullmatch(r"[a-z0-9 %.,?!'&()\-]+", value):
        raise GateError('privacy_blocked')
    words = set(re.findall(r'[a-z]+', value))
    if not words <= WORDS:
        raise GateError('privacy_blocked')
    # Dates and percentages are the only permitted numbers. Every other numeric residue stays local.
    dates = re.findall(r'(?<![\w-])\d{4}-\d{2}(?:-\d{2})?(?![\w-])', value)
    residual = re.sub(r'(?<![\w-])\d{4}-\d{2}(?:-\d{2})?(?![\w-])', ' ', value)
    month_pattern = r'\b(' + '|'.join(MONTHS) + r')\s+((?:19|20)\d{2})\b'
    for month, year in re.findall(month_pattern, residual):
        dates.append(f'{year}-{MONTHS[month]:02d}-01')
    residual = re.sub(month_pattern, ' ', residual)
    pct_pattern = r'(?<![\w.\-])-?\d{1,3}(?:\.\d{1,2})?\s*(?:%|percent(?:age)?\b)'
    percentages = re.findall(pct_pattern, residual)
    residual = re.sub(pct_pattern, ' ', residual)
    if re.search(r'\d', residual):
        raise GateError('privacy_blocked')
    percentages = [str(Decimal(re.match(r'-?\d+(?:\.\d+)?', item)[0])) for item in percentages]
    try:
        dates = [str(date.fromisoformat(item + '-01' if len(item) == 7 else item)) for item in dates]
    except ValueError:
        dates = []
        invalid_date = True
    else:
        invalid_date = False
    categories = [key for key, aliases in CATEGORY_ALIASES.items() if words & aliases]
    if 'food' in words and not (len(categories) == 1 and categories[0] in {'restaurants', 'groceries'}):
        categories.append('food')
    reduction = bool(percentages or words & REDUCTION_WORDS)
    comparison = bool(words & COMPARE_WORDS)
    ranking = bool(words & RANK_WORDS or ('category' in words and words & SPEND_WORDS)) and not categories
    intent = ('category_reduction' if reduction else 'spending_comparison' if comparison else 'category_spending')
    if not categories and (ranking or words & {'overall', 'total', 'all'}):
        categories = ['all']
    if not (categories or words & SPEND_WORDS or percentages or comparison):
        intent = 'clarify'
    periods = []
    if words & {'week', 'weekly'}:
        periods.append('week')
    if words & {'month', 'monthly'}:
        periods.append('month')
    period = periods[0] if periods else 'month' if dates or words & set(MONTHS) else None
    modes = []
    if dates:
        modes.append('explicit')
    if 'latest' in words:
        modes.append('latest')
    if words & {'last', 'previous'}:
        modes.append('last')
    date_mode = modes[0] if len(modes) == 1 else 'missing' if not modes else 'ambiguous'
    if (invalid_date or len(dates) > 1 or len(periods) > 1 or words & {'this', 'next', 'today', 'yesterday', 'tomorrow'}
            or (words & set(MONTHS) and not dates) or 'year' in words):
        date_mode = 'ambiguous'
    uncertain_percent = bool(percentages and words and not (words & (REDUCTION_WORDS | {'about', 'instead'})))
    if (len(categories) > 1 or len(percentages) > 1 or words & {'without', 'not', 'points', 'more', 'up'}
            or re.search(r'\bto\s+\d+(?:\.\d+)?\s*(?:%|percent)', value) or uncertain_percent
            or (comparison and (reduction or (categories and categories != ['all'])))):
        intent = 'clarify'
    request = LanguageRequest(intent=intent, categories=categories, period=period, dates=dates,
                              date_mode=date_mode, percentages=percentages)
    return request.model_dump_json()


class ComparisonArgs(Arguments):
    period: Literal['week', 'month']


class CategoryArgs(ComparisonArgs):
    category: str = Field(min_length=1, max_length=100, description='Approved category, or all for a bounded spending breakdown.')
    period_start: date


class ReductionArgs(CategoryArgs):
    reduction_percent: Decimal = Field(ge=0, le=100, max_digits=5, decimal_places=2)


ARGUMENTS = {'category_spending': CategoryArgs, 'spending_comparison': ComparisonArgs, 'category_reduction': ReductionArgs}
TOOLS = [{'type': 'function', 'function': {
    'name': name, 'description': 'Read-only historical ' + name.replace('_', ' ') + '; use canonical request and validated context.',
    'parameters': model.model_json_schema(),
}} for name, model in ARGUMENTS.items()]


def today_local():
    return datetime.now(ZoneInfo('Europe/Helsinki')).date()


def safe_prior(prior):
    """Project persisted context again; never forward unknown keys or dataset-derived labels."""
    if not isinstance(prior, dict) or prior.get('name') not in ARGUMENTS:
        return None
    name = prior['name']
    try:
        args = ARGUMENTS[name].model_validate(prior.get('arguments')).model_dump(mode='json')
    except ValidationError:
        return None
    if name != 'spending_comparison' and args['category'] not in {*CATEGORY_ALIASES, 'all'}:
        return None
    if name == 'category_reduction' and args['category'] == 'all':
        return None
    return {'name': name, 'arguments': args}


def routing_context(customer, prior):
    latest = {}
    for period in ('week', 'month'):
        windows = complete_windows(customer, period)
        latest[period] = period_dates(windows[-1]) if windows else None
    return {'previous_selection': safe_prior(prior), 'latest_complete_periods': latest,
            'approved_categories': [*CATEGORY_ALIASES, 'all'], 'calendar_today': str(today_local())}


def expected_selection(question, prior, customer):
    try:
        request = LanguageRequest.model_validate_json(question)
    except ValidationError:
        request = LanguageRequest.model_validate_json(sanitize_question(question))
    old = (safe_prior(prior) or {}).get('arguments', {})
    if request.intent == 'clarify' or request.date_mode == 'ambiguous':
        raise GateError('clarification_needed')
    categories = request.categories or ([old['category']] if old.get('category') else [])
    if categories == ['food']:
        categories = [old['category']] if old.get('category') in {'restaurants', 'groceries'} else []
    if request.intent != 'spending_comparison' and (len(categories) != 1 or categories[0] not in {*CATEGORY_ALIASES, 'all'}):
        raise GateError('clarification_needed')
    period = request.period or old.get('period') or ('month' if categories == ['all'] or request.intent == 'spending_comparison' else None)
    if period is None:
        raise GateError('clarification_needed')
    windows = complete_windows(customer, period)
    latest = period_dates(windows[-1])['start'] if windows else None
    start = None
    if request.date_mode == 'explicit':
        if len(request.dates) != 1:
            raise GateError('clarification_needed')
        start = request.dates[0]
    elif request.date_mode == 'last':
        today = today_local()
        last = today.replace(day=1) - timedelta(days=1) if period == 'month' else today - timedelta(days=today.weekday() + 7)
        start = str(last.replace(day=1) if period == 'month' else last)
    elif request.date_mode == 'latest':
        start = latest
    elif request.date_mode == 'missing':
        start = old.get('period_start')
        if categories == ['all'] and not start:
            start = latest
    if request.intent == 'spending_comparison':
        # The published comparison function only compares the latest full period to earlier history.
        if request.date_mode != 'missing' and (start is None or start != latest):
            raise GateError('clarification_needed')
        return {'name': request.intent, 'arguments': {'period': period}}
    if not start:
        raise GateError('clarification_needed')
    args = {'category': categories[0], 'period': period, 'period_start': start}
    if request.intent == 'category_reduction':
        values = request.percentages or ([old['reduction_percent']] if old.get('reduction_percent') is not None else [])
        if categories == ['all'] or len(values) != 1 or not 0 <= Decimal(str(values[0])) <= 100:
            raise GateError('clarification_needed')
        args['reduction_percent'] = str(Decimal(str(values[0])))
    return {'name': request.intent, 'arguments': args}


def selection(message, question, prior, customer):
    # Resolve ambiguity before considering a model's guesses, including a missing tool call.
    expected = expected_selection(question, prior, customer)
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
        if 'category' in args:
            args['category'] = args['category'].strip().casefold()
        if name != expected['name']:
            raise GateError('invalid_model_output')
        reference = ARGUMENTS[name].model_validate(expected['arguments'])
        if ARGUMENTS[name].model_validate(args) != reference:
            raise GateError('clarification_needed')
    except (KeyError, TypeError, AttributeError, ValidationError):
        raise GateError('invalid_model_output') from None
    return {'name': name, 'arguments': args}


def run_tool(customer, selected):
    selected = safe_prior(selected)
    if selected is None:
        raise GateError('invalid_model_output')
    name, args = selected['name'], selected['arguments']
    try:
        if name == 'spending_comparison':
            result = spending_comparison(customer, args['period'])
            data = {key: result[key] for key in ('currency', 'period', 'status', 'comparison', 'baseline', 'difference_eur', 'coverage')}
        elif name == 'category_reduction':
            result = category_reduction(customer, **{**args, 'period_start': date.fromisoformat(args['period_start'])})
            data = {key: result[key] for key in ('currency', 'category', 'period', 'source_period', 'reduction_percent',
                                                'baseline_spending_eur', 'hypothetical_spending_eur', 'potential_reduction_eur')}
            data['category'] = args['category']
        else:
            window = pd.Period(args['period_start'], freq='W-SUN' if args['period'] == 'week' else 'M')
            if window not in complete_windows(customer, args['period']) or str(window.start_time.date()) != args['period_start']:
                raise ValueError('Invalid period')
            rows = in_window(spending_rows(customer), window)
            data = {'currency': 'EUR', 'category': args['category'], 'period': args['period'], 'source_period': period_dates(window)}
            if args['category'] == 'all':
                labels = rows.category.fillna('').str.strip().str.casefold()
                labels = labels.where(labels.isin(CATEGORY_ALIASES), 'other')
                totals = [(label, total_amount(group)) for label, group in rows.groupby(labels)]
                totals.sort(key=lambda item: (-item[1], item[0]))
                data.update(spending_eur=float(total_amount(rows)),
                            categories=[{'category': label, 'spending_eur': float(amount)} for label, amount in totals[:5]],
                            other_spending_eur=float(sum((amount for _, amount in totals[5:]), Decimal(0))))
            else:
                rows = rows[rows.category.fillna('').str.strip().str.casefold() == args['category']]
                if rows.empty:
                    raise LookupError('No observations')
                data['spending_eur'] = float(total_amount(rows))
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
        elif data['category'] == 'all':
            ranked = '; '.join(f"{row['category']}: EUR {row['spending_eur']:.2f}" for row in data['categories'])
            facts['summary'] = (f"Recorded category breakdown ({dates}): EUR {data['spending_eur']:.2f} total. "
                                + (ranked or 'No recorded spending.'))
            facts['scope'] = (f"At most five category groups shown; remainder EUR {data['other_spending_eur']:.2f}. "
                              'Unrecognized labels are grouped as other. This is historical spending, not a current budget.')
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
