"""Trade-A-Plane scraper, driven by headless Chromium via Playwright.

Why a headless browser? Trade-A-Plane sits behind DataDome, which
fingerprints the browser, requires JS execution, and serves a CAPTCHA
on suspicious traffic. A plain `requests.get()` reliably gets 403'd at
the edge. Playwright + light stealth tweaks (`navigator.webdriver`
spoofing, real viewport, real locale) usually clear the easy checks
but **not** the harder ones — when DataDome serves its CAPTCHA, this
scraper logs and returns an empty list rather than try to solve it.

Cost of doing business:
- ~500MB of Chromium in the image.
- Each `fetch()` launches a browser; budget ~10s per category.
- DataDome is fragile to beat from datacenter IPs. If logs consistently
  say "blocked by DataDome", you'll need a residential proxy or a paid
  scraping API (configurable later).
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from urllib.parse import quote

from bs4 import BeautifulSoup

from .base import ScrapedListing, Scraper

log = logging.getLogger(__name__)

BASE_URL = "https://www.trade-a-plane.com"
SEARCH_PATH = "/search?s-type=aircraft"

# Override automation tells before the page's JS runs.
_STEALTH_INIT_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
Object.defineProperty(navigator, 'plugins', {
    get: () => [{name: 'Chrome PDF Plugin'}, {name: 'Chrome PDF Viewer'}, {name: 'Native Client'}]
});
window.chrome = { runtime: {} };
"""


class TradeAPlaneScraper(Scraper):
    source = "tradeaplane"

    def __init__(
        self,
        user_agent: str,
        categories: list[str] | None = None,
        per_category_timeout_ms: int = 20_000,
    ) -> None:
        self.user_agent = user_agent
        self.categories = categories or ["Single Engine Piston"]
        self.per_category_timeout_ms = per_category_timeout_ms

    def fetch(self, query: str | None = None) -> Iterable[ScrapedListing]:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            log.error(
                "TAP: playwright not installed (image was built without it?). "
                "Set POLL_TRADEAPLANE_ENABLED=false or rebuild with playwright."
            )
            return []

        all_listings: list[ScrapedListing] = []
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                ],
            )
            try:
                ctx = browser.new_context(
                    user_agent=self.user_agent,
                    viewport={"width": 1366, "height": 768},
                    locale="en-US",
                    timezone_id="America/Los_Angeles",
                )
                ctx.add_init_script(_STEALTH_INIT_SCRIPT)

                for category in self.categories:
                    listings = self._fetch_category(ctx, category, query)
                    log.info(
                        "TAP category %r yielded %d listings", category, len(listings)
                    )
                    all_listings.extend(listings)
            finally:
                browser.close()
        return all_listings

    def _fetch_category(
        self, ctx, category: str, query: str | None
    ) -> list[ScrapedListing]:
        url = f"{BASE_URL}{SEARCH_PATH}&category_level1={quote(category)}"
        if query:
            url += f"&keywords={quote(query)}"

        page = ctx.new_page()
        try:
            try:
                page.goto(
                    url,
                    timeout=self.per_category_timeout_ms,
                    wait_until="domcontentloaded",
                )
            except Exception:
                log.exception("TAP: page.goto failed for %s", url)
                return []

            html = page.content()
            if _looks_blocked(html):
                log.warning(
                    "TAP: blocked at the edge (DataDome challenge) — "
                    "category=%r url=%s", category, url
                )
                return []

            # Give the listing container a moment to render. Any of these
            # selectors might match depending on the current TAP layout —
            # the parser handles whichever shape comes back.
            try:
                page.wait_for_selector(
                    ".listing-container, .listing, .ad-listing, [data-listing-id]",
                    timeout=5_000,
                )
            except Exception:
                # Not necessarily fatal — log and try to parse anyway.
                log.warning(
                    "TAP: no listing selector matched within 5s on %s — "
                    "parsing whatever rendered.", url
                )

            html = page.content()
            return _parse_listings(html)
        finally:
            page.close()


def _looks_blocked(html: str) -> bool:
    """Heuristic match for DataDome's challenge page."""
    return any(
        marker in html
        for marker in (
            "geo.captcha-delivery.com",
            "captcha-delivery",
            'id="cmsg"',  # the DataDome stub literally has <p id="cmsg">
        )
    )


def _parse_listings(html: str) -> list[ScrapedListing]:
    """Best-effort parse — TAP's markup varies, so try several shapes.

    The matched node MUST contain an <a href> and at least a title
    element. Price/location are best-effort.
    """
    soup = BeautifulSoup(html, "html.parser")

    cards = soup.select(
        ".listing-container, .listing, .ad-listing, [data-listing-id]"
    )
    out: list[ScrapedListing] = []
    for el in cards:
        link_el = (
            el.select_one("a[href*='listing']")
            or el.select_one("a[href*='aircraft']")
            or el.select_one("a")
        )
        if not link_el or not link_el.get("href"):
            continue

        href = link_el["href"]
        if href.startswith("/"):
            href = BASE_URL + href
        if not href.startswith("http"):
            continue

        title_el = (
            el.select_one(".titlebar a")
            or el.select_one(".titlebar")
            or el.select_one(".title")
            or el.select_one("h2, h3")
            or link_el
        )
        price_el = (
            el.select_one(".price-container")
            or el.select_one(".price")
            or el.select_one("[itemprop='price']")
        )
        location_el = (
            el.select_one(".location")
            or el.select_one(".dealer-location")
            or el.select_one(".seller-location")
        )

        title = title_el.get_text(" ", strip=True) if title_el else ""
        if not title:
            continue

        out.append(
            ScrapedListing(
                source="tradeaplane",
                site="tradeaplane",
                title=title[:512],
                link=href[:1024],
                price=price_el.get_text(" ", strip=True) if price_el else "",
                location=location_el.get_text(" ", strip=True) if location_el else "",
            )
        )
    return out
