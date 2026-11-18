"""Writing the finished site: output/<design-title>/index.html plus assets/."""
import html
import os
import re
import unicodedata

# Canva's app CSS locks the viewport. Body mustn't become its own scroll container: with Canva's
# `overscroll-behavior: none` it would swallow wheel and trackpad scrolling.
PAGE_CSS = (
    "html, body { margin: 0 !important; padding: 0 !important; height: auto !important;"
    " overscroll-behavior: auto !important; user-select: auto !important; }\n"
    "html { overflow-y: auto !important; overflow-x: hidden !important; scroll-behavior: smooth; }\n"
    "body { overflow: visible !important; }\n"
    # Each page keeps its design size and is scaled by --site-scale; the section takes the scaled
    # size so the document flows.
    ":root { --site-scale: 1; }\n"
    ".canva-page { position: relative; overflow: hidden; margin: 0 auto;"
    " width: calc(var(--page-width) * var(--site-scale) * 1px);"
    " height: calc(var(--page-height) * var(--site-scale) * 1px); }\n"
    ".canva-page > * { position: absolute; top: 0; left: 0;"
    " width: calc(var(--page-width) * 1px); height: calc(var(--page-height) * 1px);"
    " transform: scale(var(--site-scale)); transform-origin: 0 0; }\n"
    ".canva-lottie, .canva-video { display: block; width: 100%; height: 100%; }\n"
    ".canva-video { object-fit: cover; }\n"
    "a.canva-link { color: inherit; text-decoration: inherit; }\n"
    "a.canva-link:hover, a.canva-link:focus-visible { text-decoration: underline; }\n"
    ".canva-link-area { position: absolute; inset: 0; z-index: 1; }\n"
    ".canva-link-area:focus-visible { outline: 3px solid #4a7ff7; outline-offset: 2px; }\n"
)

# The ResizeObserver catches a scrollbar appearing, which narrows the page without a resize event.
SCALE_SCRIPT = (
    "<script>(function () {"
    " var root = document.documentElement, width = %d;"
    " function fit() { root.style.setProperty('--site-scale', root.clientWidth / width); }"
    " fit(); addEventListener('resize', fit);"
    " if (window.ResizeObserver) new ResizeObserver(fit).observe(root);"
    "})();</script>"
)


def slugify(title):
    """"Sam's Café Menu" -> 'sams-cafe-menu'"""
    ascii_title = unicodedata.normalize('NFKD', title).encode('ascii', 'ignore').decode()
    ascii_title = re.sub(r"['’]", '', ascii_title)
    return re.sub(r'[^a-z0-9]+', '-', ascii_title.lower()).strip('-')


def site_dir_for(output_root, title, design_id):
    # Falls back to the design ID for titles with nothing to slugify (e.g. a non-Latin script).
    return os.path.join(output_root, slugify(title) or f"canva-{design_id}")


def pages_to_html(pages):
    return ''.join(
        f'<section class="canva-page" id="page-{number}" '
        f'style="--page-width: {page["width"]}; --page-height: {page["height"]};">{page["html"]}</section>'
        for number, page in enumerate(pages, 1)
    )


def write_site(site_dir, *, title, lang, body_html, stylesheet, html_class, body_class, body_scripts, design_width):
    with open(os.path.join(site_dir, 'assets', 'styles.css'), 'w', encoding='utf-8') as f:
        f.write(stylesheet + '\n' + PAGE_CSS)

    title = html.escape(title)
    page = (
        f'<!DOCTYPE html>\n<html lang="{html.escape(lang)}" class="{html.escape(html_class)}">'
        f'<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
        f'<title>{title}</title><link rel="icon" href="data:,">'
        f'<meta property="og:title" content="{title}"><meta property="og:type" content="website">'
        f'<link rel="stylesheet" href="assets/styles.css"></head>'
        f'<body class="{html.escape(body_class)}">{SCALE_SCRIPT % design_width}'
        f'<main>{body_html}</main>{body_scripts}</body></html>'
    )
    index = os.path.join(site_dir, 'index.html')
    with open(index, 'w', encoding='utf-8') as f:
        f.write(page)
    total = sum(os.path.getsize(os.path.join(d, name)) for d, _, names in os.walk(site_dir) for name in names)
    print(f"Wrote {index} ({len(page) / 1e6:.1f} MB; site total {total / 1e6:.1f} MB)")
    return index
