import datetime
import json
import random
from dataclasses import dataclass
from typing import Union, List

import pytz
from django.test import TestCase
from django.urls import reverse
from flags.state import enable_flag

from song_signup.models import (
    Singer, SongRequest, SongSuggestion, TicketOrder, SING_SKU, GroupSongRequest,
    CurrentGroupSong, AlreadyLoggedIn
)
from song_signup.views import _sanitize_string, AUDIENCE_SESSION

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
    return {
        'id': obj_id or 1, 'name': get_song_str(singer_id, song_id),
        'singer': get_singer_str(singer_id), "wait_amount": wait_amount or 0
    }


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


def song_exists(song_name):
    try:
        SongRequest.objects.get(song_name=song_name)
    except SongRequest.DoesNotExist:
        return False

    return True


def add_songs_to_singer(singer_id, songs_ids: Union[int, list], frozen_time=None, hebrew=False):
    singer = get_singer(singer_id, hebrew=hebrew)

    if isinstance(songs_ids, int):
        songs_ids = range(1, songs_ids + 1)

    for song_id in songs_ids:
        if frozen_time:
            frozen_time.tick()

        SongRequest.objects.create(song_name=f"song_{singer_id}_{song_id}", singer=singer, musical="Wicked")
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


def add_partners(primary_singer_id, partners_ids, song_num, frozen_time=None, hebrew=False):
    if isinstance(partners_ids, int):
        partners_ids = [partners_ids]

    partners = [get_singer(partner_id, hebrew=hebrew) for partner_id in partners_ids]

    if frozen_time:
        frozen_time.tick()

    song = get_song(primary_singer_id, song_num)
    song.partners.set(partners)
    Singer.ordering.calculate_positions()
    song.save()


def assert_singers_in_queryset(testcase, queryset, expected_singers: List[int]):
    testcase.assertEqual([singer.username for singer in queryset],
                         [f"user_{singer_id}" for singer_id in expected_singers])


def assert_singers_in_disney(testcase, expected_singers):
    """
    Receives a list singers ids, in the order that's expected to be in the disneyland singer ordering
    """
    assert_singers_in_queryset(testcase, Singer.ordering.singer_disneyland_ordering(), expected_singers)


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


@dataclass
class ExpectedDashboard:
    singer: int
    primary_singer: int = None  # When the singer's next song is as someone else's partner
    next_song: int = None
    wait_amount: int = -1 # Using -1, since None is a possible value here
    empty: bool = False

    def __post_init__(self):
        if not self.empty and (self.next_song is None or self.wait_amount is -1):
            raise ValueError("A not empty dashboard has to include all data (next song and wait amount")


def assert_dashboards(testcase, expected_dashboards: List[ExpectedDashboard]):
    for dashboard in expected_dashboards:
        singer_id = dashboard.singer
        primary_singer_id = dashboard.primary_singer or singer_id
        login_singer(testcase, singer_id)
        res = testcase.client.get(reverse('dashboard_data'))
        data = remove_keys(res.content, ['id'])

        if dashboard.empty:
            expected_basic_data = None
        else :
            expected_basic_data = {
        "name": get_song_str(primary_singer_id, dashboard.next_song),
        "singer": get_singer_str(primary_singer_id),
        "wait_amount": dashboard.wait_amount
        }

        testcase.assertEqual(data, {"user_next_song":expected_basic_data},
                                f"Dashboard of singer {singer_id} is "
                                f"{data['user_next_song']} and doesn't match {dashboard}")


def add_song_suggestions():
    [suggester] = create_singers([-5])  # ID that won't conflict with others
    SongSuggestion.objects.create(song_name='suggested_song_1', musical='a musical', suggested_by=suggester)
    SongSuggestion.objects.create(song_name='suggested_song_2', musical='a musical', suggested_by=suggester)


def add_current_group_song(song_name, musical):
    [suggester] = create_singers([-50])  # ID that won't conflict with others
    group_song = GroupSongRequest.objects.create(song_name=song_name, musical=musical,
                                                 suggested_by=suggester)
    group_song = CurrentGroupSong.objects.create(group_song=group_song)
    group_song.start_song()


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
        enable_flag('CAN_SIGNUP')
        add_song_suggestions()

    def tearDown(self):
        suggestions = SongSuggestion.objects.all().order_by('request_time')
        self.assertEqual(suggestions.count(), 2)
        self.assertEqual(suggestions[0].song_name, 'suggested_song_1')
        self.assertEqual(suggestions[1].song_name, 'suggested_song_2')


def remove_keys(mydict, keys: list):
    if isinstance(mydict, bytes):
        mydict = json.loads(mydict)

    for key, value in mydict.items():
        if isinstance(value, dict):
            remove_keys(value, keys)

    for key in keys:
        if key in mydict:
            del mydict[key]

    return mydict

def remove_keys_list(dict_list: List[dict], keys: list):
    for mydict in dict_list:
        remove_keys(mydict, keys)



def get_json(response):
    return json.loads(response.content)


def login_singer(testcase, user_id=1, num_songs=None):
    try:
        [user] = create_singers([user_id], num_songs=num_songs)
    except AlreadyLoggedIn:
        user = get_singer(singer_id=user_id)
    testcase.client.force_login(user)
    return user


def login_audience(testcase):
    session = testcase.client.session
    session[AUDIENCE_SESSION] = True
    session.save()
