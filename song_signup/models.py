from django.contrib.auth.models import AbstractUser
from django.contrib.postgres.fields import CITextField
from django.core.exceptions import ValidationError
from django.db.models import (
    Model, DateTimeField, ForeignKey, CASCADE, SET_NULL, ManyToManyField, IntegerField, BooleanField, signals
)
from django.conf import settings
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
    def ordered_requests(self):
        """
        Returns singer's song requests in the order that they have been/will be performed.
        First lists the songs already performed, and then the unperformed songs according to
        their priority.
        """
        return self.songs.order_by('performance_time', 'priority')  # These fields are mutually exclusive

    @property
    def songs_per_cycle(self):
        """
        Return a tuple of the three possible cycle songs for the singer: (cycle1_song, cycle2_song, cycle3_song).
        If no song exists for a certain cycle, or the singer doesn't have a place in that cycle,
        returns None in its place.
        """
        ordered_requests_iter = iter(self.ordered_requests)

        return (
            self.cy1_position and next(ordered_requests_iter, None),
            self.cy2_position and next(ordered_requests_iter, None),
            self.cy3_position and next(ordered_requests_iter, None)
        )

    def add_to_cycle(self, song_request):
        """
        When a singer adds its first song request, the user is added to a single cycle.x
        If the first cycle isn't full - adds to the first cycle.
        If the first cycle is full, adds to the second cycle - copying one more singer from the first cycle after him.
        If the second cycle is full, adds to the third cycle.
        Returns True if singer was added to a cycle
        """
        # Superusers don't participate in this game
        if self.is_superuser or any([self.cy1_position, self.cy2_position, self.cy3_position]):
            return False

        if not Singer.cycles.cy1_full():
            self.cy1_position = Singer.cycles.next_pos_cy1()
            self.save()
        elif not Singer.cycles.cy2_full():
            self.cy2_position = Singer.cycles.next_pos_cy2()
            self.save()

            duet_partner = song_request.duet_partner
            if duet_partner and duet_partner.cy2_position is None:
                duet_partner.cy2_position = Singer.cycles.next_pos_cy2()
                duet_partner.save()

            Singer.cycles.clone_singer_cy1_to_cy2(song_request)
        else:
            self.cy3_position = Singer.cycles.next_pos_cy3()
            self.save()

        return True

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

    def save(self, *args, **kwargs):
        if self.performance_time is not None and self.priority is not None:
            raise ValidationError("Performance Time and Priority are mutually exclusive")

        if self.performance_time is None and self.priority is None:
            raise ValidationError("Must set either Performance Time or Priority")

        super().save(*args, **kwargs)

    # TODO: Put oxford comma logic here
    def get_additional_singers(self):
        return ", ".join([str(singer) for singer in self.additional_singers.all()])

    get_additional_singers.short_description = 'Additional Singers'

    @property
    def was_performed(self):
        return bool(self.performance_time)

    @property
    def is_first_request(self):
        return self.singer.songs.all().order_by('request_time').first() == self or \
                (self.duet_partner and self.duet_partner.songs.all().order_by('request_time').first())

    @property
    def all_singers(self):
        return Singer.objects.filter(pk=self.singer.pk) | self.additional_singers.all()

    def __str__(self):
        return f"Song request: {self.song_name} by {self.singer}"
    
    @property
    def basic_data(self):
        return {'name': self.song_name, 'singer': str(self.singer)}

    @property
    def cycle(self):
        """
        The cycle that this song is in, or None if it's not assigned to a cycle.
        """
        for cycle_num, song in enumerate(self.singer.songs_per_cycle):
            if self == song:
                return cycle_num + 1

        return None

    def calculate_position(self):
        """
        Calculate absolute position of the request in the entire set list of the evening
        """
        if self.cycle == 1:
            return self.singer.cy1_position
        elif self.cycle == 2:
            return self.singer.cy2_position + Singer.cycles.cy1().count()
        elif self.cycle == 3:
            return self.singer.cy3_position + Singer.cycles.cy1().count() + Singer.cycles.cy2().count()
        else:
            return None

    class Meta:
        unique_together = ('song_name', 'musical', 'singer')
        ordering = ('position',)

    objects = SongRequestManager()


# Add singer to cycle when his first request is created for the first time
@receiver(signals.post_save, sender=SongRequest)
def after_create_songrequest(sender, instance, created, *args, **kwargs):
    if created:
        added = instance.singer.add_to_cycle(instance)
        if added and instance.duet_partner:
            instance.duet_partner.add_to_cycle(instance)


# Recalculate position of all requests on change
@receiver(signals.post_save, sender=SongRequest)
def after_save_songrequest(sender, instance, created, *args, **kwargs):
    signals.post_save.disconnect(after_save_songrequest, sender=sender)
    SongRequest.objects.calculate_positions()
    signals.post_save.connect(after_save_songrequest, sender=sender)
