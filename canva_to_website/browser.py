"""Starting Chrome and logging it into Canva."""
import re
import time

import undetected_chromedriver as uc
from selenium.common.exceptions import NoSuchWindowException, SessionNotCreatedException


def _options():
    options = uc.ChromeOptions()
    # Open a blank page instead of Chrome's New Tab page, which Chrome can swap out just after
    # launch, leaving the driver attached to a closed window.
    options.add_argument('about:blank')
    return options


def start_browser():
    try:
        driver = uc.Chrome(options=_options(), use_subprocess=True)
    except SessionNotCreatedException as e:
        # undetected-chromedriver fetches the newest ChromeDriver, which refuses a Chrome that
        # hasn't updated yet. Retry with a driver matching the installed Chrome.
        match = re.search(r'Current browser version is (\d+)', str(e))
        if not match:
            raise
        driver = uc.Chrome(options=_options(), use_subprocess=True, version_main=int(match.group(1)))

    # If a tab swap happens anyway, reattach to the open tab and make sure it stays put.
    stable_checks = 0
    for _ in range(30):
        try:
            driver.execute_script('return 1')
            stable_checks += 1
            if stable_checks == 3:
                break
        except NoSuchWindowException:
            stable_checks = 0
            if driver.window_handles:
                driver.switch_to.window(driver.window_handles[-1])
        time.sleep(0.5)
    return driver


def set_cookies(driver, cookies):
    # driver.add_cookie() needs a loaded canva.com page and fails when Canva's locale redirect
    # replaces it, so cookies are set through DevTools instead.
    driver.execute_cdp_cmd('Network.enable', {})
    driver.execute_cdp_cmd('Network.setCookies', {'cookies': cookies})
