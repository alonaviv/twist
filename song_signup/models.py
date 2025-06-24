import logging
import re
from django.dispatch import receiver
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.contrib.postgres.fields import CITextField
from django.core.exceptions import ValidationError
from django.db.models import (
    CASCADE,
    PROTECT,
    BooleanField,
    DateTimeField,
    ForeignKey,
    IntegerField,
    ManyToManyField,
    Model,
    TextField,
    URLField,
    CharField,
    OneToOneField,
    ImageField,
    JSONField,
)
from django.db.models.signals import m2m_changed
from twist.utils import format_commas
from django.utils import timezone
from titlecase import titlecase

from song_signup.managers import (
    DisneylandOrdering,
    SongRequestManager,
    SongSuggestionManager,
    GroupSongRequestManager,
)

SING_SKU = 'SING'
ATTN_SKU = 'ATTN'

logger = logging.getLogger(__name__)


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
    logged_in_customers = JSONField(default=list, blank=True)
    phone_number = CharField(max_length=15, null=True)

    class Meta:
        unique_together = ('order_id', 'event_sku', 'ticket_type')

    def __str__(self):
        return f"SKU: {self.event_sku}; Order #{self.order_id}; Type {'FREEBIE' if self.is_freebie else self.ticket_type}"


class Celebration(Model):
    """
    Represents a request to mention a celebration, from the ticket site
    """
    order_id = IntegerField()
    event_date = CharField(max_length=100, null=True)
    event_sku = CharField(max_length=20)
    customer_name = CharField(max_length=100)
    phone_number = CharField(max_length=15, null=True, blank=True)
    celebrating = TextField()


class Singer(AbstractUser):
    """
    Used for both audience and singer users. Can't create a base class due to django limitation with AbstractUser,
    And every other solution seemed too dangerous at this point. So leaving model as Singer, with a flag that can
    turn it into an audience member
    """
    no_image_upload = BooleanField(default=False)
    placeholder = BooleanField(default=False)
    ticket_order = ForeignKey(TicketOrder, related_name='singers', on_delete=PROTECT, null=True)
    is_audience = BooleanField(default=False)
    selfie = ImageField(upload_to='selfies/', blank=True, null=True)
    raffle_participant = BooleanField(default=False)
    raffle_winner = BooleanField(default=False)
    active_raffle_winner = BooleanField(default=False) # Show raffle winner animation

    @property
    def is_singer(self):
        return not self.is_audience or self.raffle_winner

    def save(self, *args, **kwargs):
        # Only validate on creation:
        if not self.pk and not self.is_superuser:
            if Singer.objects.filter(first_name=self.first_name, last_name=self.last_name).exists():
                raise AlreadyLoggedIn("The name that you're trying to login with already exists. "
                                      "Did you already login with us tonight? If so, check the box below.")

            if not self.ticket_order.is_freebie and self.ticket_order.singers.count() >= self.ticket_order.num_tickets:
                ticket_type = 'singer' if self.ticket_order.ticket_type == SING_SKU else 'audience'
                raise TicketsDepleted(f"Sorry, looks like all ticket holders for this order number already logged in. "
                                      f"Are you sure your ticket is of type '{ticket_type}'?")

        super().save(*args, **kwargs)

        if self.ticket_order and str(self) not in self.ticket_order.logged_in_customers:
            self.ticket_order.logged_in_customers.append(str(self))
            self.ticket_order.save()

    @property
    def all_songs(self):
        return (self.songs.all() | self.songs_as_partner.all()).distinct()

    @property
    def pending_songs(self):
        return self.all_songs.filter(performance_time__isnull=True).order_by('position')

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
        last_song = self.songs.all().filter(performance_time__isnull=False).order_by(
            'performance_time').last()

        if not last_song:
            return None

        return last_song.performance_time

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

    objects = GroupSongRequestManager()


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
    to_alon = CITextField(max_length=1000, null=True, blank=True)
    request_time = DateTimeField(auto_now_add=True)
    performance_time = DateTimeField(default=None, null=True, blank=True)
    singer = ForeignKey(settings.AUTH_USER_MODEL, on_delete=CASCADE, related_name='songs', null=True)
    partners = ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name='songs_as_partner')
    priority = IntegerField(null=True, blank=True)  # Priority in each singer's list
    position = IntegerField(null=True, blank=True)  # Absolute position in entire list
    placeholder = BooleanField(default=False)
    skipped = BooleanField(default=False)
    default_lyrics = BooleanField(default=False)
    found_music = BooleanField(default=False)
    spotlight = BooleanField(default=False)
    standby = BooleanField(default=False) # If song is out of the regular ordering, waiting to be spotlighted

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_song_name = titlecase(self.song_name)
        self._original_musical = titlecase(self.musical)

    def get_partners(self):
        return ", ".join([str(singer) for singer in self.partners.all()])

    # Code for oxford comma, if you decide to bring back multiple extra users
    # additional_singers = [str(singer) for singer in
    #                       song.additional_singers.all().exclude(pk=user.pk).order_by('first_name', 'last_name')]
    #
    # additional_singers_text = ', '.join(additional_singers[:-2] + [" and ".join(additional_singers[-2:])])

    get_partners.short_description = 'Partners'

    @property
    def was_performed(self):
        return bool(self.performance_time)

    @property
    def all_singers(self):
        return Singer.objects.filter(pk=self.singer.pk) | self.partners.all()

    def __str__(self):
        return f"Song request: {self.song_name} by {self.singer}"

    @property
    def wait_amount(self):
        # Returns 0 if song is the current song
        # Returns None if the song isn't scheduled yet
        if self.position:
            return int(self.position - SongRequest.objects.current_song().position)

    @property
    def basic_data(self):
        return {'id': self.id, 'name': self.song_name, 'singer': str(self.singer), 'wait_amount': self.wait_amount}

    @property
    def partners_str(self):
        return format_commas([singer.get_full_name() for singer in self.partners.all()])

    def save(self, *args, **kwargs):
        if not self.priority:
            self.priority = SongRequest.objects.next_priority(self)

        # Update the lyrics if the song was just added, or if its name or musical changed
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
        unique_together = ('song_name', 'musical', 'singer', 'position')
        ordering = ('position',)

    objects = SongRequestManager()


@receiver(m2m_changed, sender=SongRequest.partners.through)
def validate_partners_changed(sender, instance, action, **kwargs):
    if action == 'pre_add':
        for partner_id in kwargs['pk_set']:
            try:
                partner = Singer.objects.get(id=partner_id)
                if partner.is_superuser:
                    continue

                if partner.songs_as_partner.exclude(id=instance.id).count() > 0:
                    raise ValidationError(f"A person can be selected as partner once per night, "
                                         f"and {partner} already used his/her slot.")

            except Singer.DoesNotExist:
                raise ValidationError(f"Partner with id {partner_id} does not exist. "
                             f"Show this to Alon - it seems like a bug.. :(")


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

TRIVIA_CHOICES = ((1, 'A'), (2, 'B'), (3, 'C'), (4, 'D'))

class TriviaQuestion(Model):
    MAX_DISPLAY = 100
    WINNER_DISPLAY_DELAY = 15 # seconds

    question = TextField(max_length=72)
    image = ImageField(upload_to='trivia-questions/', blank=True, null=True)
    choiceA = TextField()
    choiceB = TextField()
    choiceC = TextField()
    choiceD = TextField()
    answer = IntegerField(choices=TRIVIA_CHOICES)
    is_active = BooleanField(default=False)
    notes = TextField(blank=True, null=True)

    def __str__(self):
        if len(self.question) < self.MAX_DISPLAY:
            return self.question

        return self.question[:self.MAX_DISPLAY] + "..."

    @property
    def winner(self):
        for response in self.responses.order_by('timestamp'):
            now = timezone.now()
            if response.is_correct and (now - response.timestamp).seconds >= self.WINNER_DISPLAY_DELAY:
                return response.user

    @property
    def answer_text(self):
        answer_mapping = {
            1: self.choiceA,
            2: self.choiceB,
            3: self.choiceC,
            4: self.choiceD,
        }
        return answer_mapping.get(self.answer, '')


class TriviaResponse(Model):
    user = ForeignKey(Singer, on_delete=CASCADE, related_name='trivia_responses')
    question = ForeignKey(TriviaQuestion, on_delete=CASCADE, related_name='responses')
    choice = IntegerField(choices=TRIVIA_CHOICES)
    timestamp = DateTimeField(auto_now_add=True)

    @property
    def is_correct(self):
        return self.question.answer is self.choice
