from django.contrib.auth.models import UserManager
from django.db.models import Manager


# TODO: Put in some config
FIRST_CYCLE_LEN = 5


class SongRequestManager(Manager):
    def calculate_positions(self):
        for song_reqeust in self.all():
            song_reqeust.position = song_reqeust.calculate_position()
            song_reqeust.save()


class CycleManager(UserManager):
    def cy1(self, only_primary=False):
        return self.filter(cy1_position__isnull=False).order_by('cy1_position')

    def cy2(self):
        return self.filter(cy2_position__isnull=False).order_by('cy2_position')

    def cy3(self):
        return self.filter(cy3_position__isnull=False).order_by('cy3_position')

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

    def clone_singer_cy1_to_cy2(self, song_request):
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

