import logging
import sys
from functools import wraps
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s: %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

# Lijst met niet-toegestane woorden en thema's
BLOCKED_TERMS = [
    'nsfw', 'xxx', 'seks', 'naakt', 'erotisch', 'erotiek', 'pornografie',
    'expliciet', 'adult', '18+', 'mature', 'seksueel'
]

def contains_blocked_content(text):
    """Check if text contains any blocked terms"""
    if not text:
        return False
    text = text.lower()
    return any(term in text for term in BLOCKED_TERMS)

def retry_with_exponential_backoff(max_retries=3, initial_wait=5):
    """Decorator for retrying functions with exponential backoff"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if 'rate limit' in str(e).lower() and retries < max_retries - 1:
                        wait_time = initial_wait * (2 ** retries)
                        time.sleep(wait_time)
                        retries += 1
                        continue
                    raise
            return func(*args, **kwargs)
        return wrapper
    return decorator
