import re
import sys

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Retries timeouts, resets and 5xx responses so one flaky download doesn't fail a conversion.
HTTP = requests.Session()
HTTP.mount('https://', HTTPAdapter(pool_maxsize=16, max_retries=Retry(
    total=4, connect=4, read=4, backoff_factor=1.5, status_forcelist=[429, 500, 502, 503, 504])))
DOWNLOAD_WORKERS = 8

# Canva IDs (media, fonts) end up in file names, CSS and HTML, so they're checked first.
SAFE_ID = re.compile(r'[A-Za-z0-9_-]{1,64}')


class ConversionError(Exception):
    """A problem the user can fix, like a wrong link or an expired login. Shown without a traceback."""


def download(url, timeout=30):
    response = HTTP.get(url, timeout=timeout)
    response.raise_for_status()
    return response


def warn(message):
    print(f"Warning: {message}", file=sys.stderr)
