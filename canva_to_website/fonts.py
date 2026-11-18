"""Saving the design's fonts with the site.

Canva refers to fonts by ID (``YAFdJs2qTWQ_0``) and registers them from JavaScript, so there are
no @font-face rules in the page. The files live at ``font-public.canva.com/<id>/<folder>/<file>``,
so the IDs are matched against the font files the editor downloaded.
"""
import os
import re
from concurrent.futures import ThreadPoolExecutor

from .common import DOWNLOAD_WORKERS, SAFE_ID, download

FONT_HOST = 'https://font-public.canva.com/'
# Longest names first so 'ExtraBold' isn't matched as 'Bold'.
WEIGHTS = {
    'ExtraLight': 200, 'UltraLight': 200, 'ExtraBold': 800, 'UltraBold': 800,
    'SemiBold': 600, 'DemiBold': 600, 'Thin': 100, 'Light': 300, 'Regular': 400,
    'Medium': 500, 'Bold': 700, 'Black': 900, 'Heavy': 900,
}
FORMATS = {'woff2': 'woff2', 'woff': 'woff', 'ttf': 'truetype', 'otf': 'opentype'}


def used_font_families(soup):
    """The main font of each styled element, e.g. 'YAFdJs2qTWQ_0'."""
    families = set()
    for element in soup.find_all(style=True):
        match = re.search(r"font-family:\s*([^;]+)", element['style'])
        if match:
            families.add(match.group(1).split(',')[0].strip().strip('"\''))
    return families


def font_files(family, font_urls):
    font_id, _, folder = family.rpartition('_')
    if not font_id:
        return []
    files = [url for url in font_urls if url.startswith(f"{FONT_HOST}{font_id}/{folder}/")]
    # The family's suffix doesn't always match the folder (YAEK94THsCY_1 is served from /0/).
    return files or [url for url in font_urls if url.startswith(f"{FONT_HOST}{font_id}/")]


def weight_and_style(filename):
    weight = next((value for name, value in WEIGHTS.items() if name in filename), 400)
    style = 'italic' if 'Italic' in filename or 'Oblique' in filename else 'normal'
    return weight, style


def save_fonts(families, font_urls, fonts_dir):
    """Downloads the fonts into fonts_dir and returns their @font-face rules."""
    font_urls = list(dict.fromkeys(font_urls))
    faces = []
    for family in sorted(families):
        if not SAFE_ID.fullmatch(family):
            continue
        files = font_files(family, font_urls)
        print(f"Found font {family}: {len(files)} file(s)")
        for url in files:
            filename = f"{family}-{re.sub(r'[^\w.-]', '_', url.split('?')[0].rsplit('/', 1)[-1])}"
            extension = filename.rsplit('.', 1)[-1].lower()
            if extension in FORMATS:
                faces.append((family, url, filename, extension))

    os.makedirs(fonts_dir, exist_ok=True)

    def save(face):
        with open(os.path.join(fonts_dir, face[2]), 'wb') as f:
            f.write(download(face[1]).content)

    with ThreadPoolExecutor(DOWNLOAD_WORKERS) as pool:
        list(pool.map(save, faces))

    rules = []
    for family, _, filename, extension in faces:
        weight, style = weight_and_style(filename)
        # Relative to assets/styles.css
        rules.append(f"@font-face {{ font-family: '{family}'; src: url('fonts/{filename}') "
                     f"format('{FORMATS[extension]}'); font-display: swap; "
                     f"font-weight: {weight}; font-style: {style}; }}\n")
    return ''.join(rules)
