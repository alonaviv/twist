import datetime
from freezegun import freeze_time
from django.test import TestCase
from song_signup.tests.utils_for_tests import (
    SongRequestTestCase, create_singers, add_songs_to_singer, set_performed,
    get_song, add_songs_to_singers, add_partners, TEST_START_TIME, create_order, SING_SKU, ATTN_SKU,
    get_singer_str, create_audience, get_audience_str
)
from song_signup.models import TicketsDepleted, Singer
from django.core.management import call_command


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


class TestTicketOrderModel(TestCase):
    def test_save_customers(self):
        singer_order = create_order(3, SING_SKU, order_id=4321)
        audience_order = create_order(2, ATTN_SKU, order_id=4321)
        singers = create_singers([1, 2, 3], order=singer_order)
        audience = create_audience([4, 5], order=audience_order)

        with self.assertRaises(TicketsDepleted):
            create_singers(([6]), order=singer_order)

        with self.assertRaises(TicketsDepleted):
            create_audience(([6]), order=audience_order)

        # Logout all customers
        for customer in Singer.objects.all():
            customer.is_active = False
            customer.save()

        call_command('reset_db')

        self.assertSetEqual(set(singer_order.logged_in_customers), {get_singer_str(1), get_singer_str(2),
                                                                    get_singer_str(3)})
        self.assertSetEqual(set(audience_order.logged_in_customers), {get_audience_str(4), get_audience_str(5)})





