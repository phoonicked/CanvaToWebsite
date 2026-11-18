"""Reading exported Canva cookies (Cookie-Editor JSON or a cookies.txt file)."""
import json

from .common import ConversionError

SAME_SITE_VALUES = {'strict': 'Strict', 'lax': 'Lax', 'none': 'None', 'no_restriction': 'None'}


def to_cdp_cookie(cookie):
    """Converts an exported cookie into a DevTools Network.CookieParam."""
    result = {key: cookie[key] for key in ('name', 'value', 'path', 'domain', 'secure', 'httpOnly') if key in cookie}
    if 'domain' not in result:
        result['url'] = 'https://www.canva.com/'
    same_site = SAME_SITE_VALUES.get(str(cookie.get('sameSite', '')).lower())
    if same_site:
        result['sameSite'] = same_site
    expiry = cookie.get('expiry', cookie.get('expirationDate'))
    if expiry and not cookie.get('session'):
        result['expires'] = expiry
    return result


def parse_cookies_txt(text):
    """Parses the Netscape cookies.txt format."""
    cookies = []
    for line in text.splitlines():
        http_only = line.startswith('#HttpOnly_')
        if http_only:
            line = line[len('#HttpOnly_'):]
        parts = line.split('\t')
        if line.startswith('#') or len(parts) != 7:
            continue
        domain, _, path, secure, expires, name, value = parts
        cookies.append({'domain': domain, 'path': path, 'secure': secure.upper() == 'TRUE',
                        'httpOnly': http_only, 'name': name, 'value': value,
                        'expirationDate': int(expires) if expires.isdigit() else None})
    return cookies


def read_cookies(path):
    try:
        with open(path, encoding='utf-8') as f:
            text = f.read()
    except FileNotFoundError:
        raise ConversionError(f"The file '{path}' was not found.") from None
    try:
        cookies = json.loads(text)
    except json.JSONDecodeError:
        cookies = parse_cookies_txt(text)
    if not isinstance(cookies, list) or not cookies:
        raise ConversionError(f"No cookies found in '{path}'. Export them again from Cookie-Editor as JSON.")
    return [to_cdp_cookie(cookie) for cookie in cookies]
