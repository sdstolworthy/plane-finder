from __future__ import annotations

from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render

from .models import Listing


def index(request):
    qs = Listing.objects.all()

    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(
            Q(title__icontains=q)
            | Q(location__icontains=q)
            | Q(site__icontains=q)
            | Q(source__icontains=q)
        )

    source = (request.GET.get("source") or "").strip()
    if source:
        qs = qs.filter(source__iexact=source)

    site = (request.GET.get("site") or "").strip()
    if site:
        qs = qs.filter(site__iexact=site)

    paginator = Paginator(qs, 50)
    page = paginator.get_page(request.GET.get("page"))

    source_choices = (
        Listing.objects.values_list("source", flat=True).distinct().order_by("source")
    )
    site_choices = (
        Listing.objects.values_list("site", flat=True).distinct().order_by("site")
    )

    return render(
        request,
        "listings/index.html",
        {
            "page": page,
            "q": q,
            "source": source,
            "site": site,
            "source_choices": source_choices,
            "site_choices": site_choices,
            "total": paginator.count,
        },
    )
