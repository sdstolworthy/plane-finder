"""Craigslist aviation-category scraper.

Enumerates every Craigslist subdomain via /about/sites, hits each
site's `/search/ava` (aviation - all) HTML search page, and parses the
`cl-static-search-result` cards. RSS is disabled at the edge so HTML is
the only working surface.

The default User-Agent is a Chrome-on-Linux string — generic UAs get
403'd at Craigslist's edge.
"""

from __future__ import annotations

import concurrent.futures
import logging
import re
from collections.abc import Iterable

import requests
from bs4 import BeautifulSoup

from .base import ScrapedListing, Scraper

log = logging.getLogger(__name__)

SITES_URL = "https://www.craigslist.org/about/sites"
AVIATION_CATEGORY = "ava"

_SITE_RE = re.compile(r"https?://([a-z0-9-]+)\.craigslist\.org\b")
_NON_REGIONAL = {"www", "geo", "accounts", "post", "forums", "blog", "list"}


class CraigslistScraper(Scraper):
    source = "craigslist"

    def __init__(
        self,
        user_agent: str,
        max_workers: int = 8,
        sites: list[str] | None = None,
    ) -> None:
        self.user_agent = user_agent
        self.max_workers = max_workers
        self._explicit_sites = sites  # if None, discover at fetch time

    def _make_session(self) -> requests.Session:
        s = requests.Session()
        s.headers.update(
            {
                "User-Agent": self.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
            }
        )
        return s

    def _discover_sites(self, session: requests.Session) -> list[str]:
        resp = session.get(SITES_URL, timeout=30)
        resp.raise_for_status()
        found = {m.group(1) for m in _SITE_RE.finditer(resp.text)}
        return sorted(found - _NON_REGIONAL)

    def _fetch_one(
        self, session: requests.Session, site: str, query: str | None
    ) -> list[ScrapedListing]:
        url = f"https://{site}.craigslist.org/search/{AVIATION_CATEGORY}"
        params = {"query": query} if query else None
        try:
            resp = session.get(url, params=params, timeout=20)
        except requests.RequestException:
            return []
        if resp.status_code != 200:
            return []
        if "text/html" not in resp.headers.get("content-type", ""):
            return []
        return _parse_listings(site, resp.text)

    def fetch(self, query: str | None = None) -> Iterable[ScrapedListing]:
        session = self._make_session()
        sites = self._explicit_sites or self._discover_sites(session)
        log.info("craigslist: %d sites, query=%r", len(sites), query)

        out: list[ScrapedListing] = []
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self.max_workers
        ) as ex:
            futures = {
                ex.submit(self._fetch_one, session, s, query): s for s in sites
            }
            for fut in concurrent.futures.as_completed(futures):
                site = futures[fut]
                try:
                    out.extend(fut.result())
                except Exception:
                    log.exception("craigslist site %s raised", site)
        return out


def _parse_listings(site: str, html: str) -> list[ScrapedListing]:
    soup = BeautifulSoup(html, "html.parser")
    out: list[ScrapedListing] = []
    for li in soup.select("li.cl-static-search-result"):
        a = li.select_one("a")
        title = li.select_one(".title")
        price = li.select_one(".price")
        location = li.select_one(".location")
        link = a["href"] if a and a.has_attr("href") else ""
        if not link:
            continue
        out.append(
            ScrapedListing(
                source="craigslist",
                site=site,
                title=title.get_text(strip=True) if title else "",
                link=link,
                price=price.get_text(strip=True) if price else "",
                location=location.get_text(strip=True) if location else "",
            )
        )
    return out
