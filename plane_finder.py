"""Search every Craigslist site for aircraft listings.

Pulls the public list of Craigslist subdomains from /about/sites and fans
out one HTTP request per site against the `ava` (aviation - all) category,
parsing the static search-result HTML each site renders.

Notes on the approach:
- Craigslist disabled the `?format=rss` surface for most clients; the
  static HTML search page is the only thing that responds 200.
- A browser-shaped User-Agent is required — generic UAs get 403'd at the
  edge. Override via `--user-agent` if you want to be more honest about
  it (and accept that it may stop working).
- One page of results per site (~120 listings); pagination is left as an
  exercise. For aviation that's usually plenty.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import json
import re
import sys
from dataclasses import asdict, dataclass

import requests
from bs4 import BeautifulSoup

SITES_URL = "https://www.craigslist.org/about/sites"
AVIATION_CATEGORY = "ava"
DEFAULT_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

SITE_RE = re.compile(r"https?://([a-z0-9-]+)\.craigslist\.org\b")
# Subdomains that aren't regional sites (corporate / meta pages).
NON_REGIONAL = {"www", "geo", "accounts", "post", "forums", "blog", "list"}


@dataclass(frozen=True)
class Listing:
    site: str
    title: str
    link: str
    price: str
    location: str


def fetch_sites(session: requests.Session) -> list[str]:
    resp = session.get(SITES_URL, timeout=30)
    resp.raise_for_status()
    found = {m.group(1) for m in SITE_RE.finditer(resp.text)}
    return sorted(found - NON_REGIONAL)


def parse_listings(site: str, html: str) -> list[Listing]:
    soup = BeautifulSoup(html, "html.parser")
    out: list[Listing] = []
    for li in soup.select("li.cl-static-search-result"):
        a = li.select_one("a")
        title = li.select_one(".title")
        price = li.select_one(".price")
        location = li.select_one(".location")
        out.append(
            Listing(
                site=site,
                title=title.get_text(strip=True) if title else "",
                link=a["href"] if a and a.has_attr("href") else "",
                price=price.get_text(strip=True) if price else "",
                location=location.get_text(strip=True) if location else "",
            )
        )
    return out


def fetch_listings(
    session: requests.Session,
    site: str,
    query: str | None,
) -> list[Listing]:
    url = f"https://{site}.craigslist.org/search/{AVIATION_CATEGORY}"
    params = {"query": query} if query else None
    try:
        resp = session.get(url, params=params, timeout=20)
    except requests.RequestException:
        return []
    if resp.status_code != 200 or "text/html" not in resp.headers.get(
        "content-type", ""
    ):
        return []
    return parse_listings(site, resp.text)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--query", help="Keyword filter, e.g. 'cessna'")
    p.add_argument(
        "--sites",
        help="Comma-separated subdomains to scope to (skips the sites-list fetch)",
    )
    p.add_argument(
        "--workers",
        type=int,
        default=16,
        help="Concurrent fetches (default: 16; be polite)",
    )
    p.add_argument(
        "--format",
        choices=["text", "json", "csv"],
        default="text",
        help="Output format (default: text)",
    )
    p.add_argument(
        "--user-agent",
        default=DEFAULT_UA,
        help="Override the User-Agent header",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": args.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }
    )

    if args.sites:
        sites = [s.strip() for s in args.sites.split(",") if s.strip()]
    else:
        print("Fetching Craigslist site list...", file=sys.stderr)
        sites = fetch_sites(session)
        print(f"  {len(sites)} sites discovered", file=sys.stderr)

    all_listings: list[Listing] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {
            ex.submit(fetch_listings, session, s, args.query): s for s in sites
        }
        for fut in concurrent.futures.as_completed(futures):
            site = futures[fut]
            try:
                hits = fut.result()
            except Exception as exc:
                print(f"  {site}: error: {exc}", file=sys.stderr)
                continue
            if hits:
                print(f"  {site}: {len(hits)}", file=sys.stderr)
                all_listings.extend(hits)

    all_listings.sort(key=lambda L: (L.site, L.title))

    if args.format == "json":
        json.dump([asdict(L) for L in all_listings], sys.stdout, indent=2)
        sys.stdout.write("\n")
    elif args.format == "csv":
        writer = csv.DictWriter(
            sys.stdout,
            fieldnames=["site", "title", "price", "location", "link"],
        )
        writer.writeheader()
        for L in all_listings:
            writer.writerow(asdict(L))
    else:
        for L in all_listings:
            bits = [b for b in (L.price, L.location) if b]
            tail = f"  ({' — '.join(bits)})" if bits else ""
            print(f"[{L.site}] {L.title}{tail}")
            print(f"  {L.link}")
            print()

    print(
        f"Total: {len(all_listings)} listings across {len(sites)} sites.",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
