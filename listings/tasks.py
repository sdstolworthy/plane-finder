"""Django-Q2 task functions.

Registered as schedules via the `seed_schedules` management command.
"""

from __future__ import annotations

import concurrent.futures
import logging

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import Listing, extract_posting_id
from .scraper import ScrapedListing, fetch_listings, fetch_sites, make_session

log = logging.getLogger(__name__)


def poll_all(query: str | None = None) -> dict:
    """Poll every Craigslist site and upsert listings into the DB.

    Returns a small dict so django-q2's task-result UI shows useful info.
    Settings provide the knobs (sites allowlist, concurrency, UA) so the
    task callable stays parameterless from the schedule's perspective.
    """
    query = query if query is not None else settings.POLL_QUERY
    session = make_session(settings.POLL_USER_AGENT)

    sites = settings.POLL_SITES or fetch_sites(session)
    log.info("poll_all: %d sites, query=%r", len(sites), query)

    seen: list[ScrapedListing] = []
    errors = 0
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=settings.POLL_WORKERS
    ) as ex:
        futures = {ex.submit(fetch_listings, session, s, query): s for s in sites}
        for fut in concurrent.futures.as_completed(futures):
            site = futures[fut]
            try:
                seen.extend(fut.result())
            except Exception:
                log.exception("site %s raised", site)
                errors += 1

    created, updated = _upsert(seen)

    log.info(
        "poll_all: sites=%d scraped=%d created=%d updated=%d errors=%d",
        len(sites), len(seen), created, updated, errors,
    )
    return {
        "sites": len(sites),
        "scraped": len(seen),
        "created": created,
        "updated": updated,
        "errors": errors,
        "finished_at": timezone.now().isoformat(),
    }


def _upsert(scraped: list[ScrapedListing]) -> tuple[int, int]:
    created = 0
    updated = 0
    # Per-row upsert. With ~100s of items per cycle this is fine; if the
    # volume ever justifies it, swap to bulk_create(ignore_conflicts=True)
    # + a separate update pass keyed on link.
    with transaction.atomic():
        for s in scraped:
            obj, was_created = Listing.objects.update_or_create(
                link=s.link,
                defaults={
                    "site": s.site,
                    "posting_id": extract_posting_id(s.link),
                    "title": s.title,
                    "price": s.price,
                    "location": s.location,
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1
    return created, updated
