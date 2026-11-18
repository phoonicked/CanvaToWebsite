"""Reading inputs: cookies, Canva's design data and links."""
import base64
import json
from urllib.parse import quote

import pytest
from bs4 import BeautifulSoup

from canva_to_website import links
from canva_to_website.common import ConversionError
from canva_to_website.cookies import read_cookies
from canva_to_website.design_data import find_links, find_media, read_design_data

from .conftest import CONTACT_SECTION, LINKED_ELEMENT, PAGE_2


def test_reads_cookie_editor_json(tmp_path):
    path = tmp_path / 'cookies.json'
    path.write_text(json.dumps([{'name': 'a', 'value': '1', 'domain': '.canva.com', 'sameSite': 'no_restriction',
                                 'expirationDate': 1900000000.5}, {'name': 'b', 'value': '2', 'sameSite': 'lax'}]))
    first, second = read_cookies(path)
    assert first == {'name': 'a', 'value': '1', 'domain': '.canva.com', 'sameSite': 'None', 'expires': 1900000000.5}
    assert second['sameSite'] == 'Lax' and second['url'] == 'https://www.canva.com/'


def test_reads_cookies_txt(tmp_path):
    path = tmp_path / 'cookies.txt'
    path.write_text('# Netscape HTTP Cookie File\n'
                    '.canva.com\tTRUE\t/\tTRUE\t1900000000\ta\t1\n'
                    '#HttpOnly_.canva.com\tTRUE\t/\tTRUE\t0\tb\t2\n')
    first, second = read_cookies(path)
    assert first['name'] == 'a' and first['secure'] and first['expires'] == 1900000000
    assert second['name'] == 'b' and second['httpOnly'] and 'expires' not in second


@pytest.mark.parametrize('content', [None, '', '[]'])
def test_missing_or_empty_cookies_are_reported(tmp_path, content):
    path = tmp_path / 'cookies.json'
    if content is not None:
        path.write_text(content)
    with pytest.raises(ConversionError):
        read_cookies(path)


def test_reads_links_and_sections_from_the_design_data(editor_html):
    data = read_design_data(editor_html)
    assert data is not None
    element_links, sections = find_links(data)
    assert element_links == {LINKED_ELEMENT: 'https://canva.link/testlink'}  # Canva's own image URL is ignored
    assert sections[CONTACT_SECTION] == [PAGE_2]


def test_missing_design_data_is_none():
    assert read_design_data('<html><body>Something else</body></html>') is None


def test_finds_media_records(editor_html):
    assert find_media(editor_html, 'VAsticker01')['title'] == 'Wiggle'
    assert find_media(editor_html, 'VAmissing00') is None


def test_canva_page_links_become_anchors(monkeypatch):
    ui = base64.b64encode(json.dumps({'D': {'T': {'A': CONTACT_SECTION}}}).encode()).decode()
    login = 'https://www.canva.com/login/?redirect=' + quote(f'/design/DAtest/abc/edit?ui={quote(ui)}', safe='')

    class Redirect:
        headers = {'location': login}

    monkeypatch.setattr(links.HTTP, 'head', lambda url, **kwargs: Redirect())
    sections = {CONTACT_SECTION: [PAGE_2]}
    assert links.link_href('https://canva.link/testlink', sections, {PAGE_2: 2}, 'DAtest') == '#page-2'


def test_other_links_are_kept():
    assert links.link_href('https://example.com/x', {}, {}, 'DAtest') == 'https://example.com/x'


def test_linked_elements_become_clickable():
    soup = BeautifulSoup(f'<div id="{LINKED_ELEMENT}"><p>Instagram</p></div>', 'html.parser')
    assert links.add_element_links(soup, {LINKED_ELEMENT: 'https://instagram.com/x'}, {}, {}, 'DAtest') == 1
    link = soup.select_one('a.canva-link-area')
    assert link['href'] == 'https://instagram.com/x' and link['aria-label'] == 'Instagram'


def test_addresses_in_text_become_links():
    soup = BeautifulSoup('<p>Email me@example.com or see www.example.com.</p>', 'html.parser')
    assert links.autolink(soup) == 2
    assert [a['href'] for a in soup.find_all('a')] == ['mailto:me@example.com', 'https://www.example.com']
    assert soup.get_text() == 'Email me@example.com or see www.example.com.'
