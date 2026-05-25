from django.contrib import admin

from .models import Listing


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = ("title", "source", "site", "price", "location", "first_seen", "last_seen")
    list_filter = ("source", "site")
    search_fields = ("title", "location", "site", "source", "posting_id")
    date_hierarchy = "first_seen"
    readonly_fields = ("first_seen", "last_seen", "posting_id")
    ordering = ("-first_seen",)
