from django.contrib import admin, messages
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.core.exceptions import ValidationError
from constance import config

from .models import (SongLyrics, SongRequest, Singer, GroupSongRequest, TicketOrder,
                     CurrentGroupSong, TriviaQuestion, TriviaResponse, Celebration, FilmingOptOut
)
from .forms import SongRequestForm
from .tasks import get_lyrics

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

def spotlight(modeladmin, request, queryset):
    if queryset.count() != 1:
        messages.error(request, "You can only spotlight a single song")
        return

    song = queryset.first()
    SongRequest.objects.set_spotlight(song)

spotlight.short_description = "Spotlight this song"
spotlight.allowed_permissions = ['change']

def set_standby(modeladmin, request, queryset):
    for song in queryset:
        song.standby = True
        song.save()
    Singer.ordering.calculate_positions()

set_standby.short_description = "Move to standby"
set_standby.allowed_permissions = ['change']

def unset_standby(modeladmin, request, queryset):
    for song in queryset:
        song.standby = False
        song.save()
    Singer.ordering.calculate_positions()

unset_standby.short_description = "Undo standby"
unset_standby.allowed_permissions = ['change']


def force_lyrics_refresh(modeladmin, request, queryset):
    for song in queryset:
        get_lyrics.delay(song_id=song.id)

force_lyrics_refresh.short_description = "Force lyrics refresh"
force_lyrics_refresh.allowed_permissions = ['change']

def force_group_lyrics_refresh(modeladmin, request, queryset):
    for song in queryset:
        get_lyrics.delay(group_song_id=song.id)

force_group_lyrics_refresh.short_description = "Force lyrics refresh"
force_group_lyrics_refresh.allowed_permissions = ['change']

def prepare_group_song(modeladmin, request, queryset):
    if queryset.count() == 1:
        group_song = queryset.first()
        CurrentGroupSong.objects.all().delete()
        CurrentGroupSong.objects.create(group_song=group_song)


prepare_group_song.short_description = 'Prepare group song (Need to actually start it with button above)'
prepare_group_song.allowed_permissions = ['change']


def activate_question(modeladmin, request, queryset):
    if queryset.count() == 1:
        trivia_question = queryset.first()
        trivia_question.is_active = True
        trivia_question.save()

activate_question.short_description = 'Activate Trivia Question'
activate_question.allowed_permissions = ['change']

class NotYetPerformedFilter(admin.SimpleListFilter):
    title = 'Songs to Display'
    parameter_name = 'already_performed'

    def lookups(self, request, model_admin):
        return (
            ('not_performed', 'Not Performed'),
            ('all', 'All'),
        )

    def queryset(self, request, queryset):
        value = self.value()
        if value == 'all':
            return queryset
        return queryset.filter(performance_time__isnull=True)

    def choices(self, changelist):
        for lookup, title in self.lookup_choices:
            yield {
                'selected': self.value() == lookup if self.value() is not None else lookup == 'not_performed',
                'query_string': changelist.get_query_string({self.parameter_name: lookup}),
                'display': title,
            }


@admin.register(SongRequest)
class SongRequestAdmin(admin.ModelAdmin):
    form = SongRequestForm
    list_display = ['display_position', 'song_name', 'musical', 'singer', 'get_partners', 'get_initial_signup',
                    'was_performed', 'get_performance_time', 'skipped', 'standby', 'spotlight', 'is_peoples_choice',
                    'allows_filming', 'lyrics', 'default_lyrics', 'get_to_alon']
    list_filter = [NotYetPerformedFilter, 'skipped', 'standby', 'spotlight', 'is_peoples_choice']
    search_fields = ['song_name', 'musical', 'singer__first_name', 'singer__last_name']
    actions = [set_solo_performed, set_solo_not_performed, set_solo_skipped, set_solo_unskipped, spotlight,
              set_standby, unset_standby, force_lyrics_refresh]
    list_per_page = 500

    def get_to_alon(self, obj):
        return obj.to_alon
    get_to_alon.short_description = 'To Alon'

    def get_partners(self, obj):
        partners = ", ".join([f"{singer.first_name} {singer.last_name}" for singer in obj.partners.all()])
        return format_html(
            '<div style="width: 100px; white-space: normal; word-wrap: break-word;">{}</div>',
            partners or ''
        )

    get_partners.short_description = 'Partners'

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

    def default_lyrics(self, obj):
        return obj.has_default_lyrics

    default_lyrics.short_description = "Set Default Lyrics"
    default_lyrics.admin_order_field = "has_default_lyrics"

    def display_position(self, obj):
        return obj.position
    display_position.short_description = "#"

    class Media:
        js = ["js/admin-reload.js"]


@admin.register(Singer)
class SingerAdmin(admin.ModelAdmin):
    list_display = ['username', 'date_joined', 'is_active', 'no_image_upload', 'ticket_order',
                    'is_audience', 'selfie_preview', 'get_songs', 'raffle_winner', 'raffle_participant']
    list_filter = ['is_audience', 'no_image_upload']

    def selfie_preview(self, obj):
        if obj.selfie:
            return mark_safe(f'<img src="{obj.selfie.url}" width="100" height="100" />')
    selfie_preview.short_description = 'Selfie'

    def get_songs(self, obj):
        return [str(song.song_name) for song in obj.all_songs]
    get_songs.short_description = 'Songs'


@admin.register(FilmingOptOut)
class FilmingOptOutAdmin(admin.ModelAdmin):
    """
    Everyone who ever checked "Don't post videos of me", with their photo, grouped by event.
    Filled automatically on every DB reset. Open this while editing videos.
    """
    list_display = ['photo_preview', 'full_name', 'ticket_type', 'event_name', 'phone_number', 'recorded_at']
    list_filter = ['event_name', 'is_audience']
    search_fields = ['full_name', 'event_name', 'phone_number']
    list_per_page = 200
    readonly_fields = ['photo_preview', 'recorded_at']
    fields = ['full_name', 'is_audience', 'event_name', 'event_sku', 'phone_number', 'photo', 'photo_preview',
              'recorded_at']

    def photo_preview(self, obj):
        if obj.photo:
            return mark_safe(f'<a href="{obj.photo.url}" target="_blank">'
                             f'<img src="{obj.photo.url}" style="height: 200px; width: auto;" /></a>')
        return 'No photo'
    photo_preview.short_description = 'Photo'

    def ticket_type(self, obj):
        return 'Audience' if obj.is_audience else 'Singer'
    ticket_type.short_description = 'Ticket'
    ticket_type.admin_order_field = 'is_audience'


@admin.register(SongLyrics)
class LyricsAdmin(admin.ModelAdmin):
    list_display = ['song_name', 'artist_name', 'default', 'url', 'link', 'song_request', 'group_song_request']
    list_filter = ('default', 'song_name')
    list_per_page = 500

    def link(self, obj):
        return mark_safe(f'<a href="{reverse("lyrics_by_id", args=(obj.id,))}">Link</a>')

    link.short_description = "Link"


@admin.register(TicketOrder)
class OrdersAdmin(admin.ModelAdmin):
    list_display = ['order_id', 'event_name', 'event_sku', 'num_tickets', 'ticket_type', 'customer_name',
                    'get_logged_in', 'phone_number']
    list_filter = ['event_sku']

    def get_logged_in(self, obj):
        return ', '.join(obj.logged_in_customers)
    get_logged_in.short_description = "Logged In"


@admin.register(CurrentGroupSong)
class CurrentGroupSongAdmin(admin.ModelAdmin):
    list_display = ['get_song_name', 'get_musical', 'get_suggested_by', 'is_active']

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


@admin.register(TriviaQuestion)
class TriviaQuestionAdmin(admin.ModelAdmin):
    list_display = ['id', 'get_question', 'image_preview', 'get_answer_text', 'get_answer', 'notes', 'get_winner']
    actions = [activate_question]

    def get_question(self, obj):
        return str(obj)
    get_question.short_description = 'Question'

    def image_preview(self, obj):
        if obj.image:
            return mark_safe(f'<img src="{obj.image.url}" width="100" />')
    image_preview.short_description = 'Image'

    def get_answer_text(self, obj):
        return obj.answer_text
    get_answer_text.short_description = 'Answer Text'

    def get_answer(self, obj):
        return obj.get_answer_display()
    get_answer.short_description = 'Answer'

    def get_winner(self, obj):
        winner = obj.winner
        return str(winner) if winner else None
    get_winner.short_description = 'Winner'


@admin.register(TriviaResponse)
class TriviaResponseAdmin(admin.ModelAdmin):
    list_display = ['user', 'question', 'choice', 'timestamp']


@admin.register(Celebration)
class CelebrationAdmin(admin.ModelAdmin):
    list_display = ['customer_name', 'event_date', 'event_sku', 'celebrating', 'phone_number']
    list_filter = ['event_sku']
