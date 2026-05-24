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
            Q(title__icontains=q) | Q(location__icontains=q) | Q(site__icontains=q)
        )

    site = (request.GET.get("site") or "").strip()
    if site:
        qs = qs.filter(site__iexact=site)

    paginator = Paginator(qs, 50)
    page = paginator.get_page(request.GET.get("page"))

    site_choices = (
        Listing.objects.values_list("site", flat=True).distinct().order_by("site")
    )

    return render(
        request,
        "listings/index.html",
        {
            "page": page,
            "q": q,
            "site": site,
            "site_choices": site_choices,
            "total": paginator.count,
        },
    )
