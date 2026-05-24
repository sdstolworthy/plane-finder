"""Craigslist scraping helpers.

Pure functions — no Django imports — so they're trivially unit-testable
and can be reused outside the request cycle.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup

SITES_URL = "https://www.craigslist.org/about/sites"
AVIATION_CATEGORY = "ava"

SITE_RE = re.compile(r"https?://([a-z0-9-]+)\.craigslist\.org\b")
NON_REGIONAL = {"www", "geo", "accounts", "post", "forums", "blog", "list"}


@dataclass(frozen=True)
class ScrapedListing:
    site: str
    title: str
    link: str
    price: str
    location: str


def make_session(user_agent: str) -> requests.Session:
    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }
    )
    return s


def fetch_sites(session: requests.Session) -> list[str]:
    resp = session.get(SITES_URL, timeout=30)
    resp.raise_for_status()
    found = {m.group(1) for m in SITE_RE.finditer(resp.text)}
    return sorted(found - NON_REGIONAL)


def parse_listings(site: str, html: str) -> list[ScrapedListing]:
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
                site=site,
                title=title.get_text(strip=True) if title else "",
                link=link,
                price=price.get_text(strip=True) if price else "",
                location=location.get_text(strip=True) if location else "",
            )
        )
    return out


def fetch_listings(
    session: requests.Session,
    site: str,
    query: str | None = None,
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
    return parse_listings(site, resp.text)
