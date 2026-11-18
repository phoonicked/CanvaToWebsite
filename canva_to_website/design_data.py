"""Reading the design data Canva embeds in the editor page.

The data's keys are minified and change between Canva releases, so it's read by ID format
instead: a record holding an LB… ID is an element (the same ID is on its DOM container), and one
holding a PB… ID is a page or a website section.
"""
import json
import re

BOOTSTRAP_PATTERN = re.compile(r"window\['bootstrap'\]\s*=\s*JSON\.parse\('((?:[^'\\]|\\.)*)'\)", re.S)
JS_ESCAPES = {'n': '\n', 't': '\t', 'r': '\r', 'b': '\b', 'f': '\f', 'v': '\v', '0': '\0'}
ELEMENT_ID = re.compile(r'LB[\w-]{14}')
PAGE_ID = re.compile(r'PB[\w-]{14}')
LINK = re.compile(r'(https?://|mailto:|tel:)', re.I)
CANVA_ASSET = re.compile(r'https://[\w.-]*(media|static|font|video)[\w-]*\.canva\.com/')


def read_design_data(page_source):
    """The design as embedded in the editor page (window.bootstrap), or None if it isn't there."""
    match = BOOTSTRAP_PATTERN.search(page_source)
    if not match:
        return None

    def unescape(escape):
        code = escape.group(1)
        if code[0] in 'ux' and len(code) > 1:
            return chr(int(code[1:], 16))
        return JS_ESCAPES.get(code, code)

    try:
        return json.loads(re.sub(r'\\(u[0-9a-fA-F]{4}|x[0-9a-fA-F]{2}|[\s\S])', unescape, match.group(1)))
    except json.JSONDecodeError:
        return None


def find_links(design_data):
    """Returns ({element ID: link}, {page or section ID: [page IDs inside it]})."""
    links, sections = {}, {}

    def visit(node, element):
        if isinstance(node, dict):
            values = list(node.values())
            own_id = next((v for v in values if isinstance(v, str)
                           and (ELEMENT_ID.fullmatch(v) or PAGE_ID.fullmatch(v))), None)
        elif isinstance(node, list):
            values, own_id = node, None
        else:
            return []
        if own_id and ELEMENT_ID.fullmatch(own_id):
            element = own_id
        pages = []
        for value in values:
            if not isinstance(value, str):
                pages += visit(value, element)
            elif element and element not in links and LINK.match(value) and not CANVA_ASSET.match(value):
                links[element] = value
        if own_id and PAGE_ID.fullmatch(own_id):
            sections[own_id] = pages
            return [own_id]
        return pages

    visit(design_data, None)
    return links, sections


def find_media(page_source, media_id):
    """The record for a sticker or video (title, files, duration), or None."""
    decoder, start = json.JSONDecoder(), 0
    while (index := page_source.find(f'{{"id":"{media_id}"', start)) != -1:
        try:
            record, _ = decoder.raw_decode(page_source, index)
            if 'files' in record:
                return record
        except json.JSONDecodeError:
            pass
        start = index + 1
    return None
