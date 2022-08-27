import pytz
from collections import defaultdict
from django.utils import timezone
from freezegun import freeze_time

from song_signup.admin import set_performed
from song_signup.models import SongRequest, Singer
from song_signup.tests.test_utils import SongRequestTestCase
from song_signup.views import disable_signup


def convert_time(time):
    return time.astimezone(pytz.timezone('israel')).strftime("%H:%M")


def get_arrival_num_dict():
    """
    Return dict that gives each singer the order num in which he/she arrived, according to the first time they signed
    up with a song (ignoring those who didn't sign up)
    """

    def first_request_time(singer):
        return singer.first_request_time

    arrival_order_dict = dict()
    singers = Singer.ordering.active_singers()

    for i, singer in enumerate(sorted(singers, key=first_request_time), start=1):
        arrival_order_dict[singer] = i

    return arrival_order_dict


def get_first_song_wait(singer):
    """
    Get amount of time that passed between first song request (which we treat as arrival) and first performance
    """
    performed_songs = singer.all_songs.filter(performance_time__isnull=False).order_by('performance_time')
    if performed_songs.exists() and singer.first_request_time:
        return performed_songs.first().performance_time - singer.first_request_time


def get_waited_most():
    """
    Return (singer, wait_time) of the singer who waited the most for their first song
    """
    waited_dict = {get_first_song_wait(singer): singer for singer in Singer.ordering.active_singers()
                   if get_first_song_wait(singer) is not None}
    max_wait_time = max(waited_dict)
    return waited_dict[max_wait_time], max_wait_time


def print_db_analysis():
    arrival_num_dict = get_arrival_num_dict()
    singers = Singer.ordering.active_singers()
    num_performances_dict = defaultdict(set)  # Number of songs performed -> singers that performed that num

    print(f"Num active singers: {len(Singer.ordering.active_singers())}")
    print(f"Total registered singers: {Singer.objects.all().count()}")
    max_waited_singer, max_waited_time = get_waited_most()
    print(f"Longest wait to sing: {max_waited_time.seconds//3600} hours and {(max_waited_time.seconds//60)%60} - {max_waited_singer}")
    print("")

    for singer in singers:
        num_performance = singer.all_songs.filter(performance_time__isnull=False).count()
        num_performances_dict[num_performance].add(singer)

    print("Num songs per singer")
    for num, singers in sorted(num_performances_dict.items(), reverse=True):
        num_singers_want_more = len([singer for singer in singers if singer.all_songs.count() > num])
        print(f"{num}: {len(singers)} singer sang {num} times: {', '.join(f'{singer.first_name}({convert_time(singer.first_request_time)})' for singer in singers)}. Out of them {num_singers_want_more} had more songs requested")

    print("\nFINAL SONG LIST")
    for i, song in enumerate(SongRequest.objects.filter(performance_time__isnull=False).order_by('performance_time'),
                             start=1):
        print_song(i, song, arrival_num_dict)


def print_song(i, song, arrival_num_dict):
    print(f'{i}: {song.singer.first_name} ({arrival_num_dict[song.singer]}) '
          f'{f" + {song.duet_partner.first_name} ({arrival_num_dict[song.duet_partner]}) " if song.duet_partner and not song.duet_partner.is_superuser else ""} - '
          f'{song.song_name} {f"performed-{convert_time(song.performance_time)}" if song.performance_time else ""} requested-{convert_time(song.request_time)}')


def get_current_song():
    """
    Return the song that will be currently performed - taking into account the fact that the song may have been
    requested later in time, in if so should be ignored
    """
    for song in SongRequest.objects.filter(performance_time__isnull=True,
                                           position__isnull=False, placeholder=False).order_by('position'):
        if song.request_time < timezone.now():
            return song


class TestRealDB(SongRequestTestCase):
    fixtures = ['raanana-10-7']
    # fixtures = ['first_outdoor_jlm']

    def test_real_db_file(self):
        INTERACTIVE = False
        CLOSE_SIGNUP_TIME = '22:08'

        print("\n=====ORIGINAL EVENING======")
        print_db_analysis()

        original_song_order = SongRequest.objects.filter(performance_time__isnull=False).order_by('performance_time')
        original_performance_times = [song.performance_time for song in original_song_order]

        for song in original_song_order:
            song.performance_time = None
            song.save()

        print("\n=====SIMULATED EVENING======")
        # Run evening: Shani marks as performed
        with freeze_time(original_performance_times[0]) as frozen_time:
            for performance_time in original_performance_times:
                Singer.ordering.calculate_positions()
                if INTERACTIVE:
                    print("Time: ", convert_time(timezone.now()))
                    for i, song in enumerate(SongRequest.objects.filter(position__isnull=False).order_by('position'),
                                             start=1):
                        print_song(i, song)

                frozen_time.move_to(performance_time)

                if convert_time(performance_time) == CLOSE_SIGNUP_TIME:
                    disable_signup(None)

                Singer.ordering.calculate_positions()

                current_song = get_current_song()
                set_performed(None, None, [current_song])

                if INTERACTIVE:
                    print(f"\n\nMarking {current_song} as performed at {convert_time(performance_time)}. "
                          f"Has {current_song.singer.songs.filter(request_time__lte=timezone.now(), performance_time__isnull=True).count()} songs left\n")
                    breakpoint()

        print_db_analysis()
