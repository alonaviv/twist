from freezegun import freeze_time
from song_signup.models import SongRequest, Singer
from song_signup.tests.utils_for_tests import (
    SongRequestTestCase, create_singers, add_songs_to_singers, TEST_START_TIME
)

class TestSongRequestManager(SongRequestTestCase):
    def test_spotlight(self):
        with freeze_time(time_to_freeze=TEST_START_TIME) as frozen_time:
            create_singers(3)
            song1, song2, song3 = add_songs_to_singers(3, 1)
            song3.standby = True # Will make position be None
            song3.save()

            Singer.ordering.calculate_positions()
            song1.refresh_from_db()
            song2.refresh_from_db()
            song3.refresh_from_db()

            SongRequest.objects.set_spotlight(song1)
            self.assertEqual(SongRequest.objects.get_spotlight(), song1)
            self.assertEqual(song1.position, 1)
            self.assertEqual(song2.position, 2)
            self.assertIsNone(song3.position)

            SongRequest.objects.set_spotlight(song2)
            self.assertEqual(SongRequest.objects.get_spotlight(), song2)
            self.assertEqual(song1.position, 1)
            self.assertEqual(song2.position, 2)
            self.assertIsNone(song3.position)


            SongRequest.objects.set_spotlight(song3)
            self.assertEqual(SongRequest.objects.get_spotlight(), song3)

            song3.refresh_from_db()
            self.assertEqual(song1.position, 1)
            self.assertEqual(song2.position, 2)
            self.assertIsNone(song3.position)
            self.assertTrue(song3.standby)

            SongRequest.objects.remove_spotlight()
            self.assertIsNone(SongRequest.objects.get_spotlight())
            song3.refresh_from_db()

            self.assertEqual(song1.position, 1)
            self.assertEqual(song2.position, 2)
            self.assertIsNone(song3.position)
            self.assertEqual(song3.performance_time, TEST_START_TIME)
            self.assertFalse(song3.standby)

    def test_spotlight_manual(self):
        with freeze_time(time_to_freeze=TEST_START_TIME) as frozen_time:
            create_singers(3)
            song1, song2, song3 = add_songs_to_singers(3, 1)
            Singer.ordering.calculate_positions()
            song1.refresh_from_db()
            song2.refresh_from_db()
            song3.refresh_from_db()

            song1.spotlight = True
            song1.save()

            song2.spotlight = True
            song2.save()

            SongRequest.objects.set_spotlight(song3)
            song1.refresh_from_db()
            song2.refresh_from_db()
            song3.refresh_from_db()
            self.assertFalse(song1.spotlight)
            self.assertFalse(song2.spotlight)
            self.assertTrue(song3.spotlight)
            self.assertEqual(song3.position, 3)

            self.assertEqual(SongRequest.objects.get_spotlight(), song3)
            SongRequest.objects.remove_spotlight()
            song3.refresh_from_db()
            self.assertFalse(song3.spotlight)
            self.assertEqual(song3.performance_time, TEST_START_TIME)
            self.assertIsNone(song3.position)
