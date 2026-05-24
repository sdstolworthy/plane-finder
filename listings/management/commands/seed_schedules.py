"""Idempotently register the recurring Craigslist poll schedule.

Run on each worker startup (see docker-compose `worker` command). Safe to
re-run — it `update_or_create`s by name.
"""

from __future__ import annotations

import json

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone
from django_q.models import Schedule


class Command(BaseCommand):
    help = "Register the periodic Craigslist poll schedule."

    def handle(self, *args, **opts):
        kwargs_json = json.dumps({"query": settings.POLL_QUERY})
        obj, created = Schedule.objects.update_or_create(
            name="poll-craigslist",
            defaults={
                "func": "listings.tasks.poll_all",
                "schedule_type": Schedule.MINUTES,
                "minutes": settings.POLL_INTERVAL_MINUTES,
                "repeats": -1,
                "kwargs": kwargs_json,
                # Fire once shortly after startup, then on the interval.
                "next_run": timezone.now() + timezone.timedelta(seconds=30),
            },
        )
        verb = "Created" if created else "Updated"
        self.stdout.write(
            f"{verb} schedule 'poll-craigslist' every {settings.POLL_INTERVAL_MINUTES} min "
            f"(query={settings.POLL_QUERY!r})"
        )
