import datetime
import re

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.contrib.postgres.fields import CITextField
from django.db.models import (
    CASCADE,
    SET_NULL,
    PROTECT,
    BooleanField,
    DateTimeField,
    FloatField,
    ForeignKey,
    IntegerField,
    ManyToManyField,
    Model,
    TextField,
    URLField,
    CharField,
    OneToOneField,
    DecimalField
)
from django.utils import timezone
from titlecase import titlecase

from song_signup.managers import (
    DisneylandOrdering,
    SongRequestManager,
    SongSuggestionManager,
)

SING_SKU = 'SING'
ATTN_SKU = 'ATTN'


class TicketsDepleted(Exception):
    pass


class AlreadyLoggedIn(Exception):
    pass


class TicketOrder(Model):
    """
    Represents the group of tickets of the same type within a Lineapp order
    """
    order_id = IntegerField()
    event_sku = CharField(max_length=20)
    event_name = CharField(max_length=100, null=True)
    num_tickets = IntegerField()
    ticket_type = CharField(max_length=20, choices=[(SING_SKU, 'Singer'), (ATTN_SKU, 'Audience')])
    customer_name = CharField(max_length=100)
    is_freebie = BooleanField(default=False)  # Ticket group for giving singer access to those without singer tickets

    class Meta:
        unique_together = ('order_id', 'event_sku', 'ticket_type')

    def __str__(self):
        return f"SKU: {self.event_sku}; Order #{self.order_id}; Type {'FREEBIE' if self.is_freebie else self.ticket_type}"


class Singer(AbstractUser):
    # Abbreviation: cy == cycle, lscy == late-singers cycle
    # There are three cycles in the evening. Each singer has a possible position in the lineup of each cycle
    cy1_position = IntegerField(blank=True, null=True)
    cy2_position = IntegerField(blank=True, null=True)
    lscy_position = IntegerField(blank=True, null=True)
    cy3_position = IntegerField(blank=True, null=True)
    no_image_upload = BooleanField(default=False)
    placeholder = BooleanField(default=False)
    ticket_order = ForeignKey(TicketOrder, related_name='singers', on_delete=PROTECT, null=True)

    def save(self, *args, **kwargs):
        # Only validate on creation:
        if not self.pk and not self.is_superuser:
            if self.ticket_order is None:
                raise ValueError("You must have a ticket order number in order to sign in")

            if Singer.objects.filter(first_name=self.first_name, last_name=self.last_name).exists():
                raise AlreadyLoggedIn("The name that you're trying to login with already exists."
                                      "Did you already login with us tonight? If so, check the box below.")

            if not self.ticket_order.is_freebie and self.ticket_order.singers.count() >= self.ticket_order.num_tickets:
                ticket_type = 'singer' if self.ticket_order.ticket_type == SING_SKU else 'audience'
                raise TicketsDepleted(f"Sorry, looks like all ticket holders for this order number already logged in. "
                                      f"Are you sure your ticket is of type '{ticket_type}'?")

        super().save(*args, **kwargs)

    @property
    def all_songs(self):
        return self.songs.all() | self.duet_songs.all()

    @property
    def pending_songs(self):
        return self.all_songs.filter(performance_time__isnull=True).order_by('priority')

    @property
    def next_song(self):
        return self.pending_songs.first()

    @property
    def first_request_time(self):
        first_song_request = self.songs.order_by('request_time').first()

        if first_song_request:
            return first_song_request.request_time

    @property
    def last_performance_time(self):
        last_song = self.all_songs.filter(performance_time__isnull=False).order_by(
            'performance_time').last()

        if not last_song:
            return None

        performance_time = last_song.performance_time

        # For duets, set the secondary singer to be one second later,
        # so she will be after the primary singer in the list
        if last_song in self.duet_songs.all():
            performance_time += datetime.timedelta(seconds=1)

        return performance_time

    def _add_to_disneyland_lineup(self):
        """
        Function to add a new singer to the list when using the "Disneyland" algorithm.
        """
        pass

    def _add_to_cycle(self):
        """
        Function to add a new singer to the list when using the "3 cycles" algorithm.
        When a singer adds its first song request, the user is added to cycles 1 2 and 3, skipping cycles that are
        already full.
        Cycle 1 - First come, first served for the first 10
        Cycle 2 - Singers of cycle 1 repeat, with new singers placed between them
        (new singer in place 1, old singer in place 1, and so forth until 20)
        Cycle LATE-SINGERS-SLOT - Only late new singers, that aren't in cycle 2
        Cycle 3 - Repeat cycle 2

        If cycle 3 is done - repeats cycle LATE-SINGERS + Cycle 3 again. (Happens in calculate_positions)
        """
        # Superusers don't participate in this game
        if self.is_superuser or any([self.cy1_position, self.cy2_position, self.cy3_position]) or self.placeholder:
            return
        if not Singer.ordering.cy1_full():
            self.cy1_position = Singer.ordering.next_pos_cy1()
            self.cy2_position = self.cy1_position * 2  # Cycle one singers take the even places of cycle 2
            self.cy3_position = self.cy2_position
            self.save()
        elif not Singer.ordering.cy2_full():
            self.cy2_position = Singer.ordering.next_new_singer_pos_cy2()
            self.cy3_position = self.cy2_position
        else:
            self.lscy_position = Singer.ordering.next_pos_lscy()

        self.save()

    def add_to_lineup(self):
        """
        Can choose which algorithm to use here
        """
        self._add_to_disneyland_lineup()

    def __str__(self):
        return f'{self.first_name} {self.last_name}'

    class Meta:
        verbose_name = "Singer"
        verbose_name_plural = "Singers"

    ordering = DisneylandOrdering()


class GroupSongRequest(Model):
    song_name = CITextField(max_length=50, null=False, blank=False)
    musical = CITextField(max_length=50, null=False, blank=False)
    suggested_by = CITextField(max_length=50, null=True, default='-')
    request_time = DateTimeField(auto_now_add=True)
    performance_time = DateTimeField(default=None, null=True, blank=True)
    type = CITextField(max_length=20, choices=[('USER', 'USER'), ('REGULAR', 'REGULAR'),
                                               ('DRINKING-SONG', 'DRINKING-SONG'),
                                               ('OPENING', 'OPENING'), ('CLOSING', 'CLOSING')],
                       default='USER')
    default_lyrics = BooleanField(default=False)
    found_music = BooleanField(default=False)

    def save(self, get_lyrics=True, *args, **kwargs):
        self.song_name = titlecase(self.song_name)
        self.musical = titlecase(self.musical)
        super().save(*args, **kwargs)

        if get_lyrics:
            from song_signup.tasks import get_lyrics
            get_lyrics.delay(group_song_id=self.id)

    @property
    def basic_data(self):
        return {'id': self.id, 'name': self.song_name, 'singer': "GROUP SONG", 'wait_amount': None}


class CurrentGroupSong(Model):
    """
    Singleton model to get the group song currently being performed.
    """
    group_song = OneToOneField(GroupSongRequest, on_delete=CASCADE, null=True, blank=True)
    is_active = BooleanField(default=False)

    def save(self, *args, **kwargs):
        if CurrentGroupSong.objects.exists() and not self.pk:
            return
        return super().save(*args, **kwargs)

    @classmethod
    def start_song(cls):
        instance = cls.objects.all().first()

        if instance:
            instance.is_active = True
            instance.save()
            instance.group_song.performance_time = timezone.now()
            instance.group_song.save(get_lyrics=False)

    @classmethod
    def end_song(cls):
        instance = cls.objects.all().first()
        if instance:
            instance.delete()


class SongSuggestion(Model):
    song_name = CITextField(max_length=50)
    musical = CITextField(max_length=50)
    suggested_by = ForeignKey(settings.AUTH_USER_MODEL, on_delete=CASCADE, related_name='songs_suggested')
    request_time = DateTimeField(auto_now_add=True)
    is_used = BooleanField(default=False)

    def check_if_used(self):
        try:
            SongRequest.objects.get(song_name=self.song_name, musical=self.musical)
            self.is_used = True

        except SongRequest.DoesNotExist:
            self.is_used = False

        self.save()

    objects = SongSuggestionManager()


class SongRequest(Model):
    song_name = CITextField(max_length=50)
    musical = CITextField(max_length=50)
    notes = CITextField(max_length=1000, null=True, blank=True)
    request_time = DateTimeField(auto_now_add=True)
    performance_time = DateTimeField(default=None, null=True, blank=True)
    singer = ForeignKey(settings.AUTH_USER_MODEL, on_delete=CASCADE, related_name='songs', null=True)
    duet_partner = ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True,
                              related_name='duet_songs')
    additional_singers = ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name='songs_as_additional')
    priority = IntegerField(null=True, blank=True)  # Priority in each singer's list
    position = DecimalField(null=True, blank=True,decimal_places=1, max_digits=5)  # Absolute position in entire list
    cycle = FloatField(null=True, blank=True)  # The cycle where song was scheduled
    placeholder = BooleanField(default=False)
    skipped = BooleanField(default=False)
    default_lyrics = BooleanField(default=False)
    found_music = BooleanField(default=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_song_name = titlecase(self.song_name)
        self._original_musical = titlecase(self.musical)

    def get_additional_singers(self):
        return ", ".join([str(singer) for singer in self.additional_singers.all()])

    # Code for oxford comma, if you decide to bring back multiple extra users
    # additional_singers = [str(singer) for singer in
    #                       song.additional_singers.all().exclude(pk=user.pk).order_by('first_name', 'last_name')]
    #
    # additional_singers_text = ', '.join(additional_singers[:-2] + [" and ".join(additional_singers[-2:])])

    get_additional_singers.short_description = 'Additional Singers'

    @property
    def was_performed(self):
        return bool(self.performance_time)

    @property
    def all_singers(self):
        return Singer.objects.filter(pk=self.singer.pk) | self.additional_singers.all()

    def __str__(self):
        return f"Song request: {self.song_name} by {self.singer}"

    @property
    def wait_amount(self):
        if self.position:
            return int(self.position - SongRequest.objects.current_song().position)

    @property
    def basic_data(self):
        return {'id': self.id, 'name': self.song_name, 'singer': str(self.singer), 'wait_amount': self.wait_amount}

    def save(self, *args, **kwargs):
        self.singer.add_to_lineup()  # Only used in the 3 cycles algo

        if not self.priority:
            self.priority = SongRequest.objects.next_priority(self)

        # Update the lyxrics if the song was just added, or if its name or musical changed
        fetch_lyrics = False
        if (
                self.id is None
                or self._original_song_name != self.song_name
                or self._original_musical != self.musical
        ):
            fetch_lyrics = True

        self.song_name = titlecase(self.song_name)
        self.musical = titlecase(self.musical)
        super().save(*args, **kwargs)

        if fetch_lyrics:
            from song_signup.tasks import get_lyrics

            get_lyrics.delay(song_id=self.id)
            self._original_song_name = self.song_name
            self._original_musical = self.musical

    class Meta:
        unique_together = ('song_name', 'musical', 'singer', 'cycle', 'position')
        ordering = ('position',)

    objects = SongRequestManager()


class SongLyrics(Model):
    song_name = TextField()
    artist_name = TextField()
    lyrics = TextField()
    url = URLField(null=True, blank=True)
    song_request = ForeignKey(SongRequest, on_delete=CASCADE, related_name='lyrics', null=True, blank=True)
    group_song_request = ForeignKey(GroupSongRequest, on_delete=CASCADE, related_name='lyrics', null=True, blank=True)
    default = BooleanField(default=False)

    class Meta:
        verbose_name_plural = "Song lyrics"

    def save(self, *args, **kwargs):
        # Limit consecutive newlines to three
        self.lyrics = re.sub(r'\n{4,}', '\n' * 3, self.lyrics)

        # Only one can be default
        if self.default:
            if self.song_request:
                self.song_request.lyrics.update(default=False)
            if self.group_song_request:
                self.group_song_request.lyrics.update(default=False)

        super().save(*args, **kwargs)
