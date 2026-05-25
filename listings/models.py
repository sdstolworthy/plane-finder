from __future__ import annotations

import re

from django.db import models

# Posting URL shape: https://<site>.craigslist.org/<area>/<cat>/d/<slug>/<id>.html
POSTING_ID_RE = re.compile(r"/(\d+)\.html(?:[?#].*)?$")


def extract_posting_id(link: str) -> str:
    m = POSTING_ID_RE.search(link or "")
    return m.group(1) if m else ""


class Listing(models.Model):
    """A single aircraft listing, deduped on its URL.

    `source` is the scraper identifier (craigslist, tradeaplane, ...).
    `site` is the source-specific sub-grouping — Craigslist subdomain
    for Craigslist, the source name itself for sources without that
    concept.
    """

    source = models.CharField(max_length=32, db_index=True, default="craigslist")
    site = models.CharField(max_length=64, db_index=True)
    posting_id = models.CharField(max_length=32, db_index=True, blank=True)
    title = models.CharField(max_length=512)
    link = models.URLField(max_length=1024, unique=True)
    price = models.CharField(max_length=64, blank=True)
    location = models.CharField(max_length=256, blank=True)
    first_seen = models.DateTimeField(auto_now_add=True, db_index=True)
    last_seen = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-first_seen"]
        indexes = [
            models.Index(fields=["source", "site"]),
            models.Index(fields=["site", "posting_id"]),
            models.Index(fields=["-first_seen"]),
        ]

    def __str__(self) -> str:
        return f"[{self.source}/{self.site}] {self.title}"
