from freezegun import freeze_time
from mock import patch

from song_signup.models import Singer, SongRequest
from song_signup.tests.test_utils import (
    SongRequestTestCase, TEST_START_TIME, create_singers, assert_singers_in_disney,
    set_performed, add_duet, add_songs_to_singers, get_singer, assert_song_positions, add_songs_to_singer,
    login, logout,
)
from flags.state import disable_flag

class TestDisneylandOrdering(SongRequestTestCase):
    def test_active_singers(self):
        create_singers(5)
        add_songs_to_singers(3, 1)

        self.assertEqual(set(Singer.ordering.active_singers()), {get_singer(1), get_singer(2), get_singer(3)})
        assert_song_positions(self, [
            (1, 1),
            (2, 1),
            (3, 1)
        ])

        logout(2)
        logout(4)
        self.assertEqual(set(Singer.ordering.active_singers()), {get_singer(1), get_singer(3)})
        assert_song_positions(self, [
            (1, 1),
            (3, 1)
        ])

        login(2)
        login(4)

        self.assertEqual(set(Singer.ordering.active_singers()), {get_singer(1), get_singer(2), get_singer(3)})
        assert_song_positions(self, [
            (1, 1),
            (2, 1),
            (3, 1)
        ])

    def test_no_performances_no_songs(self):
        # Singers that didn't sign up for a song yet don't apper in the list
        with freeze_time(TEST_START_TIME, auto_tick_seconds=5) as frozen_time:
            create_singers(10, frozen_time)
            assert_singers_in_disney(self, [])
            self.assertEqual(Singer.ordering.new_singers_num(), 0)

    def test_no_performances(self):
        with freeze_time(TEST_START_TIME, auto_tick_seconds=5) as frozen_time:
            create_singers(10, frozen_time, num_songs=3)
            assert_singers_in_disney(self, range(1, 11))
            self.assertEqual(Singer.ordering.new_singers_num(), 10)

    def test_first_performances(self):
        with freeze_time(TEST_START_TIME, auto_tick_seconds=5) as frozen_time:
            create_singers([1, 2], frozen_time, num_songs=3)
            set_performed(1, 1, frozen_time)
            assert_singers_in_disney(self, [2, 1])
            self.assertEqual(Singer.ordering.new_singers_num(), 1)

    def test_duets(self):
        """
        If two singers have a duet, once the duet is sung both will be moved to the end of the queue
        """
        with freeze_time(TEST_START_TIME, auto_tick_seconds=5) as frozen_time:
            create_singers(5, frozen_time, num_songs=3)
            add_duet(5, 3, 1)

            set_performed(1, 1, frozen_time)
            assert_singers_in_disney(self, [2, 3, 4, 5, 1])
            self.assertEqual(Singer.ordering.new_singers_num(), 4)

            set_performed(2, 1, frozen_time)
            assert_singers_in_disney(self, [3, 4, 5, 1, 2])
            self.assertEqual(Singer.ordering.new_singers_num(), 3)

            # 3 duets with 5, so they both get moved to the back of the list
            set_performed(3, 1, frozen_time)
            assert_singers_in_disney(self, [4, 1, 2, 3, 5])
            self.assertEqual(Singer.ordering.new_singers_num(), 1)  # Both 3 and 5 stop being new singers

            set_performed(4, 1, frozen_time)
            assert_singers_in_disney(self, [1, 2, 3, 5, 4])
            self.assertEqual(Singer.ordering.new_singers_num(), 0)

    def test_long_ordering(self):
        with freeze_time(TEST_START_TIME, auto_tick_seconds=5) as frozen_time:
            create_singers([1, 2], frozen_time, num_songs=3)
            assert_singers_in_disney(self, [1, 2])
            self.assertEqual(Singer.ordering.new_singers_num(), 2)

            create_singers([3, 4], frozen_time, num_songs=3)
            set_performed(1, 1, frozen_time)
            assert_singers_in_disney(self, [2, 3, 4, 1])
            self.assertEqual(Singer.ordering.new_singers_num(), 3)

            create_singers([5, 6], frozen_time, num_songs=3)
            assert_singers_in_disney(self, [2, 3, 4, 1, 5, 6])
            self.assertEqual(Singer.ordering.new_singers_num(), 5)

            set_performed(2, 1, frozen_time)
            assert_singers_in_disney(self, [3, 4, 1, 5, 6, 2])
            self.assertEqual(Singer.ordering.new_singers_num(), 4)

            # Singer 9 joins but doesn't sign up for a song, doesn't count in the ordering
            create_singers([7, 8, 9], frozen_time)
            add_songs_to_singers([7, 8], 3)
            assert_singers_in_disney(self, [3, 4, 1, 5, 6, 2, 7, 8])
            self.assertEqual(Singer.ordering.new_singers_num(), 6)

            set_performed(3, 1, frozen_time)
            set_performed(4, 1, frozen_time)
            assert_singers_in_disney(self, [1, 5, 6, 2, 7, 8, 3, 4])
            self.assertEqual(Singer.ordering.new_singers_num(), 4)

            create_singers([10], frozen_time, num_songs=1)
            self.assertEqual(Singer.ordering.new_singers_num(), 5)
            set_performed(1, 2, frozen_time)
            assert_singers_in_disney(self, [5, 6, 2, 7, 8, 3, 4, 10, 1])
            self.assertEqual(Singer.ordering.new_singers_num(), 5)  # 1 already sung, doesn't count as new singer

            # 9 signs up for a song now, appears at the end
            add_songs_to_singer(9, 1, frozen_time)
            assert_singers_in_disney(self, [5, 6, 2, 7, 8, 3, 4, 10, 1, 9])

            # Shani stops signup, which pushes all the people who haven't sung yet to the start of the list

            disable_flag('CAN_SIGNUP')
            assert_singers_in_disney(self, [5, 6, 7, 8, 10, 9, 2, 3, 4, 1])
            self.assertEqual(Singer.ordering.new_singers_num(), 6)

            set_performed(5, 1, frozen_time)
            assert_singers_in_disney(self, [6, 7, 8, 10, 9, 2, 3, 4, 1, 5])
            self.assertEqual(Singer.ordering.new_singers_num(), 5)

            set_performed(6, 1, frozen_time)
            set_performed(7, 1, frozen_time)
            set_performed(8, 1, frozen_time)
            self.assertEqual(Singer.ordering.new_singers_num(), 2)
            set_performed(10, 1, frozen_time)
            self.assertEqual(Singer.ordering.new_singers_num(), 1)
            set_performed(9, 1, frozen_time)
            self.assertEqual(Singer.ordering.new_singers_num(), 0)
            set_performed(2, 2, frozen_time)
            set_performed(3, 2, frozen_time)
            self.assertEqual(Singer.ordering.new_singers_num(), 0)

            set_performed(4, 2, frozen_time)
            set_performed(1, 3, frozen_time)
            self.assertEqual(Singer.ordering.new_singers_num(), 0)
            assert_singers_in_disney(self, [5, 6, 7, 8, 10, 9, 2, 3, 4, 1])


class TestCalculatePositionsDisney(SongRequestTestCase):
    def test_no_singers_have_songs(self):
        create_singers(10)
        singer_ordering = [
            5, 6, 2, 7, 8, 9, 3, 4, 10, 1
        ]

        with patch('song_signup.managers.DisneylandOrdering.singer_disneyland_ordering',
                   return_value=[get_singer(singer_id) for singer_id in singer_ordering]):
            Singer.ordering.calculate_positions()

        self.assertFalse(SongRequest.objects.filter(position__isnull=False).exists())

    def test_all_singers_have_songs(self):
        create_singers(10)
        singer_ordering = [
            5, 6, 2, 7, 8, 9, 3, 4, 10, 1
        ]

        with patch('song_signup.managers.DisneylandOrdering.singer_disneyland_ordering',
                   return_value=[get_singer(singer_id) for singer_id in singer_ordering]):
            # Adding songs invokes the calculate_positions method
            add_songs_to_singers(10, 3)

            assert_song_positions(self, [
                (5, 1),
                (6, 1),
                (2, 1),
                (7, 1),
                (8, 1),
                (9, 1),
                (3, 1),
                (4, 1),
                (10, 1),
                (1, 1)
            ])

    def test_some_singers_have_songs(self):
        """
        7 and 9 didn't sign up with songs
        """
        create_singers(10)
        singer_ordering = [
            5, 6, 2, 7, 8, 9, 3, 4, 10, 1
        ]

        with patch('song_signup.managers.DisneylandOrdering.singer_disneyland_ordering',
                   return_value=[get_singer(singer_id) for singer_id in singer_ordering]):
            add_songs_to_singers(6, 1)
            add_songs_to_singers([8, 10], 1)

            assert_song_positions(self, [
                (5, 1),
                (6, 1),
                (2, 1),
                (8, 1),
                (3, 1),
                (4, 1),
                (10, 1),
                (1, 1)
            ])

    def test_next_songs(self):
        """
        Some singers already sang their first or second song
        """
        create_singers(10)
        singer_ordering = [
            5, 6, 2, 7, 8, 9, 3, 4, 10, 1
        ]

        with patch('song_signup.managers.DisneylandOrdering.singer_disneyland_ordering',
                   return_value=[get_singer(singer_id) for singer_id in singer_ordering]):
            add_songs_to_singers(10, 3)

            set_performed(1, 1)
            set_performed(2, 1)
            set_performed(3, 1)
            set_performed(4, 1)
            set_performed(1, 2)

            assert_song_positions(self, [
                (5, 1),
                (6, 1),
                (2, 2),
                (7, 1),
                (8, 1),
                (9, 1),
                (3, 2),
                (4, 2),
                (10, 1),
                (1, 3)
            ])

    def test_duets(self):
        """
        Ignoring duets now - doesn't affect the orcer.
        """
        create_singers(10)
        singer_ordering = [
            5, 6, 2, 7, 8, 9, 3, 4, 10, 1
        ]

        with patch('song_signup.managers.DisneylandOrdering.singer_disneyland_ordering',
                   return_value=[get_singer(singer_id) for singer_id in singer_ordering]):
            # Adding songs and setting as performed invokes the calculate_positions method
            add_songs_to_singers(9, 3)  # Singer 10 only has a duet

            add_duet(8, 6, 1)
            add_duet(9, 4, 1)
            add_duet(3, 8, 1)
            add_duet(10, 7, 1)

            assert_song_positions(self, [
                (5, 1),
                (6, 1),
                (2, 1),
                (7, 1),
                (8, 1),
                (9, 1),
                (3, 1),
                (4, 1),
                # 10 Doesn't have a primary song, only a duet
                (1, 1)
            ])


class TestSimulatedEvenings(SongRequestTestCase):
    def test_scenario1(self):
        # NOTE - This was originally written with the old duet logic which penalized duet singers and counted them as
        # a full turn. Now we changed it so duet singers are blocked from beind added to more than one song.
        # This test was adjusted in order to reflect the change, so it ignores duet singers completely. The restriction
        # on being added to more than one duet is tested elsewhere.
        with freeze_time(TEST_START_TIME, auto_tick_seconds=5) as frozen_time:
            # Singer 1 joins with 1 song #1
            create_singers([1], frozen_time, num_songs=1)
            assert_song_positions(self, [(1, 1)])

            # Singer 2 joins with as singer 1 sings
            create_singers([2], frozen_time, num_songs=3)
            set_performed(1, 1, frozen_time)
            assert_song_positions(self, [(2, 1)])

            # Singer 1 adds song #2
            add_songs_to_singer(1, [2], frozen_time)
            assert_song_positions(self, [(2, 1), (1, 2)])

            # Singers 3-5 join as 2 sings, singer 5 doesn't sign up with a song
            create_singers([3, 4, 5], frozen_time)
            add_songs_to_singers([3, 4], 3, frozen_time)
            Singer.ordering.calculate_positions()
            assert_song_positions(self, [(2, 1), (1, 2), (3, 1), (4, 1)])
            set_performed(2, 1, frozen_time)
            assert_song_positions(self, [(1, 2), (3, 1), (4, 1), (2, 2)])

            # Singers 6-9 join without signing up for songs yet. Singer #1 adds another song (#3)
            # Singers 6 and 8 choose a song before 1 sings, and singers 7 and 9 choose a song after he sings. Then 6 and
            # 7 choose another song.
            # The first request time, not the join time, is what counts for the ordering.
            # So 6,8 are before 1, and 7,9 are after.
            # Singer #1 adds his song at the end of all of this, so his song will appear between 6,8 and 7,9
            create_singers([6, 7, 8, 9], frozen_time)
            assert_song_positions(self, [(1, 2), (3, 1), (4, 1), (2, 2)])
            add_songs_to_singers([6, 8], 1, frozen_time)
            assert_song_positions(self, [(1, 2), (3, 1), (4, 1), (2, 2), (6, 1), (8, 1)])
            set_performed(1, 2, frozen_time)
            add_songs_to_singers([7, 9], 1, frozen_time)
            assert_song_positions(self, [(3, 1), (4, 1), (2, 2), (6, 1), (8, 1), (7, 1), (9, 1)])
            add_songs_to_singer(1, [3], frozen_time)
            assert_song_positions(self, [(3, 1), (4, 1), (2, 2), (6, 1), (8, 1), (1, 3), (7, 1), (9, 1)])

            # Add 3 more songs to singer 6, 7, 9 (8 will add only later)
            add_songs_to_singers([6, 7, 9], [2, 3, 4], frozen_time)
            assert_song_positions(self, [(3, 1), (4, 1), (2, 2), (6, 1), (8, 1), (1, 3), (7, 1), (9, 1)])

            # Singer 6 logs out
            logout(6)
            assert_song_positions(self, [(3, 1), (4, 1), (2, 2), (8, 1), (1, 3), (7, 1), (9, 1)])

            # Singers 10-11 join without songs (along with 5 who doesn't have a song yet either)
            create_singers([10, 11], frozen_time)
            assert_song_positions(self, [(3, 1), (4, 1), (2, 2), (8, 1), (1, 3), (7, 1), (9, 1)])

            # 4 adds 7 as a duet partner. 2 adds 3 as a duet partner. No effect.
            add_duet(7, 4, 1, frozen_time)
            assert_song_positions(self, [(3, 1), (4, 1), (2, 2), (8, 1), (1, 3), (7,1), (9, 1)])
            add_duet(3, 2, 2, frozen_time)
            assert_song_positions(self, [(3, 1), (4, 1), (2, 2), (8, 1), (1, 3), (7,1), (9, 1)])

            # Singer 6 logs back in
            login(6)
            assert_song_positions(self, [(3, 1), (4, 1), (2, 2), (6, 1), (8, 1), (1, 3), (7,1), (9, 1)])

            # Singers 12-13 join while 3 is singing. 3 is a duet partner with 2, but now his song still comes back to
            # the end of the list
            create_singers([12, 13], frozen_time, num_songs=2)
            assert_song_positions(self, [(3, 1), (4, 1), (2, 2), (6, 1), (8, 1), (1, 3), (9, 1), (12, 1), (13, 1)])
            set_performed(3, 1, frozen_time)
            assert_song_positions(self, [(4, 1), (2, 2), (6, 1), (8, 1), (1, 3), (7,1), (9, 1),
                                         (12, 1), (13, 1), (3, 1)])

            # Singer 14 joins as Singer 4 sings a duet with 7. 4 gets put at the end of the list, after 14.
            # 7s position doesn't change.
            create_singers([14], frozen_time, num_songs=1)
            assert_song_positions(self, [(4, 1), (2, 2), (6, 1), (8, 1), (1, 3), (9, 1), (12, 1), (13, 1), (14, 1)])
            set_performed(4, 1, frozen_time)
            assert_song_positions(self, [(2, 2), (6, 1), (8, 1), (1, 3), (7,1), (9, 1), (12, 1),
                                         (13, 1), (14, 1), (4, 2)])

            # Singers 5 and 11 decide to add their songs. They appear at the end of the list,
            # as the first song request is what counts
            add_songs_to_singer(5, 1, frozen_time)
            assert_song_positions(self, [(2, 2), (6, 1), (8, 1), (1, 3), (7,1), (9, 1), (12, 1), (13, 1), (14, 1), (4, 2), (7, 1), (5, 1)])
            add_songs_to_singer(11, 2, frozen_time)
            assert_song_positions(self, [(2, 2), (6, 1), (8, 1), (1, 3), (7,1), (9, 1), (12, 1), (13, 1), (14, 1),
                                         (4, 2), (7, 1), (5, 1), (11, 1)])

            # Singer 2 duets with 3, and they both appear at the end of the list together.
            set_performed(2, 2, frozen_time)
            assert_song_positions(self, [(6, 1), (8, 1), (1, 3), (7, 1), (9, 1), (12, 1), (13, 1), (14, 1), (4, 2),
                                         (7, 1), (5, 1), (11, 1), (2, 3), (3, 2)])

            # Singers 15-16 join as 6 sings.
            create_singers([15, 16], frozen_time, num_songs=1)
            set_performed(6, 1, frozen_time)
            assert_song_positions(self, [(8, 1), (1, 3), (7, 1), (9, 1), (12, 1), (13, 1), (14, 1), (4, 2), (7, 1), (5, 1),
                                         (11, 1), (2, 3), (3, 2), (15, 1), (16, 1), (6, 2)])

            # Shani closes signup - all new singers jump to start of list, including 7 the duetor that hasn't
            # sung her primary song yet.
            disable_flag('CAN_SIGNUP')
            assert_song_positions(self, [(8, 1), (7, 1), (9, 1), (12, 1), (13, 1), (14, 1), (5, 1),
                                         (11, 1), (15, 1), (16, 1), (1, 3), (4, 2), (7, 1), (2, 3), (3, 2), (6, 2)])

            # 9 adds a duet with 6, 8 adds a duet with 11, 1 adds a duet with 12. Only 11 isn't in the list, so is added.
            add_duet(6, 9, 1, frozen_time)
            add_duet(11, 8, 1, frozen_time)
            add_duet(12, 1, 3, frozen_time)
            assert_song_positions(self, [(8, 1), (7, 1), (9, 1), (12, 1), (13, 1), (14, 1), (5, 1),
                                         (15, 1), (16, 1), (1, 3), (4, 2), (7, 1), (2, 3), (3, 2), (11, 1)])

            # 8 Sings duet with 11.
            set_performed(8, 1, frozen_time)
            assert_song_positions(self, [(7, 1), (9, 1), (12, 1), (13, 1), (14, 1), (5, 1),
                                         (15, 1), (16, 1), (1, 3), (4, 2), (7, 1), (2, 3), (3, 2), (11, 1)])

            # 7 sings
        set_performed(7, 1, frozen_time)
            assert_song_positions(self, [(9, 1), (12, 1), (13, 1), (14, 1), (5, 1),
                                         (15, 1), (16, 1), (1, 3), (4, 2), (7, 1), (2, 3), (3, 2), (11, 1)])

            # TODO GOT HERE WITH FIXES

            # 9 Sings duet with 6 - they both go to the end, 6 with song 2 that he didn't sing yet
            set_performed(9, 1, frozen_time)
            assert_song_positions(self, [(12, 1), (13, 1), (14, 1), (5, 1),
                                         (15, 1), (16, 1), (1, 3), (4, 2), (7, 1), (2, 3), (3, 2), (11, 1), (9, 2), (6, 2)])

            # Singer 7 logs out
            logout(7)
            assert_song_positions(self, [(12, 1), (13, 1), (14, 1), (5, 1),
                                         (15, 1), (16, 1), (1, 3), (4, 2), (2, 3), (3, 2), (11, 1), (9, 2), (6, 2)])

            # 8 adds his second song. Appears after in his place after 11
            add_songs_to_singer(8, [2])
            assert_song_positions(self, [(12, 1), (13, 1), (14, 1), (5, 1),
                                         (15, 1), (16, 1), (1, 3), (4, 2), (2, 3), (3, 2),
                                         (8, 2), (11, 1), (9, 2), (6, 2)])

            # 12 Sings. Is dueting with 1, later on - so doesn't appear in the list
            set_performed(12, 1, frozen_time)
            assert_song_positions(self, [(13, 1), (14, 1), (5, 1),
                                         (15, 1), (16, 1), (1, 3), (4, 2), (2, 3), (3, 2),
                                         (8, 2), (11, 1), (9, 2), (6, 2)])

            # Singers 13, 14, 5, 15, 16 sing.
            # Only 13 has an extra song and is put in the back of the list. The rest are done
            set_performed(13, 1, frozen_time)
            set_performed(14, 1, frozen_time)
            set_performed(5, 1, frozen_time)
            set_performed(15, 1, frozen_time)
            set_performed(16, 1, frozen_time)
            assert_song_positions(self, [(1, 3), (4, 2), (2, 3), (3, 2),
                                         (8, 2), (11, 1), (9, 2), (6, 2), (13, 2)])

            # Singer 7 logs back in
            login(7)
            assert_song_positions(self, [(1, 3), (4, 2), (7, 1), (2, 3), (3, 2),
                                         (8, 2), (11, 1), (9, 2), (6, 2), (13, 2)])

            # 1 Duets with 12. So 12 is moved to the end of the list. 1 is done with her songs
            set_performed(1, 3, frozen_time)
            assert_song_positions(self, [(4, 2), (7, 1), (2, 3), (3, 2),
                                         (8, 2), (11, 1), (9, 2), (6, 2), (13, 2), (12, 2)])

            # Half the cycle sings. 2 and 8 sang their last song
            set_performed(4, 2, frozen_time)
            set_performed(7, 1, frozen_time)
            set_performed(2, 3, frozen_time)
            set_performed(3, 2, frozen_time)
            set_performed(8, 2, frozen_time)
            set_performed(11, 1, frozen_time)
            assert_song_positions(self,
                                  [(9, 2), (6, 2), (13, 2), (12, 2),
                                   (4, 3), (7, 2), (3, 3), (11, 2)])

            # Almost full cycle sing. The singers who sang their last song are, 13, 12, 4, 3
            set_performed(9, 2, frozen_time)
            set_performed(6, 2, frozen_time)
            set_performed(13, 2, frozen_time)
            set_performed(12, 2, frozen_time)
            set_performed(4, 3, frozen_time)
            set_performed(7, 2, frozen_time)
            set_performed(3, 3, frozen_time)
            assert_song_positions(self,
                                  [(11, 2), (9, 3), (6, 3), (7, 3)])

            # Full cycle sing. 11 sang its last
            set_performed(11, 2, frozen_time)
            set_performed(9, 3, frozen_time)
            set_performed(6, 3, frozen_time)
            set_performed(7, 3, frozen_time)
            assert_song_positions(self,
                                  [(9, 4), (6, 4), (7, 4)])

            # All but last sing their final song
            set_performed(9, 4, frozen_time)
            set_performed(6, 4, frozen_time)
            assert_song_positions(self,
                                  [(7, 4)])

            # Last singer sings
            set_performed(7, 4)
            assert_song_positions(self, [])
