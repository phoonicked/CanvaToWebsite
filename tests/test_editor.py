"""Loading and reading a design, against a fake Canva editor page in headless Chrome."""
import pytest

from canva_to_website.common import ConversionError
from canva_to_website.editor import collect_resources, extract_pages, load_design

from .conftest import EDITOR_PAGE, PAGE_1, PAGE_2

pytestmark = pytest.mark.browser


@pytest.fixture(scope='module')
def pages(chrome):
    load_design(chrome, EDITOR_PAGE.as_uri(), timeout=15, settle_interval=0.2)
    return extract_pages(chrome)


def test_finds_every_page_including_ones_rendered_on_scroll(pages):
    assert [page['id'] for page in pages] == [PAGE_1, PAGE_2]
    assert 'Contact page' in pages[1]['html']
    assert (pages[0]['width'], pages[0]['height']) == (1366, 768)


def test_keeps_the_design_layer_and_drops_the_screen_reader_copy(pages):
    html = pages[0]['html']
    assert 'Go to contact' in html
    assert 'Screen reader copy' not in html
    assert 'aria-hidden' not in html.split('>', 1)[0]


def test_turns_blob_images_and_canvases_into_data(pages):
    html = pages[0]['html']
    assert 'blob:' not in html
    assert '<canvas' not in html
    assert html.count('src="data:image/png') == 2


def test_collects_the_title_language_and_styles(chrome, pages):
    resources = collect_resources(chrome)
    assert resources['designTitle'] == 'Test Design'
    assert resources['lang'] == 'en-GB'
    assert resources['stylesheets']


def test_reports_a_page_that_isnt_a_design(chrome, tmp_path):
    not_a_design = tmp_path / 'login.html'
    not_a_design.write_text('<p>Log in to Canva</p>')
    with pytest.raises(ConversionError):
        load_design(chrome, not_a_design.as_uri(), timeout=2)
