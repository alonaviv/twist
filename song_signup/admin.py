from datetime import datetime

from django.contrib import admin

from .models import SongRequest
from .views import assign_song_priorities


def set_performed(modeladmin, request, queryset):
    for song in queryset:
        song.performance_time = datetime.now()
        song.priority = -1
        song.save()

    assign_song_priorities()


def set_not_performed(modeladmin, request, queryset):
    for song in queryset:
        song.performance_time = None
        song.save()

    assign_song_priorities()


set_performed.short_description = 'Mark song as performed'
set_not_performed.short_description = 'Mark song as not performed'


class NotYetPerformedFilter(admin.SimpleListFilter):
    title = 'Songs to Display'
    parameter_name = 'already_performed'

    def lookups(self, request, model_admin):
        return (
            ('already_performed', 'Include already performed'),
        )

    def queryset(self, request, queryset):
        if not self.value() == 'already_performed':
            return queryset.filter(performance_time=None)
        else:
            return queryset.all()


class SongRequestAdmin(admin.ModelAdmin):
    list_display = (
        'priority', 'singer', 'get_additional_singers', 'song_name', 'request_time', 'musical',
    )
    list_filter = (NotYetPerformedFilter,)
    actions = [set_performed, set_not_performed]

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(SongRequest, SongRequestAdmin)
