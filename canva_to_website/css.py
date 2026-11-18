"""Downloading the editor's stylesheets and keeping only the rules the design uses."""
import re
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin

import requests
import tinycss2

from .common import DOWNLOAD_WORKERS, download, warn

CLASS_NAME = re.compile(r'\.(-?[_a-zA-Z][\w-]*)')
GROUPING_AT_RULES = {'media', 'supports', 'layer', 'container'}


def download_stylesheets(stylesheets):
    """Takes the editor's stylesheet list ({href} or {css}) and returns all the CSS."""
    def fetch(sheet):
        if 'href' not in sheet:
            return sheet['css']
        try:
            return absolutize_urls(download(sheet['href']).text, sheet['href'])
        except requests.RequestException as e:
            warn(f"could not download {sheet['href']} ({e})")
            return ''

    with ThreadPoolExecutor(DOWNLOAD_WORKERS) as pool:
        return '\n'.join(pool.map(fetch, stylesheets))


def absolutize_urls(css, base_url):
    def replace(match):
        quote, path = match.groups()
        if re.match(r'^(data:|https?:|//|#)', path):
            return match.group(0)
        return f"url({quote}{urljoin(base_url, path)}{quote})"
    return re.sub(r"""url\(\s*(['"]?)([^'")]+)\1\s*\)""", replace, css)


def filter_css(css, classes):
    """Keeps rules whose selectors only use classes in `classes`.

    @font-face rules are dropped: Canva's point at its servers (and a 119 MB fallback font set)
    and would override the local fonts.
    """
    def applies(prelude):
        return any(all(name in classes for name in CLASS_NAME.findall(selector))
                   for selector in prelude.split(','))

    def keep(rules):
        kept = []
        for rule in rules:
            if rule.type == 'qualified-rule':
                if applies(tinycss2.serialize(rule.prelude)):
                    kept.append(rule.serialize())
            elif rule.type == 'at-rule':
                keyword = rule.lower_at_keyword
                if keyword in GROUPING_AT_RULES and rule.content is not None:
                    inner = keep(tinycss2.parse_blocks_contents(rule.content, skip_comments=True,
                                                                skip_whitespace=True))
                    if inner:
                        kept.append(f"@{rule.at_keyword}{tinycss2.serialize(rule.prelude)}{{{''.join(inner)}}}")
                elif keyword == 'layer' and rule.content is None:
                    kept.append(rule.serialize())
        return kept

    return '\n'.join(keep(tinycss2.parse_stylesheet(css, skip_comments=True, skip_whitespace=True)))
