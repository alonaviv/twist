from datetime import datetime, timezone, timedelta
import pytz

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


def get_hours_difference_from_utc():
    utc = datetime.now(timezone.utc)
    ist = datetime.now(pytz.timezone('Israel'))
    delta = ist.replace(tzinfo=None) - utc.replace(tzinfo=None)
    return int(delta.total_seconds() // 3600)


class SongRequestAdmin(admin.ModelAdmin):
    list_display = (
        'priority', 'singer', 'get_additional_singers', 'song_name', 'get_request_time', 'musical',
    )
    list_filter = (NotYetPerformedFilter,)
    actions = [set_performed, set_not_performed]

    def has_delete_permission(self, request, obj=None):
        return False

    def get_request_time(self, obj):
        return (obj.request_time + timedelta(hours=get_hours_difference_from_utc())).strftime("%H:%M %p")
    get_request_time.short_description = 'Request Time'


admin.site.register(SongRequest, SongRequestAdmin)
