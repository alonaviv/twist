from django.contrib import admin

from .models import SongSuggestion


@admin.register(SongSuggestion)
class SongSuggestionAdmin(admin.ModelAdmin):
    list_display = (
        'song_name',
        'musical',
        'event_sku',
        'votes',
        'chosen',
        'chosen_by',
        'created_at',
    )
    list_filter = ('event_sku', 'chosen')
    search_fields = ('song_name', 'musical', 'event_sku', 'chosen_by')
