import argparse
import sys

from .browser import set_cookies, start_browser
from .common import ConversionError
from .converter import DESIGN_URL, convert
from .cookies import read_cookies


def parse_arguments(argv=None):
    parser = argparse.ArgumentParser(prog='canva-to-website',
                                     description='Turn a Canva design into a static website.')
    parser.add_argument('--cookies', required=True, help='your exported Canva cookies (JSON or cookies.txt)')
    parser.add_argument('--url', required=True, help='link to the Canva design')
    parser.add_argument('--output', default='output', help='folder to put sites in (default: output)')
    parser.add_argument('--video-quality', type=int, default=720, choices=[240, 480, 720, 1080],
                        help='highest video resolution to download (default: 720)')
    parser.add_argument('--max-video-mb', type=int, default=24,
                        help='compress videos over this size (default: 24, fits every major static host; '
                             '0 turns compression off)')
    args = parser.parse_args(argv)
    if not DESIGN_URL.match(args.url):
        parser.error('--url should be a Canva design link, like https://www.canva.com/design/DAxxxxxxx/...')
    if args.max_video_mb < 0:
        parser.error('--max-video-mb must be 0 or more')
    return args


def main(argv=None):
    args = parse_arguments(argv)
    try:
        cookies = read_cookies(args.cookies)
        driver = start_browser()
        try:
            set_cookies(driver, cookies)
            convert(driver, args.url, args.output, args.video_quality, args.max_video_mb)
        finally:
            driver.quit()
    except ConversionError as e:
        sys.exit(f"Error: {e}")
    except KeyboardInterrupt:
        sys.exit(130)
