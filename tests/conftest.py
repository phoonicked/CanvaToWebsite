from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / 'fixtures'
EDITOR_PAGE = FIXTURES / 'editor.html'

# IDs used in fixtures/editor.html
PAGE_1 = 'PBaaaaaaaaaaaaaa'
PAGE_2 = 'PBbbbbbbbbbbbbbb'
CONTACT_SECTION = 'PBssssssssssssss'
LINKED_ELEMENT = 'LBkkkkkkkkkkkkkk'


@pytest.fixture(scope='session')
def editor_html():
    return EDITOR_PAGE.read_text(encoding='utf-8')


@pytest.fixture(scope='module')
def chrome():
    """Plain headless Chrome. The browser tests are skipped if it isn't installed."""
    from selenium import webdriver
    from selenium.common.exceptions import WebDriverException

    options = webdriver.ChromeOptions()
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--window-size=1200,800')
    try:
        driver = webdriver.Chrome(options=options)
    except WebDriverException as e:
        pytest.skip(f"Chrome isn't available: {e.msg}")
    yield driver
    driver.quit()
