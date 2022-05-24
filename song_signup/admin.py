from datetime import datetime, timezone

import pytz
from django.contrib import admin
from django.contrib.auth.models import User
from django.utils import timezone

from .models import SongRequest, NoUpload, GroupSongRequest
from .views import _assign_song_priorities


def set_performed(modeladmin, request, queryset):
    for song in queryset:
        song.performance_time = datetime.now()
        song.priority = -1
        song.save()

    _assign_song_priorities()


def set_not_performed(modeladmin, request, queryset):
    for song in queryset:
        song.performance_time = None
        song.save()

    _assign_song_priorities()


set_performed.short_description = 'Mark song as performed'
set_performed.allowed_permissions = ['change']
set_not_performed.short_description = 'Mark song as not performed'
set_not_performed.allowed_permissions = ['change']


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


class GroupSongRequestAdmin(admin.ModelAdmin):
    list_display = (
        'song_name', 'musical', 'requested_by', 'get_request_time',
    )

    def get_request_time(self, obj):
        return obj.request_time.astimezone(timezone.get_current_timezone()).strftime("%H:%M %p")

    get_request_time.short_description = 'Request Time'
    get_request_time.admin_order_field = 'request_time'

    ordering = ['request_time']


class SongRequestAdmin(admin.ModelAdmin):
    list_display = (
        'priority', 'song_name', 'musical', 'singer', 'get_additional_singers', 'get_request_time',
        'get_performance_time', 'get_initial_signup'
    )
    list_filter = (NotYetPerformedFilter,)
    actions = [set_performed, set_not_performed]
    change_list_template = "admin/song_request_changelist.html"

    def has_delete_permission(self, request, obj=None):
        return False

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


class CustomUserInline(admin.StackedInline):
    model = NoUpload
    can_delete = False
    verbose_name_plural = 'Custom Users'


class CustomUserAdmin(admin.ModelAdmin):
    inlines = (CustomUserInline,)
    list_display = ['id', 'username', 'date_joined', 'is_superuser', 'no_image_upload']

    def no_image_upload(self, obj):
        return obj.noupload.no_image_upload

    no_image_upload.boolean = True


admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)

admin.site.register(SongRequest, SongRequestAdmin)
admin.site.register(GroupSongRequest, GroupSongRequestAdmin)
