from itertools import chain

from django.contrib.auth.models import UserManager
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Manager, Max
from flags.state import flag_enabled

FIRST_CYCLE_LEN = 10
CYCLE_1 = 1.0
CYCLE_2 = 2.0
LATE_SINGER_CYCLE = 2.5
CYCLE_3 = 3.0


class SongRequestManager(Manager):
    def reset_positions_and_cycles(self):
        self.all().update(position=None, cycle=None)

    def duets_partners_in_cycles(self, cycle):
        return [song.duet_partner for song in self.filter(cycle=cycle)]

    def next_priority(self, song_request):
        songs_of_singer = self.filter(singer=song_request.singer).exclude(pk=song_request.pk)
        return songs_of_singer.aggregate(Max('priority'))['priority__max'] + 1 if songs_of_singer else 1

    def current_song(self):
        return self.filter(performance_time__isnull=True, position__isnull=False, placeholder=False).first()

    def next_song(self):
        try:
            return self.filter(performance_time__isnull=True, position__isnull=False, placeholder=False)[1]
        except IndexError:
            return None


class ThreeCycleOrdering(UserManager):
    """
    Ordering manager that uses the 3 cycles algorithm.
    TODO: HAS An unfixed bug! It breaks on real db of default-ip-172-31-3-99-2022-07-10-095904-the-bug.psql
    """

    def calculate_positions(self):
        from song_signup.models import SongRequest
        SongRequest.objects.reset_positions_and_cycles()

        overall_position = 1
        for singer in self.cy1():
            # If singer performed duet in current cycle, she can have no more songs this cycle.
            if singer not in SongRequest.objects.duets_partners_in_cycles(CYCLE_1):
                if self._schedule_song(singer, overall_position, CYCLE_1):
                    overall_position += 1

        # In cycle 2, positions that are not filled yet get a placeholder
        for cy2_position in range(1, self.cy2().last().cy2_position + 1):
            placeholder_song, _ = self._get_placeholder_song(overall_position)
            # If singer doesn't exist in this cy2 slot, leave the placeholder
            try:
                singer = self.get(cy2_position=cy2_position, placeholder=False)
                placeholder_song.delete()
                # If singer performed duet in current cycle, she can have no more songs this cycle.
                if singer not in SongRequest.objects.duets_partners_in_cycles(CYCLE_2):
                    if self._schedule_song(singer, overall_position, CYCLE_2):
                        overall_position += 1

            except ObjectDoesNotExist:
                # If singer doesn't exist in this cy2 slot, leave the placeholder
                overall_position += 1

        for singer in self.lscy():
            # If singer performed duet in current cycle, she can have no more songs this cycle.
            if singer not in SongRequest.objects.duets_partners_in_cycles(LATE_SINGER_CYCLE):
                if self._schedule_song(singer, overall_position, LATE_SINGER_CYCLE):
                    overall_position += 1

        for singer in self.cy3():
            # If singer performed duet in current cycle, or in the late cycle,  she can have no more songs this cycle.
            if singer not in SongRequest.objects.duets_partners_in_cycles(LATE_SINGER_CYCLE) and \
                    singer not in SongRequest.objects.duets_partners_in_cycles(CYCLE_3):
                if self._schedule_song(singer, overall_position, CYCLE_3):
                    overall_position += 1

        # Repeat cycles LATE-SINGERS + 3 as long as there are unscheduled songs
        sub_3_cycle = 3.1
        while SongRequest.objects.filter(position__isnull=True, placeholder=False).count():
            for singer in chain(self.lscy(), self.cy3()):
                # If singer performed duet in current cycle, she can have no more songs this cycle.
                if singer in SongRequest.objects.duets_partners_in_cycles(sub_3_cycle):
                    continue
                if self._schedule_song(singer, overall_position, sub_3_cycle):
                    overall_position += 1
            sub_3_cycle = round(sub_3_cycle + 0.1, 1)

    def _get_placeholder_song(self, position):
        from song_signup.models import SongRequest
        placeholder_singer, _ = self.get_or_create(first_name='PLACEHOLDER-FOR-NEW-SINGER', placeholder=True)
        return SongRequest.objects.get_or_create(singer=placeholder_singer, position=position,
                                                 cycle=CYCLE_2, placeholder=True)

    @staticmethod
    def _schedule_song(singer, position, cycle):
        """
        Schedule the next song of the singer at given position and cycle.
        Return True iff song was scheduled
        """
        non_scheduled_song = singer.songs.filter(position__isnull=True). \
            order_by('priority').first()
        if non_scheduled_song:
            non_scheduled_song.position = position
            non_scheduled_song.cycle = cycle
            non_scheduled_song.save()
            return True

        return False

    def cy1(self):
        return self.filter(cy1_position__isnull=False).order_by('cy1_position')

    def cy2(self):
        return self.filter(cy2_position__isnull=False).order_by('cy2_position')

    def lscy(self):  # New singers cycle - for latecomers before cycle 3
        return self.filter(lscy_position__isnull=False).order_by('lscy_position')

    def cy3(self):
        return self.filter(cy3_position__isnull=False).order_by('cy3_position')

    def new_singers_cy2(self):
        return self.cy2().filter(cy1_position__isnull=True)

    def next_pos_cy1(self):
        return self.cy1().last().cy1_position + 1 if self.cy1() else 1

    def next_new_singer_pos_cy2(self):
        """
        Returns the next available position in cycle 2 for new singers (who aren't in cycle 1).
        These are placed in the odd positions in the cycle
        """
        if self.new_singers_cy2().exists():
            return self.new_singers_cy2().last().cy2_position + 2
        else:
            return 1

    def next_pos_lscy(self):
        """
        Returns the next available position in the LATE-SINGERS cycle (lscy)
        This is the (variable length) cycle for latecomers, before cycle 3 starts.
        """
        return self.lscy().last().lscy_position + 1 if self.lscy() else 1

    def cy1_full(self):
        return self.cy1().count() >= FIRST_CYCLE_LEN

    def cy2_full(self):
        """
        The second cycle is full once the last available spot for a new singer is filled.
        """
        return self.next_new_singer_pos_cy2() > FIRST_CYCLE_LEN * 2


class DisneylandOrdering(UserManager):
    """
    Ordering manager that uses the "Disneyland" algorithm. Once a singer has sung, she moves back to the end of the
    list. In order to allow latecomers to be able to sing, towards the end of the evening Shani will close the signup
    and we'll move to a mode in which only those who haven't sung yet get to sing.
    """
    def new_singers_num(self):
        return len([singer for singer in self.all() if singer.all_songs.exists()
                    and singer.last_performance_time is None])

    def calculate_positions(self):
        from song_signup.models import SongRequest
        SongRequest.objects.reset_positions_and_cycles()

        position = 1
        scheduled_songs = []
        duet_singers = set()
        for singer in self.singer_disneyland_ordering():
            # If singer has a duet earlier in the ordering, her primary song is skipped.
            # Once the duet is over, her position will be tied to the position of the primary singer (as they both
            # will have their last_performance_time updated , so she'll be rescheduled.
            if singer not in duet_singers:
                song_to_schedule = singer.songs.filter(performance_time__isnull=True).order_by('priority').first()
                if song_to_schedule:
                    song_to_schedule.position = position
                    song_to_schedule.save()
                    scheduled_songs.append(song_to_schedule)

                    if song_to_schedule.duet_partner:
                        duet_singers.add(song_to_schedule.duet_partner)

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
            return sorted(self.all(), key=lambda singer: singer.last_performance_time or singer.date_joined)
        else:
            all_singers = self.all()
            new_singers, old_singers = [], []
            for singer in all_singers:
                new_singers.append(singer) if singer.last_performance_time is None else old_singers.append(singer)

            return sorted(new_singers, key=lambda singer: singer.date_joined) + sorted(old_singers, key=lambda
                singer: singer.last_performance_time)
