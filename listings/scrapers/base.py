"""Scraper interface.

Adding a new source: subclass `Scraper`, set the class-level `source`
identifier, implement `fetch(query)`, and register the class in
`listings/scrapers/__init__.py::build_registry()`.

`fetch()` should be best-effort — partial failures (one site down,
one parse error) should be logged and swallowed so the rest of the
cycle proceeds. Raise only if the scraper itself is misconfigured
(e.g. missing dep, bad credential).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class ScrapedListing:
    """One normalized aircraft listing, ready to upsert into the DB."""

    source: str
    """Stable identifier for the source scraper (e.g. 'craigslist')."""

    site: str
    """Source-specific sub-grouping. For Craigslist this is the regional
    subdomain (seattle, sfbay, ...). For sources without that concept,
    fall back to the source name."""

    title: str
    link: str
    price: str
    location: str


class Scraper(ABC):
    """Abstract base class for an aircraft-listing source."""

    source: str
    """Subclasses MUST override with a unique, lowercase, no-spaces id."""

    @abstractmethod
    def fetch(self, query: str | None = None) -> Iterable[ScrapedListing]:
        """Yield every listing the source has right now.

        Args:
            query: Optional keyword filter. Scrapers may ignore it if
                the source doesn't support search; the poll layer
                applies no client-side filtering — the result of
                `fetch()` is taken as-is.
        """
