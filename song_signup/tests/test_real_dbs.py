import pytz
from django.utils import timezone
from django.db.models import Count
from freezegun import freeze_time

from song_signup.models import SongRequest, Singer
from song_signup.tests.test_utils import SongRequestTestCase
from song_signup.admin import set_performed
from song_signup.views import disable_signup


def convert_time(time):
    return time.astimezone(pytz.timezone('israel')).strftime("%H:%M")


def get_arrival_num_dict():
    """
    Return dict that gives each singer the order num in which he/she arrived, according to the first time they signed
    up with a song (ignoring those who didn't sign up)
    """

    def first_request_time(singer):
        return singer.date_joined
        return singer.songs.filter(request_time__isnull=False).order_by('request_time').first().request_time

    arrival_order_dict = dict()
    singers = Singer.objects.filter(is_superuser=False).annotate(num_songs=Count('songs')).exclude(num_songs=0)

    for i, singer in enumerate(sorted(singers, key=first_request_time), start=1):
        arrival_order_dict[singer] = i

    return arrival_order_dict


def print_db_analysis():
    arrival_num_dict = get_arrival_num_dict()
    print("=== Song Order ===")
    for i, song in enumerate(SongRequest.objects.filter(performance_time__isnull=False).order_by('performance_time'),
                             start=1):
        print(f'{i}: {song.singer.first_name} ({arrival_num_dict[song.singer]}) '
              f'{f" + {song.duet_partner.first_name} ({arrival_num_dict[song.duet_partner]}) " if song.duet_partner and not song.duet_partner.is_superuser else ""} - '
              f'{song.song_name} ({convert_time(song.performance_time)})')


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
    fixtures = ['first_outdoor_jlm']

    def test_real_db_file(self):
        CLOSE_SIGNUP_TIME = '22:08'
        print("\n=====ORIGINAL EVENING======")
        print_db_analysis()

        original_song_order = SongRequest.objects.filter(performance_time__isnull=False).order_by('performance_time')
        original_performance_times = [song.performance_time for song in original_song_order]

        for song in original_song_order:
            song.performance_time = None
            song.save()

        # Run evening: Shani marks as performed
        with freeze_time() as frozen_time:
            for performance_time in original_performance_times:
                frozen_time.move_to(performance_time)

                if convert_time(performance_time) == CLOSE_SIGNUP_TIME:
                    disable_signup(None)

                Singer.ordering.calculate_positions()

                set_performed(None, None, [get_current_song()])

        print("\n=====SIMULATED EVENING======")
        print_db_analysis()

