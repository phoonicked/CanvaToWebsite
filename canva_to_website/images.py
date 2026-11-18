"""Saving every image with the site, once each, as WebP where that's smaller.

Images arrive as base64 (from blob: URLs and canvases) or as Canva URLs, many of them signed links
that expire, so the site keeps its own copies.
"""
import base64
import hashlib
import io
import os
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import unquote

from PIL import Image

from .common import DOWNLOAD_WORKERS, download, warn

MAX_DIMENSION = 2732  # 2x the usual 1366px page width
WEBP_QUALITY = 82
EXTENSIONS = {'image/gif': 'gif', 'image/svg+xml': 'svg', 'image/webp': 'webp',
              'image/png': 'png', 'image/jpeg': 'jpg', 'image/avif': 'avif'}


def localize_images(soup, images_dir):
    """Points every <img> and video poster at a saved file. Returns the number of files saved."""
    refs = []
    for page_index, page in enumerate(soup.select('.canva-page')):
        for img in page.find_all('img', src=True):
            refs.append((img, 'src'))
            img['decoding'] = 'async'
            if page_index:
                img['loading'] = 'lazy'
        for video in page.find_all('video'):
            if video.get('poster'):
                refs.append((video, 'poster'))
            if page_index:
                video['preload'] = 'none'

    sources = list(dict.fromkeys(tag[attr] for tag, attr in refs))
    with ThreadPoolExecutor(max(DOWNLOAD_WORKERS, os.cpu_count() or 1)) as pool:
        processed = dict(zip(sources, pool.map(_process, sources)))

    os.makedirs(images_dir, exist_ok=True)
    saved, size_in, size_out = {}, 0, 0
    for tag, attr in refs:
        result = processed[tag[attr]]
        if not result:
            continue
        digest, content, extension, original_size = result
        if digest not in saved:
            filename = f"{digest}.{extension}"
            with open(os.path.join(images_dir, filename), 'wb') as f:
                f.write(content)
            saved[digest] = f"assets/{os.path.basename(images_dir)}/{filename}"
            size_in += original_size
            size_out += len(content)
        tag[attr] = saved[digest]
        # Canva marks its CDN images crossorigin. On a local file that forces a CORS request,
        # which browsers refuse when the page is opened from disk.
        tag.attrs.pop('crossorigin', None)
    print(f"Saved {len(saved)} image(s): {size_in / 1e6:.1f} MB -> {size_out / 1e6:.1f} MB")
    return len(saved)


def _process(src):
    """Returns (digest, bytes, extension, original size), or None if it can't be read."""
    try:
        if src.startswith('data:'):
            header, _, payload = src.partition(',')
            mime = header[5:].split(';')[0]
            data = base64.b64decode(payload) if ';base64' in header else unquote(payload).encode()
        elif src.startswith(('http://', 'https://')):
            response = download(src, timeout=60)
            data, mime = response.content, response.headers.get('content-type', '').split(';')[0]
        else:
            return None
    except Exception as e:
        warn(f"could not save image {src[:80]}: {e}")
        return None

    digest = hashlib.sha256(data).hexdigest()[:16]
    content, extension = data, EXTENSIONS.get(mime, 'bin')
    if mime in ('image/png', 'image/jpeg', 'image/webp'):
        try:
            with Image.open(io.BytesIO(data)) as image:
                image.thumbnail((MAX_DIMENSION, MAX_DIMENSION))
                if image.mode not in ('RGB', 'RGBA'):
                    has_alpha = image.mode in ('LA', 'PA', 'P') or 'transparency' in image.info
                    image = image.convert('RGBA' if has_alpha else 'RGB')
                buffer = io.BytesIO()
                image.save(buffer, 'WEBP', quality=WEBP_QUALITY, method=5)
                if buffer.tell() < len(data):
                    content, extension = buffer.getvalue(), 'webp'
        except Exception as e:
            warn(f"could not re-encode an image ({e}); saving it unchanged")
    return digest, content, extension, len(data)
