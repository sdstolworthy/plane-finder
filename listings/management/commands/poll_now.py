"""Run a single Craigslist poll synchronously. Useful for smoke tests."""

from __future__ import annotations

from django.core.management.base import BaseCommand

from listings.tasks import poll_all


class Command(BaseCommand):
    help = "Trigger a Craigslist poll immediately, in-process."

    def add_arguments(self, parser):
        parser.add_argument("--query", help="Override settings.POLL_QUERY")

    def handle(self, *args, **opts):
        result = poll_all(query=opts.get("query"))
        for k, v in result.items():
            self.stdout.write(f"{k}: {v}")
