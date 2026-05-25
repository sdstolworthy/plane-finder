"""Django-Q2 task functions.

`poll_all` iterates over every registered Scraper and upserts whatever
each yields. Per-scraper failure is isolated — one broken source
doesn't kill the cycle.
"""

from __future__ import annotations

import logging

from django.db import transaction
from django.utils import timezone

from .models import Listing, extract_posting_id
from .scrapers import ScrapedListing, build_registry

log = logging.getLogger(__name__)


def poll_all(query: str | None = None) -> dict:
    """Poll every registered scraper and upsert listings into the DB."""
    scrapers = build_registry()
    log.info("poll_all: %d scrapers (%s), query=%r",
             len(scrapers), [s.source for s in scrapers], query)

    scraped: list[ScrapedListing] = []
    per_source: dict[str, int] = {}
    errors: dict[str, str] = {}

    for scraper in scrapers:
        try:
            results = list(scraper.fetch(query))
            scraped.extend(results)
            per_source[scraper.source] = len(results)
            log.info("scraper %s yielded %d listings", scraper.source, len(results))
        except Exception as exc:
            log.exception("scraper %s raised", scraper.source)
            errors[scraper.source] = str(exc)
            per_source[scraper.source] = 0

    created, updated = _upsert(scraped)
    log.info(
        "poll_all: scraped=%d created=%d updated=%d errors=%s per_source=%s",
        len(scraped), created, updated, list(errors), per_source,
    )
    return {
        "scrapers": [s.source for s in scrapers],
        "per_source": per_source,
        "errors": errors,
        "total_scraped": len(scraped),
        "created": created,
        "updated": updated,
        "finished_at": timezone.now().isoformat(),
    }


def _upsert(scraped: list[ScrapedListing]) -> tuple[int, int]:
    created = 0
    updated = 0
    with transaction.atomic():
        for s in scraped:
            obj, was_created = Listing.objects.update_or_create(
                link=s.link,
                defaults={
                    "source": s.source,
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
