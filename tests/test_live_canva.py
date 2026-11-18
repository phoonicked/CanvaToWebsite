"""Converts a real design, to catch Canva changing its editor.

Skipped unless you point it at a design:
    CANVA_COOKIES=cookies.json CANVA_URL="https://www.canva.com/design/..." pytest -m live
"""
import os
import re
from pathlib import Path

import pytest

COOKIES = os.environ.get('CANVA_COOKIES')
URL = os.environ.get('CANVA_URL')

pytestmark = [pytest.mark.live,
              pytest.mark.skipif(not (COOKIES and URL), reason='set CANVA_COOKIES and CANVA_URL to run')]


def test_converts_a_real_design(tmp_path):
    from canva_to_website.browser import set_cookies, start_browser
    from canva_to_website.converter import convert
    from canva_to_website.cookies import read_cookies

    driver = start_browser()
    try:
        set_cookies(driver, read_cookies(COOKIES))
        site = Path(convert(driver, URL, tmp_path, max_video_quality=240))
    finally:
        driver.quit()

    index = (site / 'index.html').read_text(encoding='utf-8')
    assert index.count('class="canva-page"') >= 1
    assert (site / 'assets' / 'styles.css').stat().st_size > 1000
    assert not re.search(r'(src|poster)="https://[^"]*canva\.com', index)  # nothing loads from Canva
