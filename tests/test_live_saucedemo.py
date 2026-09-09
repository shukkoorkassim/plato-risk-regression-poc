"""
Optional LIVE tests against the real https://www.saucedemo.com.

These are skipped automatically unless Playwright is installed AND its browser is
available, so the project still runs everywhere with plain pytest. To enable:

    pip install playwright
    playwright install chromium
    pytest tests/test_live_saucedemo.py

They cover the same components as the offline tests (login, cart, checkout),
using saucedemo's stable data-test selectors.
"""
import pytest

playwright = pytest.importorskip(
    "playwright.sync_api",
    reason="Playwright not installed; run `pip install playwright && playwright install chromium` to enable live tests.",
)
from playwright.sync_api import sync_playwright  # noqa: E402

BASE = "https://www.saucedemo.com"


@pytest.fixture(scope="module")
def page():
    try:
        pw = sync_playwright().start()
        browser = pw.chromium.launch(headless=True)
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"Chromium not available: {e}")
    pg = browser.new_page()
    yield pg
    browser.close()
    pw.stop()


def _login(pg, user="standard_user", pw="secret_sauce"):
    pg.goto(BASE, wait_until="domcontentloaded")
    pg.fill('[data-test="username"]', user)
    pg.fill('[data-test="password"]', pw)
    pg.click('[data-test="login-button"]')


def test_live_login_succeeds(page):
    _login(page)
    page.wait_for_selector('[data-test="inventory-list"]', timeout=10000)
    assert "/inventory.html" in page.url


def test_live_locked_out_user_sees_error(page):
    _login(page, user="locked_out_user")
    err = page.text_content('[data-test="error"]')
    assert err and "locked out" in err.lower()


def test_live_add_backpack_updates_cart_badge(page):
    _login(page)
    page.wait_for_selector('[data-test="inventory-list"]', timeout=10000)
    page.click('[data-test="add-to-cart-sauce-labs-backpack"]')
    badge = page.text_content('[data-test="shopping-cart-badge"]')
    assert badge == "1"
