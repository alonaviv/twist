from django.test import TestCase, TransactionTestCase
from freezegun import freeze_time
from song_signup.models import SongRequest, Singer, SongSuggestion
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


class TestSongSuggestionManager(TestCase):
    """Tests for SongSuggestionManager methods."""
    
    def test_check_used_suggestions_marks_used(self):
        """Test that check_used_suggestions marks suggestions as used when matching SongRequest exists."""
        suggester, singer = create_singers(2)
        
        # Create suggestions
        suggestion1 = SongSuggestion.objects.create(
            song_name='Defying Gravity',
            musical='Wicked',
            suggested_by=suggester
        )
        suggestion2 = SongSuggestion.objects.create(
            song_name='Popular',
            musical='Wicked',
            suggested_by=suggester
        )
        
        # Initially not used
        self.assertFalse(suggestion1.is_used)
        self.assertFalse(suggestion2.is_used)
        
        # Create a song request that matches suggestion1
        SongRequest.objects.create(
            song_name='Defying Gravity',
            musical='Wicked',
            singer=singer
        )
        
        # Run the manager method
        SongSuggestion.objects.check_used_suggestions()
        
        # Refresh from DB
        suggestion1.refresh_from_db()
        suggestion2.refresh_from_db()
        
        # suggestion1 should now be marked as used
        self.assertTrue(suggestion1.is_used)
        # suggestion2 should still not be used
        self.assertFalse(suggestion2.is_used)
    
    def test_check_used_suggestions_case_insensitive(self):
        """Test that check_used_suggestions works case-insensitively."""
        suggester, singer = create_singers(2)
        
        suggestion = SongSuggestion.objects.create(
            song_name='Defying Gravity',
            musical='Wicked',
            suggested_by=suggester
        )
        
        # Create song request with different casing
        SongRequest.objects.create(
            song_name='DEFYING GRAVITY',
            musical='WICKED',
            singer=singer
        )
        
        SongSuggestion.objects.check_used_suggestions()
        suggestion.refresh_from_db()
        
        self.assertTrue(suggestion.is_used)
    
    def test_check_used_suggestions_marks_unused_when_deleted(self):
        """Test that check_used_suggestions marks suggestions as unused when SongRequest is deleted."""
        suggester, singer = create_singers(2)
        
        suggestion = SongSuggestion.objects.create(
            song_name='Defying Gravity',
            musical='Wicked',
            suggested_by=suggester
        )
        
        # Create and mark as used
        song_request = SongRequest.objects.create(
            song_name='Defying Gravity',
            musical='Wicked',
            singer=singer
        )
        SongSuggestion.objects.check_used_suggestions()
        suggestion.refresh_from_db()
        self.assertTrue(suggestion.is_used)
        
        # Delete the song request
        song_request.delete()
        SongSuggestion.objects.check_used_suggestions()
        suggestion.refresh_from_db()
        
        # Should now be marked as unused
        self.assertFalse(suggestion.is_used)
    
    def test_check_used_suggestions_multiple_suggestions(self):
        """Test that check_used_suggestions handles multiple suggestions correctly."""
        suggester, singer1, singer2, singer3 = create_singers(4)
        
        # Create multiple suggestions
        suggestions = [
            SongSuggestion.objects.create(
                song_name=f'Song {i}',
                musical='Musical',
                suggested_by=suggester
            )
            for i in range(5)
        ]
        
        # Create song requests for some
        SongRequest.objects.create(song_name='Song 0', musical='Musical', singer=singer1)
        SongRequest.objects.create(song_name='Song 2', musical='Musical', singer=singer2)
        SongRequest.objects.create(song_name='Song 4', musical='Musical', singer=singer3)
        
        SongSuggestion.objects.check_used_suggestions()
        
        # Refresh and check
        for i, suggestion in enumerate(suggestions):
            suggestion.refresh_from_db()
            if i in [0, 2, 4]:
                self.assertTrue(suggestion.is_used, f"Song {i} should be used")
            else:
                self.assertFalse(suggestion.is_used, f"Song {i} should not be used")
