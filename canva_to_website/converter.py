"""The whole conversion, from an open Canva editor to a site folder."""
import os
import re
import shutil

from bs4 import BeautifulSoup

from .common import ConversionError, warn
from .css import download_stylesheets, filter_css
from .design_data import find_links, read_design_data
from .editor import collect_resources, extract_pages, load_design
from .fonts import save_fonts, used_font_families
from .images import localize_images
from .links import add_element_links, autolink
from .media import MediaEmbedder
from .site import pages_to_html, site_dir_for, write_site
from .video import VideoCompressor

DESIGN_URL = re.compile(r'^https://(www\.)?canva\.[a-z.]+/design/([\w-]+)')


def convert(driver, url, output_root='output', max_video_quality=720, max_video_mb=24):
    """Converts the design at `url` using a logged-in browser. Returns the site folder."""
    match = DESIGN_URL.match(url)
    if not match:
        raise ConversionError("The link should be a Canva design link, like https://www.canva.com/design/DAxxxxxxx/...")
    design_id = match.group(2)

    load_design(driver, url)
    pages = extract_pages(driver)
    print(f"Found {len(pages)} page(s)")
    soup = BeautifulSoup(pages_to_html(pages), 'html.parser')
    resources = collect_resources(driver)
    page_source = driver.page_source
    title = resources['designTitle'].strip() or 'Canva design'

    # The folder is entirely generated, so start clean rather than leave stale files behind.
    site_dir = site_dir_for(output_root, title, design_id)
    assets_dir = os.path.join(site_dir, 'assets')
    if os.path.exists(os.path.join(site_dir, 'index.html')):
        shutil.rmtree(site_dir)
    os.makedirs(assets_dir, exist_ok=True)

    compressor = VideoCompressor(max_video_mb) if max_video_mb else None
    body_scripts = MediaEmbedder(page_source, assets_dir, max_video_quality, compressor).embed(soup)
    localize_images(soup, os.path.join(assets_dir, 'images'))

    if count := autolink(soup):
        print(f"Linked {count} email/web address(es)")
    design_data = read_design_data(page_source)
    if design_data is None:
        warn("couldn't read the design data, so links set in Canva weren't added")
    else:
        links, sections = find_links(design_data)
        page_numbers = {page['id']: number for number, page in enumerate(pages, 1)}
        if count := add_element_links(soup, links, sections, page_numbers, design_id):
            print(f"Linked {count} element(s)")

    font_rules = save_fonts(used_font_families(soup), resources['fontUrls'], os.path.join(assets_dir, 'fonts'))
    classes = {name for element in soup.find_all(class_=True) for name in element['class']}
    classes.update((resources['htmlClass'] + ' ' + resources['bodyClass']).split())
    css = filter_css(download_stylesheets(resources['stylesheets']), classes)

    write_site(site_dir, title=title, lang=resources['lang'], body_html=str(soup),
               stylesheet=font_rules + css, html_class=resources['htmlClass'],
               body_class=resources['bodyClass'], body_scripts=body_scripts,
               design_width=max(page['width'] for page in pages))
    return site_dir
