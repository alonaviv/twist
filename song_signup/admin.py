from django.contrib import admin
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.core.exceptions import ValidationError
from constance import config

from .models import (SongLyrics, SongRequest, Singer, GroupSongRequest, TicketOrder,
                     CurrentGroupSong, TriviaQuestion, TriviaResponse, Celebration
)
from .forms import SongRequestForm


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
        'display_id', 'lyrics', 'song_name', 'musical', 'suggested_by', 'type', 'default_lyrics', 'found_music',
        'get_request_time', 'get_performance_time'
    )
    list_filter = ('type',)
    list_editable = ('default_lyrics', 'found_music')
    actions = [prepare_group_song]
    change_list_template = "admin/group_song_request_changelist.html"

    def display_id(self, obj):
        return obj.id
    display_id.short_description = "#"

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        current_group_song = CurrentGroupSong.objects.first()
        if current_group_song:
            extra_context['group_song'] = current_group_song.group_song.song_name
            extra_context['is_active'] = current_group_song.is_active

        return super().changelist_view(request, extra_context=extra_context)

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
        'display_position', 'get_skipped', 'lyrics', 'get_singer', 'get_song', 'get_musical', 'get_partners', 'get_notes', 'get_to_alon',
        'default_lyrics', 'found_music', 'allows_filming', 'get_performance_time', 'get_request_time', 'get_initial_signup',
    )
    list_filter = (NotYetPerformedFilter,)
    list_editable = ('default_lyrics', 'found_music')
    actions = [set_solo_performed, set_solo_not_performed, set_solo_skipped, set_solo_unskipped]
    ordering = ['position']
    change_list_template = "admin/song_request_changelist.html"
    list_per_page = 500
    form = SongRequestForm

    def get_skipped(self, obj):
        if obj.skipped:
            return mark_safe('<img src="/static/img/admin/forward.png" style="height: 16px;" />')
    get_skipped.short_description = 'S'

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['new_singers_num'] = Singer.ordering.new_singers_num()
        extra_context['singers_num'] = len(Singer.ordering.active_singers())
        extra_context['group_songs_performed'] = GroupSongRequest.objects.num_performed()
        extra_context['group_songs_quota'] = config.EXPECTED_NUM_SONGS - len(
            Singer.ordering.active_singers()) - config.TARGET_REPEAT_SINGERS
        extra_context['solo_songs_quota'] = extra_context['singers_num'] + config.TARGET_REPEAT_SINGERS
        extra_context['solo_songs_performed'] = SongRequest.objects.num_performed()
        extra_context['total_songs_performed'] = extra_context['group_songs_performed'] + extra_context['solo_songs_performed']
        extra_context['total_songs_quota'] = config.EXPECTED_NUM_SONGS


        current_group_song = CurrentGroupSong.objects.first()
        if current_group_song:
            extra_context['group_song'] = current_group_song.group_song.song_name
            extra_context['is_active'] = current_group_song.is_active

        active_question = TriviaQuestion.objects.filter(is_active=True).first()
        if active_question:
            extra_context['trivia_question'] = active_question

        return super().changelist_view(request, extra_context=extra_context)

    def has_delete_permission(self, request, obj=None):
        return False

    def get_request_time(self, obj):
        return obj.request_time.astimezone(timezone.get_current_timezone()).strftime("%H:%M %p")

    get_request_time.short_description = 'Request Time'
    get_request_time.admin_order_field = 'request_time'

    def get_singer(self, obj):
        return format_html(
            '<div style="width: 100px; white-space: normal; word-wrap: break-word;">{}</div>',
            obj.singer
        )
    get_singer.short_description = 'Singer'

    def get_song(self, obj):
        return format_html(
            '<div style="width: 100px; white-space: normal; word-wrap: break-word;">{}</div>',
            obj.song_name
        )
    get_song.short_description = 'Song'

    def get_musical(self, obj):
        return format_html(
            '<div style="width: 70px; white-space: normal; word-wrap: break-word;">{}</div>',
            obj.musical
        )
    get_musical.short_description = 'Musical'

    def get_notes(self, obj):
        return format_html(
            '<div style="width: 120px; white-space: normal; word-wrap: break-word;">{}</div>',
            obj.notes or ''
        )
    get_notes.short_description = 'Notes'

    def get_to_alon(self, obj):
        return format_html(
            '<div style="width: 120px; white-space: normal; word-wrap: break-word;">{}</div>',
            obj.to_alon or ''
        )

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
                    'is_audience', 'selfie_preview', 'get_songs']
    list_filter =['is_audience']

    def selfie_preview(self, obj):
        if obj.selfie:
            return mark_safe(f'<img src="{obj.selfie.url}" width="100" height="100" />')
    selfie_preview.short_description = 'Selfie'

    def get_songs(self, obj):
        return [str(song.song_name) for song in obj.all_songs]
    get_songs.short_description = 'Songs'


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
                    'get_logged_in', 'phone_number', 'lead']
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
    change_list_template = "admin/trivia_question_changelist.html"

    def get_question(self, obj):
        return str(obj)
    get_question.short_description = "Question"

    def get_winner(self, obj):
        return obj.winner
    get_winner.short_description = "Winner"

    def get_answer(self, obj):
        return obj.get_answer_display()
    get_answer.short_description = "Answer #"

    def get_answer_text(self, obj):
        return obj.answer_text
    get_answer_text.short_description = "Answer"

    def image_preview(self, obj):
        if obj.image:
            return mark_safe(f'<img src="{obj.image.url}" width="50" height="50" />')
    image_preview.short_description = 'Image'

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        active_question = TriviaQuestion.objects.filter(is_active=True).first()
        if active_question:
            extra_context['active_question'] = active_question
            extra_context['winner'] = active_question.winner

        return super().changelist_view(request, extra_context=extra_context)

    class Media:
        js = ["js/admin-reload.js"]

from django.contrib import admin
from .models import TriviaResponse

class IsCorrectFilter(admin.SimpleListFilter):
    title = 'Right answer?'
    parameter_name = 'is_correct'

    def lookups(self, request, model_admin):
        return (
            ('correct', 'Correct Answers'),
            ('incorrect', 'Wrong Answers'),
        )

    def queryset(self, request, queryset):
        value = self.value()
        correct = []
        incorrect = []

        for response in queryset.all():
            if response.is_correct:
                correct.append(response.id)
            else:
                incorrect.append(response.id)
        if value == 'correct':
            return queryset.filter(pk__in=correct)
        elif value == 'incorrect':
            return queryset.filter(pk__in=incorrect)

@admin.register(TriviaResponse)
class TriviaResponseAdmin(admin.ModelAdmin):
    list_display = ['user', 'question', 'choice', 'get_timestamp', 'is_correct']
    list_filter = ['question', IsCorrectFilter]

    def is_correct(self, obj):
        return obj.is_correct
    is_correct.short_description = "Right answer?"
    is_correct.boolean = True

    def get_timestamp(self, obj):
        return obj.timestamp.astimezone(timezone.get_current_timezone()).strftime("%H:%M:%-S.%f")

    get_timestamp.short_description = 'Timestamp'
    get_timestamp.admin_order_field = 'timestamp'


@admin.register(Celebration)
class CelebrationAdmin(admin.ModelAdmin):
    list_display = ['order_id', 'event_date', 'customer_name', 'phone_number', 'celebrating', 'get_logged_in_customers']

    def get_logged_in_customers(self, obj):
        try:
            ticket = TicketOrder.objects.get(order_id=obj.order_id, event_sku=obj.event_sku)
            if ticket.logged_in_customers:
                return ', '.join(ticket.logged_in_customers)
            return "-"
        except TicketOrder.DoesNotExist:
            return "-"

    get_logged_in_customers.short_description = "Logged In"
