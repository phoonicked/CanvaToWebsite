"""Bringing back animated stickers and videos, which the editor shows as still frames.

Elements marked ``data-canva-media`` during extraction become a Lottie player (stickers are
Lottie JSON) or a <video> saved with the site.
"""
import hashlib
import os
import re
import shutil
import subprocess
import tempfile

from .common import HTTP, SAFE_ID, download, warn
from .design_data import find_media

LOTTIE_PLAYER_URL = 'https://cdnjs.cloudflare.com/ajax/libs/lottie-web/5.12.2/lottie.min.js'
LOTTIE_PLAYER_SHA256 = 'a0757321f974527bda3cc2593bf56cc7ffe4578421249ced6ae49ffb1c529f90'
VIDEO_EXTENSIONS = {'video/mp4': 'mp4', 'video/webm': 'webm', 'video/quicktime': 'mov'}


def quality_height(file):
    match = re.match(r'(\d+)', file.get('quality', ''))
    return int(match.group(1)) if match else 0


class MediaEmbedder:
    def __init__(self, page_source, assets_dir, max_video_quality=720, compressor=None):
        self.page_source = page_source
        self.assets_dir = assets_dir
        self.max_video_quality = max_video_quality
        self.compressor = compressor
        self.lottie_data = {}
        self.video_files = {}

    def embed(self, soup):
        """Updates the soup in place and returns the scripts to append to <body>."""
        for element in soup.select('[data-canva-media]'):
            media_id = element['data-canva-media']
            del element['data-canva-media']
            record = find_media(self.page_source, media_id) if SAFE_ID.fullmatch(media_id) else None
            if not record or not record.get('files'):
                warn(f"no media details found for {media_id!r}; keeping the still frame")
            elif record['files'][0]['url'].split('?')[0].endswith('.json'):
                self._embed_sticker(soup, element, media_id, record)
            elif record.get('contentType') == 'VIDEO':
                self._embed_video(soup, element, media_id, record)
        return self._body_scripts()

    def _embed_sticker(self, soup, element, media_id, record):
        if not self.lottie_data:
            self._save_lottie_player()
        if media_id not in self.lottie_data:
            self.lottie_data[media_id] = download(record['files'][0]['url']).text
            print(f"Embedded animated sticker '{record.get('title', media_id)}'")
        element.clear()
        element.append(soup.new_tag('div', attrs={
            'class': 'canva-lottie', 'data-lottie': media_id, 'role': 'img', 'aria-label': record.get('title', ''),
        }))

    def _save_lottie_player(self):
        content = download(LOTTIE_PLAYER_URL).content
        if hashlib.sha256(content).hexdigest() != LOTTIE_PLAYER_SHA256:
            raise RuntimeError(f"{LOTTIE_PLAYER_URL} doesn't match its expected checksum")
        with open(os.path.join(self.assets_dir, 'lottie.min.js'), 'wb') as f:
            f.write(content)

    def _embed_video(self, soup, element, media_id, record):
        if media_id not in self.video_files:
            self.video_files[media_id] = self._download_video(media_id, record)
        video = soup.new_tag('video', attrs={
            'class': 'canva-video', 'src': self.video_files[media_id], 'controls': '', 'playsinline': '',
            'preload': 'metadata', 'aria-label': record.get('title', ''),
        })
        poster = element.find('img')
        if poster and poster.get('src'):
            video['poster'] = poster['src']
        element.clear()
        element.append(video)

    def pick_file(self, record):
        files = sorted(record['files'], key=quality_height)
        allowed = [file for file in files if quality_height(file) <= self.max_video_quality] or files[:1]
        best = allowed[-1]
        # When it'll be compressed anyway, download the smallest file with enough resolution. This
        # uses the real height, since Canva's labels don't match it (its "480P" file is 640x360).
        duration = record.get('durationSeconds')
        if (self.compressor and duration and best.get('height')
                and best.get('fileSizeBytes', 0) > self.compressor.max_bytes):
            target_height, _ = self.compressor.plan(duration, best['height'])
            best = next((file for file in allowed if file.get('height', 0) >= target_height), best)
        return best

    def _download_video(self, media_id, record):
        file = self.pick_file(record)
        title = record.get('title', media_id)
        print(f"Downloading video '{title}' ({file.get('quality')}, {file.get('fileSizeBytes', 0) / 1e6:.0f} MB)...")
        with tempfile.TemporaryDirectory() as work_dir:
            with HTTP.get(file['url'], stream=True, timeout=60) as response:
                response.raise_for_status()
                extension = VIDEO_EXTENSIONS.get(response.headers.get('content-type', '').split(';')[0], 'mp4')
                source = os.path.join(work_dir, f'source.{extension}')
                with open(source, 'wb') as f:
                    for chunk in response.iter_content(1 << 20):
                        f.write(chunk)

            if self.compressor and os.path.getsize(source) > self.compressor.max_bytes:
                filename = f"{media_id}.mp4"
                try:
                    self.compressor.compress(source, os.path.join(self.assets_dir, filename), title)
                    return f"assets/{filename}"
                except (subprocess.CalledProcessError, ValueError) as e:
                    warn(f"could not compress '{title}' ({e}); keeping the original")
            filename = f"{media_id}.{extension}"
            shutil.move(source, os.path.join(self.assets_dir, filename))
        return f"assets/{filename}"

    def _body_scripts(self):
        if not self.lottie_data:
            return ''
        # Inlined because browsers block fetching local JSON from pages opened from disk.
        data_scripts = ''.join(
            '<script type="application/json" id="canva-lottie-{}">{}</script>'.format(media_id, data.replace('</', '<\\/'))
            for media_id, data in self.lottie_data.items()
        )
        return (
            f'<script src="assets/lottie.min.js"></script>{data_scripts}<script>'
            'document.querySelectorAll("[data-lottie]").forEach(function (el) {'
            ' lottie.loadAnimation({container: el, renderer: "svg", loop: true, autoplay: true,'
            ' animationData: JSON.parse(document.getElementById("canva-lottie-" + el.dataset.lottie).textContent)});'
            '});</script>'
        )
