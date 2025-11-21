import datetime
from freezegun import freeze_time
from django.test import TestCase
from constance.test import override_config
from song_signup.tests.utils_for_tests import (
    SongRequestTestCase, create_singers, add_songs_to_singer, set_performed,
    get_song, add_songs_to_singers, add_partners, TEST_START_TIME, create_order, SING_SKU, ATTN_SKU,
    get_singer_str, create_audience, get_audience_str, EVENT_SKU
)
from peoples_choice.models import SongSuggestion
from song_signup.models import TicketsDepleted, Singer, SongRequest, _normalize_string, _fuzzy_match, _check_peoples_choice_match
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

    def test_raffle_winner_already_sang(self):
        [singer] = create_singers(1)
        self.assertFalse(singer.raffle_winner_already_sang)

        add_songs_to_singer(1, 2)
        self.assertFalse(singer.raffle_winner_already_sang)

        set_performed(1, 1)
        self.assertFalse(singer.raffle_winner_already_sang)

        singer.raffle_winner = True
        singer.save()
        self.assertTrue(singer.raffle_winner_already_sang)

        set_performed(1, 2)
        self.assertTrue(singer.raffle_winner_already_sang)

        singer.raffle_winner = False
        singer.save()
        self.assertFalse(singer.raffle_winner_already_sang)


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


class TestFuzzyMatching(TestCase):
    """Tests for fuzzy matching utilities used in people's choice matching."""
    def test_normalize_string_basic(self):
        self.assertEqual(_normalize_string("Defying Gravity"), "defying gravity")
        self.assertEqual(_normalize_string("DEFYING GRAVITY"), "defying gravity")
        self.assertEqual(_normalize_string("defying   gravity"), "defying gravity")
        self.assertEqual(_normalize_string("  Defying  Gravity  "), "defying gravity")
    
    def test_normalize_string_empty(self):
        self.assertEqual(_normalize_string(""), "")
        self.assertEqual(_normalize_string(None), "")
    
    def test_fuzzy_match_exact(self):
        self.assertTrue(_fuzzy_match("Defying Gravity", "Defying Gravity"))
        self.assertTrue(_fuzzy_match("Wicked", "Wicked"))
    
    def test_fuzzy_match_case_insensitive(self):
        self.assertTrue(_fuzzy_match("Defying Gravity", "defying gravity"))
        self.assertTrue(_fuzzy_match("WICKED", "wicked"))
        self.assertTrue(_fuzzy_match("The Phantom Of The Opera", "the phantom of the opera"))
    
    def test_fuzzy_match_extra_spaces(self):
        self.assertTrue(_fuzzy_match("Defying Gravity", "Defying  Gravity"))
        self.assertTrue(_fuzzy_match("The Phantom Of The Opera", "The  Phantom  Of  The  Opera"))
        self.assertTrue(_fuzzy_match("Defying Gravity", "  Defying Gravity  "))
    
    def test_fuzzy_match_typos_song_names(self):
        # Common typos for "Defying Gravity"
        self.assertTrue(_fuzzy_match("Defying Gravity", "Defying Gravty"))  # missing 'i'
        self.assertTrue(_fuzzy_match("Defying Gravity", "Defyng Gravity"))  # missing 'i'
        self.assertTrue(_fuzzy_match("Defying Gravity", "Defying Gravit"))  # missing 'y'
        self.assertTrue(_fuzzy_match("Defying Gravity", "Defying Gravety"))  # extra 'e'
        
        # Common typos for "Memory"
        self.assertTrue(_fuzzy_match("Memory", "Memmory"))  # double 'm'
        
        # Common typos for "Don't Rain on My Parade"
        self.assertTrue(_fuzzy_match("Don't Rain on My Parade", "Dont Rain on My Parade"))  # missing apostrophe
        self.assertTrue(_fuzzy_match("Don't Rain on My Parade", "Don't Rain On My Parade"))  # case difference
        self.assertTrue(_fuzzy_match("Don't Rain on My Parade", "Don't Rain on My Parrade"))  # typo in Parade
    
    def test_fuzzy_match_typos_musicals(self):
        # Common typos for "Wicked"
        self.assertTrue(_fuzzy_match("Wicked", "Wickd"))  # missing 'e'
        self.assertTrue(_fuzzy_match("Wicked", "Wiked"))  # missing 'c'
        
        # Common typos for "The Phantom of the Opera"
        self.assertTrue(_fuzzy_match("The Phantom of the Opera", "The Fantom of the Opera"))  # 'Ph' -> 'F'
        self.assertTrue(_fuzzy_match("The Phantom of the Opera", "The Phantom Of The Opera"))  # case
        self.assertTrue(_fuzzy_match("The Phantom of the Opera", "The Phantom of the Oprea"))  # typo in Opera
        
        # Common typos for "Les Misérables"
        self.assertTrue(_fuzzy_match("Les Misérables", "Les Miserables"))  # missing accent
        self.assertTrue(_fuzzy_match("Les Misérables", "Les Miserable"))  # missing 's' and accent
        self.assertTrue(_fuzzy_match("Les Misérables", "Les Miserablés"))  # accent in wrong place
        
        # Common typos for "Hamilton"
        self.assertTrue(_fuzzy_match("Hamilton", "Hamilon"))  # missing 't'
        self.assertTrue(_fuzzy_match("Hamilton", "Hamiltom"))  # swapped letters
        
        # Common typos for "The Lion King"
        self.assertTrue(_fuzzy_match("The Lion King", "The Lion Kng"))  # missing 'i'
        self.assertTrue(_fuzzy_match("The Lion King", "The Lion Kin"))  # missing 'g'
    
    def test_fuzzy_match_complex_broadway_songs(self):
        # "I Dreamed a Dream" from Les Misérables
        self.assertTrue(_fuzzy_match("I Dreamed a Dream", "I Dreamed A Dream"))
        self.assertTrue(_fuzzy_match("I Dreamed a Dream", "I Dreamed a Dreem"))  # typo
        
        # "Defying Gravity" from Wicked
        self.assertTrue(_fuzzy_match("Defying Gravity", "Defying Gravety"))  # typo
        
        # "Memory" from Cats
        self.assertTrue(_fuzzy_match("Memory", "Memmory"))  # double letter typo
        
        # "The Music of the Night" from Phantom
        self.assertTrue(_fuzzy_match("The Music of the Night", "The Music Of The Night"))
        self.assertTrue(_fuzzy_match("The Music of the Night", "The Music of the Nite"))  # typo
        
        # "Seasons of Love" from Rent
        self.assertTrue(_fuzzy_match("Seasons of Love", "Seasons Of Love"))
        self.assertTrue(_fuzzy_match("Seasons of Love", "Seasons of Luv"))  # typo
        
        # "You'll Be Back" from Hamilton
        self.assertTrue(_fuzzy_match("You'll Be Back", "Youll Be Back"))  # missing apostrophe
        self.assertTrue(_fuzzy_match("You'll Be Back", "You'll Be Bak"))  # typo
    
    def test_fuzzy_match_should_not_match_different_songs(self):
        # These should NOT match - they're different songs
        self.assertFalse(_fuzzy_match("Defying Gravity", "Defying Gravity (Reprise)"))
        self.assertFalse(_fuzzy_match("Memory", "Memories"))
        self.assertFalse(_fuzzy_match("I Dreamed a Dream", "I Have a Dream"))
    
    def test_fuzzy_match_edge_cases(self):
        # Empty strings
        self.assertFalse(_fuzzy_match("", "Wicked"))
        self.assertFalse(_fuzzy_match("Wicked", ""))
        self.assertFalse(_fuzzy_match("", ""))
        self.assertFalse(_fuzzy_match(None, "Wicked"))
        self.assertFalse(_fuzzy_match("Wicked", None))
    
    def test_fuzzy_match_threshold_boundary(self):
        # Test that threshold works - very different strings should not match
        self.assertFalse(_fuzzy_match("Wicked", "Hamilton"))
        self.assertFalse(_fuzzy_match("Defying Gravity", "Memory"))
        self.assertFalse(_fuzzy_match("The Phantom of the Opera", "Les Misérables"))
    
    def test_check_peoples_choice_match_with_real_data(self):
        
        # Create test suggestions
        event_sku = "TEST_SKU_123"
        SongSuggestion.objects.create(
            song_name="Defying Gravity",
            musical="Wicked",
            event_sku=event_sku
        )
        SongSuggestion.objects.create(
            song_name="Memory",
            musical="Cats",
            event_sku=event_sku
        )
        SongSuggestion.objects.create(
            song_name="The Music of the Night",
            musical="The Phantom of the Opera",
            event_sku=event_sku
        )
        
        # Test exact matches
        self.assertTrue(_check_peoples_choice_match("Defying Gravity", "Wicked", event_sku))
        self.assertTrue(_check_peoples_choice_match("Memory", "Cats", event_sku))
        
        # Test with typos
        self.assertTrue(_check_peoples_choice_match("Defying Gravty", "Wicked", event_sku))  # typo in song
        self.assertTrue(_check_peoples_choice_match("Defying Gravity", "Wickd", event_sku))  # typo in musical
        self.assertTrue(_check_peoples_choice_match("Memmory", "Cats", event_sku))  # typo in song
        self.assertTrue(_check_peoples_choice_match("The Music of the Night", "The Fantom of the Opera", event_sku))  # typo in musical
        
        # Test case insensitive
        self.assertTrue(_check_peoples_choice_match("defying gravity", "wicked", event_sku))
        self.assertTrue(_check_peoples_choice_match("DEFYING GRAVITY", "WICKED", event_sku))
        
        # Test extra spaces
        self.assertTrue(_check_peoples_choice_match("Defying  Gravity", "Wicked", event_sku))
        self.assertTrue(_check_peoples_choice_match("Defying Gravity", "  Wicked  ", event_sku))
        
        # Test non-matches
        self.assertFalse(_check_peoples_choice_match("Defying Gravity", "Hamilton", event_sku))  # wrong musical
        self.assertFalse(_check_peoples_choice_match("Memory", "Wicked", event_sku))  # wrong musical
        self.assertFalse(_check_peoples_choice_match("Hamilton", "Hamilton", event_sku))  # not in suggestions
        
        # Test with different event SKU
        self.assertFalse(_check_peoples_choice_match("Defying Gravity", "Wicked", "DIFFERENT_SKU"))
        
        # Test with empty event SKU
        self.assertFalse(_check_peoples_choice_match("Defying Gravity", "Wicked", ""))
        self.assertFalse(_check_peoples_choice_match("Defying Gravity", "Wicked", None))


class TestSongRequestPeoplesChoice(SongRequestTestCase):
    """Tests for is_peoples_choice field in SongRequest model."""
    
    def setUp(self):
        super().setUp()
        # Create peoples_choice suggestions for testing
        self.event_sku = "TEST_PC_SKU"
        SongSuggestion.objects.create(
            song_name="Defying Gravity",
            musical="Wicked",
            event_sku=self.event_sku
        )
        SongSuggestion.objects.create(
            song_name="Memory",
            musical="Cats",
            event_sku=self.event_sku
        )
        SongSuggestion.objects.create(
            song_name="The Music of the Night",
            musical="The Phantom of the Opera",
            event_sku=self.event_sku
        )
    
    @override_config(EVENT_SKU="TEST_PC_SKU")
    def test_create_song_matching_peoples_choice(self):
        """Test that creating a new song that matches a peoples_choice suggestion sets is_peoples_choice=True"""
        [singer] = create_singers(1)
        
        # Create song that matches exactly
        song = SongRequest.objects.create(
            song_name="Defying Gravity",
            musical="Wicked",
            singer=singer
        )
        self.assertTrue(song.is_peoples_choice)
        
        # Create song that matches with fuzzy matching (typo)
        song2 = SongRequest.objects.create(
            song_name="Defying Gravty",  # typo
            musical="Wicked",
            singer=singer
        )
        self.assertTrue(song2.is_peoples_choice)
        
        # Create song that matches with fuzzy matching in musical
        song3 = SongRequest.objects.create(
            song_name="Memory",
            musical="Cat",  # typo
            singer=singer
        )
        self.assertTrue(song3.is_peoples_choice)
    
    @override_config(EVENT_SKU="TEST_PC_SKU")
    def test_create_song_not_matching_peoples_choice(self):
        """Test that creating a new song that doesn't match sets is_peoples_choice=False"""
        [singer] = create_singers(1)
        
        # Create song that doesn't match
        song = SongRequest.objects.create(
            song_name="Hamilton",
            musical="Hamilton",
            singer=singer
        )
        self.assertFalse(song.is_peoples_choice)
        
        # Create song with completely different name
        song2 = SongRequest.objects.create(
            song_name="Some Other Song",
            musical="Some Other Musical",
            singer=singer
        )
        self.assertFalse(song2.is_peoples_choice)
    
    @override_config(EVENT_SKU="TEST_PC_SKU")
    def test_update_song_notes_only(self):
        """Test that updating only notes does NOT change is_peoples_choice"""
        [singer] = create_singers(1)
        
        # Create a song that matches
        song = SongRequest.objects.create(
            song_name="Defying Gravity",
            musical="Wicked",
            singer=singer,
            notes="Original notes"
        )
        self.assertTrue(song.is_peoples_choice)
        
        # Update only notes
        song.notes = "Updated notes"
        song.save()
        
        # is_peoples_choice should remain True
        song.refresh_from_db()
        self.assertTrue(song.is_peoples_choice)
        self.assertEqual(song.notes, "Updated notes")
    
    @override_config(EVENT_SKU="TEST_PC_SKU")
    def test_update_song_name_to_match(self):
        """Test that updating song name to match a peoples_choice suggestion sets is_peoples_choice=True"""
        [singer] = create_singers(1)
        
        # Create a song that doesn't match
        song = SongRequest.objects.create(
            song_name="Hamilton",
            musical="Hamilton",
            singer=singer
        )
        self.assertFalse(song.is_peoples_choice)
        
        # Update song name to match
        song.song_name = "Defying Gravity"
        song.musical = "Wicked"
        song.save()
        
        # is_peoples_choice should now be True
        song.refresh_from_db()
        self.assertTrue(song.is_peoples_choice)
    
    @override_config(EVENT_SKU="TEST_PC_SKU")
    def test_update_song_name_to_not_match(self):
        """Test that updating song name to not match sets is_peoples_choice=False"""
        [singer] = create_singers(1)
        
        # Create a song that matches
        song = SongRequest.objects.create(
            song_name="Defying Gravity",
            musical="Wicked",
            singer=singer
        )
        self.assertTrue(song.is_peoples_choice)
        
        # Update song name to not match
        song.song_name = "Hamilton"
        song.musical = "Hamilton"
        song.save()
        
        # is_peoples_choice should now be False
        song.refresh_from_db()
        self.assertFalse(song.is_peoples_choice)
    
    @override_config(EVENT_SKU="TEST_PC_SKU")
    def test_update_song_musical_only(self):
        """Test that updating only musical updates is_peoples_choice"""
        [singer] = create_singers(1)
        
        # Create a song that doesn't match
        song = SongRequest.objects.create(
            song_name="Memory",
            musical="Wrong Musical",
            singer=singer
        )
        self.assertFalse(song.is_peoples_choice)
        
        # Update musical to match
        song.musical = "Cats"
        song.save()
        
        # is_peoples_choice should now be True
        song.refresh_from_db()
        self.assertTrue(song.is_peoples_choice)
    
    @override_config(EVENT_SKU="TEST_PC_SKU")
    def test_update_song_with_fuzzy_match(self):
        """Test that fuzzy matching works when updating songs"""
        [singer] = create_singers(1)
        
        # Create a song that doesn't match
        song = SongRequest.objects.create(
            song_name="Hamilton",
            musical="Hamilton",
            singer=singer
        )
        self.assertFalse(song.is_peoples_choice)
        
        # Update with typo that should still match
        song.song_name = "Defying Gravty"  # typo in Gravity
        song.musical = "Wicked"
        song.save()
        
        # Should match despite typo
        song.refresh_from_db()
        self.assertTrue(song.is_peoples_choice)
    
    @override_config(EVENT_SKU="DIFFERENT_SKU")
    def test_different_event_sku_does_not_match(self):
        """Test that songs don't match if event SKU is different"""
        [singer] = create_singers(1)
        
        # Create song that would match if SKU was correct
        song = SongRequest.objects.create(
            song_name="Defying Gravity",
            musical="Wicked",
            singer=singer
        )
        # Should not match because event SKU is different
        self.assertFalse(song.is_peoples_choice)
    
    @override_config(EVENT_SKU="")
    def test_empty_event_sku_does_not_match(self):
        """Test that songs don't match if event SKU is empty"""
        [singer] = create_singers(1)
        
        # Create song that would match if SKU was set
        song = SongRequest.objects.create(
            song_name="Defying Gravity",
            musical="Wicked",
            singer=singer
        )
        # Should not match because event SKU is empty
        self.assertFalse(song.is_peoples_choice)
    
    @override_config(EVENT_SKU="TEST_PC_SKU")
    def test_only_song_name_matches_not_musical(self):
        """Test that if only song name matches but musical doesn't, it should NOT match"""
        [singer] = create_singers(1)
        
        # Song name matches "Defying Gravity" but musical is wrong
        song = SongRequest.objects.create(
            song_name="Defying Gravity",
            musical="Hamilton",  # Wrong musical
            singer=singer
        )
        self.assertFalse(song.is_peoples_choice)
        
        # Song name matches with typo but musical is wrong
        song2 = SongRequest.objects.create(
            song_name="Defying Gravty",  # Matches with fuzzy matching
            musical="Hamilton",  # Wrong musical
            singer=singer
        )
        self.assertFalse(song2.is_peoples_choice)
    
    @override_config(EVENT_SKU="TEST_PC_SKU")
    def test_only_musical_matches_not_song_name(self):
        """Test that if only musical matches but song name doesn't, it should NOT match"""
        [singer] = create_singers(1)
        
        # Musical matches "Wicked" but song name is wrong
        song = SongRequest.objects.create(
            song_name="Hamilton",  # Wrong song name
            musical="Wicked",  # Correct musical
            singer=singer
        )
        self.assertFalse(song.is_peoples_choice)
        
        # Musical matches with typo but song name is wrong
        song2 = SongRequest.objects.create(
            song_name="Some Other Song",  # Wrong song name
            musical="Wickd",  # Matches "Wicked" with fuzzy matching
            singer=singer
        )
        self.assertFalse(song2.is_peoples_choice)
    
    @override_config(EVENT_SKU="TEST_PC_SKU")
    def test_update_only_song_name_matches_not_musical(self):
        """Test that updating to match only song name (not musical) does NOT set is_peoples_choice"""
        [singer] = create_singers(1)
        
        # Create a song that doesn't match
        song = SongRequest.objects.create(
            song_name="Hamilton",
            musical="Hamilton",
            singer=singer
        )
        self.assertFalse(song.is_peoples_choice)
        
        # Update song name to match but keep wrong musical
        song.song_name = "Defying Gravity"
        song.musical = "Hamilton"  # Still wrong musical
        song.save()
        
        # Should NOT match because musical is wrong
        song.refresh_from_db()
        self.assertFalse(song.is_peoples_choice)
    
    @override_config(EVENT_SKU="TEST_PC_SKU")
    def test_update_only_musical_matches_not_song_name(self):
        """Test that updating to match only musical (not song name) does NOT set is_peoples_choice"""
        [singer] = create_singers(1)
        
        # Create a song that doesn't match
        song = SongRequest.objects.create(
            song_name="Hamilton",
            musical="Hamilton",
            singer=singer
        )
        self.assertFalse(song.is_peoples_choice)
        
        # Update musical to match but keep wrong song name
        song.song_name = "Hamilton"  # Still wrong song name
        song.musical = "Wicked"  # Correct musical
        song.save()
        
        # Should NOT match because song name is wrong
        song.refresh_from_db()
        self.assertFalse(song.is_peoples_choice)





