from datetime import datetime, timezone

from django.contrib import admin
from django.utils import timezone

from .models import SongRequest, Singer, GroupSongRequest


def set_performed(modeladmin, request, queryset):
    for song in queryset:
        song.performance_time = datetime.now()
        song.save()

    Singer.cycles.seal_cycles()  # Will seal the evening when cycle 2 is all performed


def set_not_performed(modeladmin, request, queryset):
    for song in queryset:
        song.performance_time = None
        song.save()


set_performed.short_description = 'Mark song as performed'
set_performed.allowed_permissions = ['change']
set_not_performed.short_description = 'Mark song as not performed'
set_not_performed.allowed_permissions = ['change']


class NotYetPerformedFilter(admin.SimpleListFilter):
    title = 'Songs to Display'
    parameter_name = 'already_performed'

    def lookups(self, request, model_admin):
        return (
            ('already_performed', 'Include already performed and not yet scheduled'),
        )

    def queryset(self, request, queryset):
        if not self.value() == 'already_performed':
            return queryset.filter(performance_time=None, position__isnull=False)
        else:
            return queryset.all()


@admin.register(GroupSongRequest)
class GroupSongRequestAdmin(admin.ModelAdmin):
    list_display = (
        'song_name', 'musical', 'requested_by', 'get_request_time',
    )

    def get_request_time(self, obj):
        return obj.request_time.astimezone(timezone.get_current_timezone()).strftime("%H:%M %p")

    get_request_time.short_description = 'Request Time'
    get_request_time.admin_order_field = 'request_time'

    ordering = ['request_time']


@admin.register(SongRequest)
class SongRequestAdmin(admin.ModelAdmin):
    list_display = (
        'position', 'formatted_cycle', 'singer', 'song_name', 'musical', 'duet_partner', 'priority',
        'get_performance_time', 'get_request_time', 'get_initial_signup'
    )
    list_filter = (NotYetPerformedFilter,)
    actions = [set_performed, set_not_performed]
    change_list_template = "admin/song_request_changelist.html"

    def has_delete_permission(self, request, obj=None):
        return False

    def formatted_cycle(self, obj):
        return obj.cycle and f'{obj.cycle:g}'

    formatted_cycle.short_description = 'Cycle'

    def get_request_time(self, obj):
        return obj.request_time.astimezone(timezone.get_current_timezone()).strftime("%H:%M %p")

    get_request_time.short_description = 'Request Time'
    get_request_time.admin_order_field = 'request_time'

    def get_initial_signup(self, obj):
        if not obj.singer.is_superuser:
            return obj.singer.date_joined.astimezone(timezone.get_current_timezone()).strftime("%H:%M %p")

    get_initial_signup.short_description = 'Initial Signup'
    get_initial_signup.admin_order_field = 'singer__date_joined'

    def get_performance_time(self, obj):
        if obj.performance_time:
            return obj.performance_time.astimezone(timezone.get_current_timezone()).strftime("%H:%M %p")

        else:
            return None

    get_performance_time.short_description = 'Performance Time'
    get_performance_time.admin_order_field = 'performance_time'


@admin.register(Singer)
class SingerAdmin(admin.ModelAdmin):
    list_display = ['username', 'cy1_position', 'cy2_position', 'cy3_position',
                    'date_joined', 'is_superuser', 'no_image_upload']
