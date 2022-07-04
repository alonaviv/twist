from itertools import chain
from typing import List

from django.test import TestCase
from mock import patch, MagicMock

from song_signup.managers import LATE_SINGER_CYCLE
from song_signup.models import Singer, SongRequest

CYCLE_NAMES = ['cy1', 'cy2', 'lscy', 'cy3']
PLACEHOLDER = 'PLACEHOLDER'


def _create_singers(num):
    for i in range(1, num + 1):
        Singer.objects.create_user(
            username=f"user_{i}",
            first_name=f"user_{i}",
            last_name="last_name",
            is_staff=True,
        )


def _get_singer(singer_id):
    return Singer.objects.get(username=f"user_{singer_id}")


def _get_song(singer_id, song_num):
    return SongRequest.objects.get(song_name=f"song_{singer_id}_{song_num}")


def _assign_positions(singer_positions):
    """
    Receives a list of 3 tuples, one for each cycle, that lists the order of the singer ids in that cycle.
    If None appears in the list, skips that position number and moves on
    """
    for singer_list, cy_name in zip(singer_positions, CYCLE_NAMES):
        position = 1
        for singer_id in singer_list:
            if singer_id is not None:
                singer = _get_singer(singer_id)
                setattr(singer, f'{cy_name}_position', position)
                singer.save()
            position += 1


def _add_songs_to_singer(singer_id, num_songs):
    singer = _get_singer(singer_id)

    for song_num in range(1, num_songs + 1):
        SongRequest.objects.create(song_name=f"song_{singer_id}_{song_num}", singer=singer)


def _add_songs_to_singers(singers, num_songs):
    """
    Can either pass a list of ints, or the num of singers to be generated
    """
    if isinstance(singers, int):
        singers = range(1, singers + 1)

    for singer_id in singers:
        _add_songs_to_singer(singer_id, num_songs)


def _add_singers_to_cycle(singers):
    """
    Adds the given number of singers to the cycle, according to ascending order.
    Alternatively, receives a list of the specific singer ids to use
    """
    if isinstance(singers, int):
        singers = range(1, singers + 1)

    for singer_id in singers:
        singer = _get_singer(singer_id)
        singer.add_to_cycle()

        # Run add_to_cycle() on placeholder singer, to check that it doesn't mess things up
        placeholder_singer, _ = Singer.objects.get_or_create(first_name='PLACEHOLDER-FOR-NEW-SINGER', placeholder=True)
        placeholder_singer.add_to_cycle()


def _add_duet(duet_singer_id, primary_singer_id, song_num):
    duet_singer = _get_singer(duet_singer_id)

    song = _get_song(primary_singer_id, song_num)
    song.duet_partner = duet_singer
    song.save()


def _assert_singers_in_queryset(testcase, queryset, expected_singers: List[int]):
    testcase.assertEqual([singer.username for singer in queryset],
                         [f"user_{singer_id}" for singer_id in expected_singers])


def _assert_singers_in_cycles(testcase, expected_singers: List[List[int]]):
    """
    Receives a list of 4 lists, one per cycle. Each cycle list has the singer ids expected to be in each cycle, in order
    """
    for expected_singers_in_cycle, cy_name in zip(expected_singers, CYCLE_NAMES):
        cycle_queryset = getattr(Singer.cycles, cy_name)()
        _assert_singers_in_queryset(testcase, cycle_queryset, expected_singers_in_cycle)


def _gen_cycle_nums(cycles):
    """
    Receives a list of items representing cycles.
    Returns the cycles numbers. If, cycles is a list of 5x lists, will return [1.0, 2.0, 2.5, 3.0, 3.1, 4.1]
    """
    yield from [1.0, 2.0, LATE_SINGER_CYCLE, 3.0]
    extra_cycle_num = 3.1
    for i in range(len(cycles) - 3):
        yield extra_cycle_num
        extra_cycle_num = round(extra_cycle_num + 0.1, 1)


def _assert_song_positions(testcase, expected_songs):
    """
    Receives a list lists (one for each cycle). Each cycle list containing tuples representing a song (singer_id, song_id)
    Asserts that the given list matches the entire list of songs
    """
    positions = []
    for expected_songs_in_cycle, cycle_num in zip(expected_songs, _gen_cycle_nums(expected_songs)):
        cycle_songs = SongRequest.objects.filter(cycle=cycle_num).order_by('position')
        positions.extend(song.position for song in cycle_songs)

        testcase.assertEqual([song.song_name if not song.placeholder else PLACEHOLDER for song in cycle_songs],
                             [f"song_{expected[0]}_{expected[1]}" if isinstance(expected, tuple) else expected for
                              expected in expected_songs_in_cycle], f"Failed comparison of cycle {cycle_num}")

    num_songs = len(list(chain.from_iterable(expected_songs)))
    testcase.assertEqual(positions, list(range(1, num_songs + 1)))

    # Verify that all songs were covered in the expected songs
    testcase.assertFalse(SongRequest.objects.filter(cycle=round(cycle_num+0.1, 1)).exists())


class TestCycleManager(TestCase):
    @patch('song_signup.managers.FIRST_CYCLE_LEN', 4)
    @patch('song_signup.models.Singer.add_to_cycle', MagicMock())
    def test_cy_funcs(self):
        _create_singers(10)
        cy1_singers = [1, 2, 3, 4]
        cy2_singers = [5, 1, 6, 2, 7, 3, 8, 4]
        lscy_singers = [9, 10]
        cy3_singers = [5, 1, 6, 2, 7, 3, 8, 4]

        _assign_positions([
            cy1_singers,
            cy2_singers,
            lscy_singers,
            cy3_singers
        ])

        _assert_singers_in_cycles(self, [cy1_singers, cy2_singers, lscy_singers, cy3_singers])
        _assert_singers_in_queryset(self, Singer.cycles.new_singers_cy2(), [5, 6, 7, 8])

    @patch('song_signup.models.Singer.add_to_cycle', MagicMock())
    def test_next_pos_cy1(self):
        _create_singers(6)
        _assign_positions([[3, 4, 5, 6]])
        self.assertEqual(Singer.cycles.next_pos_cy1(), 5)

    @patch('song_signup.models.Singer.add_to_cycle', MagicMock())
    def test_first_pos_cy1(self):
        self.assertEqual(Singer.cycles.next_pos_cy1(), 1)

    @patch('song_signup.models.Singer.add_to_cycle', MagicMock())
    def test_next_pos_lscy(self):
        _create_singers(10)
        _assign_positions([[], [], [9, 10], []])
        self.assertEqual(Singer.cycles.next_pos_lscy(), 3)

    @patch('song_signup.models.Singer.add_to_cycle', MagicMock())
    def test_first_next_pos_lscy(self):
        self.assertEqual(Singer.cycles.next_pos_lscy(), 1)

    @patch('song_signup.models.Singer.add_to_cycle', MagicMock())
    def test_next_new_singer_cy2(self):
        _create_singers(4)

        # No new singers in cycle 2 yet
        singer1 = _get_singer(1)
        singer1.cy1_position = 1
        singer1.cy2_position = 2
        singer1.save()

        singer2 = _get_singer(2)
        singer2.cy1_position = 2
        singer2.cy2_position = 4
        singer2.save()

        self.assertEqual(Singer.cycles.next_new_singer_pos_cy2(), 1)

        # First new singer
        singer3 = _get_singer(3)
        singer3.cy2_position = 1
        singer3.save()
        self.assertEqual(Singer.cycles.next_new_singer_pos_cy2(), 3)

        # Second new singer
        singer4 = _get_singer(4)
        singer4.cy2_position = 3
        singer4.save()
        self.assertEqual(Singer.cycles.next_new_singer_pos_cy2(), 5)

    @patch('song_signup.managers.FIRST_CYCLE_LEN', 4)
    @patch('song_signup.models.Singer.add_to_cycle', MagicMock())
    def test_cy1_full(self):
        _create_singers(4)
        _assign_positions([[1, 2, 3, 4]])
        self.assertTrue(Singer.cycles.cy1_full())

    @patch('song_signup.managers.FIRST_CYCLE_LEN', 4)
    @patch('song_signup.models.Singer.add_to_cycle', MagicMock())
    def test_cy1_not_full(self):
        _create_singers(4)
        _assign_positions([[1, 2, 3]])
        self.assertFalse(Singer.cycles.cy1_full())

    @patch('song_signup.managers.FIRST_CYCLE_LEN', 4)
    @patch('song_signup.models.Singer.add_to_cycle', MagicMock())
    def test_cy2_full(self):
        _create_singers(8)
        _assign_positions([
            [1, 2, 3, 4],
            [5, 1, 6, 2, 7, 3, 8, 4],
        ])
        self.assertTrue(Singer.cycles.cy2_full())

    @patch('song_signup.managers.FIRST_CYCLE_LEN', 4)
    @patch('song_signup.models.Singer.add_to_cycle', MagicMock())
    def test_cy2_almost_full(self):
        _create_singers(8)
        _assign_positions([
            [1, 2, 3, 4],
            [5, 1, 6, 2, 7, 3, 4],
        ])
        self.assertFalse(Singer.cycles.cy2_full())

    @patch('song_signup.managers.FIRST_CYCLE_LEN', 4)
    @patch('song_signup.models.Singer.add_to_cycle', MagicMock())
    def test_cy2_empty(self):
        _create_singers(8)
        _assign_positions([
            [1, 2, 3, 4],
            [1, 2, 3, 4],
        ])
        self.assertFalse(Singer.cycles.cy2_full())


class TestCalculatePositions(TestCase):
    @patch('song_signup.managers.FIRST_CYCLE_LEN', 4)
    @patch('song_signup.models.Singer.add_to_cycle', MagicMock())
    def test_all_singers_have_songs(self):
        _create_singers(10)
        _assign_positions([
            [1, 2, 3, 4],
            [5, 1, 6, 2, 7, 3, 8, 4],
            [9, 10],
            [5, 1, 6, 2, 7, 3, 8, 4]
        ])
        _add_songs_to_singers(10, 3)
        # Adding songs invokes the calculate_positions method

        _assert_song_positions(self, [
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
    @patch('song_signup.models.Singer.add_to_cycle', MagicMock())
    def test_some_singers_have_songs(self):
        _create_singers(11)
        _assign_positions([
            [1, 2, 3, 4],
            [5, 1, 6, 2, 7, 3, 8, 4],
            [9, 10],
            [11, 5, 1, 6, 2, 7, 3, 8, 4]
        ])
        _add_songs_to_singers([1, 5, 6], 3)
        _add_songs_to_singers([4, 7, 9], 2)
        _add_songs_to_singers([3, 8, 10], 1)
        # Adding songs invokes the calculate_positions method

        _assert_song_positions(self, [
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
    @patch('song_signup.models.Singer.add_to_cycle', MagicMock())
    def test_duets(self):
        _create_singers(10)
        _assign_positions([
            [1, 2, 3, 4],
            [5, 1, 6, 2, 7, 3, 8, 4],
            [9, 10],
            [5, 1, 6, 2, 7, 3, 8, 4]
        ])
        _add_songs_to_singers(10, 3)
        # Cycle 2 duets
        _add_duet(6, 1, 2)
        _add_duet(2, 5, 1)
        _add_duet(4, 7, 1)
        _add_duet(3, 8, 2)

        # Cycle 3 duets
        _add_duet(5, 9, 1)
        _add_duet(2, 10, 1)
        _add_duet(3, 7, 2)
        # Adding songs invokes the calculate_positions method

        _assert_song_positions(self, [
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
    @patch('song_signup.models.Singer.add_to_cycle', MagicMock())
    def test_third_cycle_repeat(self):
        _create_singers(10)
        _assign_positions([
            [1, 2, 3, 4],
            [5, 1, 6, 2, 7, 3, 8, 4],
            [9, 10],
            [5, 1, 6, 2, 7, 3, 8, 4]
        ])

        _add_songs_to_singers([3, 4, 6, 7, 8], 3)
        _add_songs_to_singers([2, 5, 9], 4)
        _add_songs_to_singers([1, 10], 5)

        _assert_song_positions(self, [
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


class TestPlaceholders(TestCase):
    @patch('song_signup.managers.FIRST_CYCLE_LEN', 4)
    @patch('song_signup.models.Singer.add_to_cycle', MagicMock())
    def test_one_singer(self):
        _create_singers(1)

        _assign_positions([
            [1],
            [None, 1],
            [],
            [None, 1],
        ])
        _add_songs_to_singers([1], 2)

        _assert_song_positions(self, [
            [
                (1, 1),
            ],
            [
                PLACEHOLDER,
                (1, 2),
            ]
        ])

    @patch('song_signup.managers.FIRST_CYCLE_LEN', 4)
    @patch('song_signup.models.Singer.add_to_cycle', MagicMock())
    def test_two_singers(self):
        _create_singers(2)

        _assign_positions([
            [1, 2],
            [None, 1, None, 2],
        ])
        _add_songs_to_singers([1, 2], 2)

        _assert_song_positions(self, [
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
    @patch('song_signup.models.Singer.add_to_cycle', MagicMock())
    def test_first_cycle_full(self):
        _create_singers(4)

        _assign_positions([
            [1, 2, 3, 4],
            [None, 1, None, 2, None, 3, None, 4],
        ])
        _add_songs_to_singers([1, 2, 3, 4], 2)

        _assert_song_positions(self, [
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
    @patch('song_signup.models.Singer.add_to_cycle', MagicMock())
    def test_first_cycle_full_songs_missing(self):
        _create_singers(4)

        _assign_positions([
            [1, 2, 3, 4],
            [None, 1, None, 2, None, 3, None, 4],
        ])
        _add_songs_to_singers([2, 3], 1)
        _add_songs_to_singers([1, 4], 2)

        _assert_song_positions(self, [
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
    @patch('song_signup.models.Singer.add_to_cycle', MagicMock())
    def test_second_cycle_incomplete(self):
        _create_singers(6)

        _assign_positions([
            [1, 2, 3, 4],
            [5, 1, 6, 2, None, 3, None, 4],
        ])
        _add_songs_to_singers([1, 2, 3, 4], 2)
        _add_songs_to_singers([5, 6], 1)

        _assert_song_positions(self, [
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
    @patch('song_signup.models.Singer.add_to_cycle', MagicMock())
    def test_second_cycle_full(self):
        _create_singers(9)

        _assign_positions([
            [1, 2, 3, 4],
            [5, 1, 6, 2, 7, 3, 8, 4],
            [9],
        ])
        _add_songs_to_singers([1, 2, 3, 4], 2)
        _add_songs_to_singers([5, 6, 7, 8, 9], 1)

        _assert_song_positions(self, [
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
    @patch('song_signup.models.Singer.add_to_cycle', MagicMock())
    def test_second_cycle_veteran_songs_missing(self):
        _create_singers(9)

        _assign_positions([
            [1, 2, 3, 4],
            [5, 1, 6, 2, 7, 3, 8, 4],
            [9],
        ])
        _add_songs_to_singers([1, 3, 4], 2)
        _add_songs_to_singers([5, 6, 7, 8, 9, 2], 1)

        _assert_song_positions(self, [
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
    @patch('song_signup.models.Singer.add_to_cycle', MagicMock())
    def test_second_cycle_new_songs_missing(self):
        _create_singers(10)

        _assign_positions([
            [1, 2, 3, 4],
            [5, 1, 6, 2, 7, 3, 8, 4],
            [9, 10],
        ])
        _add_songs_to_singers([1, 3, 4], 2)
        _add_songs_to_singers([5, 7, 9, 2], 1)

        _assert_song_positions(self, [
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
        _add_songs_to_singers([6], 1)
        _assert_song_positions(self, [
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


class TestAddToCycle(TestCase):
    @patch('song_signup.managers.FIRST_CYCLE_LEN', 4)
    def test_add_to_cycle(self):
        _create_singers(11)
        superuser = _get_singer(11)
        superuser.is_superuser = True
        superuser.save()  # Superusers don't get assigned to any cycles

        expected_cy1_singers = [1, 2, 3, 4]
        expected_cy2_singers = [5, 1, 6, 2, 7, 3, 8, 4]
        expected_lscy_singers = [9, 10]
        expected_cy3_singers = [5, 1, 6, 2, 7, 3, 8, 4]

        _add_singers_to_cycle(11)

        _assert_singers_in_cycles(self, [expected_cy1_singers, expected_cy2_singers,
                                         expected_lscy_singers, expected_cy3_singers])
        self.assertIsNone(superuser.cy1_position)
        self.assertIsNone(superuser.cy2_position)
        self.assertIsNone(superuser.lscy_position)
        self.assertIsNone(superuser.cy3_position)

    @patch('song_signup.managers.FIRST_CYCLE_LEN', 4)
    def test_add_to_cycle_in_stages(self):
        _create_singers(12)

        _add_singers_to_cycle([1, 2])
        _assert_singers_in_cycles(self, [[1, 2], [1, 2], [], [1, 2]])

        _add_singers_to_cycle([3, 4])
        _assert_singers_in_cycles(self, [[1, 2, 3, 4], [1, 2, 3, 4], [], [1, 2, 3, 4]])

        _add_singers_to_cycle([5])
        _assert_singers_in_cycles(self, [[1, 2, 3, 4], [5, 1, 2, 3, 4], [], [5, 1, 2, 3, 4]])

        _add_singers_to_cycle([6, 7, 8])
        _assert_singers_in_cycles(self, [[1, 2, 3, 4], [5, 1, 6, 2, 7, 3, 8, 4], [], [5, 1, 6, 2, 7, 3, 8, 4]])

        _add_singers_to_cycle([9])
        _assert_singers_in_cycles(self, [[1, 2, 3, 4], [5, 1, 6, 2, 7, 3, 8, 4], [9], [5, 1, 6, 2, 7, 3, 8, 4]])

        _add_singers_to_cycle([10, 11, 12])
        _assert_singers_in_cycles(self,
                                  [[1, 2, 3, 4], [5, 1, 6, 2, 7, 3, 8, 4], [9, 10, 11, 12], [5, 1, 6, 2, 7, 3, 8, 4]])

# class AlgorithmTest(TestCase):
#     def setUp(self):
#         enable_flag('CAN_SIGNUP')
#         _create_singers(30)
#
#     def complete_cycle2(self):
#         with patch('song_signup.managers.CycleManager.cy2_complete') as cy2_complete_mock:
#             cy2_complete_mock.return_value = True
#             Singer.cycles.seal_cycles()
#
#     def test_round_1_few_singers(self):
#         """
#         Three users each ask for five songs. The order should be
#         ABCABCABC...
#         Then, 2 new singers add their songs, one each. They should be bumped to the top and the order should be
#         ABCDEABCABC...
#         """
#         for singer_id in range(3):
#             self.singer_add_songs(singer_id, 5)
#
#         all_songs = SongRequest.objects.filter(position__isnull=False).order_by("position").all()
#         singer_order = [(song.singer.username, song.cycle) for song in all_songs]
#         self.assertEqual(singer_order, [("user_0", 1.0), ("user_1", 1.0), ("user_2", 1.0),
#                                         ("user_0", 1.1), ("user_1", 1.1), ("user_2", 1.1),
#                                         ("user_0", 1.2), ("user_1", 1.2), ("user_2", 1.2),
#                                         ("user_0", 1.3)])
#
#         # 2 new singers add single song
#         self.singer_add_songs(3, 1)
#         self.singer_add_songs(4, 1)
#         all_songs = SongRequest.objects.filter(position__isnull=False).order_by("position").all()
#         singer_order = [(song.singer.username, song.cycle) for song in all_songs]
#         # TODO: Bug here - users 3 and 4 take their place in the 2nd subcycle, even though they don't have a song,
#         # TODO: and then users 0 and 1 who do have songs aren't in the list. The list in this case is only of len 8.
#         # self.assertEqual(singer_order, [("user_0", 1.0), ("user_1", 1.0), ("user_2", 1.0), ("user_3", 1.0),
#         #                                 ("user_4", 1.0), ("user_0", 1.1),  ("user_1", 1.1),
#         #                                 ("user_2", 1.1), ("user_0", 1.2), ("user_1", 1.2)])
#
#     def test_duet_round_1(self):
#         """
#         Two users ask for songs, then one of them requests a duet.
#         It should count as both of their songs so the first user should sing again
#         """
#         s1 = Singer.objects.get(username="user_1")
#         s2 = Singer.objects.get(username="user_2")
#         SongRequest.objects.create(song_name="song_1_0", singer=s1)
#         SongRequest.objects.create(song_name="song_2_0", singer=s2)
#         SongRequest.objects.create(song_name="song_1_1", singer=s1, duet_partner=s2)
#         SongRequest.objects.create(song_name="song_2_2", singer=s2)
#         SongRequest.objects.create(song_name="song_1_2", singer=s1)
#
#         all_songs = SongRequest.objects.order_by("position").all()
#         self.assertEqual(all_songs[0].singer.id, s1.id)
#         self.assertEqual(all_songs[1].singer.id, s2.id)
#         self.assertEqual(all_songs[2].singer.id, s1.id)
#         self.assertEqual(all_songs[3].singer.id, s1.id)  # <- This is what we're actually checking
#         self.assertEqual(all_songs[4].singer.id, s2.id)
#
#     def test_duet_round_1_skips_to_third_person(self):
#         """
#         Three users in round 1, one of them requests a duet.
#         It should count as both of their songs so the order should skip to the third user sing again
#         """
#         s1 = Singer.objects.get(username="user_1")
#         s2 = Singer.objects.get(username="user_2")
#         s3 = Singer.objects.get(username="user_3")
#         SongRequest.objects.create(song_name="song_1_0", singer=s1)
#         SongRequest.objects.create(song_name="song_2_0", singer=s2)
#         SongRequest.objects.create(song_name="song_3_0", singer=s3)
#         SongRequest.objects.create(song_name="song_1_1", singer=s1, duet_partner=s2)
#         SongRequest.objects.create(song_name="song_2_1", singer=s2)
#         SongRequest.objects.create(song_name="song_3_1", singer=s3)
#
#         all_songs = SongRequest.objects.order_by("position").all()
#         self.assertEqual(all_songs[0].singer.id, s1.id)
#         self.assertEqual(all_songs[1].singer.id, s2.id)
#         self.assertEqual(all_songs[2].singer.id, s3.id)
#         self.assertEqual(all_songs[3].singer.id, s1.id)
#         self.assertEqual(all_songs[4].singer.id, s3.id)  # <- This is what we're actually checking
#         self.assertEqual(all_songs[5].singer.id, s2.id)
#
#     def test_round_2_and_3(self):
#         """
#         The first ten users (ABC...IJ) will get a song
#         Then the next ten users (KLM...) should be interspersed with the first ten like
#         KALBMC etc.
#         Then the third cycle will only include (once) users who were not in the first two cycles (bug? feature?)
#
#         Note that this is slow because for each added song we are going over all of the songs (N^2). Still, 90^2
#         is a very small number so it should be much faster
#         """
#         SINGERS_WITH_4_SONGS = [24, 25, 0, 12, 2, 14]  # Expected order in cycle 3.1
#         SINGERS_WITH_5_SONGS = [24, 0, 12]  # Expected order in cycle 3.2
#         assert set(SINGERS_WITH_5_SONGS).issubset(set(SINGERS_WITH_4_SONGS))
#
#         # Cycle 1 singers
#         for i in range(10):
#             singer = Singer.objects.get(username=f"user_{i}")
#             for song in range(3):
#                 SongRequest.objects.create(song_name=f"song_{i}_{song}", singer=singer)
#
#         # Cycle 2 singers
#         for i in range(10, 20):
#             singer = Singer.objects.get(username=f"user_{i}")
#             for song in range(2):
#                 SongRequest.objects.create(song_name=f"song_{i}_{song}", singer=singer)
#
#         # Cycle 3 singers
#         for i in range(20, 30):
#             singer = Singer.objects.get(username=f"user_{i}")
#             SongRequest.objects.create(song_name=f"song_{i}_1", singer=singer)
#
#         # Add a 4th song to some singers from different cycles - for 3.1 cycle
#         for i in SINGERS_WITH_4_SONGS:
#             singer = Singer.objects.get(username=f"user_{i}")
#             SongRequest.objects.create(song_name=f"song_{i}_4", singer=singer)
#
#         # Add a 5th song to some singers from different cycles - for 3.2 cycle
#         for i in SINGERS_WITH_5_SONGS:
#             singer = Singer.objects.get(username=f"user_{i}")
#             SongRequest.objects.create(song_name=f"song_{i}_5", singer=singer)
#
#         self.complete_cycle2()
#         all_songs = SongRequest.objects.filter(position__isnull=False).order_by("position").all()
#
#         # Cycle 1
#         for i in range(10):
#             self.assertEqual(all_songs[i].singer.username, f"user_{i}")
#             self.assertEqual(all_songs[i].cycle, 1.0)
#
#         # Cycle 2
#         for i in range(10):
#             # New singers
#             self.assertEqual(all_songs[10 + 2 * i].singer.username, f"user_{i + 10}")
#             self.assertEqual(all_songs[10 + 2 * i].cycle, 2.0)
#
#             # Singers from cycle 1
#             self.assertEqual(all_songs[10 + 2 * i + 1].singer.username, f"user_{i}")
#             self.assertEqual(all_songs[10 + 2 * i + 1].cycle, 2.0)
#
#         # Cycle 3
#         for i in range(10):
#             # New singers
#             self.assertEqual(all_songs[30 + i].singer.username, f"user_{i + 20}")
#             self.assertEqual(all_songs[30 + i].cycle, 3.0)
#
#             # Gen 2 singers
#             self.assertEqual(all_songs[40 + 2 * i].singer.username, f"user_{i + 10}")
#             self.assertEqual(all_songs[40 + 2 * i].cycle, 3.0)
#
#             # Gen 3 singers
#             self.assertEqual(all_songs[40 + 2 * i + 1].singer.username, f"user_{i}")
#             self.assertEqual(all_songs[40 + 2 * i + 1].cycle, 3.0)
#
#         # Cycle 3.1 (Repeat cycle 3 with whoever still has songs)
#         for position, singer in enumerate(SINGERS_WITH_4_SONGS):
#             self.assertEqual(all_songs[60 + position].singer.username, f"user_{singer}")
#             self.assertEqual(all_songs[60 + position].cycle, 3.1)
#
#         # Cycle 3.2 (Repeat cycle 3 with whoever still has songs)
#         for position, singer in enumerate(SINGERS_WITH_5_SONGS):
#             self.assertEqual(all_songs[60 + len(SINGERS_WITH_4_SONGS) + position].singer.username, f"user_{singer}")
#             self.assertEqual(all_songs[60 + len(SINGERS_WITH_4_SONGS) + position].cycle, 3.2)
#
#         self.assertEqual(len(all_songs), 10 + 20 + 30 + len(SINGERS_WITH_4_SONGS) + len(SINGERS_WITH_5_SONGS))
