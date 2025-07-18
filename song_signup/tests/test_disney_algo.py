from freezegun import freeze_time
from mock import patch

from song_signup.models import Singer, SongRequest
from song_signup.tests.utils_for_tests import (
    SongRequestTestCase, TEST_START_TIME, create_singers, assert_singers_in_disney,
    set_performed, add_partners, add_songs_to_singers, get_singer, assert_song_positions, add_songs_to_singer,
    login, logout, create_audience, get_song, set_standby, unset_standby,
    ExpectedDashboard, assert_dashboards, logout_audience, assert_current_song
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
