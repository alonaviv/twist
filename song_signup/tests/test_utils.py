import json
import datetime
import random
from itertools import chain
from typing import Union, List

import pytz
from django.test import TestCase

from song_signup.managers import LATE_SINGER_CYCLE
from song_signup.models import (Singer, SongRequest, SongSuggestion, TicketOrder, SING_SKU, GroupSongRequest,
                                CurrentGroupSong)
from song_signup.views import enable_signup, _sanitize_string

CYCLE_NAMES = ['cy1', 'cy2', 'lscy', 'cy3']
PLACEHOLDER = 'PLACEHOLDER'
TEST_START_TIME = datetime.datetime(year=2022, month=7, day=10, tzinfo=pytz.UTC)
EVENT_SKU = "EVT123"
PASSCODE = 'dev'


def create_order(num_singers, order_id: int = None):
    if not order_id:
        order_id = random.randint(111111, 999999)
    return TicketOrder.objects.create(
        order_id=order_id,
        event_sku=EVENT_SKU,
        event_name="Test Event",
        num_tickets=num_singers,
        customer_name="Test Customer",
        ticket_type=SING_SKU,
        is_freebie=False
    )


def get_singer_str(singer_id: int, hebrew=False):
    return f'User_{singer_id} Last_name' if not hebrew else f'משתמש_{singer_id} שם משפחה'

def get_song_str(singer_id: int, song_id: int):
    return f'Song_{singer_id}_{song_id}'


def get_song_basic_data(singer_id: int, song_id: int, obj_id: int = None, wait_amount: int = None):
    return {'id': obj_id or 1, 'name': get_song_str(singer_id, song_id),
            'singer': get_singer_str(singer_id), "wait_amount": wait_amount or 0}


def create_singers(singer_ids: Union[int, list], frozen_time=None, num_songs=None, order=None, hebrew=False):
    if isinstance(singer_ids, int):
        singer_ids = range(1, singer_ids + 1)

    if not order:
        order = create_order(len(singer_ids))

    singers = []
    for i in singer_ids:
        singers.append(Singer.objects.create_user(
            username=f"user_{i}" if not hebrew else f"משתמש_{i}",
            first_name=_sanitize_string(f"user_{i}" if not hebrew else f"משתמש_{i}"),
            last_name=_sanitize_string("last_name" if not hebrew else "שם משפחה"),
            ticket_order=order
        ))
        if frozen_time:
            frozen_time.tick()
        if num_songs:
            add_songs_to_singer(i, num_songs, hebrew=hebrew)

    return singers


def get_singer(singer_id, hebrew=False):
    return Singer.objects.get(username=f"user_{singer_id}" if not hebrew else f"משתמש_{singer_id}")


def get_song(singer_id, song_num):
    return SongRequest.objects.get(song_name=f"song_{singer_id}_{song_num}")


def assign_positions_cycles(singer_positions):
    """
    Receives a list of 3 tuples, one for each cycle, that lists the order of the singer ids in that cycle.
    If None appears in the list, skips that position number and moves on
    """
    for singer_list, cy_name in zip(singer_positions, CYCLE_NAMES):
        position = 1
        for singer_id in singer_list:
            if singer_id is not None:
                singer = get_singer(singer_id)
                setattr(singer, f'{cy_name}_position', position)
                singer.save()
            position += 1


def add_songs_to_singer(singer_id, songs_ids: Union[int, list], frozen_time=None, hebrew=False):
    singer = get_singer(singer_id, hebrew=hebrew)

    if isinstance(songs_ids, int):
        songs_ids = range(1, songs_ids + 1)

    for song_id in songs_ids:
        if frozen_time:
            frozen_time.tick()

        SongRequest.objects.create(song_name=f"song_{singer_id}_{song_id}", singer=singer)
        Singer.ordering.calculate_positions()


def set_performed(singer_id, song_id, frozen_time=None):
    if frozen_time:
        frozen_time.tick()

    song = get_song(singer_id, song_id)
    song.performance_time = datetime.datetime.now(tz=pytz.UTC)
    song.save()
    Singer.ordering.calculate_positions()


def set_skipped(singer_id, song_id):
    song = get_song(singer_id, song_id)
    song.skipped = True
    song.save()


def set_unskipped(singer_id, song_id):
    song = get_song(singer_id, song_id)
    song.skipped = False
    song.save()


def add_songs_to_singers(singers: Union[list, int], num_songs, frozen_time=None):
    """
    Can either pass a list of ints, or the num of singers to be generated
    """
    if isinstance(singers, int):
        singers = range(1, singers + 1)

    for singer_id in singers:
        add_songs_to_singer(singer_id, num_songs, frozen_time=frozen_time)


def add_singers_to_cycle(singers):
    """
    Adds the given number of singers to the cycle, according to ascending order.
    Alternatively, receives a list of the specific singer ids to use
    """
    if isinstance(singers, int):
        singers = range(1, singers + 1)

    for singer_id in singers:
        singer = get_singer(singer_id)
        singer._add_to_cycle()

        # Run add_to_cycle() on placeholder singer, to check that it doesn't mess things up
        placeholder_singer, _ = Singer.objects.get_or_create(first_name='PLACEHOLDER-FOR-NEW-SINGER', placeholder=True)
        placeholder_singer._add_to_cycle()


def add_duet(duet_singer_id, primary_singer_id, song_num, frozen_time=None, hebrew=False):
    duet_singer = get_singer(duet_singer_id, hebrew=hebrew)

    if frozen_time:
        frozen_time.tick()

    song = get_song(primary_singer_id, song_num)
    song.duet_partner = duet_singer
    Singer.ordering.calculate_positions()
    song.save()


def assert_singers_in_queryset(testcase, queryset, expected_singers: List[int]):
    testcase.assertEqual([singer.username for singer in queryset],
                         [f"user_{singer_id}" for singer_id in expected_singers])


def assert_singers_in_cycles(testcase, expected_singers: List[List[int]]):
    """
    Receives a list of 4 lists, one per cycle. Each cycle list has the singer ids expected to be in each cycle, in order
    """
    for expected_singers_in_cycle, cy_name in zip(expected_singers, CYCLE_NAMES):
        cycle_queryset = getattr(Singer.ordering, cy_name)()
        assert_singers_in_queryset(testcase, cycle_queryset, expected_singers_in_cycle)


def assert_singers_in_disney(testcase, expected_singers):
    """
    Receives a list singers ids, in the order that's expected to be in the disneyland singer ordering
    """
    assert_singers_in_queryset(testcase, Singer.ordering.singer_disneyland_ordering(), expected_singers)


def gen_cycle_nums(cycles):
    """
    Receives a list of items representing cycles.
    Returns the cycles numbers. If, cycles is a list of 5x lists, will return [1.0, 2.0, 2.5, 3.0, 3.1, 4.1]
    """
    yield from [1.0, 2.0, LATE_SINGER_CYCLE, 3.0]
    extra_cycle_num = 3.1
    for i in range(len(cycles) - 3):
        yield extra_cycle_num
        extra_cycle_num = round(extra_cycle_num + 0.1, 1)


def assert_song_positions_cycles(testcase, expected_songs):
    """
    Receives a list lists (one for each cycle). Each cycle list containing tuples representing a song (singer_id, song_id)
    Asserts that the given list matches the entire list of songs
    """
    positions = []
    for expected_songs_in_cycle, cycle_num in zip(expected_songs, gen_cycle_nums(expected_songs)):
        cycle_songs = SongRequest.objects.filter(cycle=cycle_num).order_by('position')
        positions.extend(song.position for song in cycle_songs)

        testcase.assertEqual([song.song_name if not song.placeholder else PLACEHOLDER for song in cycle_songs],
                             [f"song_{expected[0]}_{expected[1]}" if isinstance(expected, tuple) else expected for
                              expected in expected_songs_in_cycle], f"Failed comparison of cycle {cycle_num}")

    num_songs = len(list(chain.from_iterable(expected_songs)))
    testcase.assertEqual(positions, list(range(1, num_songs + 1)))

    # Verify that all songs were covered in the expected songs
    testcase.assertFalse(SongRequest.objects.filter(cycle=round(cycle_num + 0.1, 1)).exists())


def assert_song_positions(testcase, expected_songs):
    """
    Receives a list of the expected order of songs in the queue, each song represented as (singer_id, song_id)
    Asserts that the given list matches the entire list of songs
    """
    Singer.ordering.calculate_positions()
    all_songs = SongRequest.objects.filter(position__isnull=False).order_by('position')

    # Assert that all songs are as expected and in order
    testcase.assertEqual([song.song_name for song in all_songs],
                         [f"Song_{expected[0]}_{expected[1]}" for expected in expected_songs])

    # Assert that positions are sequential
    positions = [song.position for song in all_songs]
    testcase.assertEqual(positions, list(range(1, len(expected_songs) + 1)))


def add_song_suggestions():
    [suggester] = create_singers([-5]) # ID that won't conflict with others
    SongSuggestion.objects.create(song_name='suggested_song_1', musical='a musical', suggested_by=suggester)
    SongSuggestion.objects.create(song_name='suggested_song_2', musical='a musical', suggested_by=suggester)


def add_current_group_song(song_name, musical):
    [suggester] = create_singers([-50]) # ID that won't conflict with others
    group_song = GroupSongRequest.objects.create(song_name=song_name, musical=musical,
                                                 suggested_by=suggester)
    CurrentGroupSong.objects.create(group_song=group_song)


def logout(singer_id):
    singer = get_singer(singer_id)
    singer.is_active = False
    singer.save()


def login(singer_id):
    singer = get_singer(singer_id)
    singer.is_active = True
    singer.save()


class SongRequestTestCase(TestCase):
    def setUp(self):
        enable_signup(None)
        add_song_suggestions()

    def tearDown(self):
        suggestions = SongSuggestion.objects.all().order_by('request_time')
        self.assertEqual(suggestions.count(), 2)
        self.assertEqual(suggestions[0].song_name, 'suggested_song_1')
        self.assertEqual(suggestions[1].song_name, 'suggested_song_2')

def remove_keys(mydict, keys: list):
    for key in keys:
        if key in mydict:
            del mydict[key]

    return mydict

def get_json(response):
    return json.loads(response.content)
