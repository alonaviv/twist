from django.shortcuts import render
from django.utils.safestring import mark_safe

from .strings import STRINGS

PRACTICE_TICKETS_URL = 'https://tic.li/gBqLGKy'
ALL_EVENTS_URL = 'https://tic.li/g5ZAbNz'
WHATSAPP_GROUP_URL = 'http://tinyurl.com/552vzk87'
# The chatty community group, as opposed to the quiet announcements-only one above.
COMMUNITY_GROUP_URL = 'https://tinyurl.com/3hsp7dvy'

DEFAULT_LANG = 'he'
# Label for the *other* language, so the toggle always reads in the language it switches to.
LANG_SWITCH = {'he': ('en', 'English'), 'en': ('he', 'עברית')}


def singer_tickets(request):
    lang = request.GET.get('lang', DEFAULT_LANG)
    if lang not in STRINGS:
        lang = DEFAULT_LANG

    urls = {
        'practice_url': PRACTICE_TICKETS_URL,
        'all_events_url': ALL_EVENTS_URL,
        'whatsapp_group_url': WHATSAPP_GROUP_URL,
        'community_group_url': COMMUNITY_GROUP_URL,
    }

    # Copy blocks are HTML fragments with {url} slots — fill them in, then mark safe so the
    # inline <strong> and <a> render. The strings are ours, never user input.
    strings = {key: mark_safe(text.format(**urls)) for key, text in STRINGS[lang].items()}

    other_lang, other_label = LANG_SWITCH[lang]
    return render(request, 'explanations/singer_tickets.html', {
        **urls,
        't': strings,
        'lang': lang,
        'text_dir': 'rtl' if lang == 'he' else 'ltr',
        'other_lang': other_lang,
        'other_lang_label': other_label,
    })
