import re

def is_hebrew(s):
    """Return true if there's at list one hebrew char in the string"""
    return bool(re.search(r'[\u0590-\u05FF]', s))
