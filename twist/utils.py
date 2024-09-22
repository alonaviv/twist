import re

def is_hebrew(s):
    """Return true if there's at list one hebrew char in the string"""
    return bool(re.search(r'[\u0590-\u05FF]', s))


def format_commas(names):
    if not names:
        return ''
    if len(names) == 1:
        return names[0]
    else:
        return f"{', '.join(names[:-1])} and {names[-1]}"
