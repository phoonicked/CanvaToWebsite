"""Shrinking videos to fit static hosts' file size limits (Cloudflare Pages: 25 MB, GitHub: 100 MB)."""
import os
import re
import subprocess
import tempfile

# (height, lowest video kbps that still looks good at that height), best first
RESOLUTION_LADDER = [(1080, 2500), (720, 1000), (480, 350), (360, 200)]
AUDIO_KBPS = 64
CONTAINER_OVERHEAD = 0.97


class VideoCompressor:
    """Two-pass encodes at the highest resolution the size budget can carry well.

    Uses the ffmpeg binary that comes with the imageio-ffmpeg package.
    """

    def __init__(self, max_mb):
        self.max_bytes = max_mb * 1_000_000
        self._ffmpeg = None

    @property
    def ffmpeg(self):
        if self._ffmpeg is None:
            import imageio_ffmpeg
            self._ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        return self._ffmpeg

    def plan(self, duration, source_height):
        """Returns (height, video kbps) for a video of this length."""
        video_kbps = int(self.max_bytes * 8 / 1000 / duration * CONTAINER_OVERHEAD - AUDIO_KBPS)
        for height, floor in RESOLUTION_LADDER:
            if height <= source_height and video_kbps >= floor:
                return height, video_kbps
        return min(360, source_height), max(video_kbps, RESOLUTION_LADDER[-1][1])

    def compress(self, source, destination, title):
        output = subprocess.run([self.ffmpeg, '-hide_banner', '-i', source], capture_output=True, text=True).stderr
        duration = re.search(r'Duration: (\d+):(\d+):([\d.]+)', output)
        size = re.search(r'Video: .*?, \d{2,5}x(\d{2,5})', output)
        if not duration or not size:
            raise ValueError('ffmpeg could not read the video')
        h, m, s = duration.groups()
        height, video_kbps = self.plan(int(h) * 3600 + int(m) * 60 + float(s), int(size.group(1)))

        print(f"Compressing '{title}' to {height}p at {video_kbps} kbps...")
        with tempfile.TemporaryDirectory() as work_dir:
            common = ['-y', '-v', 'error', '-i', source, '-c:v', 'libx264', '-preset', 'medium',
                      '-b:v', f'{video_kbps}k', '-vf', f'scale=-2:{height}',
                      '-passlogfile', os.path.join(work_dir, 'pass')]
            subprocess.run([self.ffmpeg, *common, '-pass', '1', '-an', '-f', 'mp4', os.devnull], check=True)
            subprocess.run([self.ffmpeg, *common, '-pass', '2', '-c:a', 'aac', '-b:a', f'{AUDIO_KBPS}k',
                            '-movflags', '+faststart', destination], check=True)
        result = os.path.getsize(destination)
        note = ' (over budget: the video is too long to fit at acceptable quality)' if result > self.max_bytes else ''
        print(f"  {os.path.getsize(source) / 1e6:.0f} MB -> {result / 1e6:.1f} MB{note}")
