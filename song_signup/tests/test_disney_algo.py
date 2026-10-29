from freezegun import freeze_time
from mock import patch

from song_signup.models import Singer, SongRequest
from song_signup.tests.utils_for_tests import (
    SongRequestTestCase, TEST_START_TIME, create_singers, assert_singers_in_disney,
    set_performed, add_partners, add_songs_to_singers, get_singer, assert_song_positions, add_songs_to_singer,
    login, logout, create_audience, get_song, set_standby, unset_standby,
    ExpectedDashboard, assert_dashboards, logout_audience, assert_current_song, get_singer_str, set_skipped,
    set_unskipped
)
from flags.state import disable_flag, enable_flag

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

    def test_new_singers_couter(self):
        """
        New duet logic:
        If two singers have a duet, once the duet is sung both only the primary will be moved to the end of the list.
        """
        with freeze_time(TEST_START_TIME, auto_tick_seconds=5) as frozen_time:
            create_singers(5, frozen_time, num_songs=3)
            add_partners(3, [4, 5], 1)

            set_performed(1, 1, frozen_time)
            assert_singers_in_disney(self, [2, 3, 4, 5, 1])
            self.assertEqual(Singer.ordering.new_singers_num(), 4)

            set_performed(2, 1, frozen_time)
            assert_singers_in_disney(self, [3, 4, 5, 1, 2])
            self.assertEqual(Singer.ordering.new_singers_num(), 3)

            # 3 duets with 5. Only 3 moves to the back of the list.
            set_performed(3, 1, frozen_time)
            assert_singers_in_disney(self, [4, 5, 1, 2, 3])
            self.assertEqual(Singer.ordering.new_singers_num(), 2)  # Counts 5 as new singer, even though sang duet

            set_performed(4, 1, frozen_time)
            assert_singers_in_disney(self, [5, 1, 2, 3, 4])
            self.assertEqual(Singer.ordering.new_singers_num(), 1)

            set_performed(5, 1, frozen_time)
            assert_singers_in_disney(self, [1, 2, 3, 4, 5])
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
        Ignoring duets now - doesn't affect the order.
        """
        create_singers(10)
        singer_ordering = [
            5, 6, 2, 7, 8, 9, 3, 4, 10, 1
        ]

        with patch('song_signup.managers.DisneylandOrdering.singer_disneyland_ordering',
                   return_value=[get_singer(singer_id) for singer_id in singer_ordering]):
            # Adding songs and setting as performed invokes the calculate_positions method
            add_songs_to_singers(9, 3)  # Singer 10 only has a duet

            add_partners(6, 8, 1)
            add_partners(4, [9, 5], 1)
            add_partners(8, 3, 1)
            add_partners(7, [2, 10], 1)

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

    def test_dashboard(self):
        """
        Ignoring duets now - doesn't affect the order.
        """
        create_singers(10)
        singer_ordering = [
            5, 6, 2, 7, 8, 9, 3, 4, 10, 1
        ]

        with patch('song_signup.managers.DisneylandOrdering.singer_disneyland_ordering',
                   return_value=[get_singer(singer_id) for singer_id in singer_ordering]):
            # Adding songs and setting as performed invokes the calculate_positions method
            add_songs_to_singers(9, 3)  # Singer 10 only has a duet

            add_partners(6, 8, 1)
            add_partners(4, [9, 5], 1)
            add_partners(8, 3, 1)
            add_partners(7, [2, 10], 1)

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
            assert_dashboards(self, [
                ExpectedDashboard(singer=1, next_song=1, wait_amount=0),
            ])

            audience70, audience71, *_ = create_audience(audience_ids=[70, 71, 72, 73])

            # Singer 2 joins with as singer 1 sings
            create_singers([2], frozen_time, num_songs=3)
            set_performed(1, 1, frozen_time)
            assert_song_positions(self, [(2, 1)])
            assert_dashboards(self, [
                ExpectedDashboard(singer=1, empty=True),
                ExpectedDashboard(singer=2, next_song=1, wait_amount=0)
            ])

            audience74, audience75, *_ = create_audience(audience_ids=[74, 75, 76, 77])

            # Singer 1 adds song #2
            add_songs_to_singer(1, [2], frozen_time)
            assert_song_positions(self, [(2, 1), (1, 2)])
            assert_dashboards(self, [
                ExpectedDashboard(singer=2, next_song=1, wait_amount=0),
                ExpectedDashboard(singer=1, next_song=2, wait_amount=1),
            ])

            # Singers 3-5 join as 2 sings, singer 5 doesn't sign up with a song
            create_singers([3, 4, 5], frozen_time)
            add_songs_to_singers([3, 4], 3, frozen_time)
            Singer.ordering.calculate_positions()
            assert_song_positions(self, [(2, 1), (1, 2), (3, 1), (4, 1)])
            assert_dashboards(self, [
                ExpectedDashboard(singer=2, next_song=1, wait_amount=0),
                ExpectedDashboard(singer=1, next_song=2, wait_amount=1),
                ExpectedDashboard(singer=3, next_song=1, wait_amount=2),
                ExpectedDashboard(singer=4, next_song=1, wait_amount=3),
                ExpectedDashboard(singer=5, empty=True),
            ])
            set_performed(2, 1, frozen_time)
            assert_song_positions(self, [(1, 2), (3, 1), (4, 1), (2, 2)])
            assert_dashboards(self, [
                ExpectedDashboard(singer=1, next_song=2, wait_amount=0),
                ExpectedDashboard(singer=3, next_song=1, wait_amount=1),
                ExpectedDashboard(singer=4, next_song=1, wait_amount=2),
                ExpectedDashboard(singer=5, empty=True),
                ExpectedDashboard(singer=2, next_song=2, wait_amount=3),
            ])

            # Create 2 singers with a song that will get a spotlight later
            create_singers([222, 223], frozen_time)
            add_songs_to_singers([222, 223], 1, frozen_time)
            Singer.ordering.calculate_positions()
            assert_song_positions(self, [(1, 2), (3, 1), (4, 1), (2, 2), (222, 1), (223, 1)])
            assert_dashboards(self, [
                ExpectedDashboard(singer=1, next_song=2, wait_amount=0),
                ExpectedDashboard(singer=3, next_song=1, wait_amount=1),
                ExpectedDashboard(singer=4, next_song=1, wait_amount=2),
                ExpectedDashboard(singer=5, empty=True),
                ExpectedDashboard(singer=2, next_song=2, wait_amount=3),
                ExpectedDashboard(singer=222, next_song=1, wait_amount=4),
                ExpectedDashboard(singer=223, next_song=1, wait_amount=5),
            ])

            # Move song of 222 to standby - should be removed from list of singers.
            set_standby(222, 1)
            Singer.ordering.calculate_positions()
            assert_song_positions(self, [(1, 2), (3, 1), (4, 1), (2, 2), (223, 1)])
            assert_dashboards(self, [
                ExpectedDashboard(singer=1, next_song=2, wait_amount=0),
                ExpectedDashboard(singer=3, next_song=1, wait_amount=1),
                ExpectedDashboard(singer=4, next_song=1, wait_amount=2),
                ExpectedDashboard(singer=5, empty=True),
                ExpectedDashboard(singer=2, next_song=2, wait_amount=3),
                ExpectedDashboard(singer=223, next_song=1, wait_amount=4),
            ])

            # Move song of 222 out of standby - should be returned to same place
            unset_standby(222, 1)
            assert_current_song(self, 1, 2)
            Singer.ordering.calculate_positions()
            assert_song_positions(self, [(1, 2), (3, 1), (4, 1), (2, 2), (222, 1), (223, 1)])
            assert_dashboards(self, [
                ExpectedDashboard(singer=1, next_song=2, wait_amount=0),
                ExpectedDashboard(singer=3, next_song=1, wait_amount=1),
                ExpectedDashboard(singer=4, next_song=1, wait_amount=2),
                ExpectedDashboard(singer=5, empty=True),
                ExpectedDashboard(singer=2, next_song=2, wait_amount=3),
                ExpectedDashboard(singer=222, next_song=1, wait_amount=4),
                ExpectedDashboard(singer=223, next_song=1, wait_amount=5),
            ])

            # Spotlight singer 222 from within regular list - order doesn't change,
            # lyrics are just displayed over the first singer
            SongRequest.objects.set_spotlight(get_song(222, 1))
            Singer.ordering.calculate_positions()
            assert_current_song(self, 222, 1)
            assert_song_positions(self, [(1, 2), (3, 1), (4, 1), (2, 2), (222, 1), (223, 1)])
            assert_dashboards(self, [
                ExpectedDashboard(singer=1, next_song=2, wait_amount=0),
                ExpectedDashboard(singer=3, next_song=1, wait_amount=1),
                ExpectedDashboard(singer=4, next_song=1, wait_amount=2),
                ExpectedDashboard(singer=5, empty=True),
                ExpectedDashboard(singer=2, next_song=2, wait_amount=3),
                ExpectedDashboard(singer=222, next_song=1, wait_amount=4),
                ExpectedDashboard(singer=223, next_song=1, wait_amount=5),
            ])

            # End spotlight - singer 222 disapears from list (since he already sang)
            SongRequest.objects.remove_spotlight()
            assert_current_song(self, 1, 2)
            assert_song_positions(self, [(1, 2), (3, 1), (4, 1), (2, 2), (223, 1)])
            assert_dashboards(self, [
                ExpectedDashboard(singer=1, next_song=2, wait_amount=0),
                ExpectedDashboard(singer=3, next_song=1, wait_amount=1),
                ExpectedDashboard(singer=4, next_song=1, wait_amount=2),
                ExpectedDashboard(singer=5, empty=True),
                ExpectedDashboard(singer=2, next_song=2, wait_amount=3),
                ExpectedDashboard(singer=223, next_song=1, wait_amount=4),
            ])

            # Move song of 223 to standby - removed from list
            set_standby(223, 1)
            self.assertEqual(list(SongRequest.objects.filter(standby=True)), [get_song(223, 1)])
            Singer.ordering.calculate_positions()
            assert_current_song(self, 1, 2)
            assert_song_positions(self, [(1, 2), (3, 1), (4, 1), (2, 2)])
            assert_dashboards(self, [
                ExpectedDashboard(singer=1, next_song=2, wait_amount=0),
                ExpectedDashboard(singer=3, next_song=1, wait_amount=1),
                ExpectedDashboard(singer=4, next_song=1, wait_amount=2),
                ExpectedDashboard(singer=5, empty=True),
                ExpectedDashboard(singer=2, next_song=2, wait_amount=3),
            ])

            # Spotlight singer 223 while in standby. Still removed regular list but appears in standby.
            SongRequest.objects.set_spotlight(get_song(223, 1))
            self.assertEqual(list(SongRequest.objects.filter(standby=True)), [get_song(223, 1)])
            assert_current_song(self, 223, 1)
            Singer.ordering.calculate_positions()
            assert_song_positions(self, [(1, 2), (3, 1), (4, 1), (2, 2)])
            assert_dashboards(self, [
                ExpectedDashboard(singer=1, next_song=2, wait_amount=0),
                ExpectedDashboard(singer=3, next_song=1, wait_amount=1),
                ExpectedDashboard(singer=4, next_song=1, wait_amount=2),
                ExpectedDashboard(singer=5, empty=True),
                ExpectedDashboard(singer=2, next_song=2, wait_amount=3),
            ])

            # End Spotlight singer 223. Removed from standby and not in regular list either.
            SongRequest.objects.remove_spotlight()
            self.assertEqual(list(SongRequest.objects.filter(standby=True)), [])
            assert_current_song(self, 1, 2)
            assert_song_positions(self, [(1, 2), (3, 1), (4, 1), (2, 2)])
            assert_dashboards(self, [
                ExpectedDashboard(singer=1, next_song=2, wait_amount=0),
                ExpectedDashboard(singer=3, next_song=1, wait_amount=1),
                ExpectedDashboard(singer=4, next_song=1, wait_amount=2),
                ExpectedDashboard(singer=5, empty=True),
                ExpectedDashboard(singer=2, next_song=2, wait_amount=3),
            ])

            audience78, *_ = create_audience(audience_ids=[78, 79, 80, 81])

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

            audience82, audience83, *_ = create_audience(audience_ids=[82, 83, 84, 85])

            # Add 3 more songs to singer 6, 7, 9 (8 will add only later)
            add_songs_to_singers([6, 7, 9], [2, 3, 4], frozen_time)
            # Add one more song to singer 7
            add_songs_to_singers([7], [5])
            assert_song_positions(self, [(3, 1), (4, 1), (2, 2), (6, 1), (8, 1), (1, 3), (7, 1), (9, 1)])

            # Singer 6 logs out
            logout(6)
            assert_song_positions(self, [(3, 1), (4, 1), (2, 2), (8, 1), (1, 3), (7, 1), (9, 1)])

            logout_audience(72)
            logout_audience(83)

            # Singers 10-11 join without songs (along with 5 who doesn't have a song yet either)
            create_singers([10, 11], frozen_time)
            assert_song_positions(self, [(3, 1), (4, 1), (2, 2), (8, 1), (1, 3), (7, 1), (9, 1)])
            assert_dashboards(self, [
                ExpectedDashboard(singer=3, next_song=1, wait_amount=0),
                ExpectedDashboard(singer=4, next_song=1, wait_amount=1),
                ExpectedDashboard(singer=2, next_song=2, wait_amount=2),
                ExpectedDashboard(singer=8, next_song=1, wait_amount=3),
                ExpectedDashboard(singer=1, next_song=3, wait_amount=4),
                ExpectedDashboard(singer=7, next_song=1, wait_amount=5),
                ExpectedDashboard(singer=9, next_song=1, wait_amount=6),
                ExpectedDashboard(singer=5, empty=True),
                ExpectedDashboard(singer=10, empty=True),
                ExpectedDashboard(singer=11, empty=True),
            ])


            logout_audience(80)

            # 4 adds 7 and 3 (singers) and 70 (audience) as partners.
            add_partners(4, [3, 7], 1, frozen_time, audience_partner_ids=[70])
            assert_song_positions(self, [(3, 1), (4, 1), (2, 2), (8, 1), (1, 3), (7,1), (9, 1)])
            assert_dashboards(self, [
                ExpectedDashboard(singer=3, next_song=1, wait_amount=0),
                ExpectedDashboard(singer=4, next_song=1, wait_amount=1),
                ExpectedDashboard(singer=2, next_song=2, wait_amount=2),
                ExpectedDashboard(singer=8, next_song=1, wait_amount=3),
                ExpectedDashboard(singer=1, next_song=3, wait_amount=4),
                ExpectedDashboard(singer=7, primary_singer=4, next_song=1, wait_amount=1),
                ExpectedDashboard(singer=9, next_song=1, wait_amount=6),
                ExpectedDashboard(singer=5, empty=True),
                ExpectedDashboard(singer=10, empty=True),
                ExpectedDashboard(singer=11, empty=True),
            ])

            # 2 adds 4 as a duet partner.
            add_partners(2, 4, 2, frozen_time, audience_partner_ids=[78, 79])
            assert_song_positions(self, [(3, 1), (4, 1), (2, 2), (8, 1), (1, 3), (7,1), (9, 1)])
            assert_dashboards(self, [
                ExpectedDashboard(singer=3, next_song=1, wait_amount=0),
                ExpectedDashboard(singer=4, next_song=1, wait_amount=1),
                ExpectedDashboard(singer=2, next_song=2, wait_amount=2),
                ExpectedDashboard(singer=8, next_song=1, wait_amount=3),
                ExpectedDashboard(singer=1, next_song=3, wait_amount=4),
                ExpectedDashboard(singer=7, primary_singer=4, next_song=1, wait_amount=1),
                ExpectedDashboard(singer=9, next_song=1, wait_amount=6),
                ExpectedDashboard(singer=5, empty=True),
                ExpectedDashboard(singer=10, empty=True),
                ExpectedDashboard(singer=11, empty=True),
            ])

            # Singer 6 logs back in
            login(6)
            assert_song_positions(self, [(3, 1), (4, 1), (2, 2), (6, 1), (8, 1), (1, 3), (7,1), (9, 1)])
            assert_dashboards(self, [
                ExpectedDashboard(singer=3, next_song=1, wait_amount=0),
                ExpectedDashboard(singer=4, next_song=1, wait_amount=1),
                ExpectedDashboard(singer=2, next_song=2, wait_amount=2),
                ExpectedDashboard(singer=6, next_song=1, wait_amount=3),
                ExpectedDashboard(singer=8, next_song=1, wait_amount=4),
                ExpectedDashboard(singer=1, next_song=3, wait_amount=5),
                ExpectedDashboard(singer=7, primary_singer=4, next_song=1, wait_amount=1),
                # 7's primary song still takes a place in the list, so the wait amount includes it
                ExpectedDashboard(singer=9, next_song=1, wait_amount=7),
                ExpectedDashboard(singer=5, empty=True),
                ExpectedDashboard(singer=10, empty=True),
                ExpectedDashboard(singer=11, empty=True),
            ])

            # Singers 12-13 join while 3 is singing
            create_singers([12, 13], frozen_time, num_songs=2)
            assert_song_positions(self, [(3, 1), (4, 1), (2, 2), (6, 1), (8, 1), (1, 3), (7, 1), (9, 1),
                                         (12, 1), (13, 1)])
            set_performed(3, 1, frozen_time)
            assert_song_positions(self, [(4, 1), (2, 2), (6, 1), (8, 1), (1, 3), (7,1), (9, 1),
                                         (12, 1), (13, 1), (3, 2)])

            # Singer 14 joins as Singer 4 sings a duet with 7. 4 gets put at the end of the list, after 14.
            # 7s position doesn't change.
            create_singers([14], frozen_time, num_songs=1)
            assert_song_positions(self, [(4, 1), (2, 2), (6, 1), (8, 1), (1, 3), (7, 1), (9, 1),
                                         (12, 1), (13, 1), (3, 2), (14, 1)])
            set_performed(4, 1, frozen_time)
            assert_song_positions(self, [(2, 2), (6, 1), (8, 1), (1, 3), (7, 1), (9, 1), (12, 1),
                                         (13, 1), (3, 2), (14, 1), (4, 2)])

            # Singers 5 and 11 decide to add their songs. They appear at the end of the list,
            # as the first song request is what counts
            add_songs_to_singer(5, 1, frozen_time)
            assert_song_positions(self, [(2, 2), (6, 1), (8, 1), (1, 3), (7, 1), (9, 1), (12, 1),
                                         (13, 1), (3, 2), (14, 1), (4, 2), (5, 1)])
            add_songs_to_singer(11, 2, frozen_time)
            assert_song_positions(self, [(2, 2), (6, 1), (8, 1), (1, 3), (7,1), (9, 1), (12, 1),
                                         (13, 1), (3, 2), (14, 1), (4, 2), (5, 1), (11, 1)])

            # Singer 2 duets with 3, and they both appear at the end of the list together.
            set_performed(2, 2, frozen_time)
            assert_song_positions(self, [(6, 1), (8, 1), (1, 3), (7, 1), (9, 1), (12, 1), (13, 1),
                                         (3, 2), (14, 1), (4, 2), (5, 1), (11, 1), (2, 3)])

            # Singers 15-16 join as 6 sings.
            create_singers([15, 16], frozen_time, num_songs=1)
            set_performed(6, 1, frozen_time)
            assert_song_positions(self, [(8, 1), (1, 3), (7, 1), (9, 1), (12, 1), (13, 1), (3, 2), (14, 1),
                                         (4, 2), (5, 1), (11, 1), (2, 3), (15, 1), (16, 1), (6, 2)])

            # Shani closes signup - all new singers jump to start of list, including 7 the duetor that hasn't
            # sung her primary song yet.
            disable_flag('CAN_SIGNUP')
            assert_song_positions(self, [(8, 1), (7, 1), (9, 1), (12, 1), (13, 1), (14, 1), (5, 1),
                                         (11, 1), (15, 1), (16, 1), (1, 3), (3, 2), (4, 2), (2, 3), (6, 2)])
            assert_dashboards(self, [
                ExpectedDashboard(singer=8, next_song=1, wait_amount=0),
                ExpectedDashboard(singer=7, next_song=1, wait_amount=1),
                ExpectedDashboard(singer=9, next_song=1, wait_amount=2),
                ExpectedDashboard(singer=12, next_song=1, wait_amount=3),
                ExpectedDashboard(singer=13, next_song=1, wait_amount=4),
                ExpectedDashboard(singer=14, next_song=1, wait_amount=5),
                ExpectedDashboard(singer=5, next_song=1, wait_amount=6),
                ExpectedDashboard(singer=11, next_song=1, wait_amount=7),
                ExpectedDashboard(singer=15, next_song=1, wait_amount=8),
                ExpectedDashboard(singer=16, next_song=1, wait_amount=9),
                ExpectedDashboard(singer=1, next_song=3, wait_amount=10),
                ExpectedDashboard(singer=3, next_song=2, wait_amount=11),
                ExpectedDashboard(singer=4, next_song=2, wait_amount=12),
                ExpectedDashboard(singer=2, next_song=3, wait_amount=13),
                ExpectedDashboard(singer=6, next_song=2, wait_amount=14),
            ])

            # 9 adds a duet with 6, 8 adds a duet with 11, 1 adds a duet with 12. Changes nothing
            add_partners(9, [6, 2], 1, frozen_time)
            add_partners(8, 11, 1, frozen_time, audience_partner_ids=[83])
            add_partners(1, [8, 12], 3, frozen_time, audience_partner_ids=[84])
            assert_song_positions(self, [(8, 1), (7, 1), (9, 1), (12, 1), (13, 1), (14, 1), (5, 1),
                                         (11, 1), (15, 1), (16, 1), (1, 3), (3, 2), (4, 2), (2, 3), (6, 2)])
            assert_dashboards(self, [
                ExpectedDashboard(singer=8, next_song=1, wait_amount=0),
                ExpectedDashboard(singer=7, next_song=1, wait_amount=1),
                ExpectedDashboard(singer=9, next_song=1, wait_amount=2),
                ExpectedDashboard(singer=12, next_song=1, wait_amount=3),
                ExpectedDashboard(singer=13, next_song=1, wait_amount=4),
                ExpectedDashboard(singer=14, next_song=1, wait_amount=5),
                ExpectedDashboard(singer=5, next_song=1, wait_amount=6),
                ExpectedDashboard(singer=11, primary_singer=8, next_song=1, wait_amount=0),
                ExpectedDashboard(singer=15, next_song=1, wait_amount=8),
                ExpectedDashboard(singer=16, next_song=1, wait_amount=9),
                ExpectedDashboard(singer=1, next_song=3, wait_amount=10),
                ExpectedDashboard(singer=3, next_song=2, wait_amount=11),
                ExpectedDashboard(singer=4, next_song=2, wait_amount=12),
                ExpectedDashboard(singer=2, primary_singer=9, next_song=1, wait_amount=2),
                ExpectedDashboard(singer=6, primary_singer=9, next_song=1, wait_amount=2),
            ])

            # 8 Sings duet with 11.
            set_performed(8, 1, frozen_time)
            assert_song_positions(self, [(7, 1), (9, 1), (12, 1), (13, 1), (14, 1), (5, 1),
                                         (11, 1), (15, 1), (16, 1), (1, 3), (3, 2), (4, 2), (2, 3), (6, 2)])

            # 7 sings
            set_performed(7, 1, frozen_time)
            assert_song_positions(self, [(9, 1), (12, 1), (13, 1), (14, 1), (5, 1),
                                         (11, 1), (15, 1), (16, 1), (1, 3), (3, 2), (4, 2), (2, 3), (6, 2), (7, 2)])

            # 9 Sings duet with 6
            set_performed(9, 1, frozen_time)
            assert_song_positions(self, [(12, 1), (13, 1), (14, 1), (5, 1), (11, 1), (15, 1), (16, 1),
                                         (1, 3), (3, 2), (4, 2), (2, 3), (6, 2), (7, 2), (9, 2)])

            # Singer 7 logs out
            logout(7)
            assert_song_positions(self, [(12, 1), (13, 1), (14, 1), (5, 1), (11, 1), (15, 1), (16, 1),
                                         (1, 3), (3, 2), (4, 2), (2, 3), (6, 2), (9, 2)])

            # 8 adds his second song. Appears after in his place after 6
            add_songs_to_singer(8, [2])
            assert_song_positions(self, [(12, 1), (13, 1), (14, 1), (5, 1), (11, 1), (15, 1), (16, 1),
                                         (1, 3), (3, 2), (4, 2), (2, 3), (6, 2), (8, 2), (9, 2)])

            # 12 Sings. Is dueting with 1, later on but still reappears on the list
            set_performed(12, 1, frozen_time)
            assert_song_positions(self, [(13, 1), (14, 1), (5, 1), (11, 1), (15, 1), (16, 1),
                                         (1, 3), (3, 2), (4, 2), (2, 3), (6, 2), (8, 2), (9, 2), (12, 2)])

            # Singers 13, 14, 5, 15, 16 sing.
            # Only 13 has an extra song and is put in the back of the list. The rest are done
            # 11 is skipped and so doesn't sing yet
            set_performed(13, 1, frozen_time)
            set_performed(14, 1, frozen_time)
            set_performed(5, 1, frozen_time)
            set_performed(15, 1, frozen_time)
            set_performed(16, 1, frozen_time)
            assert_song_positions(self, [(11, 1), (1, 3), (3, 2), (4, 2), (2, 3), (6, 2), (8, 2), (9, 2),
                                         (12, 2), (13, 2)])

            # Singer 7 logs back in. Its place is behind 8. When 7 logged out he was behind 7, but 8 was hidden
            # then since it had no songs. Originally it was behind 8.
            login(7)
            assert_song_positions(self, [(11, 1), (1, 3), (3, 2), (4, 2), (2, 3), (6, 2),
                                         (8, 2), (7, 2), (9, 2), (12, 2), (13, 2)])

            # 1 Duets with 12
            set_performed(1, 3, frozen_time)
            assert_song_positions(self, [(11, 1), (3, 2), (4, 2), (2, 3), (6, 2),
                                         (8, 2), (7, 2), (9, 2), (12, 2), (13, 2)])

            # Half the cycle sings. 2 and 8 sang their last song. 6 is skipped and stays at the front.
            set_performed(4, 2, frozen_time)
            set_performed(7, 2, frozen_time)
            set_performed(2, 3, frozen_time)
            set_performed(3, 2, frozen_time)
            set_performed(8, 2, frozen_time)
            set_performed(11, 1, frozen_time)
            assert_song_positions(self, [(6, 2), (9, 2), (12, 2), (13, 2),
                                         (4, 3), (7, 3), (3, 3), (11, 2)])

            # Almost full cycle sing. The singers who sang their last song are, 13, 12, 4, 3
            set_performed(9, 2, frozen_time)
            set_performed(6, 2, frozen_time)
            set_performed(13, 2, frozen_time)
            set_performed(12, 2, frozen_time)
            set_performed(4, 3, frozen_time)
            set_performed(7, 3, frozen_time)
            set_performed(3, 3, frozen_time)
            assert_song_positions(self,
                                  [(11, 2), (9, 3), (6, 3), (7, 4)])

            # Full cycle sing. 11 sang its last
            set_performed(11, 2, frozen_time)
            set_performed(9, 3, frozen_time)
            set_performed(6, 3, frozen_time)
            set_performed(7, 4, frozen_time)
            assert_song_positions(self,
                                  [(9, 4), (6, 4), (7, 5)])

            # All but last sing their final song
            set_performed(9, 4, frozen_time)
            set_performed(6, 4, frozen_time)
            assert_song_positions(self,
                                  [(7, 5)])

            # Last singer sings
            set_performed(7, 5)
            assert_song_positions(self, [])

    def test_scenario_with_swaps(self):
        def swap(singer_id1, singer_id2):
            Singer.ordering.swap_first_cycle_places(get_singer(singer_id1), get_singer(singer_id2))

        with freeze_time(TEST_START_TIME, auto_tick_seconds=5) as frozen_time:
            create_singers([1], frozen_time, num_songs=1)
            create_singers([2, 3, 4, 5, 6], frozen_time, num_songs=2)
            add_partners(4, [6], 1, frozen_time)
            assert_song_positions(self, [(1, 1), (2, 1), (3, 1), (4, 1), (5, 1), (6, 1)])

            # Singer 1 is up, and Shani has singer 4 go first instead
            swap(1, 4)
            assert_song_positions(self, [(4, 1), (2, 1), (3, 1), (1, 1), (5, 1), (6, 1)])

            set_performed(4, 1, frozen_time)
            assert_song_positions(self, [(2, 1), (3, 1), (1, 1), (5, 1), (6, 1), (4, 2)])

            # Singer 7 signs up late, after singer 4 sang, and swaps with singer 2 from the rush
            create_singers([7], frozen_time, num_songs=1)
            assert_song_positions(self, [(2, 1), (3, 1), (1, 1), (5, 1), (6, 1), (4, 2), (7, 1)])
            swap(2, 7)
            assert_song_positions(self, [(7, 1), (3, 1), (1, 1), (5, 1), (6, 1), (4, 2), (2, 1)])

            set_performed(7, 1, frozen_time)
            assert_song_positions(self, [(3, 1), (1, 1), (5, 1), (6, 1), (4, 2), (2, 1)])

            # Singer 1's only song goes to standby, taking them out of the line, and comes back to their swapped place
            set_standby(1, 1)
            assert_song_positions(self, [(3, 1), (5, 1), (6, 1), (4, 2), (2, 1)])
            unset_standby(1, 1)
            assert_song_positions(self, [(3, 1), (1, 1), (5, 1), (6, 1), (4, 2), (2, 1)])

            # Singer 1 deletes their only song and adds another one: they come back to their swapped place
            get_song(1, 1).delete()
            assert_song_positions(self, [(3, 1), (5, 1), (6, 1), (4, 2), (2, 1)])
            add_songs_to_singer(1, [2], frozen_time)
            assert_song_positions(self, [(3, 1), (1, 2), (5, 1), (6, 1), (4, 2), (2, 1)])

            # Singers 3 and 6 swap while singer 5 is logged out, and singer 5 comes back to their own place. Singer 6
            # sang only as singer 4's partner, so they still count as not having sung.
            logout(5)
            assert_song_positions(self, [(3, 1), (1, 2), (6, 1), (4, 2), (2, 1)])
            swap(3, 6)
            assert_song_positions(self, [(6, 1), (1, 2), (3, 1), (4, 2), (2, 1)])
            login(5)
            assert_song_positions(self, [(6, 1), (1, 2), (5, 1), (3, 1), (4, 2), (2, 1)])

            # Shani closes signup: everyone who hasn't sung is pulled ahead, keeping the swapped order
            disable_flag('CAN_SIGNUP')
            assert_song_positions(self, [(6, 1), (1, 2), (5, 1), (3, 1), (2, 1), (4, 2)])

            # Undoing the swap of singers 3 and 6 after closing signup puts both back, with nothing left of the swap
            swap(3, 6)
            assert_song_positions(self, [(3, 1), (1, 2), (5, 1), (6, 1), (2, 1), (4, 2)])
            for singer_id in (3, 6):
                self.assertIsNone(get_singer(singer_id).line_time)
                self.assertIsNone(get_singer(singer_id).swapped_with)

            # Singer 3 is up but not in the room, so Shani skips them. A skipped song keeps its position; only the
            # current song passes over it, so singer 1 is up.
            set_skipped(3, 1)
            assert_song_positions(self, [(3, 1), (1, 2), (5, 1), (6, 1), (2, 1), (4, 2)])
            assert_current_song(self, 1, 2)

            # Shani swaps singer 3 with singer 5, who is up now; the skip travels with singer 3
            swap(3, 5)
            assert_song_positions(self, [(5, 1), (1, 2), (3, 1), (6, 1), (2, 1), (4, 2)])
            assert_current_song(self, 5, 1)

            # Swapping back leaves singer 3 skipped, and unskipping makes them the current song again
            swap(3, 5)
            assert_song_positions(self, [(3, 1), (1, 2), (5, 1), (6, 1), (2, 1), (4, 2)])
            assert_current_song(self, 1, 2)
            set_unskipped(3, 1)
            assert_current_song(self, 3, 1)

            # Singer 1 is marked performed by mistake and then not performed: they return to their swapped place
            set_performed(1, 2, frozen_time)
            assert_song_positions(self, [(3, 1), (5, 1), (6, 1), (2, 1), (4, 2)])
            song = get_song(1, 2)
            song.performance_time = None
            song.save()
            assert_song_positions(self, [(3, 1), (1, 2), (5, 1), (6, 1), (2, 1), (4, 2)])

            # Once singer 1 really sings, they leave the list, having no other song
            set_performed(1, 2, frozen_time)
            assert_song_positions(self, [(3, 1), (5, 1), (6, 1), (2, 1), (4, 2)])


class TestDashboard(SongRequestTestCase):
    def test_partner_next_cycle(self):
        create_singers(2)
        add_songs_to_singers([1], 2)
        assert_song_positions(self,
                              [(1, 1)])
        assert_dashboards(self, [
            ExpectedDashboard(singer=1, next_song=1, wait_amount=0),
            ExpectedDashboard(singer=2, empty=True),
        ])

        add_partners(1, 2, 2)
        assert_dashboards(self, [
            ExpectedDashboard(singer=1, next_song=1, wait_amount=0),
            ExpectedDashboard(singer=2, primary_singer=1, next_song=2, wait_amount=None),
        ])

    def test_partner_bumped_up(self):
        create_singers(2)
        add_songs_to_singers([1], 2)
        set_performed(1, 1)
        add_songs_to_singers([2], 1)
        assert_song_positions(self,
                              [(1, 2), (2, 1)])
        assert_dashboards(self, [
            ExpectedDashboard(singer=1, next_song=2, wait_amount=0),
            ExpectedDashboard(singer=2, next_song=1, wait_amount=1),
        ])

        add_partners(1, 2, 2)
        assert_dashboards(self, [
            ExpectedDashboard(singer=1, next_song=2, wait_amount=0),
            ExpectedDashboard(singer=2, primary_singer=1, next_song=2, wait_amount=0),
        ])

    def test_bumped_up_chain(self):
        create_singers(4)
        add_songs_to_singers([1], 1)
        add_songs_to_singers([2], 1)
        add_songs_to_singers([3], 1)
        assert_song_positions(self,
                              [(1, 1), (2, 1), (3, 1)])
        assert_dashboards(self, [
            ExpectedDashboard(singer=1, next_song=1, wait_amount=0),
            ExpectedDashboard(singer=2, next_song=1, wait_amount=1),
            ExpectedDashboard(singer=3, next_song=1, wait_amount=2),
        ])

        add_partners(2, 3, 1)
        assert_dashboards(self, [
            ExpectedDashboard(singer=1, next_song=1, wait_amount=0),
            ExpectedDashboard(singer=2, next_song=1, wait_amount=1),
            ExpectedDashboard(singer=3, primary_singer=2, next_song=1, wait_amount=1),
        ])

        add_partners(1, 2, 1)
        assert_dashboards(self, [
            ExpectedDashboard(singer=1, next_song=1, wait_amount=0),
            ExpectedDashboard(singer=2, primary_singer=1, next_song=1, wait_amount=0),
            ExpectedDashboard(singer=3, primary_singer=2, next_song=1, wait_amount=1),
        ])


class TestOrderingTieBreak(SongRequestTestCase):
    """
    Singers whose times are equal (songs requested in the same instant, or performances in the same instant) line up
    by id. In each test singer 1 logs in again before the order is read, which makes the database return them last:
    without the id breaking the tie, they would end up after the others with the same time.
    """
    def test_same_request_time(self):
        with freeze_time(TEST_START_TIME) as frozen_time:
            create_singers(5)
            add_songs_to_singer(4, 1)
            frozen_time.tick()
            add_songs_to_singers([3, 1, 2], 1)  # The same instant
            frozen_time.tick()
            add_songs_to_singer(5, 1)
        login(1)
        assert_singers_in_disney(self, [4, 1, 2, 3, 5])
        assert_song_positions(self, [(4, 1), (1, 1), (2, 1), (3, 1), (5, 1)])
        disable_flag('CAN_SIGNUP')
        assert_singers_in_disney(self, [4, 1, 2, 3, 5])

    def test_same_performance_time(self):
        with freeze_time(TEST_START_TIME) as frozen_time:
            create_singers(3, num_songs=2)
            frozen_time.tick()
            set_performed(2, 1)  # The same instant
            set_performed(1, 1)
        login(1)
        # Singer 3 hasn't sung, then singers 1 and 2 by id
        assert_singers_in_disney(self, [3, 1, 2])
        disable_flag('CAN_SIGNUP')
        assert_singers_in_disney(self, [3, 1, 2])

    def test_performance_time_equal_to_request_time(self):
        # With signup open, singer 1's performance and singer 2's first request are in the same instant
        with freeze_time(TEST_START_TIME) as frozen_time:
            create_singers(2)
            add_songs_to_singer(1, 2)
            frozen_time.tick()
            set_performed(1, 1)
            add_songs_to_singer(2, 1)
        login(1)
        assert_singers_in_disney(self, [1, 2])


class TestSwapFirstCyclePlaces(SongRequestTestCase):
    def swap(self, singer_id1, singer_id2):
        Singer.ordering.swap_first_cycle_places(get_singer(singer_id1), get_singer(singer_id2))

    def assert_not_swapped(self, singer_id):
        singer = get_singer(singer_id)
        self.assertIsNone(singer.line_time)
        self.assertIsNone(singer.swapped_with)

    def assert_swapped(self, singer_id, swapped_with_id):
        """
        The singer swapped with swapped_with_id and holds their place: that singer's first request time.
        """
        singer = get_singer(singer_id)
        self.assertEqual(singer.swapped_with, get_singer(swapped_with_id))
        self.assertEqual(singer.line_time, get_singer(swapped_with_id).first_request_time)

    def test_swap_then_later_cycles_by_performance(self):
        with freeze_time(TEST_START_TIME, auto_tick_seconds=5) as frozen_time:
            create_singers(5, frozen_time, num_songs=2)
            assert_singers_in_disney(self, [1, 2, 3, 4, 5])

            self.swap(2, 4)
            assert_singers_in_disney(self, [1, 4, 3, 2, 5])
            assert_song_positions(self, [(1, 1), (4, 1), (3, 1), (2, 1), (5, 1)])
            self.assert_swapped(2, swapped_with_id=4)
            self.assert_swapped(4, swapped_with_id=2)

            set_performed(1, 1, frozen_time)
            assert_singers_in_disney(self, [4, 3, 2, 5, 1])
            set_performed(4, 1, frozen_time)
            assert_singers_in_disney(self, [3, 2, 5, 1, 4])

            # A latecomer lines up after those who already sang
            create_singers([6], frozen_time, num_songs=1)
            assert_singers_in_disney(self, [3, 2, 5, 1, 4, 6])
            set_performed(3, 1, frozen_time)
            set_performed(2, 1, frozen_time)
            set_performed(5, 1, frozen_time)
            assert_singers_in_disney(self, [1, 4, 6, 3, 2, 5])
            assert_song_positions(self, [(1, 2), (4, 2), (6, 1), (3, 2), (2, 2), (5, 2)])

    def test_swap_again_undoes(self):
        with freeze_time(TEST_START_TIME, auto_tick_seconds=5) as frozen_time:
            create_singers(4, frozen_time, num_songs=1)
            self.swap(1, 3)
            assert_singers_in_disney(self, [3, 2, 1, 4])
            self.swap(1, 3)
            assert_singers_in_disney(self, [1, 2, 3, 4])
            self.assert_not_swapped(1)
            self.assert_not_swapped(3)

    def test_chain_and_undoing_one_step(self):
        with freeze_time(TEST_START_TIME, auto_tick_seconds=5) as frozen_time:
            create_singers(4, frozen_time, num_songs=1)
            assert_singers_in_disney(self, [1, 2, 3, 4])

            self.swap(1, 2)
            assert_singers_in_disney(self, [2, 1, 3, 4])
            self.assert_swapped(1, swapped_with_id=2)
            self.assert_swapped(2, swapped_with_id=1)

            # Singer 1, now in singer 2's place, swaps with singer 3
            self.swap(1, 3)
            assert_singers_in_disney(self, [2, 3, 1, 4])
            self.assert_swapped(1, swapped_with_id=3)
            self.assert_swapped(2, swapped_with_id=1)
            # Singer 3 swapped with singer 1, who was holding singer 2's place by then
            self.assertEqual(get_singer(3).swapped_with, get_singer(1))
            self.assertEqual(get_singer(3).line_time, get_singer(2).first_request_time)

            # Swapping singers 1 and 3 again undoes the second swap: singer 3 is back in their own place, and singer 1
            # is back in singer 2's place, as after the first swap. Known issue, left as is: singer 1's swapped_with
            # still names singer 3, the last singer they swapped with, so the admin shows the wrong name. The order is
            # right.
            self.swap(1, 3)
            assert_singers_in_disney(self, [2, 1, 3, 4])
            self.assert_not_swapped(3)
            self.assert_swapped(2, swapped_with_id=1)
            self.assertEqual(get_singer(1).swapped_with, get_singer(3))
            self.assertEqual(get_singer(1).line_time, get_singer(2).first_request_time)

            # Undoing the first swap puts everyone back
            self.swap(1, 2)
            assert_singers_in_disney(self, [1, 2, 3, 4])
            self.assert_not_swapped(1)
            self.assert_not_swapped(2)

    def test_swap_with_signup_closed(self):
        with freeze_time(TEST_START_TIME, auto_tick_seconds=5) as frozen_time:
            create_singers(4, frozen_time, num_songs=2)
            set_performed(1, 1, frozen_time)
            create_singers([5], frozen_time, num_songs=1)
            # Singer 5 signed up after singer 1 sang, so with signup open they line up behind singer 1
            assert_singers_in_disney(self, [2, 3, 4, 1, 5])

            # Closing signup pulls singer 5 ahead of singer 1, who already sang
            disable_flag('CAN_SIGNUP')
            assert_singers_in_disney(self, [2, 3, 4, 5, 1])

            self.swap(2, 5)
            assert_singers_in_disney(self, [5, 3, 4, 2, 1])
            assert_song_positions(self, [(5, 1), (3, 1), (4, 1), (2, 1), (1, 2)])

    def test_swap_survives_opening_and_closing_signup(self):
        with freeze_time(TEST_START_TIME, auto_tick_seconds=5) as frozen_time:
            create_singers(2, frozen_time, num_songs=2)
            set_performed(1, 1, frozen_time)
            # Singer 3 signs up after singer 1 sang, so with signup open they line up behind singer 1
            create_singers([3], frozen_time, num_songs=1)
            assert_singers_in_disney(self, [2, 1, 3])

            # Singer 3 takes singer 2's place ahead of singer 1, and singer 2 takes singer 3's place behind them
            self.swap(2, 3)
            assert_singers_in_disney(self, [3, 1, 2])

            # Closing signup pulls singers 3 and 2 ahead of singer 1, who already sang, keeping the swapped order
            disable_flag('CAN_SIGNUP')
            assert_singers_in_disney(self, [3, 2, 1])

            # Reopening signup puts singer 2 back behind singer 1, still in singer 3's place
            enable_flag('CAN_SIGNUP')
            assert_singers_in_disney(self, [3, 1, 2])

    def test_deleting_the_oldest_song_keeps_the_swapped_place(self):
        with freeze_time(TEST_START_TIME, auto_tick_seconds=5) as frozen_time:
            create_singers(4, frozen_time, num_songs=2)
            original_time = get_singer(3).first_request_time
            assert_song_positions(self, [(1, 1), (2, 1), (3, 1), (4, 1)])
            self.swap(1, 3)
            assert_singers_in_disney(self, [3, 2, 1, 4])
            assert_song_positions(self, [(3, 1), (2, 1), (1, 1), (4, 1)])

            # Deleting their oldest song doesn't move singer 3; their next song takes the place
            get_song(3, 1).delete()
            assert_singers_in_disney(self, [3, 2, 1, 4])
            assert_song_positions(self, [(3, 2), (2, 1), (1, 1), (4, 1)])

            # Swapping back gives singer 3 their original place: the request time of the song they deleted.
            # Known issue, left as is: with that song gone, their first request time is now their second song's, so
            # the swap doesn't see them as back in their own place and doesn't clear it. Singer 3 keeps line_time and
            # swapped_with, and the admin still marks them as swapped with singer 1. The order is right.
            self.swap(1, 3)
            assert_singers_in_disney(self, [1, 2, 3, 4])
            assert_song_positions(self, [(1, 1), (2, 1), (3, 2), (4, 1)])
            self.assert_not_swapped(1)
            self.assertEqual(get_singer(3).line_time, original_time)
            self.assertEqual(get_singer(3).swapped_with, get_singer(1))

    def test_deleting_all_songs_and_adding_one_keeps_the_swapped_place(self):
        with freeze_time(TEST_START_TIME, auto_tick_seconds=5) as frozen_time:
            create_singers(4, frozen_time, num_songs=1)
            assert_song_positions(self, [(1, 1), (2, 1), (3, 1), (4, 1)])
            self.swap(1, 3)
            assert_song_positions(self, [(3, 1), (2, 1), (1, 1), (4, 1)])

            get_song(1, 1).delete()
            assert_song_positions(self, [(3, 1), (2, 1), (4, 1)])
            add_songs_to_singer(1, [2], frozen_time)
            assert_song_positions(self, [(3, 1), (2, 1), (1, 2), (4, 1)])

    def test_skip_travels_with_the_singer(self):
        with freeze_time(TEST_START_TIME, auto_tick_seconds=5) as frozen_time:
            create_singers(3, frozen_time, num_songs=1)
            set_skipped(3, 1)
            assert_song_positions(self, [(1, 1), (2, 1), (3, 1)])
            assert_current_song(self, 1, 1)

            self.swap(1, 3)
            assert_song_positions(self, [(3, 1), (2, 1), (1, 1)])
            assert_current_song(self, 2, 1)

    def test_skipped_singer_swapped_down_the_line_is_still_skipped_there(self):
        with freeze_time(TEST_START_TIME, auto_tick_seconds=5) as frozen_time:
            create_singers(4, frozen_time, num_songs=1)

            # Singer 1 is up but not in the room, so Shani skips them
            set_skipped(1, 1)
            assert_song_positions(self, [(1, 1), (2, 1), (3, 1), (4, 1)])
            assert_current_song(self, 2, 1)

            # Shani swaps singer 1 with singer 3, moving the skipped singer down the line
            self.swap(1, 3)
            assert_song_positions(self, [(3, 1), (2, 1), (1, 1), (4, 1)])
            assert_current_song(self, 3, 1)

            set_performed(3, 1, frozen_time)
            assert_song_positions(self, [(2, 1), (1, 1), (4, 1)])
            assert_current_song(self, 2, 1)

            # When singer 1's turn comes, they're still skipped, so singer 4 is up
            set_performed(2, 1, frozen_time)
            assert_song_positions(self, [(1, 1), (4, 1)])
            assert_current_song(self, 4, 1)

    def test_dashboards_follow_the_swap(self):
        with freeze_time(TEST_START_TIME, auto_tick_seconds=5) as frozen_time:
            create_singers(3, frozen_time, num_songs=1)
            assert_song_positions(self, [(1, 1), (2, 1), (3, 1)])
            assert_dashboards(self, [
                ExpectedDashboard(singer=1, next_song=1, wait_amount=0),
                ExpectedDashboard(singer=2, next_song=1, wait_amount=1),
                ExpectedDashboard(singer=3, next_song=1, wait_amount=2),
            ])

            self.swap(1, 3)
            assert_song_positions(self, [(3, 1), (2, 1), (1, 1)])
            assert_dashboards(self, [
                ExpectedDashboard(singer=3, next_song=1, wait_amount=0),
                ExpectedDashboard(singer=2, next_song=1, wait_amount=1),
                ExpectedDashboard(singer=1, next_song=1, wait_amount=2),
            ])


class TestSwapPlacesAdmin(SongRequestTestCase):
    def run_swap_action(self, ticked_songs, order_by='position'):
        """
        Runs the Swap places action on the songs Shani ticked. Returns the mocked admin messages, to check whether the
        action refused.
        """
        from song_signup.admin import swap_places
        queryset = SongRequest.objects.filter(pk__in=[song.pk for song in ticked_songs]).order_by(order_by)
        with patch('song_signup.admin.messages') as mock_messages:
            swap_places(None, None, queryset)
        return mock_messages

    def swap_icon(self, singer_id, song_num):
        from django.contrib import admin
        from song_signup.admin import SongRequestAdmin
        return SongRequestAdmin(SongRequest, admin.site).get_swapped(get_song(singer_id, song_num))

    def swapped_with_column(self, singer_id, song_num):
        from django.contrib import admin
        from song_signup.admin import SongRequestAdmin
        return SongRequestAdmin(SongRequest, admin.site).get_swapped_with(get_song(singer_id, song_num))

    def test_swaps_two_songs(self):
        with freeze_time(TEST_START_TIME, auto_tick_seconds=5) as frozen_time:
            create_singers(3, frozen_time, num_songs=1)
        assert_song_positions(self, [(1, 1), (2, 1), (3, 1)])
        mock_messages = self.run_swap_action([get_song(1, 1), get_song(3, 1)])
        mock_messages.error.assert_not_called()
        assert_song_positions(self, [(3, 1), (2, 1), (1, 1)])

    def test_order_of_the_selected_songs_does_not_matter(self):
        with freeze_time(TEST_START_TIME, auto_tick_seconds=5) as frozen_time:
            create_singers(3, frozen_time, num_songs=1)
        times = {singer_id: get_singer(singer_id).first_request_time for singer_id in (1, 3)}
        assert_song_positions(self, [(1, 1), (2, 1), (3, 1)])

        for order_by in ('position', '-position'):
            self.run_swap_action([get_song(1, 1), get_song(3, 1)], order_by=order_by)
            assert_song_positions(self, [(3, 1), (2, 1), (1, 1)])
            self.assertEqual(get_singer(1).line_time, times[3])
            self.assertEqual(get_singer(3).line_time, times[1])
            self.assertEqual(get_singer(1).swapped_with, get_singer(3))
            self.assertEqual(get_singer(3).swapped_with, get_singer(1))

            # Swap back for the next order
            self.run_swap_action([get_song(1, 1), get_song(3, 1)], order_by=order_by)
            assert_song_positions(self, [(1, 1), (2, 1), (3, 1)])

    def test_refuses_a_singer_who_sang(self):
        with freeze_time(TEST_START_TIME, auto_tick_seconds=5) as frozen_time:
            create_singers(3, frozen_time, num_songs=2)
            set_performed(1, 1, frozen_time)
        assert_song_positions(self, [(2, 1), (3, 1), (1, 2)])
        mock_messages = self.run_swap_action([get_song(1, 2), get_song(3, 1)])
        mock_messages.error.assert_called_once()
        assert_song_positions(self, [(2, 1), (3, 1), (1, 2)])

    def test_singer_who_sang_only_as_partner_can_swap(self):
        with freeze_time(TEST_START_TIME, auto_tick_seconds=5) as frozen_time:
            create_singers(3, frozen_time, num_songs=1)
            add_partners(1, [3], 1, frozen_time)
            set_performed(1, 1, frozen_time)
        assert_song_positions(self, [(2, 1), (3, 1)])
        mock_messages = self.run_swap_action([get_song(2, 1), get_song(3, 1)])
        mock_messages.error.assert_not_called()
        assert_song_positions(self, [(3, 1), (2, 1)])

    def test_refuses_a_song_not_in_the_setlist(self):
        with freeze_time(TEST_START_TIME, auto_tick_seconds=5) as frozen_time:
            create_singers(3, frozen_time, num_songs=2)
        assert_song_positions(self, [(1, 1), (2, 1), (3, 1)])
        mock_messages = self.run_swap_action([get_song(1, 2), get_song(3, 1)])
        mock_messages.error.assert_called_once()
        assert_song_positions(self, [(1, 1), (2, 1), (3, 1)])

    def test_refuses_more_than_two_songs(self):
        with freeze_time(TEST_START_TIME, auto_tick_seconds=5) as frozen_time:
            create_singers(3, frozen_time, num_songs=1)
        assert_song_positions(self, [(1, 1), (2, 1), (3, 1)])
        mock_messages = self.run_swap_action([get_song(1, 1), get_song(2, 1), get_song(3, 1)])
        mock_messages.error.assert_called_once()
        assert_song_positions(self, [(1, 1), (2, 1), (3, 1)])

    def test_refuses_fewer_than_two_songs(self):
        with freeze_time(TEST_START_TIME, auto_tick_seconds=5) as frozen_time:
            create_singers(3, frozen_time, num_songs=1)
        assert_song_positions(self, [(1, 1), (2, 1), (3, 1)])
        mock_messages = self.run_swap_action([get_song(1, 1)])
        mock_messages.error.assert_called_once()
        assert_song_positions(self, [(1, 1), (2, 1), (3, 1)])

    def test_icon_on_the_swapped_turn(self):
        with freeze_time(TEST_START_TIME, auto_tick_seconds=5) as frozen_time:
            create_singers(3, frozen_time, num_songs=2)
            self.run_swap_action([get_song(1, 1), get_song(3, 1)])
            assert_song_positions(self, [(3, 1), (2, 1), (1, 1)])
            self.assertIn(get_singer_str(3), self.swap_icon(1, 1))
            self.assertIn(get_singer_str(1), self.swap_icon(3, 1))
            self.assertIsNone(self.swap_icon(1, 2))
            self.assertIsNone(self.swap_icon(2, 1))
            self.assertEqual(self.swapped_with_column(1, 1), get_singer(3))
            self.assertIsNone(self.swapped_with_column(1, 2))

            # Once singer 3 sings, the icon stays on the song they sang, and not on their next one
            set_performed(3, 1, frozen_time)
            assert_song_positions(self, [(2, 1), (1, 1), (3, 2)])
            self.assertIsNotNone(self.swap_icon(3, 1))
            self.assertIsNone(self.swap_icon(3, 2))

    def test_icon_leaves_and_returns_with_standby(self):
        with freeze_time(TEST_START_TIME, auto_tick_seconds=5) as frozen_time:
            create_singers(3, frozen_time, num_songs=1)
            self.run_swap_action([get_song(1, 1), get_song(3, 1)])
            assert_song_positions(self, [(3, 1), (2, 1), (1, 1)])
            set_standby(1, 1)
            assert_song_positions(self, [(3, 1), (2, 1)])
            self.assertIsNone(self.swap_icon(1, 1))
            unset_standby(1, 1)
            assert_song_positions(self, [(3, 1), (2, 1), (1, 1)])
            self.assertIsNotNone(self.swap_icon(1, 1))


class TestSongActionsDropdown(SongRequestTestCase):
    def test_actions_in_order_with_a_separator_before_the_undos(self):
        from django.contrib import admin
        from django.test import RequestFactory
        from song_signup.admin import SongRequestAdmin

        request = RequestFactory().get('/admin/song_signup/songrequest/')
        request.user = Singer.objects.create_superuser(username='admin_user', password='admin_password')
        song_admin = SongRequestAdmin(SongRequest, admin.site)

        self.assertEqual([name for name, _ in song_admin.get_action_choices(request)], [
            '',
            'set_solo_performed', 'set_solo_skipped', 'spotlight', 'swap_places', 'set_standby',
            '',
            'set_solo_not_performed', 'set_solo_unskipped', 'unset_standby', 'set_peoples_choice',
            'unset_peoples_choice', 'force_lyrics_refresh',
        ])

        # Every choice but the two empty ones runs the action of the same name
        actions = song_admin.get_actions(request)
        for name, _ in song_admin.get_action_choices(request):
            if name:
                self.assertEqual(actions[name][0].__name__, name)
