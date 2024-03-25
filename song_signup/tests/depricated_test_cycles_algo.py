from mock import patch, MagicMock

from song_signup.models import Singer
from song_signup.tests.test_utils import (
    create_singers, get_singer, assign_positions_cycles,
    add_songs_to_singers, add_singers_to_cycle, add_duet,
    assert_singers_in_queryset, assert_singers_in_cycles, assert_song_positions_cycles,
    SongRequestTestCase, PLACEHOLDER
)


class TestCycleManager(SongRequestTestCase):
    @patch('song_signup.managers.FIRST_CYCLE_LEN', 4)
    @patch('song_signup.models.Singer._add_to_cycle', MagicMock())
    def test_cy_funcs(self):
        create_singers(10)
        cy1_singers = [1, 2, 3, 4]
        cy2_singers = [5, 1, 6, 2, 7, 3, 8, 4]
        lscy_singers = [9, 10]
        cy3_singers = [5, 1, 6, 2, 7, 3, 8, 4]

        assign_positions_cycles([
            cy1_singers,
            cy2_singers,
            lscy_singers,
            cy3_singers
        ])

        assert_singers_in_cycles(self, [cy1_singers, cy2_singers, lscy_singers, cy3_singers])
        assert_singers_in_queryset(self, Singer.ordering.new_singers_cy2(), [5, 6, 7, 8])

    @patch('song_signup.models.Singer._add_to_cycle', MagicMock())
    def test_next_pos_cy1(self):
        create_singers(6)
        assign_positions_cycles([[3, 4, 5, 6]])
        self.assertEqual(Singer.ordering.next_pos_cy1(), 5)

    @patch('song_signup.models.Singer._add_to_cycle', MagicMock())
    def test_first_pos_cy1(self):
        self.assertEqual(Singer.ordering.next_pos_cy1(), 1)

    @patch('song_signup.models.Singer._add_to_cycle', MagicMock())
    def test_next_pos_lscy(self):
        create_singers(10)
        assign_positions_cycles([[], [], [9, 10], []])
        self.assertEqual(Singer.ordering.next_pos_lscy(), 3)

    @patch('song_signup.models.Singer._add_to_cycle', MagicMock())
    def test_first_next_pos_lscy(self):
        self.assertEqual(Singer.ordering.next_pos_lscy(), 1)

    @patch('song_signup.models.Singer._add_to_cycle', MagicMock())
    def test_next_new_singer_cy2(self):
        create_singers(4)

        # No new singers in cycle 2 yet
        singer1 = get_singer(1)
        singer1.cy1_position = 1
        singer1.cy2_position = 2
        singer1.save()

        singer2 = get_singer(2)
        singer2.cy1_position = 2
        singer2.cy2_position = 4
        singer2.save()

        self.assertEqual(Singer.ordering.next_new_singer_pos_cy2(), 1)

        # First new singer
        singer3 = get_singer(3)
        singer3.cy2_position = 1
        singer3.save()
        self.assertEqual(Singer.ordering.next_new_singer_pos_cy2(), 3)

        # Second new singer
        singer4 = get_singer(4)
        singer4.cy2_position = 3
        singer4.save()
        self.assertEqual(Singer.ordering.next_new_singer_pos_cy2(), 5)

    @patch('song_signup.managers.FIRST_CYCLE_LEN', 4)
    @patch('song_signup.models.Singer._add_to_cycle', MagicMock())
    def test_cy1_full(self):
        create_singers(4)
        assign_positions_cycles([[1, 2, 3, 4]])
        self.assertTrue(Singer.ordering.cy1_full())

    @patch('song_signup.managers.FIRST_CYCLE_LEN', 4)
    @patch('song_signup.models.Singer._add_to_cycle', MagicMock())
    def test_cy1_not_full(self):
        create_singers(4)
        assign_positions_cycles([[1, 2, 3]])
        self.assertFalse(Singer.ordering.cy1_full())

    @patch('song_signup.managers.FIRST_CYCLE_LEN', 4)
    @patch('song_signup.models.Singer._add_to_cycle', MagicMock())
    def test_cy2_full(self):
        create_singers(8)
        assign_positions_cycles([
            [1, 2, 3, 4],
            [5, 1, 6, 2, 7, 3, 8, 4],
        ])
        self.assertTrue(Singer.ordering.cy2_full())

    @patch('song_signup.managers.FIRST_CYCLE_LEN', 4)
    @patch('song_signup.models.Singer._add_to_cycle', MagicMock())
    def test_cy2_almost_full(self):
        create_singers(8)
        assign_positions_cycles([
            [1, 2, 3, 4],
            [5, 1, 6, 2, 7, 3, 4],
        ])
        self.assertFalse(Singer.ordering.cy2_full())

    @patch('song_signup.managers.FIRST_CYCLE_LEN', 4)
    @patch('song_signup.models.Singer._add_to_cycle', MagicMock())
    def test_cy2_empty(self):
        create_singers(8)
        assign_positions_cycles([
            [1, 2, 3, 4],
            [1, 2, 3, 4],
        ])
        self.assertFalse(Singer.ordering.cy2_full())


class TestCalculatePositions3Cycles(SongRequestTestCase):
    @patch('song_signup.managers.FIRST_CYCLE_LEN', 4)
    @patch('song_signup.models.Singer._add_to_cycle', MagicMock())
    def test_all_singers_have_songs(self):
        create_singers(10)
        assign_positions_cycles([
            [1, 2, 3, 4],
            [5, 1, 6, 2, 7, 3, 8, 4],
            [9, 10],
            [5, 1, 6, 2, 7, 3, 8, 4]
        ])
        add_songs_to_singers(10, 3)
        # Adding songs invokes the calculate_positions method

        assert_song_positions_cycles(self, [
            [
                (1, 1),
                (2, 1),
                (3, 1),
                (4, 1)
            ],
            [
                (5, 1),
                (1, 2),
                (6, 1),
                (2, 2),
                (7, 1),
                (3, 2),
                (8, 1),
                (4, 2),
            ],
            [
                (9, 1),
                (10, 1)
            ],
            [
                (5, 2),
                (1, 3),
                (6, 2),
                (2, 3),
                (7, 2),
                (3, 3),
                (8, 2),
                (4, 3)
            ],
            [
                (9, 2),
                (10, 2),
                (5, 3),
                (6, 3),
                (7, 3),
                (8, 3),
            ],
            [
                (9, 3),
                (10, 3)
            ]
        ])

    @patch('song_signup.managers.FIRST_CYCLE_LEN', 4)
    @patch('song_signup.models.Singer._add_to_cycle', MagicMock())
    def test_some_singers_have_songs(self):
        create_singers(11)
        assign_positions_cycles([
            [1, 2, 3, 4],
            [5, 1, 6, 2, 7, 3, 8, 4],
            [9, 10],
            [11, 5, 1, 6, 2, 7, 3, 8, 4]
        ])
        add_songs_to_singers([1, 5, 6], 3)
        add_songs_to_singers([4, 7, 9], 2)
        add_songs_to_singers([3, 8, 10], 1)
        # Adding songs invokes the calculate_positions method

        assert_song_positions_cycles(self, [
            [
                (1, 1),
                (3, 1),
                # 2 doesn't have any songs
                (4, 1)
            ],
            [
                (5, 1),
                (1, 2),
                (6, 1),
                # 2 doesn't have any songs
                (7, 1),
                # 3 is out of songs (had 1)
                (8, 1),
                (4, 2),
            ],
            [
                (9, 1),
                (10, 1)
            ],
            [
                # 11 doesn't have any songs
                (5, 2),
                (1, 3),
                (6, 2),
                # 2 doesn't have any songs
                (7, 2),
                # 3 ran out of songs last cycle
                # 8 is out of songs (had 1)
                # 4 is out of songs (had 2)
            ],
            [
                (9, 2),
                (5, 3),
                (6, 3),
            ]
        ])

    @patch('song_signup.managers.FIRST_CYCLE_LEN', 4)
    @patch('song_signup.models.Singer._add_to_cycle', MagicMock())
    def test_duets(self):
        create_singers(10)
        assign_positions_cycles([
            [1, 2, 3, 4],
            [5, 1, 6, 2, 7, 3, 8, 4],
            [9, 10],
            [5, 1, 6, 2, 7, 3, 8, 4]
        ])
        add_songs_to_singers(10, 3)
        # Cycle 2 duets
        add_duet(6, 1, 2)
        add_duet(2, 5, 1)
        add_duet(4, 7, 1)
        add_duet(3, 8, 2)

        # Cycle 3 duets
        add_duet(5, 9, 1)
        add_duet(2, 10, 1)
        add_duet(3, 7, 2)
        # Adding songs invokes the calculate_positions method

        assert_song_positions_cycles(self, [
            [
                (1, 1),
                (2, 1),
                (3, 1),
                (4, 1)
            ],
            [
                (5, 1),
                (1, 2),
                # 6 Doesn't sing - had a duet with 1
                # 2 Doesn't sing - had a duet with 5.
                (7, 1),
                (3, 2),
                (8, 1),  # Sings even though duets with 3. We don't penalize 8 even though 3 sung already.
                # 4 Doesn't sing - had a duet with 7
            ],
            [
                (9, 1),
                (10, 1),
            ],
            [
                # 5 Doesn't sing - had a duet with 9
                (1, 3),
                (6, 1),
                # 2 Doesn't sing - had a duet with 10
                (7, 2),
                # 3 Doesn't sing - had a duet with 7
                (8, 2),
                (4, 2)
            ],
            # Next cycle, previous duetters are given their slots back
            [
                (9, 2),
                (10, 2),
                (5, 2),
                (6, 2),
                (2, 2),
                (7, 3),
                (3, 3),
                (8, 3),
                (4, 3)
            ],
            [
                (9, 3),
                (10, 3),
                (5, 3),
                (6, 3),
                (2, 3),
            ]
        ])

    @patch('song_signup.managers.FIRST_CYCLE_LEN', 4)
    @patch('song_signup.models.Singer._add_to_cycle', MagicMock())
    def test_third_cycle_repeat(self):
        create_singers(10)
        assign_positions_cycles([
            [1, 2, 3, 4],
            [5, 1, 6, 2, 7, 3, 8, 4],
            [9, 10],
            [5, 1, 6, 2, 7, 3, 8, 4]
        ])

        add_songs_to_singers([3, 4, 6, 7, 8], 3)
        add_songs_to_singers([2, 5, 9], 4)
        add_songs_to_singers([1, 10], 5)

        assert_song_positions_cycles(self, [
            [
                (1, 1),
                (2, 1),
                (3, 1),
                (4, 1)
            ],
            [
                (5, 1),
                (1, 2),
                (6, 1),
                (2, 2),
                (7, 1),
                (3, 2),
                (8, 1),
                (4, 2),
            ],
            [
                (9, 1),
                (10, 1)
            ],
            [
                (5, 2),
                (1, 3),
                (6, 2),
                (2, 3),
                (7, 2),
                (3, 3),
                (8, 2),
                (4, 3)
            ],
            # Cycle 3.1
            [
                (9, 2),
                (10, 2),
                (5, 3),
                (1, 4),
                (6, 3),
                (2, 4),
                (7, 3),
                (8, 3),
            ],
            # Cycle 3.2
            [
                (9, 3),
                (10, 3),
                (5, 4),
                (1, 5),
            ],
            # Cycle 3.3
            [
                (9, 4),
                (10, 4),
            ],
            # Cycle 4.4
            [
                (10, 5)
            ]
        ])


class TestPlaceholders(SongRequestTestCase):
    @patch('song_signup.managers.FIRST_CYCLE_LEN', 4)
    @patch('song_signup.models.Singer._add_to_cycle', MagicMock())
    def test_one_singer(self):
        create_singers(1)

        assign_positions_cycles([
            [1],
            [None, 1],
            [],
            [None, 1],
        ])
        add_songs_to_singers([1], 2)

        assert_song_positions_cycles(self, [
            [
                (1, 1),
            ],
            [
                PLACEHOLDER,
                (1, 2),
            ]
        ])

    @patch('song_signup.managers.FIRST_CYCLE_LEN', 4)
    @patch('song_signup.models.Singer._add_to_cycle', MagicMock())
    def test_two_singers(self):
        create_singers(2)

        assign_positions_cycles([
            [1, 2],
            [None, 1, None, 2],
        ])
        add_songs_to_singers([1, 2], 2)

        assert_song_positions_cycles(self, [
            [
                (1, 1),
                (2, 1),
            ],
            [
                PLACEHOLDER,
                (1, 2),
                PLACEHOLDER,
                (2, 2),
            ]
        ])

    @patch('song_signup.managers.FIRST_CYCLE_LEN', 4)
    @patch('song_signup.models.Singer._add_to_cycle', MagicMock())
    def test_first_cycle_full(self):
        create_singers(4)

        assign_positions_cycles([
            [1, 2, 3, 4],
            [None, 1, None, 2, None, 3, None, 4],
        ])
        add_songs_to_singers([1, 2, 3, 4], 2)

        assert_song_positions_cycles(self, [
            [
                (1, 1),
                (2, 1),
                (3, 1),
                (4, 1),
            ],
            [
                PLACEHOLDER,
                (1, 2),
                PLACEHOLDER,
                (2, 2),
                PLACEHOLDER,
                (3, 2),
                PLACEHOLDER,
                (4, 2),
            ]
        ])

    @patch('song_signup.managers.FIRST_CYCLE_LEN', 4)
    @patch('song_signup.models.Singer._add_to_cycle', MagicMock())
    def test_first_cycle_full_songs_missing(self):
        create_singers(4)

        assign_positions_cycles([
            [1, 2, 3, 4],
            [None, 1, None, 2, None, 3, None, 4],
        ])
        add_songs_to_singers([2, 3], 1)
        add_songs_to_singers([1, 4], 2)

        assert_song_positions_cycles(self, [
            [
                (1, 1),
                (2, 1),
                (3, 1),
                (4, 1),
            ],
            [
                PLACEHOLDER,
                (1, 2),
                PLACEHOLDER,
                PLACEHOLDER,
                PLACEHOLDER,
                (4, 2),
            ]
        ])

    @patch('song_signup.managers.FIRST_CYCLE_LEN', 4)
    @patch('song_signup.models.Singer._add_to_cycle', MagicMock())
    def test_second_cycle_incomplete(self):
        create_singers(6)

        assign_positions_cycles([
            [1, 2, 3, 4],
            [5, 1, 6, 2, None, 3, None, 4],
        ])
        add_songs_to_singers([1, 2, 3, 4], 2)
        add_songs_to_singers([5, 6], 1)

        assert_song_positions_cycles(self, [
            [
                (1, 1),
                (2, 1),
                (3, 1),
                (4, 1),
            ],
            [
                (5, 1),
                (1, 2),
                (6, 1),
                (2, 2),
                PLACEHOLDER,
                (3, 2),
                PLACEHOLDER,
                (4, 2),
            ]
        ])

    @patch('song_signup.managers.FIRST_CYCLE_LEN', 4)
    @patch('song_signup.models.Singer._add_to_cycle', MagicMock())
    def test_second_cycle_full(self):
        create_singers(9)

        assign_positions_cycles([
            [1, 2, 3, 4],
            [5, 1, 6, 2, 7, 3, 8, 4],
            [9],
        ])
        add_songs_to_singers([1, 2, 3, 4], 2)
        add_songs_to_singers([5, 6, 7, 8, 9], 1)

        assert_song_positions_cycles(self, [
            [
                (1, 1),
                (2, 1),
                (3, 1),
                (4, 1),
            ],
            [
                (5, 1),
                (1, 2),
                (6, 1),
                (2, 2),
                (7, 1),
                (3, 2),
                (8, 1),
                (4, 2),
            ],
            [
                (9, 1)
            ]
        ])

    @patch('song_signup.managers.FIRST_CYCLE_LEN', 4)
    @patch('song_signup.models.Singer._add_to_cycle', MagicMock())
    def test_second_cycle_veteran_songs_missing(self):
        create_singers(9)

        assign_positions_cycles([
            [1, 2, 3, 4],
            [5, 1, 6, 2, 7, 3, 8, 4],
            [9],
        ])
        add_songs_to_singers([1, 3, 4], 2)
        add_songs_to_singers([5, 6, 7, 8, 9, 2], 1)

        assert_song_positions_cycles(self, [
            [
                (1, 1),
                (2, 1),
                (3, 1),
                (4, 1),
            ],
            [
                (5, 1),
                (1, 2),
                (6, 1),
                (7, 1),
                (3, 2),
                (8, 1),
                (4, 2),
            ],
            [
                (9, 1)
            ]
        ])

    @patch('song_signup.managers.FIRST_CYCLE_LEN', 4)
    @patch('song_signup.models.Singer._add_to_cycle', MagicMock())
    def test_second_cycle_new_songs_missing(self):
        create_singers(10)

        assign_positions_cycles([
            [1, 2, 3, 4],
            [5, 1, 6, 2, 7, 3, 8, 4],
            [9, 10],
        ])
        add_songs_to_singers([1, 3, 4], 2)
        add_songs_to_singers([5, 7, 9, 2], 1)

        assert_song_positions_cycles(self, [
            [
                (1, 1),
                (2, 1),
                (3, 1),
                (4, 1),
            ],
            [
                (5, 1),
                (1, 2),
                (7, 1),
                (3, 2),
                (4, 2),
            ],
            [
                (9, 1)
            ]
        ])

        # New singer adds a first song later
        add_songs_to_singers([6], 1)
        assert_song_positions_cycles(self, [
            [
                (1, 1),
                (2, 1),
                (3, 1),
                (4, 1),
            ],
            [
                (5, 1),
                (1, 2),
                (6, 1),
                (7, 1),
                (3, 2),
                (4, 2),
            ],
            [
                (9, 1)
            ]
        ])


class TestAddToCycle(SongRequestTestCase):
    @patch('song_signup.managers.FIRST_CYCLE_LEN', 4)
    def test_add_to_cycle(self):
        create_singers(11)
        superuser = get_singer(11)
        superuser.is_superuser = True
        superuser.save()  # Superusers don't get assigned to any cycles

        expected_cy1_singers = [1, 2, 3, 4]
        expected_cy2_singers = [5, 1, 6, 2, 7, 3, 8, 4]
        expected_lscy_singers = [9, 10]
        expected_cy3_singers = [5, 1, 6, 2, 7, 3, 8, 4]

        add_singers_to_cycle(11)

        assert_singers_in_cycles(self, [expected_cy1_singers, expected_cy2_singers,
                                        expected_lscy_singers, expected_cy3_singers])
        self.assertIsNone(superuser.cy1_position)
        self.assertIsNone(superuser.cy2_position)
        self.assertIsNone(superuser.lscy_position)
        self.assertIsNone(superuser.cy3_position)

    @patch('song_signup.managers.FIRST_CYCLE_LEN', 4)
    def test_add_to_cycle_in_stages(self):
        create_singers(12)

        add_singers_to_cycle([1, 2])
        assert_singers_in_cycles(self, [[1, 2], [1, 2], [], [1, 2]])

        add_singers_to_cycle([3, 4])
        assert_singers_in_cycles(self, [[1, 2, 3, 4], [1, 2, 3, 4], [], [1, 2, 3, 4]])

        add_singers_to_cycle([5])
        assert_singers_in_cycles(self, [[1, 2, 3, 4], [5, 1, 2, 3, 4], [], [5, 1, 2, 3, 4]])

        add_singers_to_cycle([6, 7, 8])
        assert_singers_in_cycles(self, [[1, 2, 3, 4], [5, 1, 6, 2, 7, 3, 8, 4], [], [5, 1, 6, 2, 7, 3, 8, 4]])

        add_singers_to_cycle([9])
        assert_singers_in_cycles(self, [[1, 2, 3, 4], [5, 1, 6, 2, 7, 3, 8, 4], [9], [5, 1, 6, 2, 7, 3, 8, 4]])

        add_singers_to_cycle([10, 11, 12])
        assert_singers_in_cycles(self,
                                 [[1, 2, 3, 4], [5, 1, 6, 2, 7, 3, 8, 4], [9, 10, 11, 12], [5, 1, 6, 2, 7, 3, 8, 4]])




