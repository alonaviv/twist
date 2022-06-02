import itertools

from django.contrib.auth.models import UserManager
from django.db.models import Manager, Max
from flags.state import disable_flag, flag_enabled

FIRST_CYCLE_LEN = 10


class SongRequestManager(Manager):
    def reset_positions_and_cycles(self):
        self.all().update(position=None, cycle=None)

    def duets_partners_in_cycles(self, cycle):
        return [song.duet_partner for song in self.filter(cycle=cycle)]

    def next_priority(self, song_request):
        songs_of_singer = self.filter(singer=song_request.singer).exclude(pk=song_request.pk)
        return songs_of_singer.aggregate(Max('priority'))['priority__max'] + 1 if songs_of_singer else 1

    def current_song(self):
        return self.filter(performance_time__isnull=True, position__isnull=False).first()

    def next_song(self):
        try:
            return self.filter(performance_time__isnull=True, position__isnull=False)[1]
        except IndexError:
            return None


class CycleManager(UserManager):
    def calculate_positions(self):
        from song_signup.models import SongRequest
        SongRequest.objects.reset_positions_and_cycles()
        current_position = 1

        for singer, cycle in self.all_cycles():
            # If singer performed duet in current cycle, she can have no more songs this cycle.
            if singer in SongRequest.objects.duets_partners_in_cycles(cycle):
                continue

            non_scheduled_song = singer.songs.filter(position__isnull=True). \
                order_by('priority').first()

            if non_scheduled_song:
                non_scheduled_song.position = current_position
                non_scheduled_song.cycle = cycle
                non_scheduled_song.save()

            current_position += 1

    def cy1(self):
        return self.filter(cy1_position__isnull=False).order_by('cy1_position')

    def cy2(self):
        return self.filter(cy2_position__isnull=False).order_by('cy2_position')

    def cy3(self):
        return self.filter(cy3_position__isnull=False).order_by('cy3_position')

    def all_cycles(self):
        # On first cycle, as people show up, loop around if cycle isn't full.
        counter = 1
        sub_cycle = 0

        while True:
            for singer in self.cy1():
                if counter > FIRST_CYCLE_LEN:
                    break
                yield singer, 1 + (sub_cycle/10)  # Cycle #1 plus sub-cycle (1.0, 1.1, 1.2..)
                counter += 1
            else:
                sub_cycle += 1
                continue
            break

        for singer in self.cy2():
            yield singer, 2

        for singer in self.cy3():
            yield singer, 3

    def next_pos_cy1(self):
        return self.cy1().last().cy1_position + 1 if self.cy1() else 1

    def next_pos_cy2(self):
        return self.cy2().last().cy2_position + 1 if self.cy2() else 1

    def next_pos_cy3(self):
        return self.cy3().last().cy3_position + 1 if self.cy3() else 1

    # TODO: Memoize this in some way. It'll never change once it's True.
    def cy1_full(self):
        return self.cy1().count() >= FIRST_CYCLE_LEN

    # TODO: Memoize this in some way. It'll never change once it's True.
    def cy2_full(self):
        """
        The second cycle is full once every singer from cy1 was cloned to cy2
        """
        return not self.cy1().filter(cy2_position__isnull=True).exists()

    def cy2_complete(self):
        from song_signup.models import SongRequest
        for pending_song in SongRequest.objects.filter(performance_time__isnull=True, position__isnull=False):
            if pending_song.cycle in (1, 2):
                return False

        return True

    def clone_singer_cy1_to_cy2(self):
        """
        When a new singer is added to cycle2, following a song request, we copy after him a singer in cycle1,
        according to the order.
        If in Cycle one there are ABC (with a max of 3): After XYZ join in that order cycle 2 will look like this:
        XAYBZC.
        This method takes the next singer in cy1, that hasn't been cloned yet to cy2, and clones him into the last
        place.
        """
        next_cy1_singer = self.cy1().filter(cy2_position__isnull=True).order_by('cy1_position').first()
        if next_cy1_singer and next_cy1_singer.cy2_position is None:
            next_cy1_singer.cy2_position = self.next_pos_cy2()
            next_cy1_singer.save()

    def seal_cycles(self):
        """
        When the cycle 2 ends, signup is sealed, meaning all new singers are in cycle 3.
        Then cycle 2 is cloned to cycle 3 in the same order.
        This method is to be called every time a song is performed, and at some point it'll seal the evening.
        """
        if flag_enabled('CAN_SIGNUP') and self.cy2_complete():
            disable_flag('CAN_SIGNUP')
            self.calculate_positions()

            for cy_2_singer in self.cy2().all():
                if cy_2_singer.cy3_position is None:
                    cy_2_singer.cy3_position = self.next_pos_cy3()
                    cy_2_singer.save()

            self.calculate_positions()
