# plane-finder

Django web service that polls a pluggable set of aircraft-listing
sources (Craigslist today; Trade-A-Plane behind Playwright; Barnstormers
/ Controller / etc. when added) in the background, stores listings in
Postgres, and serves a filterable list at `/`. Deployable to Coolify
as-is.

## Architecture

```
┌──────────┐   ┌──────────┐   ┌────────────┐
│ db       │←──│ migrate  │   │ web        │  gunicorn @ :8000
│ postgres │   │ one-shot │   │ Django     │  → list view + admin
└────┬─────┘   └──────────┘   └────────────┘
     │                              ↑
     ↓                              │ reads
┌──────────┐                   ┌────────────┐
│ Listing  │←─── writes ───────│ worker     │  django-q2 qcluster
│ rows     │                   │ poll_all() │  every POLL_INTERVAL_MINUTES
└──────────┘                   └────────────┘
```

- `web` — Django + Gunicorn + Whitenoise. List view at `/`, admin at
  `/admin/`.
- `worker` — Django-Q2 cluster running `listings.tasks.poll_all` on a
  schedule. No Redis; the DB is the broker.
- `migrate` — one-shot service that runs `migrate` + `collectstatic`
  before `web` / `worker` start. Prevents the contenttypes race.
- `db` — Postgres 16.

## Local development

```sh
docker compose up --build
# → http://localhost:8000
# → http://localhost:8000/admin/  (create a superuser first)
```

Create a superuser:

```sh
docker compose exec web python manage.py createsuperuser
```

Force an immediate poll instead of waiting for the schedule:

```sh
docker compose exec worker python manage.py poll_now --query cessna
```

Knobs (via env or `.env` — see `.env.example`):

| Var | Default | Purpose |
|-----|---------|---------|
| `POLL_INTERVAL_MINUTES` | `60` | Schedule cadence |
| `POLL_QUERY` | _empty_ | Keyword filter per site |
| `POLL_SITES` | _empty (all ~700)_ | Comma-separated subdomain allowlist |
| `POLL_WORKERS` | `8` | Concurrent fetches per poll cycle |
| `Q_WORKERS` | `2` | Django-Q worker processes |

## Deploying to Coolify

The compose file uses Coolify's "magic" env vars so most of the wiring
is automatic:

- `SERVICE_FQDN_WEB_8000=/` — Coolify generates a public domain and
  Traefik-routes it to `web:8000`. The same domain shows up as
  `${SERVICE_FQDN_WEB}` (no port) and `${SERVICE_URL_WEB}` (with scheme)
  for Django to consume.
- `SERVICE_PASSWORD_POSTGRES` — auto-generated DB password, injected
  into both `db` and `web`/`worker` for the `DATABASE_URL`.
- `SERVICE_BASE64_SECRET` — auto-generated 32-byte Django secret key.

Steps:

1. Push this repo to GitHub.
2. In Coolify, create a new "Docker Compose" resource pointing at the
   repo. Coolify reads `docker-compose.yaml`.
3. Set any non-magic overrides under **Environment Variables**
   (`POLL_QUERY`, `POLL_INTERVAL_MINUTES`, etc.).
4. Deploy.

The published URL is the value Coolify shows for `SERVICE_FQDN_WEB`.

### Note on Craigslist's anti-bot edge

Craigslist 403s generic User-Agents at the edge. The default scraper UA
is a Chrome-on-Linux string; override with `POLL_USER_AGENT` if needed.
If the Coolify VM's IP range is on Craigslist's block list, you'll see
zero scraped rows and 403s in the worker logs — there's no clean
workaround short of routing through a residential proxy.

## Adding a new scraper

Sources live behind a `Scraper` ABC (`listings/scrapers/base.py`).
Adding one is three steps:

1. **Implement** `listings/scrapers/<name>.py`:
   ```python
   from .base import ScrapedListing, Scraper

   class BarnstormersScraper(Scraper):
       source = "barnstormers"

       def fetch(self, query=None):
           # hit the source, yield ScrapedListing(source="barnstormers", ...)
           ...
   ```
2. **Register** in `listings/scrapers/__init__.py::build_registry()` —
   add an instance to the returned list (optionally gated on a settings
   flag, like the TAP scraper).
3. **Done** — `listings/tasks.py::poll_all` will pick it up automatically.
   Per-scraper failures are isolated; one broken source can't kill the
   cycle.

The model stores `source` and `site` separately. For sources without a
sub-grouping concept (TAP, Barnstormers), set `site` equal to the
source name. For Craigslist, `site` is the regional subdomain.

## Notes on individual sources

- **Craigslist** — works with plain HTTP and a Chrome-on-Linux UA. The
  scraper enumerates `/about/sites`, then hits each subdomain's
  `/search/ava`. RSS is 403'd at the edge so we parse the static HTML.
- **Trade-A-Plane** — gated by DataDome (JS challenge + browser
  fingerprinting). Disabled by default (`POLL_TRADEAPLANE_ENABLED`).
  Even with Playwright + light stealth tweaks, datacenter IPs reliably
  get served the CAPTCHA — when that happens the scraper logs
  "blocked by DataDome" and returns empty. Use a residential proxy or
  a paid scraping API (ScraperAPI/ZenRows/Bright Data) to get past it.

## Project layout

```
plane-finder/
├── Dockerfile                  # python:3.12-slim + Playwright Chromium
├── docker-compose.yaml         # web + worker + migrate + db, Coolify-aware
├── manage.py
├── requirements.txt
├── planefinder/                # Django project (settings, urls, wsgi)
└── listings/                   # The app
    ├── models.py               # Listing — deduped on URL, indexed by (source, site)
    ├── scrapers/
    │   ├── base.py             # Scraper ABC + ScrapedListing dataclass
    │   ├── craigslist.py
    │   ├── tradeaplane.py      # Playwright-driven, opt-in
    │   └── __init__.py         # build_registry() — the single source of truth
    ├── tasks.py                # poll_all() — iterates the registry
    ├── views.py                # GET / list + filter (source, site, q)
    ├── admin.py                # Django admin for Listing
    ├── templates/listings/index.html
    └── management/commands/
        ├── seed_schedules.py   # registers the periodic schedule
        └── poll_now.py         # synchronous one-off poll
```
