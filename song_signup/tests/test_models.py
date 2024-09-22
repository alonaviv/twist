import datetime
from freezegun import freeze_time

from song_signup.tests.test_utils import (
    SongRequestTestCase, create_singers, add_songs_to_singer, set_performed,
    get_song, add_songs_to_singers, add_partners, TEST_START_TIME
)


class TestSingerModel(SongRequestTestCase):
    def test_last_performance_time(self):
        with freeze_time(TEST_START_TIME) as frozen_time:
            [singer] = create_singers(1)
            frozen_time.tick()
            add_songs_to_singer(1, 3)

            frozen_time.tick()
            set_performed(1, 1)
            frozen_time.tick()

            self.assertEqual(singer.last_performance_time, get_song(1, 1).performance_time)
            self.assertEqual(singer.last_performance_time, TEST_START_TIME + datetime.timedelta(seconds=2))
            self.assertEqual(singer.date_joined, TEST_START_TIME)

            set_performed(1, 2)

            self.assertEqual(singer.last_performance_time, get_song(1, 2).performance_time)
            self.assertEqual(singer.last_performance_time, TEST_START_TIME + datetime.timedelta(seconds=3))
            self.assertEqual(singer.date_joined, TEST_START_TIME)

    def test_last_performance_time_dueter_existing_song(self):
        with freeze_time(TEST_START_TIME) as frozen_time:
            primary_singer, secondary_singer = create_singers(2)
            add_songs_to_singers(2, 2)
            frozen_time.tick()
            add_partners(1, 2, song_num=2)

            set_performed(1, 1)

            self.assertEqual(primary_singer.last_performance_time, get_song(1, 1).performance_time)
            self.assertEqual(primary_singer.last_performance_time, TEST_START_TIME + datetime.timedelta(seconds=1))
            self.assertIsNone(secondary_singer.last_performance_time)

            frozen_time.tick()
            set_performed(1, 2)
            # Duet singer's performance time remains None.
            self.assertEqual(primary_singer.last_performance_time, get_song(1, 2).performance_time)
            self.assertEqual(primary_singer.last_performance_time, TEST_START_TIME + datetime.timedelta(seconds=2))
            self.assertIsNone(secondary_singer.last_performance_time)

            frozen_time.tick()
            frozen_time.tick()
            frozen_time.tick()
            set_performed(2, 1)

            self.assertEqual(primary_singer.last_performance_time, TEST_START_TIME + datetime.timedelta(seconds=2))
            self.assertEqual(secondary_singer.last_performance_time, TEST_START_TIME + datetime.timedelta(seconds=5))
            self.assertEqual(secondary_singer.last_performance_time, get_song(2, 1).performance_time)

    def test_last_performance_time_empty(self):
        with freeze_time(TEST_START_TIME, auto_tick_seconds=5) as frozen_time:
            [singer] = create_singers(1)
            frozen_time.tick()
            add_songs_to_singer(1, 3)

            frozen_time.tick()

            self.assertEqual(singer.last_performance_time, None)

    def test_first_request_time(self):
        with freeze_time(TEST_START_TIME) as frozen_time:
            [singer] = create_singers(1)

            self.assertIsNone(singer.first_request_time)

            frozen_time.tick()
            add_songs_to_singer(1, 1)
            self.assertEqual(singer.first_request_time, TEST_START_TIME + datetime.timedelta(seconds=1))







