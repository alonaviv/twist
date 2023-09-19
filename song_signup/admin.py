from django.contrib import admin
from django.utils import timezone

from .managers import LATE_SINGER_CYCLE
from .models import SongRequest, Singer, GroupSongRequest, SongSuggestion


def set_performed(modeladmin, request, queryset):
    for song in queryset:
        song.performance_time = timezone.now()
        song.save()
        Singer.ordering.calculate_positions()


def set_not_performed(modeladmin, request, queryset):
    for song in queryset:
        song.performance_time = None
        song.save()
        Singer.ordering.calculate_positions()


set_performed.short_description = 'Mark song as performed'
set_performed.allowed_permissions = ['change']
set_not_performed.short_description = 'Mark song as not performed'
set_not_performed.allowed_permissions = ['change']


class NotYetPerformedFilter(admin.SimpleListFilter):
    title = 'Songs to Display'
    parameter_name = 'already_performed'

    def lookups(self, request, model_admin):
        return (
            ('not_scheduled', 'Include Not Scheduled'),
        )

    def queryset(self, request, queryset):
        if not self.value() == 'not_scheduled':
            return queryset.filter(performance_time=None, position__isnull=False)
        else:
            return queryset.all()


@admin.register(GroupSongRequest)
class GroupSongRequestAdmin(admin.ModelAdmin):
    list_display = (
        'song_name', 'musical', 'suggested_by', 'get_request_time',
    )

    def get_request_time(self, obj):
        return obj.request_time.astimezone(timezone.get_current_timezone()).strftime("%H:%M %p")

    get_request_time.short_description = 'Request Time'
    get_request_time.admin_order_field = 'request_time'

    ordering = ['request_time']


@admin.register(SongSuggestion)
class SongSuggestionAdmin(admin.ModelAdmin):
    list_display = (
        'song_name', 'musical', 'suggested_by', 'get_request_time', 'is_used',
    )

    def get_request_time(self, obj):
        return obj.request_time.astimezone(timezone.get_current_timezone()).strftime("%H:%M %p")

    get_request_time.short_description = 'Request Time'
    get_request_time.admin_order_field = 'request_time'

    ordering = ['request_time']


@admin.register(SongRequest)
class SongRequestAdmin(admin.ModelAdmin):
    list_display = (
        'position', 'allows_filming', 'singer', 'song_name', 'musical', 'duet_partner', 'get_notes', 'get_additional_singers',
        'suggested_by', 'get_performance_time', 'get_request_time', 'get_initial_signup'
    )
    list_filter = (NotYetPerformedFilter,)
    actions = [set_performed, set_not_performed]
    ordering = ['position']
    change_list_template = "admin/song_request_changelist.html"

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['new_singers_num'] = Singer.ordering.new_singers_num()
        return super().changelist_view(request, extra_context=extra_context)

    def has_delete_permission(self, request, obj=None):
        return False

    def formatted_cycle(self, obj):
        if obj.cycle == LATE_SINGER_CYCLE:
            return 'NEW-SINGER-SLOTS'
        return f'{obj.cycle:g}' if obj.cycle else ''

    formatted_cycle.short_description = 'Cycle'

    def get_request_time(self, obj):
        return obj.request_time.astimezone(timezone.get_current_timezone()).strftime("%H:%M %p")

    get_request_time.short_description = 'Request Time'
    get_request_time.admin_order_field = 'request_time'

    def get_notes(self, obj):
        return obj.notes

    get_notes.short_description = 'Notes..................................'

    def get_additional_singers(self, obj):
        return ", ".join([f"{singer.first_name} {singer.last_name}" for singer in obj.additional_singers.all()])

    get_additional_singers.short_description = 'Helping Singers'

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

    def allows_filming(self, obj):
        return not obj.singer.no_image_upload

    allows_filming.short_description = 'Filming?'
    allows_filming.admin_order_field = 'allows_filming'
    allows_filming.boolean = True


@admin.register(Singer)
class SingerAdmin(admin.ModelAdmin):
    list_display = ['username', 'cy1_position', 'cy2_position', 'cy3_position',
                    'date_joined', 'is_superuser', 'no_image_upload']
