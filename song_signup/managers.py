from itertools import chain

from django.contrib.auth.models import UserManager
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Manager, Max
from django.utils import timezone
from flags.state import flag_enabled
from django.db.models import Count
from constance import config


class SongSuggestionManager(Manager):
    def check_used_suggestions(self):
        """
        Go over the song suggestions, and mark which suggestions have been claimed by a singer
        """
        for suggestion in self.all():
            suggestion.check_if_used()
        # Recalculate positions and People's Choice when songs become used/unused
        self.recalculate_positions()

    def recalculate_positions(self):
        """
        Assign positions to suggestions based on votes/time while keeping 'used' suggestions at their existing positions.
        """
        suggestions = list(
            self.annotate(num_votes=Count('voters')).order_by('-num_votes', '-request_time')
        )

        # If a used suggestion has a position set, keep it; otherwise we'll assign it below
        occupied = {s.position for s in suggestions if s.is_used and s.position}

        pos = 1
        for s in suggestions:
            if s.is_used and s.position:
                # Skip pinned used items
                continue
            # Find next free position
            while pos in occupied:
                pos += 1

            s.position = pos
            s.save()
            pos += 1
        
        self.recalculate_peoples_choice()

    def recalculate_peoples_choice(self):
        """
        Recalculate which songs are People's Choice.
        People's Choice = top N unused songs with at least one vote, plus any used songs
        that are in those top N positions. Used songs expand the box but don't count towards the limit.
        """
        num_peoples_choice = config.NUM_PEOPLES_CHOICE
        
        # First, reset all to False
        self.all().update(is_peoples_choice=False)
        
        # Get all suggestions ordered by position (refresh from DB to ensure positions are current)
        all_suggestions = list(
            self.annotate(num_votes=Count('voters'))
            .filter(num_votes__gt=0, position__isnull=False)
            .order_by('position', '-request_time')
        )
        
        # Find the top N unused songs
        unused_suggestions = [s for s in all_suggestions if not s.is_used]
        top_n_unused = unused_suggestions[:num_peoples_choice]
        
        if not top_n_unused:
            return
        
        # Find the maximum position among the top N unused songs
        max_position = max(s.position for s in top_n_unused)
        
        # Mark all songs with position <= max_position as People's Choice
        # This includes both unused songs and used songs in those positions
        for suggestion in all_suggestions:
            if suggestion.position <= max_position:
                suggestion.is_peoples_choice = True
                suggestion.save()


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
                               placeholder=False, request_time__lte=timezone.now(), skipped=False)[1]
        except IndexError:
            return None

    def num_performed(self):
        return self.filter(performance_time__isnull=False).count()

    def remove_spotlight(self):
        for song in self.all():
            if song.spotlight:
                song.performance_time = timezone.now() # If a song was in spotlight, set performance time to when ended
                song.standby = False

            song.spotlight = False
            song.save()

        from song_signup.models import Singer
        Singer.ordering.calculate_positions()

    def set_spotlight(self, song_request):
        self.remove_spotlight()
        song_request.spotlight = True
        song_request.save()

    def get_spotlight(self):
        return self.filter(spotlight=True).first()


class GroupSongRequestManager(Manager):
    def num_performed(self):
        return int(self.filter(performance_time__isnull=False).count())

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

    def active_raffle_winners(self):
        """
        Return all logged-in raffle winners that already added their song
        """
        return [singer for singer in self.filter(is_audience=True, raffle_winner=True) if singer.is_active
                and singer.songs.filter(request_time__isnull=False).exists()]

    def active_raffle_participants(self):
        """
        Return all logged-in raffle participants that didn't win yet
        """
        return [singer for singer in self.filter(is_audience=True, raffle_participant=True, raffle_winner=False)
                if singer.is_active]

    def new_singers_num(self):
        return len([singer for singer in self.active_singers() if singer.all_songs.exists()
                    and singer.last_performance_time is None])

    def new_raffle_winners_num(self):
        return len([singer for singer in self.active_raffle_winners() if singer.all_songs.exists()
                    and singer.last_performance_time is None])

    def calculate_positions(self):
        # Ignoring duets - only primary singer is relevant to the positioning.
        # Duet enforcement is now done in the Model - a singer can be a duetor in at most one song.
        from song_signup.models import SongRequest
        SongRequest.objects.reset_positions()

        position = 1
        scheduled_songs = []
        for singer in self.singer_disneyland_ordering():
            song_to_schedule = singer.songs.filter(performance_time__isnull=True, standby=False,
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
