from django.test import TestCase, TransactionTestCase
from freezegun import freeze_time
from constance.test import override_config
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


class TestPeoplesChoice(TestCase):
    """Comprehensive tests for People's Choice logic."""
    
    def setUp(self):
        """Set up test data."""
        self.suggester, self.voter1, self.voter2, self.voter3, self.voter4, self.voter5 = create_singers(6)
    
    @override_config(NUM_PEOPLES_CHOICE=3)
    def test_basic_peoples_choice_calculation(self):
        """Test that top N unused songs with votes are marked as People's Choice."""
        # Create 5 suggestions
        suggestions = [
            SongSuggestion.objects.create(
                song_name=f'Song {i}',
                musical='Musical',
                suggested_by=self.suggester
            )
            for i in range(5)
        ]
        
        # Add votes: Song 0 gets 5 votes, Song 1 gets 4, Song 2 gets 3, Song 3 gets 2, Song 4 gets 1
        for i, num_votes in enumerate([5, 4, 3, 2, 1]):
            voters = [self.voter1, self.voter2, self.voter3, self.voter4, self.voter5][:num_votes]
            suggestions[i].voters.set(voters)
        
        # Refresh to ensure votes are visible
        for suggestion in suggestions:
            suggestion.refresh_from_db()
        
        # Recalculate positions and People's Choice
        SongSuggestion.objects.recalculate_positions()
        
        # Refresh from DB
        for suggestion in suggestions:
            suggestion.refresh_from_db()
        
        # Top 3 unused songs (Song 0, 1, 2) should be People's Choice
        self.assertTrue(suggestions[0].is_peoples_choice, "Song 0 should be People's Choice")
        self.assertTrue(suggestions[1].is_peoples_choice, "Song 1 should be People's Choice")
        self.assertTrue(suggestions[2].is_peoples_choice, "Song 2 should be People's Choice")
        self.assertFalse(suggestions[3].is_peoples_choice, "Song 3 should not be People's Choice")
        self.assertFalse(suggestions[4].is_peoples_choice, "Song 4 should not be People's Choice")
    
    @override_config(NUM_PEOPLES_CHOICE=3)
    def test_songs_with_zero_votes_not_peoples_choice(self):
        """Test that songs with 0 votes are not People's Choice."""
        # Create suggestions
        suggestion_with_votes = SongSuggestion.objects.create(
            song_name='Song With Votes',
            musical='Musical',
            suggested_by=self.suggester
        )
        suggestion_no_votes = SongSuggestion.objects.create(
            song_name='Song No Votes',
            musical='Musical',
            suggested_by=self.suggester
        )
        
        # Add votes to one
        suggestion_with_votes.voters.add(self.voter1)
        
        SongSuggestion.objects.recalculate_positions()
        
        suggestion_with_votes.refresh_from_db()
        suggestion_no_votes.refresh_from_db()
        
        self.assertTrue(suggestion_with_votes.is_peoples_choice)
        self.assertFalse(suggestion_no_votes.is_peoples_choice)
    
    @override_config(NUM_PEOPLES_CHOICE=3)
    def test_used_songs_expand_box(self):
        """Test that used songs in People's Choice positions expand the box but don't count toward limit."""
        # Create 5 suggestions
        suggestions = [
            SongSuggestion.objects.create(
                song_name=f'Song {i}',
                musical='Musical',
                suggested_by=self.suggester
            )
            for i in range(5)
        ]
        
        # Add votes: Song 0 gets 5 votes, Song 1 gets 4, Song 2 gets 3, Song 3 gets 2, Song 4 gets 1
        for i, num_votes in enumerate([5, 4, 3, 2, 1]):
            voters = [self.voter1, self.voter2, self.voter3, self.voter4, self.voter5][:num_votes]
            suggestions[i].voters.set(voters)
        
        # Mark Song 1 (position 2) as used
        SongRequest.objects.create(
            song_name='Song 1',
            musical='Musical',
            singer=self.voter1
        )
        
        # Mark suggestions as used before recalculating positions
        SongSuggestion.objects.check_used_suggestions()
        SongSuggestion.objects.recalculate_positions()
        
        # Refresh from DB
        for suggestion in suggestions:
            suggestion.refresh_from_db()
        
        # Top 3 unused songs are Song 0, Song 2, Song 3 (Song 1 is used, so Song 3 takes its place)
        # But Song 1 should also be People's Choice because it's in position 2
        self.assertTrue(suggestions[0].is_peoples_choice, "Song 0 should be People's Choice")
        self.assertTrue(suggestions[1].is_peoples_choice, "Song 1 (used) should be People's Choice")
        self.assertTrue(suggestions[2].is_peoples_choice, "Song 2 should be People's Choice")
        self.assertTrue(suggestions[3].is_peoples_choice, "Song 3 should be People's Choice (expanded box)")
        self.assertFalse(suggestions[4].is_peoples_choice, "Song 4 should not be People's Choice")
    
    @override_config(NUM_PEOPLES_CHOICE=3)
    def test_all_flags_reset_first(self):
        """Test that all People's Choice flags are reset to False before recalculation."""
        # Create suggestions and mark some as People's Choice manually
        suggestions = [
            SongSuggestion.objects.create(
                song_name=f'Song {i}',
                musical='Musical',
                suggested_by=self.suggester,
                is_peoples_choice=True  # Manually set
            )
            for i in range(3)
        ]
        
        # Add votes only to first one
        suggestions[0].voters.add(self.voter1)
        
        # Recalculate - should reset all and only mark Song 0
        SongSuggestion.objects.recalculate_positions()
        
        for suggestion in suggestions:
            suggestion.refresh_from_db()
        
        self.assertTrue(suggestions[0].is_peoples_choice)
        self.assertFalse(suggestions[1].is_peoples_choice, "Should be reset to False")
        self.assertFalse(suggestions[2].is_peoples_choice, "Should be reset to False")
    
    @override_config(NUM_PEOPLES_CHOICE=0)
    def test_zero_peoples_choice(self):
        """Test that when NUM_PEOPLES_CHOICE is 0, no songs are marked."""
        suggestions = [
            SongSuggestion.objects.create(
                song_name=f'Song {i}',
                musical='Musical',
                suggested_by=self.suggester
            )
            for i in range(3)
        ]
        
        # Add votes to all
        for suggestion in suggestions:
            suggestion.voters.add(self.voter1)
        
        SongSuggestion.objects.recalculate_positions()
        
        for suggestion in suggestions:
            suggestion.refresh_from_db()
            self.assertFalse(suggestion.is_peoples_choice)
    
    @override_config(NUM_PEOPLES_CHOICE=3)
    def test_recalculate_positions_calls_recalculate_peoples_choice(self):
        """Test that recalculate_positions calls recalculate_peoples_choice."""
        suggestions = [
            SongSuggestion.objects.create(
                song_name=f'Song {i}',
                musical='Musical',
                suggested_by=self.suggester
            )
            for i in range(3)
        ]
        
        # Add votes
        for i, suggestion in enumerate(suggestions):
            suggestion.voters.add(self.voter1)
        
        # recalculate_positions should also recalculate People's Choice
        SongSuggestion.objects.recalculate_positions()
        
        for suggestion in suggestions:
            suggestion.refresh_from_db()
            self.assertTrue(suggestion.is_peoples_choice)
    
    @override_config(NUM_PEOPLES_CHOICE=3)
    def test_check_used_suggestions_recalculates_peoples_choice(self):
        """Test that check_used_suggestions recalculates positions and People's Choice."""
        suggestions = [
            SongSuggestion.objects.create(
                song_name=f'Song {i}',
                musical='Musical',
                suggested_by=self.suggester
            )
            for i in range(3)
        ]
        
        # Add votes
        for suggestion in suggestions:
            suggestion.voters.add(self.voter1)
        
        # Refresh to ensure votes are visible
        for suggestion in suggestions:
            suggestion.refresh_from_db()
        
        SongSuggestion.objects.recalculate_positions()
        
        # Mark Song 0 as used
        SongRequest.objects.create(
            song_name='Song 0',
            musical='Musical',
            singer=self.voter1
        )
        
        # check_used_suggestions should recalculate People's Choice
        SongSuggestion.objects.check_used_suggestions()
        
        for suggestion in suggestions:
            suggestion.refresh_from_db()
        
        # With all songs having 1 vote, they're ordered by -request_time (newest first)
        # So Song 2 (newest) gets position 1, Song 1 gets position 2, Song 0 (oldest) gets position 3
        # After Song 0 becomes used:
        # - Top 2 unused: Song 2 (pos 1), Song 1 (pos 2)
        # - Max position: 2
        # - People's Choice: positions 1-2 = Song 2, Song 1
        # - Song 0 at position 3 should NOT be People's Choice (outside top 2)
        self.assertTrue(suggestions[2].is_peoples_choice, "Song 2 should be People's Choice")
        self.assertTrue(suggestions[1].is_peoples_choice, "Song 1 should be People's Choice")
        self.assertFalse(suggestions[0].is_peoples_choice, "Song 0 should not be People's Choice (position 3 > max_position 2)")
        self.assertTrue(suggestions[0].is_used, "Song 0 should be marked as used")
    
    @override_config(NUM_PEOPLES_CHOICE=3)
    def test_used_songs_dont_count_toward_limit(self):
        """Test that used songs don't count toward the N limit."""
        # Create 6 suggestions
        suggestions = [
            SongSuggestion.objects.create(
                song_name=f'Song {i}',
                musical='Musical',
                suggested_by=self.suggester
            )
            for i in range(6)
        ]
        
        # Add votes: 6, 5, 4, 3, 2, 1
        voters_list = [self.voter1, self.voter2, self.voter3, self.voter4, self.voter5]
        for i, num_votes in enumerate([5, 4, 3, 2, 1, 1]):
            suggestions[i].voters.set(voters_list[:num_votes])
        
        # Mark Song 0, 1, 2 as used (top 3)
        for i in range(3):
            SongRequest.objects.create(
                song_name=f'Song {i}',
                musical='Musical',
                singer=self.voter1
            )
        
        # Mark suggestions as used before recalculating positions
        SongSuggestion.objects.check_used_suggestions()
        SongSuggestion.objects.recalculate_positions()
        
        for suggestion in suggestions:
            suggestion.refresh_from_db()
        
        # Top 3 unused are Song 3, 4, 5
        # But Song 0, 1, 2 are also People's Choice (expanding the box)
        # So all 6 should be People's Choice
        for i in range(6):
            self.assertTrue(suggestions[i].is_peoples_choice, f"Song {i} should be People's Choice")
    
    @override_config(NUM_PEOPLES_CHOICE=3)
    def test_songs_without_positions_not_peoples_choice(self):
        """Test that songs without positions are not People's Choice."""
        suggestion = SongSuggestion.objects.create(
            song_name='Song',
            musical='Musical',
            suggested_by=self.suggester,
            position=None  # No position
        )
        
        suggestion.voters.add(self.voter1)
        
        SongSuggestion.objects.recalculate_peoples_choice()
        
        suggestion.refresh_from_db()
        self.assertFalse(suggestion.is_peoples_choice)
    
    @override_config(NUM_PEOPLES_CHOICE=5)
    def test_config_change_recalculates_correctly(self):
        """Test that changing NUM_PEOPLES_CHOICE recalculates correctly."""
        suggestions = [
            SongSuggestion.objects.create(
                song_name=f'Song {i}',
                musical='Musical',
                suggested_by=self.suggester
            )
            for i in range(7)
        ]
        
        # Add votes to all
        for suggestion in suggestions:
            suggestion.voters.add(self.voter1)
        
        # Refresh to ensure votes are visible
        for suggestion in suggestions:
            suggestion.refresh_from_db()
        
        # First with NUM_PEOPLES_CHOICE=5
        SongSuggestion.objects.recalculate_positions()
        
        for suggestion in suggestions:
            suggestion.refresh_from_db()
        
        # With all songs having 1 vote, they're ordered by -request_time (newest first)
        # So Song 6 (newest) gets position 1, Song 5 gets position 2, etc.
        # Top 5 should be Song 6, 5, 4, 3, 2 (positions 1-5)
        self.assertTrue(suggestions[6].is_peoples_choice, "Song 6 should be People's Choice")
        self.assertTrue(suggestions[5].is_peoples_choice, "Song 5 should be People's Choice")
        self.assertTrue(suggestions[4].is_peoples_choice, "Song 4 should be People's Choice")
        self.assertTrue(suggestions[3].is_peoples_choice, "Song 3 should be People's Choice")
        self.assertTrue(suggestions[2].is_peoples_choice, "Song 2 should be People's Choice")
        self.assertFalse(suggestions[1].is_peoples_choice, "Song 1 should not be People's Choice")
        self.assertFalse(suggestions[0].is_peoples_choice, "Song 0 should not be People's Choice")
    
    @override_config(NUM_PEOPLES_CHOICE=5)
    def test_comprehensive_peoples_choice_scenarios(self):
        """Test a comprehensive scenario with a long list including all combinations."""
        # Create 10 suggestions
        suggestions = [
            SongSuggestion.objects.create(
                song_name=f'Song {i}',
                musical='Musical',
                suggested_by=self.suggester
            )
            for i in range(10)
        ]
        
        # Add votes: decreasing order (10 votes, 9 votes, ..., 1 vote)
        voters_list = [self.voter1, self.voter2, self.voter3, self.voter4, self.voter5]
        for i, num_votes in enumerate([5, 5, 4, 4, 3, 3, 2, 2, 1, 1]):
            suggestions[i].voters.set(voters_list[:num_votes])
        
        # Refresh to ensure votes are visible
        for suggestion in suggestions:
            suggestion.refresh_from_db()
        
        # Mark some as used:
        # Song 1 (position 2) - used, should be People's Choice
        # Song 3 (position 4) - used, should be People's Choice
        # Song 6 (position 7) - used, should NOT be People's Choice (outside top 5)
        # Song 8 (position 9) - used, should NOT be People's Choice (outside top 5)
        SongRequest.objects.create(song_name='Song 1', musical='Musical', singer=self.voter1)
        SongRequest.objects.create(song_name='Song 3', musical='Musical', singer=self.voter1)
        SongRequest.objects.create(song_name='Song 6', musical='Musical', singer=self.voter1)
        SongRequest.objects.create(song_name='Song 8', musical='Musical', singer=self.voter1)
        
        # First, mark suggestions as used (but don't recalculate yet)
        for suggestion in suggestions:
            suggestion.check_if_used()
        
        # Refresh to ensure is_used is saved
        for suggestion in suggestions:
            suggestion.refresh_from_db()
        
        # Now recalculate positions and People's Choice
        SongSuggestion.objects.recalculate_positions()
        
        # Refresh from DB to ensure all fields (including is_peoples_choice) are current
        for suggestion in suggestions:
            suggestion.refresh_from_db()
        
        # Expected People's Choice (top 5 unused + used songs in those positions):
        # Actual positions from debug: Song 0 (pos 2), Song 2 (pos 4), Song 5 (pos 5), Song 4 (pos 6), Song 7 (pos 7)
        # Top 5 unused: Song 0, Song 2, Song 5, Song 4, Song 7 (positions 2, 4, 5, 6, 7)
        # Max position: 7
        # So People's Choice: positions 1-7 (Song 1, 0, 3, 2, 5, 4, 7)
        # Not People's Choice: positions 8-10 (Song 6, 9, 8)
        
        # People's Choice + not used
        self.assertTrue(suggestions[0].is_peoples_choice and not suggestions[0].is_used, "Song 0: PC + not used")
        self.assertTrue(suggestions[2].is_peoples_choice and not suggestions[2].is_used, "Song 2: PC + not used")
        self.assertTrue(suggestions[4].is_peoples_choice and not suggestions[4].is_used, "Song 4: PC + not used")
        self.assertTrue(suggestions[5].is_peoples_choice and not suggestions[5].is_used, "Song 5: PC + not used")
        self.assertTrue(suggestions[7].is_peoples_choice and not suggestions[7].is_used, "Song 7: PC + not used")
        
        # People's Choice + used (expanding the box)
        self.assertTrue(suggestions[1].is_peoples_choice and suggestions[1].is_used, "Song 1: PC + used")
        self.assertTrue(suggestions[3].is_peoples_choice and suggestions[3].is_used, "Song 3: PC + used")
        
        # Not People's Choice + used (outside the box)
        self.assertFalse(suggestions[6].is_peoples_choice, "Song 6: not PC (position 8 > max_position 7)")
        self.assertTrue(suggestions[6].is_used, "Song 6: used")
        self.assertFalse(suggestions[8].is_peoples_choice, "Song 8: not PC")
        self.assertTrue(suggestions[8].is_used, "Song 8: used")
        
        # Not People's Choice + not used
        self.assertFalse(suggestions[9].is_peoples_choice, "Song 9: not PC")
        self.assertFalse(suggestions[9].is_used, "Song 9: not used")
        
        # Verify counts
        peoples_choice_count = sum(1 for s in suggestions if s.is_peoples_choice)
        self.assertEqual(peoples_choice_count, 7, "Should have 7 People's Choice songs (5 unused + 2 used)")
        
        # Verify used songs
        used_count = sum(1 for s in suggestions if s.is_used)
        self.assertEqual(used_count, 4, "Should have 4 used songs")
