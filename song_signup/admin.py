from django.contrib import admin
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from .managers import LATE_SINGER_CYCLE
from .models import SongLyrics, SongRequest, Singer, GroupSongRequest, TicketOrder, CurrentGroupSong


def set_solo_performed(modeladmin, request, queryset):
    for song in queryset:
        song.performance_time = timezone.now()
        song.save()
        Singer.ordering.calculate_positions()


def set_solo_not_performed(modeladmin, request, queryset):
    for song in queryset:
        song.performance_time = None
        song.save()
        Singer.ordering.calculate_positions()


set_solo_performed.short_description = 'Mark song as performed'
set_solo_performed.allowed_permissions = ['change']
set_solo_not_performed.short_description = 'Mark song as not performed'
set_solo_not_performed.allowed_permissions = ['change']


def set_solo_skipped(modeladmin, request, queryset):
    for song in queryset:
        song.skipped = True
        song.save()


def set_solo_unskipped(modeladmin, request, queryset):
    for song in queryset:
        song.skipped = False
        song.save()


set_solo_skipped.short_description = 'Mark song as skipped'
set_solo_skipped.allowed_permissions = ['change']
set_solo_unskipped.short_description = 'Mark song as unskipped'
set_solo_unskipped.allowed_permissions = ['change']


def set_group_performed(modeladmin, request, queryset):
    if queryset.count() == 1:
        group_song = queryset.first()
        group_song.performance_time = timezone.now()
        group_song.save(get_lyrics=False)

        CurrentGroupSong.objects.all().delete()
        CurrentGroupSong.objects.create(group_song=group_song)


set_group_performed.short_description = 'Perform Group Song'
set_group_performed.allowed_permissions = ['change']


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
        'lyrics', 'song_name', 'musical', 'suggested_by', 'get_request_time', 'get_performance_time'
    )
    actions = [set_group_performed]
    change_list_template = "admin/group_song_request_changelist.html"

    def get_request_time(self, obj):
        return obj.request_time.astimezone(timezone.get_current_timezone()).strftime("%H:%M %p")

    get_request_time.short_description = 'Request Time'
    get_request_time.admin_order_field = 'request_time'

    def get_performance_time(self, obj):
        if obj.performance_time:
            return obj.performance_time.astimezone(timezone.get_current_timezone()).strftime("%H:%M %p")

        else:
            return None

    get_performance_time.short_description = 'Performance Time'
    get_performance_time.admin_order_field = 'performance_time'

    def lyrics(self, obj):
        return mark_safe(f'<a href="{reverse("group_lyrics", args=(obj.id,))}">Lyrics</a>')

    lyrics.short_description = "Lyrics"

    ordering = ['request_time']

    class Media:
        js = ["js/admin-reload.js"]


# @admin.register(SongSuggestion)
# class SongSuggestionAdmin(admin.ModelAdmin):
#     list_display = (
#         'song_name', 'musical', 'suggested_by', 'get_request_time', 'is_used',
#     )
#
#     def get_request_time(self, obj):
#         return obj.request_time.astimezone(timezone.get_current_timezone()).strftime("%H:%M %p")
#
#     get_request_time.short_description = 'Request Time'
#     get_request_time.admin_order_field = 'request_time'
#
#     ordering = ['request_time']


@admin.register(SongRequest)
class SongRequestAdmin(admin.ModelAdmin):
    list_display = (
        'position', 'get_skipped', 'lyrics', 'singer', 'song_name', 'musical', 'duet_partner', 'get_notes',
        'get_additional_singers', 'suggested_by', 'get_performance_time', 'get_request_time', 'get_initial_signup'
    )
    list_filter = (NotYetPerformedFilter,)
    actions = [set_solo_performed, set_solo_not_performed, set_solo_skipped, set_solo_unskipped]
    ordering = ['position']
    change_list_template = "admin/song_request_changelist.html"

    def get_skipped(self, obj):
        if obj.skipped:
            return mark_safe('<img src="/static/img/admin/forward.png" style="height: 16px;" />')
    get_skipped.short_description = 'Skipped'

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['new_singers_num'] = Singer.ordering.new_singers_num()

        group_song = CurrentGroupSong.objects.first()
        if group_song:
            extra_context['group_song'] = group_song.group_song.song_name

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

    def lyrics(self, obj):
        return mark_safe(f'<a href="{reverse("lyrics", args=(obj.id,))}">Lyrics</a>')

    lyrics.short_description = "Lyrics"

    class Media:
        js = ["js/admin-reload.js"]


@admin.register(Singer)
class SingerAdmin(admin.ModelAdmin):
    list_display = ['username', 'date_joined', 'is_active', 'no_image_upload', 'ticket_order']


@admin.register(SongLyrics)
class LyricsAdmin(admin.ModelAdmin):
    list_display = ['song_name', 'link', 'artist_name', 'url', 'song_request', 'group_song_request', 'default']

    def link(self, obj):
        return mark_safe(f'<a href="{reverse("lyrics_by_id", args=(obj.id,))}">Link</a>')

    link.short_description = "Link"


@admin.register(TicketOrder)
class OrdersAdmin(admin.ModelAdmin):
    list_display = ['order_id', 'event_name', 'event_sku', 'num_tickets', 'ticket_type', 'customer_name', 'get_singers']

    def get_singers(self, obj):
        singers = obj.singers.all()
        return format_html("<br>".join(
            [f"""<a href="{reverse('admin:song_signup_singer_change', args=[singer.pk])}">{singer}</a>""" for singer in
             singers]))

    get_singers.short_description = 'singers'


@admin.register(CurrentGroupSong)
class CurrentGroupSongAdmin(admin.ModelAdmin):
    list_display = ['get_song_name', 'get_musical', 'get_suggested_by']

    def get_song_name(self, obj):
        return obj.group_song.song_name

    get_song_name.short_description = "Song Name"

    def get_musical(self, obj):
        return obj.group_song.musical

    get_musical.short_description = "Musical"

    def get_suggested_by(self, obj):
        return obj.group_song.suggested_by

    get_suggested_by.short_description = "Suggested By"

    class Media:
        js = ["js/admin-reload.js"]
