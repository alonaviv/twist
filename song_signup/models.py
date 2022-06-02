from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.contrib.postgres.fields import CITextField
from django.db.models import (
    Model, DateTimeField, ForeignKey, CASCADE, SET_NULL, ManyToManyField, IntegerField, BooleanField, signals,
    FloatField
)
from django.dispatch import receiver

from song_signup.managers import CycleManager, SongRequestManager


class Singer(AbstractUser):
    # Abbreviation: cy == cycle
    # There are three cycles in the evening. Each singer has a possible position in the lineup of each cycle
    cy1_position = IntegerField(blank=True, null=True)
    cy2_position = IntegerField(blank=True, null=True)
    cy3_position = IntegerField(blank=True, null=True)
    no_image_upload = BooleanField(default=False)

    @property
    def all_songs(self):
        return self.songs.all() | self.duet_songs.all()

    @property
    def pending_songs(self):
        return self.all_songs.filter(performance_time__isnull=True).order_by('position', 'priority')

    @property
    def next_song(self):
        return self.pending_songs.first()

    def add_to_cycle(self):
        """
        When a singer adds its first song request, the user is added to a single cycle.x
        If the first cycle isn't full - adds to the first cycle.
        If the first cycle is full, adds to the second cycle - copying one more singer from the first cycle after him.
        If the second cycle is full, adds to the third cycle.
        """
        # Superusers don't participate in this game
        if self.is_superuser or any([self.cy1_position, self.cy2_position, self.cy3_position]):
            return

        if not Singer.cycles.cy1_full():
            self.cy1_position = Singer.cycles.next_pos_cy1()
            self.save()
        elif not Singer.cycles.cy2_full():
            self.cy2_position = Singer.cycles.next_pos_cy2()
            self.save()
            Singer.cycles.clone_singer_cy1_to_cy2()
        else:
            self.cy3_position = Singer.cycles.next_pos_cy3()
            self.save()

    def __str__(self):
        return f'{self.first_name} {self.last_name}'

    class Meta:
        verbose_name = "Singer"
        verbose_name_plural = "Singers"

    cycles = CycleManager()


class GroupSongRequest(Model):
    song_name = CITextField(max_length=50, null=False, blank=False)
    musical = CITextField(max_length=50, null=False, blank=False)
    requested_by = ForeignKey(settings.AUTH_USER_MODEL, on_delete=CASCADE)
    request_time = DateTimeField(auto_now_add=True)


class SongRequest(Model):
    song_name = CITextField(max_length=50)
    musical = CITextField(max_length=50)
    request_time = DateTimeField(auto_now_add=True)
    performance_time = DateTimeField(default=None, null=True, blank=True)
    singer = ForeignKey(settings.AUTH_USER_MODEL, on_delete=CASCADE, related_name='songs')
    duet_partner = ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True,
                              related_name='duet_songs')
    additional_singers = ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name='songs_as_additional')
    priority = IntegerField(null=True, blank=True)  # Priority in each singer's list
    position = IntegerField(null=True, blank=True)  # Absolute position in entire list
    cycle = FloatField(null=True, blank=True)  # The cycle where song was scheduled

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
        return {'name': self.song_name, 'singer': str(self.singer), 'wait_amount': self.wait_amount}

    class Meta:
        unique_together = ('song_name', 'musical', 'singer')
        ordering = ('position',)

    objects = SongRequestManager()


# Add singer to cycle when his first request is created for the first time
@receiver(signals.post_save, sender=SongRequest)
def after_create_songrequest(sender, instance, created, *args, **kwargs):
    if created:
        instance.singer.add_to_cycle()
        instance.priority = SongRequest.objects.next_priority(instance)
        instance.save()


# Recalculate position of all requests on change
@receiver(signals.post_save, sender=SongRequest)
def after_save_songrequest(sender, instance, created, *args, **kwargs):
    signals.post_save.disconnect(after_save_songrequest, sender=sender)
    Singer.cycles.calculate_positions()
    signals.post_save.connect(after_save_songrequest, sender=sender)
