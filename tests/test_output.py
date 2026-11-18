"""Building the site: names, CSS, fonts, images, video sizing and the files written."""
import base64
import io

from bs4 import BeautifulSoup
from PIL import Image

from canva_to_website.css import filter_css
from canva_to_website.fonts import font_files, weight_and_style
from canva_to_website.images import localize_images
from canva_to_website.site import pages_to_html, site_dir_for, slugify, write_site
from canva_to_website.video import VideoCompressor


def test_site_folders_are_named_after_the_design():
    assert slugify("Sam's Café Menu — 2026") == 'sams-cafe-menu-2026'
    assert site_dir_for('output', 'デザイン', 'DAxyz').endswith('canva-DAxyz')


def test_pages_get_anchor_ids():
    html = pages_to_html([{'width': 1366, 'height': 768, 'html': '<p>A</p>'},
                          {'width': 1366, 'height': 900, 'html': '<p>B</p>'}])
    assert 'id="page-1"' in html and 'id="page-2"' in html and '--page-height: 900' in html


def test_css_keeps_only_rules_the_design_uses():
    css = ('.used { color: red } .unused { color: blue } '
           '@media (min-width: 1px) { .used { margin: 0 } .unused { margin: 1px } } '
           '@font-face { font-family: X; src: url(https://font-public.canva.com/x.woff2) }')
    result = filter_css(css, {'used'})
    assert '.used' in result and '@media' in result
    assert '.unused' not in result and '@font-face' not in result


def test_fonts_are_matched_to_their_files():
    urls = ['https://font-public.canva.com/YAEK94THsCY/0/Font-BoldItalic.woff2',
            'https://font-public.canva.com/OTHERFONT00/0/Other.woff2']
    assert font_files('YAEK94THsCY_1', urls) == urls[:1]  # suffix and folder don't always match
    assert weight_and_style('Font-ExtraBold.woff2') == (800, 'normal')
    assert weight_and_style('Font-BoldItalic.woff2') == (700, 'italic')


def test_images_are_saved_once_and_linked(tmp_path):
    buffer = io.BytesIO()
    Image.new('RGB', (64, 64), 'blue').save(buffer, 'PNG')
    png = 'data:image/png;base64,' + base64.b64encode(buffer.getvalue()).decode()
    svg = 'data:image/svg+xml;base64,' + base64.b64encode(b'<svg xmlns="http://www.w3.org/2000/svg"/>').decode()
    soup = BeautifulSoup(f'<section class="canva-page"><img src="{png}" crossorigin="anonymous">'
                         f'<img src="{png}"><img src="{svg}"></section>', 'html.parser')

    assert localize_images(soup, tmp_path / 'images') == 2
    sources = [img['src'] for img in soup.find_all('img')]
    assert sources[0] == sources[1] and sources[2].endswith('.svg')
    assert all(src.startswith('assets/images/') for src in sources)
    assert not soup.find(attrs={'crossorigin': True})
    assert len(list((tmp_path / 'images').iterdir())) == 2


def test_videos_are_sized_to_fit_the_budget():
    compressor = VideoCompressor(24)
    assert compressor.plan(411.24, 720) == (480, 388)   # a 7 minute film drops to 480p
    assert compressor.plan(44, 720)[0] == 720         # a short clip keeps 720p
    assert compressor.plan(3600, 1080) == (360, 200)  # too long to fit: lowest acceptable quality


def test_writes_index_and_styles(tmp_path):
    (tmp_path / 'assets').mkdir()
    write_site(tmp_path, title='Tom & Jerry', lang='en', body_html='<section class="canva-page"></section>',
               stylesheet='.x{}', html_class='theme', body_class='', body_scripts='', design_width=1366)
    index = (tmp_path / 'index.html').read_text()
    assert '<title>Tom &amp; Jerry</title>' in index and 'width = 1366' in index
    assert 'assets/styles.css' in index
    assert '.canva-page' in (tmp_path / 'assets' / 'styles.css').read_text()
