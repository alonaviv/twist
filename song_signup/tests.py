import datetime
from itertools import chain
from typing import List, Union

import pytz
from django.test import TestCase
from freezegun import freeze_time
from mock import patch, MagicMock

from song_signup.managers import LATE_SINGER_CYCLE
from song_signup.models import Singer, SongRequest
from song_signup.views import disable_signup, enable_signup

CYCLE_NAMES = ['cy1', 'cy2', 'lscy', 'cy3']
PLACEHOLDER = 'PLACEHOLDER'

TEST_START_TIME = datetime.datetime(year=2022, month=7, day=10, tzinfo=pytz.UTC)


class SongRequestTestCase(TestCase):
    def setUp(self):
        enable_signup(None)


def _create_singers(singer_ids: Union[int, list], frozen_time=None, num_songs=None):
    if isinstance(singer_ids, int):
        singer_ids = range(1, singer_ids + 1)

    singers = []
    for i in singer_ids:
        singers.append(Singer.objects.create_user(
            username=f"user_{i}",
            first_name=f"user_{i}",
            last_name="last_name",
            is_staff=True,
        ))
        if frozen_time:
            frozen_time.tick()
        if num_songs:
            _add_songs_to_singer(i, num_songs)

    return singers


def _get_singer(singer_id):
    return Singer.objects.get(username=f"user_{singer_id}")


def _get_song(singer_id, song_num):
    return SongRequest.objects.get(song_name=f"song_{singer_id}_{song_num}")


def _assign_positions_cycles(singer_positions):
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


def _add_songs_to_singer(singer_id, songs_ids: Union[int, list], frozen_time=None):
    singer = _get_singer(singer_id)

    if isinstance(songs_ids, int):
        songs_ids = range(1, songs_ids + 1)

    for song_id in songs_ids:
        if frozen_time:
            frozen_time.tick()

        SongRequest.objects.create(song_name=f"song_{singer_id}_{song_id}", singer=singer)


def _set_performed(singer_id, song_id, frozen_time=None):
    if frozen_time:
        frozen_time.tick()

    song = _get_song(singer_id, song_id)
    song.performance_time = datetime.datetime.now(tz=pytz.UTC)
    song.save()


def _add_songs_to_singers(singers: Union[list, int], num_songs, frozen_time=None):
    """
    Can either pass a list of ints, or the num of singers to be generated
    """
    if isinstance(singers, int):
        singers = range(1, singers + 1)

    for singer_id in singers:
        _add_songs_to_singer(singer_id, num_songs, frozen_time=frozen_time)


def _add_singers_to_cycle(singers):
    """
    Adds the given number of singers to the cycle, according to ascending order.
    Alternatively, receives a list of the specific singer ids to use
    """
    if isinstance(singers, int):
        singers = range(1, singers + 1)

    for singer_id in singers:
        singer = _get_singer(singer_id)
        singer._add_to_cycle()

        # Run add_to_cycle() on placeholder singer, to check that it doesn't mess things up
        placeholder_singer, _ = Singer.objects.get_or_create(first_name='PLACEHOLDER-FOR-NEW-SINGER', placeholder=True)
        placeholder_singer._add_to_cycle()


def _add_duet(duet_singer_id, primary_singer_id, song_num, frozen_time=None):
    duet_singer = _get_singer(duet_singer_id)

    if frozen_time:
        frozen_time.tick()

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
        cycle_queryset = getattr(Singer.ordering, cy_name)()
        _assert_singers_in_queryset(testcase, cycle_queryset, expected_singers_in_cycle)


def _assert_singers_in_disney(testcase, expected_singers):
    """
    Receives a list singers ids, in the order that's expected to be in the disneyland singer ordering
    """
    _assert_singers_in_queryset(testcase, Singer.ordering.singer_disneyland_ordering(), expected_singers)


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


def _assert_song_positions_cycles(testcase, expected_songs):
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
    testcase.assertFalse(SongRequest.objects.filter(cycle=round(cycle_num + 0.1, 1)).exists())


def _assert_song_positions(testcase, expected_songs):
    """
    Receives a list of the expected order of songs in the queue, each song represented as (singer_id, song_id)
    Asserts that the given list matches the entire list of songs
    """
    all_songs = SongRequest.objects.filter(position__isnull=False).order_by('position')

    # Assert that all songs are as expected and in order
    testcase.assertEqual([song.song_name for song in all_songs],
                         [f"song_{expected[0]}_{expected[1]}" for expected in expected_songs])

    # Assert that positions are sequential
    positions = [song.position for song in all_songs]
    testcase.assertEqual(positions, list(range(1, len(expected_songs) + 1)))


#  ========== Old 3 cycle algorithm tests ===========
class TestCycleManager(SongRequestTestCase):
    @patch('song_signup.managers.FIRST_CYCLE_LEN', 4)
    @patch('song_signup.models.Singer._add_to_cycle', MagicMock())
    def test_cy_funcs(self):
        _create_singers(10)
        cy1_singers = [1, 2, 3, 4]
        cy2_singers = [5, 1, 6, 2, 7, 3, 8, 4]
        lscy_singers = [9, 10]
        cy3_singers = [5, 1, 6, 2, 7, 3, 8, 4]

        _assign_positions_cycles([
            cy1_singers,
            cy2_singers,
            lscy_singers,
            cy3_singers
        ])

        _assert_singers_in_cycles(self, [cy1_singers, cy2_singers, lscy_singers, cy3_singers])
        _assert_singers_in_queryset(self, Singer.ordering.new_singers_cy2(), [5, 6, 7, 8])

    @patch('song_signup.models.Singer._add_to_cycle', MagicMock())
    def test_next_pos_cy1(self):
        _create_singers(6)
        _assign_positions_cycles([[3, 4, 5, 6]])
        self.assertEqual(Singer.ordering.next_pos_cy1(), 5)

    @patch('song_signup.models.Singer._add_to_cycle', MagicMock())
    def test_first_pos_cy1(self):
        self.assertEqual(Singer.ordering.next_pos_cy1(), 1)

    @patch('song_signup.models.Singer._add_to_cycle', MagicMock())
    def test_next_pos_lscy(self):
        _create_singers(10)
        _assign_positions_cycles([[], [], [9, 10], []])
        self.assertEqual(Singer.ordering.next_pos_lscy(), 3)

    @patch('song_signup.models.Singer._add_to_cycle', MagicMock())
    def test_first_next_pos_lscy(self):
        self.assertEqual(Singer.ordering.next_pos_lscy(), 1)

    @patch('song_signup.models.Singer._add_to_cycle', MagicMock())
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

        self.assertEqual(Singer.ordering.next_new_singer_pos_cy2(), 1)

        # First new singer
        singer3 = _get_singer(3)
        singer3.cy2_position = 1
        singer3.save()
        self.assertEqual(Singer.ordering.next_new_singer_pos_cy2(), 3)

        # Second new singer
        singer4 = _get_singer(4)
        singer4.cy2_position = 3
        singer4.save()
        self.assertEqual(Singer.ordering.next_new_singer_pos_cy2(), 5)

    @patch('song_signup.managers.FIRST_CYCLE_LEN', 4)
    @patch('song_signup.models.Singer._add_to_cycle', MagicMock())
    def test_cy1_full(self):
        _create_singers(4)
        _assign_positions_cycles([[1, 2, 3, 4]])
        self.assertTrue(Singer.ordering.cy1_full())

    @patch('song_signup.managers.FIRST_CYCLE_LEN', 4)
    @patch('song_signup.models.Singer._add_to_cycle', MagicMock())
    def test_cy1_not_full(self):
        _create_singers(4)
        _assign_positions_cycles([[1, 2, 3]])
        self.assertFalse(Singer.ordering.cy1_full())

    @patch('song_signup.managers.FIRST_CYCLE_LEN', 4)
    @patch('song_signup.models.Singer._add_to_cycle', MagicMock())
    def test_cy2_full(self):
        _create_singers(8)
        _assign_positions_cycles([
            [1, 2, 3, 4],
            [5, 1, 6, 2, 7, 3, 8, 4],
        ])
        self.assertTrue(Singer.ordering.cy2_full())

    @patch('song_signup.managers.FIRST_CYCLE_LEN', 4)
    @patch('song_signup.models.Singer._add_to_cycle', MagicMock())
    def test_cy2_almost_full(self):
        _create_singers(8)
        _assign_positions_cycles([
            [1, 2, 3, 4],
            [5, 1, 6, 2, 7, 3, 4],
        ])
        self.assertFalse(Singer.ordering.cy2_full())

    @patch('song_signup.managers.FIRST_CYCLE_LEN', 4)
    @patch('song_signup.models.Singer._add_to_cycle', MagicMock())
    def test_cy2_empty(self):
        _create_singers(8)
        _assign_positions_cycles([
            [1, 2, 3, 4],
            [1, 2, 3, 4],
        ])
        self.assertFalse(Singer.ordering.cy2_full())


class TestCalculatePositions3Cycles(SongRequestTestCase):
    @patch('song_signup.managers.FIRST_CYCLE_LEN', 4)
    @patch('song_signup.models.Singer._add_to_cycle', MagicMock())
    def test_all_singers_have_songs(self):
        _create_singers(10)
        _assign_positions_cycles([
            [1, 2, 3, 4],
            [5, 1, 6, 2, 7, 3, 8, 4],
            [9, 10],
            [5, 1, 6, 2, 7, 3, 8, 4]
        ])
        _add_songs_to_singers(10, 3)
        # Adding songs invokes the calculate_positions method

        _assert_song_positions_cycles(self, [
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
        _create_singers(11)
        _assign_positions_cycles([
            [1, 2, 3, 4],
            [5, 1, 6, 2, 7, 3, 8, 4],
            [9, 10],
            [11, 5, 1, 6, 2, 7, 3, 8, 4]
        ])
        _add_songs_to_singers([1, 5, 6], 3)
        _add_songs_to_singers([4, 7, 9], 2)
        _add_songs_to_singers([3, 8, 10], 1)
        # Adding songs invokes the calculate_positions method

        _assert_song_positions_cycles(self, [
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
        _create_singers(10)
        _assign_positions_cycles([
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

        _assert_song_positions_cycles(self, [
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
        _create_singers(10)
        _assign_positions_cycles([
            [1, 2, 3, 4],
            [5, 1, 6, 2, 7, 3, 8, 4],
            [9, 10],
            [5, 1, 6, 2, 7, 3, 8, 4]
        ])

        _add_songs_to_singers([3, 4, 6, 7, 8], 3)
        _add_songs_to_singers([2, 5, 9], 4)
        _add_songs_to_singers([1, 10], 5)

        _assert_song_positions_cycles(self, [
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
        _create_singers(1)

        _assign_positions_cycles([
            [1],
            [None, 1],
            [],
            [None, 1],
        ])
        _add_songs_to_singers([1], 2)

        _assert_song_positions_cycles(self, [
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
        _create_singers(2)

        _assign_positions_cycles([
            [1, 2],
            [None, 1, None, 2],
        ])
        _add_songs_to_singers([1, 2], 2)

        _assert_song_positions_cycles(self, [
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
        _create_singers(4)

        _assign_positions_cycles([
            [1, 2, 3, 4],
            [None, 1, None, 2, None, 3, None, 4],
        ])
        _add_songs_to_singers([1, 2, 3, 4], 2)

        _assert_song_positions_cycles(self, [
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
        _create_singers(4)

        _assign_positions_cycles([
            [1, 2, 3, 4],
            [None, 1, None, 2, None, 3, None, 4],
        ])
        _add_songs_to_singers([2, 3], 1)
        _add_songs_to_singers([1, 4], 2)

        _assert_song_positions_cycles(self, [
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
        _create_singers(6)

        _assign_positions_cycles([
            [1, 2, 3, 4],
            [5, 1, 6, 2, None, 3, None, 4],
        ])
        _add_songs_to_singers([1, 2, 3, 4], 2)
        _add_songs_to_singers([5, 6], 1)

        _assert_song_positions_cycles(self, [
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
        _create_singers(9)

        _assign_positions_cycles([
            [1, 2, 3, 4],
            [5, 1, 6, 2, 7, 3, 8, 4],
            [9],
        ])
        _add_songs_to_singers([1, 2, 3, 4], 2)
        _add_songs_to_singers([5, 6, 7, 8, 9], 1)

        _assert_song_positions_cycles(self, [
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
        _create_singers(9)

        _assign_positions_cycles([
            [1, 2, 3, 4],
            [5, 1, 6, 2, 7, 3, 8, 4],
            [9],
        ])
        _add_songs_to_singers([1, 3, 4], 2)
        _add_songs_to_singers([5, 6, 7, 8, 9, 2], 1)

        _assert_song_positions_cycles(self, [
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
        _create_singers(10)

        _assign_positions_cycles([
            [1, 2, 3, 4],
            [5, 1, 6, 2, 7, 3, 8, 4],
            [9, 10],
        ])
        _add_songs_to_singers([1, 3, 4], 2)
        _add_songs_to_singers([5, 7, 9, 2], 1)

        _assert_song_positions_cycles(self, [
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
        _assert_song_positions_cycles(self, [
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


# ============ New Disneyland algorithm tests ============


class TestSingerModel(SongRequestTestCase):
    def test_last_performance_time(self):
        with freeze_time(TEST_START_TIME) as frozen_time:
            [singer] = _create_singers(1)
            frozen_time.tick()
            _add_songs_to_singer(1, 3)

            frozen_time.tick()
            _set_performed(1, 1)
            frozen_time.tick()

            self.assertEqual(singer.last_performance_time, _get_song(1, 1).performance_time)
            self.assertEqual(singer.last_performance_time, TEST_START_TIME + datetime.timedelta(seconds=2))
            self.assertEqual(singer.date_joined, TEST_START_TIME)

            _set_performed(1, 2)

            self.assertEqual(singer.last_performance_time, _get_song(1, 2).performance_time)
            self.assertEqual(singer.last_performance_time, TEST_START_TIME + datetime.timedelta(seconds=3))
            self.assertEqual(singer.date_joined, TEST_START_TIME)

    def test_last_performance_time_dueter_existing_song(self):
        with freeze_time(TEST_START_TIME) as frozen_time:
            primary_singer, secondary_singer = _create_singers(2)
            _add_songs_to_singers(2, 2)
            frozen_time.tick()
            _add_duet(2, 1, song_num=2)

            _set_performed(1, 1)

            self.assertEqual(primary_singer.last_performance_time, _get_song(1, 1).performance_time)
            self.assertEqual(primary_singer.last_performance_time, TEST_START_TIME + datetime.timedelta(seconds=1))
            self.assertIsNone(secondary_singer.last_performance_time)

            frozen_time.tick()
            _set_performed(1, 2)
            # Duet singer appears to have performed one second later than the primary
            self.assertEqual(primary_singer.last_performance_time, _get_song(1, 2).performance_time)
            self.assertEqual(primary_singer.last_performance_time, TEST_START_TIME + datetime.timedelta(seconds=2))
            self.assertEqual(secondary_singer.last_performance_time, TEST_START_TIME + datetime.timedelta(seconds=3))

            frozen_time.tick()
            frozen_time.tick()
            frozen_time.tick()
            _set_performed(2, 1)

            self.assertEqual(primary_singer.last_performance_time, TEST_START_TIME + datetime.timedelta(seconds=2))
            self.assertEqual(secondary_singer.last_performance_time, TEST_START_TIME + datetime.timedelta(seconds=5))
            self.assertEqual(secondary_singer.last_performance_time, _get_song(2, 1).performance_time)

    def test_last_performance_time_empty(self):
        with freeze_time(TEST_START_TIME, auto_tick_seconds=5) as frozen_time:
            [singer] = _create_singers(1)
            frozen_time.tick()
            _add_songs_to_singer(1, 3)

            frozen_time.tick()

            self.assertEqual(singer.last_performance_time, None)


class TestDisneylandOrdering(SongRequestTestCase):
    def test_no_performances_no_songs(self):
        with freeze_time(TEST_START_TIME, auto_tick_seconds=5) as frozen_time:
            _create_singers(10, frozen_time)
            _assert_singers_in_disney(self, range(1, 11))
            self.assertEqual(Singer.ordering.new_singers_num(), 0)

    def test_no_performances(self):
        with freeze_time(TEST_START_TIME, auto_tick_seconds=5) as frozen_time:
            _create_singers(10, frozen_time, num_songs=3)
            _assert_singers_in_disney(self, range(1, 11))
            self.assertEqual(Singer.ordering.new_singers_num(), 10)

    def test_first_performances(self):
        with freeze_time(TEST_START_TIME, auto_tick_seconds=5) as frozen_time:
            _create_singers([1, 2], frozen_time, num_songs=3)
            _set_performed(1, 1, frozen_time)
            _assert_singers_in_disney(self, [2, 1])
            self.assertEqual(Singer.ordering.new_singers_num(), 1)

    def test_duets(self):
        """
        If two singers have a duet, once the duet is sung both will be moved to the end of the queue
        """
        with freeze_time(TEST_START_TIME, auto_tick_seconds=5) as frozen_time:
            _create_singers(5, frozen_time, num_songs=3)
            _add_duet(5, 3, 1)

            _set_performed(1, 1, frozen_time)
            _assert_singers_in_disney(self, [2, 3, 4, 5, 1])
            self.assertEqual(Singer.ordering.new_singers_num(), 4)

            _set_performed(2, 1, frozen_time)
            _assert_singers_in_disney(self, [3, 4, 5, 1, 2])
            self.assertEqual(Singer.ordering.new_singers_num(), 3)

            # 3 duets with 5, so they both get moved to the back of the list
            _set_performed(3, 1, frozen_time)
            _assert_singers_in_disney(self, [4, 1, 2, 3, 5])
            self.assertEqual(Singer.ordering.new_singers_num(), 1)  # Both 3 and 5 stop being new singers

            _set_performed(4, 1, frozen_time)
            _assert_singers_in_disney(self, [1, 2, 3, 5, 4])
            self.assertEqual(Singer.ordering.new_singers_num(), 0)

    def test_long_ordering(self):
        with freeze_time(TEST_START_TIME, auto_tick_seconds=5) as frozen_time:
            _create_singers([1, 2], frozen_time, num_songs=3)
            _assert_singers_in_disney(self, [1, 2])
            self.assertEqual(Singer.ordering.new_singers_num(), 2)

            _create_singers([3, 4], frozen_time, num_songs=3)
            _set_performed(1, 1, frozen_time)
            _assert_singers_in_disney(self, [2, 3, 4, 1])
            self.assertEqual(Singer.ordering.new_singers_num(), 3)

            _create_singers([5, 6], frozen_time, num_songs=3)
            _assert_singers_in_disney(self, [2, 3, 4, 1, 5, 6])
            self.assertEqual(Singer.ordering.new_singers_num(), 5)

            _set_performed(2, 1, frozen_time)
            _assert_singers_in_disney(self, [3, 4, 1, 5, 6, 2])
            self.assertEqual(Singer.ordering.new_singers_num(), 4)

            # Singer 9 joins but doesn't sign up for a song, still counts in the ordering
            _create_singers([7, 8, 9], frozen_time)
            _add_songs_to_singers([7, 8], 3)
            _assert_singers_in_disney(self, [3, 4, 1, 5, 6, 2, 7, 8, 9])
            self.assertEqual(Singer.ordering.new_singers_num(), 6)

            _set_performed(3, 1, frozen_time)
            _set_performed(4, 1, frozen_time)
            _assert_singers_in_disney(self, [1, 5, 6, 2, 7, 8, 9, 3, 4])
            self.assertEqual(Singer.ordering.new_singers_num(), 4)

            _create_singers([10], frozen_time, num_songs=1)
            self.assertEqual(Singer.ordering.new_singers_num(), 5)
            _set_performed(1, 2, frozen_time)
            _assert_singers_in_disney(self, [5, 6, 2, 7, 8, 9, 3, 4, 10, 1])
            self.assertEqual(Singer.ordering.new_singers_num(), 5)  # 1 already sung, doesn't count as new singer

            # Shani stops signup, which pushes all the people who haven't sung yet to the start of the list

            disable_signup(None)
            _assert_singers_in_disney(self, [5, 6, 7, 8, 9, 10, 2, 3, 4, 1])
            self.assertEqual(Singer.ordering.new_singers_num(), 5)

            _set_performed(5, 1, frozen_time)
            _assert_singers_in_disney(self, [6, 7, 8, 9, 10, 2, 3, 4, 1, 5])
            self.assertEqual(Singer.ordering.new_singers_num(), 4)

            _set_performed(6, 1, frozen_time)
            _set_performed(7, 1, frozen_time)
            _set_performed(8, 1, frozen_time)
            self.assertEqual(Singer.ordering.new_singers_num(), 1)
            # 9 Didn't sign up for a song
            _set_performed(10, 1, frozen_time)
            self.assertEqual(Singer.ordering.new_singers_num(), 0)
            _set_performed(2, 2, frozen_time)
            _set_performed(3, 2, frozen_time)
            self.assertEqual(Singer.ordering.new_singers_num(), 0)

            _assert_singers_in_disney(self, [9, 4, 1, 5, 6, 7, 8, 10, 2, 3])

            _set_performed(4, 2, frozen_time)
            _set_performed(1, 3, frozen_time)
            self.assertEqual(Singer.ordering.new_singers_num(), 0)
            _assert_singers_in_disney(self, [9, 5, 6, 7, 8, 10, 2, 3, 4, 1])


class TestCalculatePositionsDisney(SongRequestTestCase):
    def test_no_singers_have_songs(self):
        _create_singers(10)
        singer_ordering = [
            5, 6, 2, 7, 8, 9, 3, 4, 10, 1
        ]

        with patch('song_signup.managers.DisneylandOrdering.singer_disneyland_ordering',
                   return_value=[_get_singer(singer_id) for singer_id in singer_ordering]):
            Singer.ordering.calculate_positions()

        self.assertFalse(SongRequest.objects.filter(position__isnull=False).exists())

    def test_all_singers_have_songs(self):
        _create_singers(10)
        singer_ordering = [
            5, 6, 2, 7, 8, 9, 3, 4, 10, 1
        ]

        with patch('song_signup.managers.DisneylandOrdering.singer_disneyland_ordering',
                   return_value=[_get_singer(singer_id) for singer_id in singer_ordering]):
            # Adding songs invokes the calculate_positions method
            _add_songs_to_singers(10, 3)

        _assert_song_positions(self, [
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
        _create_singers(10)
        singer_ordering = [
            5, 6, 2, 7, 8, 9, 3, 4, 10, 1
        ]

        with patch('song_signup.managers.DisneylandOrdering.singer_disneyland_ordering',
                   return_value=[_get_singer(singer_id) for singer_id in singer_ordering]):
            # Adding songs invokes the calculate_positions method
            _add_songs_to_singers(6, 1)
            _add_songs_to_singers([8, 10], 1)

        _assert_song_positions(self, [
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
        _create_singers(10)
        singer_ordering = [
            5, 6, 2, 7, 8, 9, 3, 4, 10, 1
        ]

        with patch('song_signup.managers.DisneylandOrdering.singer_disneyland_ordering',
                   return_value=[_get_singer(singer_id) for singer_id in singer_ordering]):
            # Adding songs and setting as performed invokes the calculate_positions method
            _add_songs_to_singers(10, 3)

            _set_performed(1, 1)
            _set_performed(2, 1)
            _set_performed(3, 1)
            _set_performed(4, 1)
            _set_performed(1, 2)

        _assert_song_positions(self, [
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
        If a singer also has a duet earlier in line, his song is skipped.
        If a singer also has a duet later in line, nothing happens.
        """
        _create_singers(10)
        singer_ordering = [
            5, 6, 2, 7, 8, 9, 3, 4, 10, 1
        ]

        with patch('song_signup.managers.DisneylandOrdering.singer_disneyland_ordering',
                   return_value=[_get_singer(singer_id) for singer_id in singer_ordering]):
            # Adding songs and setting as performed invokes the calculate_positions method
            _add_songs_to_singers(9, 3)  # Singer 10 only has a duet

            _add_duet(8, 6, 1)
            _add_duet(9, 4, 1)
            _add_duet(3, 8, 1)
            _add_duet(10, 7, 1)

        _assert_song_positions(self, [
            (5, 1),
            (6, 1),
            (2, 1),
            (7, 1),
            # 8 has a duet, so is skipped
            (9, 1),  # Has a duet later, which doesn't affect her
            (3, 1),  # Had a duet with 8, but 8's song was skipped, so no penalty
            (4, 1),
            # 10 Doesn't have a primary song, only a duet
            (1, 1)
        ])


class TestSimulatedEvenings(SongRequestTestCase):
    # TODO: Shani leaves on at the top
    def test_scenario1(self):
        with freeze_time(TEST_START_TIME, auto_tick_seconds=5) as frozen_time:
            # Singer 1 joins with 1 song #1
            _create_singers([1], frozen_time, num_songs=1)
            _assert_song_positions(self, [(1, 1)])

            # Singer 2 joins with as singer 1 sings
            _create_singers([2], frozen_time, num_songs=3)
            _set_performed(1, 1, frozen_time)
            _assert_song_positions(self, [(2, 1)])

            # Singer 1 adds song #2
            _add_songs_to_singer(1, [2], frozen_time)
            _assert_song_positions(self, [(2, 1), (1, 2)])

            # Singers 3-5 join as 2 sings, singer 5 doesn't sign up with a song
            _create_singers([3, 4, 5], frozen_time)
            _add_songs_to_singers([3, 4], 3, frozen_time)
            Singer.ordering.calculate_positions()
            _assert_song_positions(self, [(2, 1), (1, 2), (3, 1), (4, 1)])
            _set_performed(2, 1, frozen_time)
            _assert_song_positions(self, [(1, 2), (3, 1), (4, 1), (2, 2)])

            # Singers 6-10 join without signing up for songs yet while 1 sings, and then chooses a new song (#3)
            # Before they do, but they still get in front of 1 - as they joined while 1 was singing
            _create_singers([6, 7, 8, 9], frozen_time)
            _set_performed(1, 2, frozen_time)
            _assert_song_positions(self, [(3, 1), (4, 1), (2, 2)])
            _add_songs_to_singer(1, [3], frozen_time)
            _assert_song_positions(self, [(3, 1), (4, 1), (2, 2), (1, 3)])
            _add_songs_to_singers([6, 7, 8, 9], 4, frozen_time)
            _assert_song_positions(self, [(3, 1), (4, 1), (2, 2), (6, 1), (7, 1), (8, 1), (9, 1), (1, 3)])

            # Singers 10-11 join without songs (along with 5 who doesn't have a song yet either)
            _create_singers([10, 11], frozen_time)
            _assert_song_positions(self, [(3, 1), (4, 1), (2, 2), (6, 1), (7, 1), (8, 1), (9, 1), (1, 3)])

            # 4 adds 7 as a duet partner - So 7's song disappears. 2 adds 3 as a duet partner - no effect.
            _add_duet(7, 4, 1, frozen_time)
            _assert_song_positions(self, [(3, 1), (4, 1), (2, 2), (6, 1), (8, 1), (9, 1), (1, 3)])
            _add_duet(3, 2, 2, frozen_time)
            _assert_song_positions(self, [(3, 1), (4, 1), (2, 2), (6, 1), (8, 1), (9, 1), (1, 3)])

            # Singers 12-13 join while 3 is singing. 3 is a duet partner with 2, so his song doesn't appear at the end
            # of the list.
            _create_singers([12, 13], frozen_time, num_songs=2)
            _assert_song_positions(self, [(3, 1), (4, 1), (2, 2), (6, 1), (8, 1), (9, 1), (1, 3), (12, 1), (13, 1)])
            _set_performed(3, 1, frozen_time)
            _assert_song_positions(self, [(4, 1), (2, 2), (6, 1), (8, 1), (9, 1), (1, 3), (12, 1), (13, 1)])

            # Singer 14 joins as Singer 4 sings a duet with 7. 4 and 7 both get put at the end of the list, after 14.
            # Note that singer 4 gets his second song, while 7 gets her first primary that she hasn't used
            _create_singers([14], frozen_time, num_songs=1)
            _assert_song_positions(self, [(4, 1), (2, 2), (6, 1), (8, 1), (9, 1), (1, 3), (12, 1), (13, 1), (14, 1)])
            _set_performed(4, 1, frozen_time)
            _assert_song_positions(self,
                                   [(2, 2), (6, 1), (8, 1), (9, 1), (1, 3), (12, 1), (13, 1), (14, 1), (4, 2), (7, 1)])

            # Singers 5 and 11 decide to add their songs. They appear in their original places that were saved.
            _add_songs_to_singer(5, 1, frozen_time)
            _assert_song_positions(self,
                                   [(5, 1), (2, 2), (6, 1), (8, 1), (9, 1), (1, 3), (12, 1), (13, 1), (14, 1), (4, 2),
                                    (7, 1)])
            _add_songs_to_singer(11, 2, frozen_time)
            _assert_song_positions(self,
                                   [(5, 1), (2, 2), (6, 1), (8, 1), (9, 1), (1, 3), (11, 1), (12, 1), (13, 1), (14, 1),
                                    (4, 2), (7, 1)])

            # Singer 5 sings, and then singer 2 duets with 3, and they both appear at the end of the list together.
            # 5 adds another song and appears before them
            _set_performed(5, 1, frozen_time)
            _assert_song_positions(self,
                                   [(2, 2), (6, 1), (8, 1), (9, 1), (1, 3), (11, 1), (12, 1), (13, 1), (14, 1),
                                    (4, 2), (7, 1)])
            _set_performed(2, 2, frozen_time)
            Singer.ordering.calculate_positions()
            _assert_song_positions(self,
                                   [(6, 1), (8, 1), (9, 1), (1, 3), (11, 1), (12, 1), (13, 1), (14, 1),
                                    (4, 2), (7, 1), (2, 3), (3, 2)])
            _add_songs_to_singer(5, [2], frozen_time)
            _assert_song_positions(self,
                                   [(6, 1), (8, 1), (9, 1), (1, 3), (11, 1), (12, 1), (13, 1), (14, 1),
                                    (4, 2), (7, 1), (5, 2), (2, 3), (3, 2)])

            # Singers 15-16 join as 6 sings.

            _create_singers([15, 16], frozen_time, num_songs=1)
            _set_performed(6, 1, frozen_time)
            _assert_song_positions(self,
                                   [(8, 1), (9, 1), (1, 3), (11, 1), (12, 1), (13, 1), (14, 1),
                                    (4, 2), (7, 1), (5, 2), (2, 3), (3, 2), (15, 1), (16, 1), (6, 2)])

            # Shani closes signup - all new singers jump to start of list. Note - 7 isn't a new singer, she sang a duet
            disable_signup(None)
            _assert_song_positions(self,
                                   [(8, 1), (9, 1), (11, 1), (12, 1), (13, 1), (14, 1),
                                    (15, 1), (16, 1), (1, 3), (4, 2), (7, 1), (5, 2), (2, 3), (3, 2), (6, 2)])

            # 9 adds a duet with 6, who already sang, so 6 disappears.
            # 8 adds a duet with 11, who didn't sing yet, so 11 disappears.
            # 1 adds a duet with 12, who is farther up, so nothing happens.
            _add_duet(6, 9, 1, frozen_time)
            _add_duet(11, 8, 1, frozen_time)
            _add_duet(12, 1, 3, frozen_time)
            _assert_song_positions(self,
                                   [(8, 1), (9, 1), (12, 1), (13, 1), (14, 1),
                                    (15, 1), (16, 1), (1, 3), (4, 2), (7, 1), (5, 2), (2, 3), (3, 2)])

            # 8 Sings duet with 11 - they both go to the end, 11 with song 1 that he didn't sing yet.
            _set_performed(8, 1, frozen_time)
            _assert_song_positions(self,
                                   [(9, 1), (12, 1), (13, 1), (14, 1),
                                    (15, 1), (16, 1), (1, 3), (4, 2), (7, 1), (5, 2), (2, 3), (3, 2), (8, 2), (11, 1)])

            # 9 Sings duet with 6 - they both go to the end, 6 with song 2 that he didn't sing yet
            _set_performed(9, 1, frozen_time)
            _assert_song_positions(self,
                                   [(12, 1), (13, 1), (14, 1), (15, 1), (16, 1), (1, 3), (4, 2), (7, 1), (5, 2),
                                    (2, 3), (3, 2), (8, 2), (11, 1), (9, 2), (6, 2)])

            # 12 Sings. Is dueting with 1, later on - so doesn't appear in the list
            _set_performed(12, 1, frozen_time)
            _assert_song_positions(self,
                                   [(13, 1), (14, 1), (15, 1), (16, 1), (1, 3), (4, 2), (7, 1), (5, 2),
                                    (2, 3), (3, 2), (8, 2), (11, 1), (9, 2), (6, 2)])

            # Singers 13-16 sing. Only 13 has an extra song and is put in the back of the list. The rest are done
            _set_performed(13, 1, frozen_time)
            _set_performed(14, 1, frozen_time)
            _set_performed(15, 1, frozen_time)
            _set_performed(16, 1, frozen_time)
            _assert_song_positions(self,
                                   [(1, 3), (4, 2), (7, 1), (5, 2), (2, 3), (3, 2), (8, 2), (11, 1),
                                    (9, 2), (6, 2), (13, 2)])

            # 1 Duets with 12. So 12 is moved to the end of the list. 1 is done with her songs
            _set_performed(1, 3, frozen_time)
            _assert_song_positions(self,
                                   [(4, 2), (7, 1), (5, 2), (2, 3), (3, 2), (8, 2), (11, 1),
                                    (9, 2), (6, 2), (13, 2), (12, 2)])

            # Half the cycle sings. The singers who sang their last song are:  5, 2
            _set_performed(4, 2, frozen_time)
            _set_performed(7, 1, frozen_time)
            _set_performed(5, 2, frozen_time)
            _set_performed(2, 3, frozen_time)
            _set_performed(3, 2, frozen_time)
            _set_performed(8, 2, frozen_time)
            _set_performed(11, 1, frozen_time)
            _assert_song_positions(self,
                                   [(9, 2), (6, 2), (13, 2), (12, 2),
                                    (4, 3), (7, 2), (3, 3), (8, 3), (11, 2)])

            # Almost full cycle sing. The singers who sang their last song are, 13, 12, 4, 3
            _set_performed(9, 2, frozen_time)
            _set_performed(6, 2, frozen_time)
            _set_performed(13, 2, frozen_time)
            _set_performed(12, 2, frozen_time)
            _set_performed(4, 3, frozen_time)
            _set_performed(7, 2, frozen_time)
            _set_performed(3, 3, frozen_time)
            _assert_song_positions(self,
                                   [(8, 3), (11, 2), (9, 3), (6, 3), (7, 3)])

            # Full cycle sing. 11 sang its last
            _set_performed(8, 3, frozen_time)
            _set_performed(11, 2, frozen_time)
            _set_performed(9, 3, frozen_time)
            _set_performed(6, 3, frozen_time)
            _set_performed(7, 3, frozen_time)
            _assert_song_positions(self,
                                   [(8, 4), (9, 4), (6, 4), (7, 4)])

            # All but last sing their final song
            _set_performed(8, 4, frozen_time)
            _set_performed(9, 4, frozen_time)
            _set_performed(6, 4, frozen_time)
            _assert_song_positions(self,
                                   [(7, 4)])

            # Last singer sings
            _set_performed(7, 4)
            _assert_song_positions(self, [])
