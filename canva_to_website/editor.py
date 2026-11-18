"""Loading a design in Canva's editor and reading its pages out of the live page."""
import time

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from .common import ConversionError, warn

PAGE_SELECTOR = '[data-page-id]'
LOAD_TIMEOUT = 90

# Canva only keeps pages near the viewport rendered, so each page is scrolled into view and
# extracted while it's on screen. A page holds a container scaled to the editor zoom; inside it,
# an aria-hidden layer is the visual design and its sibling is a screen-reader copy of the text,
# which is left out.
EXTRACT_PAGE_SCRIPT = r"""
    const [index, done] = [arguments[0], arguments[arguments.length - 1]];
    const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

    // Sticker and video media IDs only exist in React's props (store.fill.video), so walk each
    // element's fiber up to its parent DOM element.
    const mediaIdOf = el => {
        const key = Object.keys(el).find(k => k.startsWith('__reactFiber$'));
        let fiber = key && el[key];
        for (let hop = 0; fiber && hop < 8; hop++, fiber = fiber.return) {
            if (hop > 0 && typeof fiber.type === 'string') break;
            const id = fiber.memoizedProps?.store?.fill?.video;
            if (typeof id === 'string' && /^[\w-]{1,64}$/.test(id)) return id;
        }
        return null;
    };

    // blob: URLs only exist inside this browser session, and Canva may revoke them once the page
    // scrolls away, so they're read now.
    const blobs = window.__canvaBlobs = window.__canvaBlobs || new Map();
    const readBlob = url => {
        if (!blobs.has(url)) {
            blobs.set(url, fetch(url).then(response => response.blob()).then(blob => new Promise((resolve, reject) => {
                const reader = new FileReader();
                reader.onload = () => resolve(reader.result);
                reader.onerror = reject;
                reader.readAsDataURL(blob);
            })));
        }
        return blobs.get(url);
    };

    (async () => {
        const page = document.querySelectorAll('[data-page-id]')[index];
        if (!page) return done(null);
        page.scrollIntoView({block: 'center'});
        let visual = null;
        for (let tries = 0; tries < 150 && !visual; tries++) {
            visual = page.firstElementChild?.querySelector(':scope > [aria-hidden="true"]');
            if (!visual) await sleep(100);
        }
        const scaler = page.firstElementChild;
        if (!scaler) return done(null);
        visual = visual || scaler;
        await sleep(300);
        await Promise.race([sleep(20000), Promise.all([...visual.querySelectorAll('img')].map(img =>
            img.complete ? null : new Promise(resolve => { img.onload = img.onerror = resolve; })))]);

        // Innermost first, so the media box gets the mark rather than its wrappers.
        for (const el of [...visual.querySelectorAll('*')].reverse()) {
            const id = mediaIdOf(el);
            if (id && !el.querySelector(`[data-canva-media="${id}"]`)) el.dataset.canvaMedia = id;
        }

        const clone = visual.cloneNode(true);
        if (visual === scaler) clone.style.removeProperty('transform');
        clone.removeAttribute('aria-hidden');

        let failed = 0;
        const clonedCanvases = clone.querySelectorAll('canvas');
        visual.querySelectorAll('canvas').forEach((canvas, i) => {
            try {
                const img = document.createElement('img');
                img.src = canvas.toDataURL();
                img.className = canvas.className;
                img.style.cssText = canvas.style.cssText;
                if (!canvas.style.width) img.style.width = canvas.offsetWidth + 'px';
                if (!canvas.style.height) img.style.height = canvas.offsetHeight + 'px';
                clonedCanvases[i].replaceWith(img);
            } catch (e) {
                failed++;
            }
        });
        for (const img of clone.querySelectorAll('img[src^="blob:"]')) {
            try {
                img.src = await readBlob(img.getAttribute('src'));
            } catch (e) {
                failed++;
            }
        }
        done({id: page.dataset.pageId, width: scaler.offsetWidth, height: scaler.offsetHeight,
              html: clone.outerHTML, failed});
    })();
"""

COLLECT_RESOURCES_SCRIPT = r"""
    const done = arguments[arguments.length - 1];
    const sheets = [...document.styleSheets, ...(document.adoptedStyleSheets || [])];
    document.fonts.ready.then(() => done({
        stylesheets: sheets.map(sheet => {
            if (sheet.href) return {href: sheet.href};
            try {
                return {css: [...sheet.cssRules].map(rule => rule.cssText).join('\n')};
            } catch (e) {
                return {css: ''};
            }
        }),
        fontUrls: performance.getEntriesByType('resource').map(entry => entry.name)
            .filter(name => name.startsWith('https://font-public.canva.com/')),
        htmlClass: document.documentElement.className,
        bodyClass: document.body.className,
        // document.title adds " - <design type>"
        designTitle: document.querySelector('meta[property="og:title"]')?.content || document.title,
        lang: document.documentElement.lang || 'en',
    }));
"""


def load_design(driver, url, timeout=LOAD_TIMEOUT, settle_interval=1.5):
    # The default 250-entry resource timing buffer can fill up before the fonts load.
    driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument',
                           {'source': 'performance.setResourceTimingBufferSize(100000);'})
    driver.get(url)
    try:
        WebDriverWait(driver, timeout).until(EC.presence_of_element_located((By.CSS_SELECTOR, PAGE_SELECTOR)))
    except TimeoutException:
        raise ConversionError("The design didn't load. Check the link, and export your cookies again "
                              "if your Canva login has expired.") from None

    previous = -1
    for _ in range(20):
        count = len(driver.find_elements(By.CSS_SELECTOR, PAGE_SELECTOR))
        if count == previous:
            break
        previous = count
        time.sleep(settle_interval)
    driver.set_script_timeout(timeout)


def extract_pages(driver):
    """Returns a dict per page: id, width, height and the page's HTML."""
    pages = []
    for index in range(len(driver.find_elements(By.CSS_SELECTOR, PAGE_SELECTOR))):
        page = driver.execute_async_script(EXTRACT_PAGE_SCRIPT, index)
        if not page:
            warn(f"page {index + 1} didn't render; skipping it")
            continue
        if page['failed']:
            warn(f"{page['failed']} image(s) on page {index + 1} could not be read")
        pages.append(page)
    if not pages:
        raise ConversionError("No pages found in the design.")
    return pages


def collect_resources(driver):
    """Stylesheets, loaded font files, title and language of the open design."""
    return driver.execute_async_script(COLLECT_RESOURCES_SCRIPT)
