# plane-finder

Searches every Craigslist regional site's `aviation` category and prints
the results. Scrapes the static search-result HTML at
`/search/ava` on each subdomain — Craigslist disabled `?format=rss` for
most clients, so HTML is the only surface that responds 200.

## Install

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

```sh
# Every Craigslist site, all aviation listings, plain text:
python plane_finder.py

# Narrow by keyword:
python plane_finder.py --query cessna

# Restrict to specific subdomains (skips the sites-list fetch):
python plane_finder.py --sites seattle,portland,sfbay --query 'super cub'

# Machine-readable output:
python plane_finder.py --query cirrus --format json > cirrus.json
python plane_finder.py --query mooney --format csv > mooney.csv
```

`--workers` (default 16) controls concurrency. Bumping it gets you results
faster but also gets you rate-limited or banned faster — Craigslist is not
fond of scrapers. Identify yourself with `--user-agent` and don't run this
on a tight loop.

## Notes

- Parses the static `cl-static-search-result` list items rendered by the
  search page. One page per site (~120 hits); pagination is not wired up.
- `ava` is the "aviation - all" category (combines `avo` by-owner and `avd`
  by-dealer). Swap `AVIATION_CATEGORY` in the script if you want one or
  the other specifically.
- The sites list is fetched live from `craigslist.org/about/sites` so new
  regions get picked up automatically.
- The default User-Agent is a Chrome-on-Linux string because Craigslist
  403s generic UAs at the edge. Override with `--user-agent` if you want.
