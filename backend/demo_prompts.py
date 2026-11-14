"""Curated questions for a transparent demo; dates come from recorded coverage, never invented inputs."""

import re

from .savings_demo import savings_answer

from .data_coach import category_reduction, complete_windows, period_dates

EVERYDAY_TIPS = {
    'how can i spend less money on groceries': (
        'General tips: plan a few meals before shopping, check what you already have, use a list and compare unit prices. '
        'Choose quantities you can use to avoid waste. Protect enough food for your household and any dietary needs. '
        'These tips do not estimate your personal savings.'),
    'how do i stop impulse buying online': (
        'General tips: put nonessential items on a wish list and pause before checking out. '
        'Turn off promotional notifications and remove saved payment details if that helps you pause. '
        'Check your plan before buying; essential purchases should not be delayed. '
        'These tips do not estimate your personal savings.'),
}

GUIDE_QUESTIONS = {
    'how can i save money', 'how can i save', 'where can i save money',
    'from what categories would be easy to save from', 'what categories can i save on',
    'what categories could i save on', 'where could i cut spending',
}


def demo_prompts(customer):
    windows = complete_windows(customer, 'month')
    if not windows:
        return {'questions': [], 'note': 'No complete recorded month is available for these demo questions.'}
    start = period_dates(windows[-1])['start']
    questions = [{'id': 'overview', 'label': 'Where did my money go?',
                  'question': f'Show spending by category in {start[:7]}'}]
    questions.append({'id': 'save-most', 'label': 'Where could I save the most?',
                      'question': f'Where could I save the most in {start[:7]}?'})
    if len(windows) >= 2:
        questions.append({'id': 'comparison', 'label': 'Compare my monthly spending',
                          'question': 'Compare my monthly spending'})
    for window in reversed(windows):
        start = period_dates(window)['start']
        try:
            category_reduction(customer, category='restaurants', period='month',
                               period_start=window.start_time.date(), reduction_percent=20)
        except (ValueError, LookupError):
            continue
        questions.append({'id': 'restaurants', 'label': f'Restaurants: 20% less ({start[:7]})',
                          'question': f'What if I reduce restaurant spending in {start[:7]} by 20%?'})
        break
    return {'questions': questions,
            'note': 'Demo questions use dated recorded spending. Reductions are hypothetical, not confirmed savings.'}


def demo_guidance(question, customer):
    # Exact curated intents only. Do not strip names, IDs, amounts or arbitrary suffixes into a permitted question.
    normalized = re.sub(r'\s+', ' ', question.casefold().strip()).rstrip('?.!').strip()
    if normalized in EVERYDAY_TIPS:
        return EVERYDAY_TIPS[normalized]
    savings = savings_answer(normalized, customer)
    if savings is not None:
        return savings
    if normalized not in GUIDE_QUESTIONS:
        return None
    prompts = demo_prompts(customer)
    if not prompts['questions']:
        return prompts['note']
    return ('To explore possible savings, start with your recorded category spending and choose a cost you are comfortable changing. '
            'A large category is not necessarily easy or safe to cut; protect essential bills and your emergency reserve. '
            'Choose a Demo question below. For example: "' + prompts['questions'][0]['question'] + '". '
            'A restaurant reduction is a hypothetical example, not a recommended budget or confirmed savings.')
