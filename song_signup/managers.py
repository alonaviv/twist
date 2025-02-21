from itertools import chain

from django.contrib.auth.models import UserManager
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Manager, Max
from django.utils import timezone
from flags.state import flag_enabled


class SongSuggestionManager(Manager):
    def check_used_suggestions(self):
        """
        Go over the song suggestions, and mark which suggestions have been claimed by a singer
        """
        for suggestion in self.all():
            suggestion.check_if_used()


class SongRequestManager(Manager):
    def reset_positions(self):
        self.all().update(position=None)

    def next_priority(self, song_request):
        songs_of_singer = self.filter(singer=song_request.singer,
                                      request_time__lte=timezone.now()).exclude(pk=song_request.pk)
        return songs_of_singer.aggregate(Max('priority'))['priority__max'] + 1 if songs_of_singer else 1

    def current_song(self):
        return self.filter(performance_time__isnull=True, position__isnull=False, placeholder=False,
                           request_time__lte=timezone.now(), skipped=False).first()

    def next_song(self):
        try:
            return self.filter(performance_time__isnull=True, position__isnull=False,
                               placeholder=False, request_time__lte=timezone.now())[1]
        except IndexError:
            return None

class ScheduledGroupSongManager(Manager):
    """
    Since it's possible to slip and move a song to the top of the list by accident, thus interrupting a song in the
    middle, the current song is static, and is only moved along when explicitely using the function  - which will only
    be triggered by pressing the "NEXT SONG" button in the admin page.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._current_song = None

    def current_song(self):
        if not self._current_song:
            self._current_song = self.all().order_by('song_pos').first()
        return self._current_song

    def update_next_song(self):
        self._current_song = self.all().order_by('song_pos').first()

class ThreeCycleOrdering(UserManager):
    # Deprecated
    pass

class DisneylandOrdering(UserManager):
    """
    Ordering manager that uses the "Disneyland" algorithm. Once a singer has sung, she moves back to the end of the
    list. In order to allow latecomers to be able to sing, towards the end of the evening Shani will close the signup
    and we'll move to a mode in which only those who haven't sung yet get to sing.
    """
    def active_singers(self):
        """
        Return all logged-in singers that have at least one song request
        """
        return [singer for singer in self.filter(is_audience=False) if singer.is_active
                and singer.songs.filter(request_time__isnull=False).exists()]

    def new_singers_num(self):
        return len([singer for singer in self.active_singers() if singer.all_songs.exists()
                    and singer.last_performance_time is None])

    def calculate_positions(self):
        # Ignoring duets - only primary singer is relevant to the positioning.
        # Duet enforcement is now done in the Model - a singer can be a duetor in at most one song.
        from song_signup.models import SongRequest
        SongRequest.objects.reset_positions()

        position = 1
        scheduled_songs = []
        for singer in self.singer_disneyland_ordering():
            song_to_schedule = singer.songs.filter(performance_time__isnull=True,
                                                   request_time__lte=timezone.now()).order_by('priority').first()
            if song_to_schedule:
                song_to_schedule.position = position
                song_to_schedule.save()
                scheduled_songs.append(song_to_schedule)

                position += 1

    def singer_disneyland_ordering(self):
        """
        Returns the order of all current singers.
        First come, first served, and once a singer has sung his song, he's moved to the end of the line, after all the
        other singers in line.
        If the list is closed (Shani closes the signup), singers who haven't sung yet get precedence, sorted by
        joined time, and only then singers who have sung, sorted by their last performance time - that is, according
        to the order that they were in before. Basically, we're just taking the existing list and pulling the new
        singers ahead, without changing the internal ordering.
        """
        if flag_enabled('CAN_SIGNUP'):
            return sorted(self.active_singers(), key=lambda singer: singer.last_performance_time
                                                                    or singer.first_request_time)
        else:
            all_singers = self.active_singers()
            new_singers, old_singers = [], []
            for singer in all_singers:
                new_singers.append(singer) if singer.last_performance_time is None else old_singers.append(singer)

            return sorted(new_singers, key=lambda singer: singer.first_request_time) + sorted(old_singers, key=lambda
                singer: singer.last_performance_time)
