"""Pluggable aircraft-listing scrapers.

Each source (Craigslist, Trade-A-Plane, Barnstormers, ...) is a `Scraper`
subclass exposed here. `REGISTRY` is the canonical list the poll task
iterates over — add new scrapers there.
"""

from __future__ import annotations

from django.conf import settings

from .base import ScrapedListing, Scraper
from .craigslist import CraigslistScraper
from .tradeaplane import TradeAPlaneScraper


def build_registry() -> list[Scraper]:
    """Return one configured instance of every scraper that's enabled.

    Settings drive the configuration; scrapers themselves stay
    side-effect-free until `fetch()` is called.
    """
    scrapers: list[Scraper] = [
        CraigslistScraper(
            user_agent=settings.POLL_USER_AGENT,
            max_workers=settings.POLL_WORKERS,
            sites=settings.POLL_SITES or None,
        ),
    ]
    if settings.POLL_TRADEAPLANE_ENABLED:
        scrapers.append(
            TradeAPlaneScraper(
                user_agent=settings.POLL_USER_AGENT,
                categories=settings.POLL_TRADEAPLANE_CATEGORIES or None,
            )
        )
    return scrapers


__all__ = [
    "ScrapedListing",
    "Scraper",
    "CraigslistScraper",
    "TradeAPlaneScraper",
    "build_registry",
]
