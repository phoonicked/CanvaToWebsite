"""Making links work: links set in Canva, plus email and web addresses typed into text."""
import base64
import json
import re
from urllib.parse import parse_qs, urljoin, urlparse

import requests

from .common import HTTP, SAFE_ID
from .design_data import PAGE_ID

TEXT_LINK = re.compile(r'(?P<email>[\w.+-]+@[\w-]+(?:\.[\w-]+)+)|https?://[^\s<]+|www\.[^\s<]+')


def autolink(soup):
    """Turns email and web addresses in the design's text into links. Returns how many."""
    count = 0
    for text_node in soup.find_all(string=TEXT_LINK):
        if text_node.find_parent(['a', 'script', 'style']):
            continue
        pieces, last = [], 0
        for match in TEXT_LINK.finditer(text_node):
            value = match.group(0).rstrip('.,;:!?)')
            if match.group('email'):
                link = soup.new_tag('a', href=f"mailto:{value}")
            else:
                link = soup.new_tag('a', href=value if value.startswith('http') else f"https://{value}",
                                    target='_blank', rel='noopener')
            link['class'] = 'canva-link'
            link.string = value
            pieces += [text_node[last:match.start()], link, match.group(0)[len(value):]]
            last = match.end()
            count += 1
        pieces.append(text_node[last:])
        for piece in pieces:
            if piece:
                text_node.insert_before(piece)
        text_node.extract()
    return count


def add_element_links(soup, links, sections, page_numbers, design_id):
    """Makes elements linked in Canva clickable. Returns how many.

    A transparent <a> covers the element; links to a page or section of this design become
    #page-N anchors.
    """
    added = 0
    for element_id, url in links.items():
        element = soup.find(id=element_id) if SAFE_ID.fullmatch(element_id) else None
        if not element:
            continue
        href = link_href(url, sections, page_numbers, design_id)
        link = soup.new_tag('a', href=href, attrs={'class': 'canva-link-area',
                                                  'aria-label': element.get_text(' ', strip=True) or href})
        if not href.startswith(('#', 'mailto:', 'tel:')):
            link['target'] = '_blank'
            link['rel'] = 'noopener'
        element.append(link)
        added += 1
    return added


def link_href(url, sections, page_numbers, design_id):
    target = linked_page_id(url, design_id)
    if not target:
        return url
    for page_id in [target, *sections.get(target, [])]:
        if page_id in page_numbers:
            return f"#page-{page_numbers[page_id]}"
    return url


def linked_page_id(url, design_id):
    """If the link points to a page or section of this design, its ID. Follows canva.link redirects."""
    for _ in range(5):
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        if 'redirect' in query:  # Canva wraps the target in a login redirect
            url = urljoin('https://www.canva.com', query['redirect'][0])
            continue
        if f'/design/{design_id}' in parsed.path and 'ui' in query:
            encoded = query['ui'][0].replace('-', '+').replace('_', '/')
            try:
                ui = json.loads(base64.b64decode(encoded + '=' * (-len(encoded) % 4)))
            except ValueError:
                return None
            return next((value for value in _strings(ui) if PAGE_ID.fullmatch(value)), None)
        if parsed.hostname != 'canva.link':
            return None
        try:
            response = HTTP.head(url, allow_redirects=False, timeout=15)
        except requests.RequestException:
            return None
        if 'location' not in response.headers:
            return None
        url = urljoin(url, response.headers['location'])
    return None


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)
