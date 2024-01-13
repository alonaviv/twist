import datetime

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.contrib.postgres.fields import CITextField
from django.db.models import (
    Model, DateTimeField, ForeignKey, CASCADE, SET_NULL, ManyToManyField, IntegerField, BooleanField, signals,
    FloatField, TextField, URLField
)

from song_signup.managers import SongRequestManager, DisneylandOrdering, SongSuggestionManager


class Singer(AbstractUser):
    # Abbreviation: cy == cycle, lscy == late-singers cycle
    # There are three cycles in the evening. Each singer has a possible position in the lineup of each cycle
    cy1_position = IntegerField(blank=True, null=True)
    cy2_position = IntegerField(blank=True, null=True)
    lscy_position = IntegerField(blank=True, null=True)
    cy3_position = IntegerField(blank=True, null=True)
    no_image_upload = BooleanField(default=False)
    placeholder = BooleanField(default=False)

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
    suggested_by = ForeignKey(settings.AUTH_USER_MODEL, on_delete=CASCADE)
    request_time = DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        from song_signup.tasks import get_lyrics
        get_lyrics.delay(group_song_id = self.id)

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
    suggested_by = ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True,
                              related_name='suggested_songs_claimed')
    priority = IntegerField(null=True, blank=True)  # Priority in each singer's list
    position = IntegerField(null=True, blank=True)  # Absolute position in entire list
    cycle = FloatField(null=True, blank=True)  # The cycle where song was scheduled
    placeholder = BooleanField(default=False)

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

        super().save(*args, **kwargs)

        from song_signup.tasks import get_lyrics
        get_lyrics.delay(song_id = self.id)

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
        # Only one can be default
        if self.default:
            if self.song_request:
                self.song_request.lyrics.update(default=False)
            if self.group_song_request:
                self.group_song_request.lyrics.update(default=False)

        super().save(*args, **kwargs)
