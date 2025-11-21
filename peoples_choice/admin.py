from django.contrib import admin
from django.shortcuts import redirect
from django.urls import reverse
from constance import config

from .models import SongSuggestion


class EventSkuFilter(admin.SimpleListFilter):
    title = 'Event SKU'
    parameter_name = 'event_sku__exact'

    def lookups(self, request, model_admin):
        # Get all distinct event SKUs
        event_skus = SongSuggestion.objects.values_list('event_sku', flat=True).distinct().order_by('event_sku')
        return [(sku, sku) for sku in event_skus]

    def queryset(self, request, queryset):
        # Apply filter based on selection or default
        if self.value():
            return queryset.filter(event_sku=self.value())
        else:
            # If no filter selected, apply default from config
            default_event_sku = getattr(config, 'EVENT_SKU', '')
            if default_event_sku:
                return queryset.filter(event_sku=default_event_sku)
            else:
                return queryset


@admin.register(SongSuggestion)
class SongSuggestionAdmin(admin.ModelAdmin):
    list_display = (
        'song_name',
        'musical',
        'votes',
        'chosen',
        'chosen_by',
        'event_sku',
    )
    list_filter = (EventSkuFilter, 'chosen')
    # Set default ordering: chosen=True first, then by votes descending
    ordering = ('-chosen', '-votes')

    def changelist_view(self, request, extra_context=None):
        # If no filter is selected, redirect to show default filter as selected
        if 'event_sku__exact' not in request.GET:
            default_event_sku = getattr(config, 'EVENT_SKU', '')
            if default_event_sku:
                query = request.GET.copy()
                query['event_sku__exact'] = default_event_sku
                info = self.model._meta.app_label, self.model._meta.model_name
                changelist_url = reverse('admin:%s_%s_changelist' % info)
                return redirect(f"{changelist_url}?{query.urlencode()}")
        return super().changelist_view(request, extra_context)
