import datetime
from freezegun import freeze_time
from django.test import TestCase, TransactionTestCase
from song_signup.tests.utils_for_tests import (
    SongRequestTestCase, create_singers, add_songs_to_singer, set_performed,
    get_song, add_songs_to_singers, add_partners, TEST_START_TIME, create_order, SING_SKU, ATTN_SKU,
    get_singer_str, create_audience, get_audience_str
)
from song_signup.models import TicketsDepleted, Singer, SongSuggestion
from django.core.management import call_command
from django.db import IntegrityError


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


class TestSongSuggestionModel(TestCase):
    def setUp(self):
        [self.suggester] = create_singers(1)
        self.suggestion = SongSuggestion.objects.create(
            song_name='Defying Gravity',
            musical='Wicked',
            suggested_by=self.suggester
        )
    
    def test_vote_count_empty(self):
        """Test vote_count returns 0 when no votes."""
        self.assertEqual(self.suggestion.vote_count, 0)
    
    def test_vote_count_single_vote(self):
        """Test vote_count returns 1 after one vote."""
        [voter] = create_singers([2])
        self.suggestion.voters.add(voter)
        self.assertEqual(self.suggestion.vote_count, 1)
    
    def test_vote_count_multiple_votes(self):
        """Test vote_count returns correct count with multiple votes."""
        voters = create_singers([2, 3, 4])
        self.suggestion.voters.set(voters)
        self.assertEqual(self.suggestion.vote_count, 3)
    
    def test_vote_count_mixed_singers_and_audience(self):
        """Test vote_count works with both singers and audience."""
        singers = create_singers([2, 3])
        audience = create_audience([4, 5])
        self.suggestion.voters.set(singers + audience)
        self.assertEqual(self.suggestion.vote_count, 4)
    
    def test_user_voted_false_when_no_vote(self):
        """Test user_voted returns False when user hasn't voted."""
        [user] = create_singers([2])
        self.assertFalse(self.suggestion.user_voted(user))
    
    def test_user_voted_true_when_voted(self):
        """Test user_voted returns True when user has voted."""
        [user] = create_singers([2])
        self.suggestion.voters.add(user)
        self.assertTrue(self.suggestion.user_voted(user))
    
    def test_user_voted_after_unvote(self):
        """Test user_voted returns False after removing vote."""
        [user] = create_singers([2])
        self.suggestion.voters.add(user)
        self.assertTrue(self.suggestion.user_voted(user))
        
        self.suggestion.voters.remove(user)
        self.assertFalse(self.suggestion.user_voted(user))
    
    def test_user_voted_different_users(self):
        """Test user_voted correctly distinguishes between users."""
        user1, user2 = create_singers([2, 3])
        
        self.suggestion.voters.add(user1)
        self.assertTrue(self.suggestion.user_voted(user1))
        self.assertFalse(self.suggestion.user_voted(user2))
    
    def test_user_voted_with_audience(self):
        """Test user_voted works with audience members."""
        [audience] = create_audience(1)
        self.assertFalse(self.suggestion.user_voted(audience))
        
        self.suggestion.voters.add(audience)
        self.assertTrue(self.suggestion.user_voted(audience))
    
    def test_unique_constraint_same_suggester(self):
        """Test that same song+musical cannot be created twice, even by same suggester."""
        with self.assertRaises(IntegrityError):
            SongSuggestion.objects.create(
                song_name='Defying Gravity',
                musical='Wicked',
                suggested_by=self.suggester
            )
    
    def test_unique_constraint_different_suggester(self):
        """Test that same song+musical cannot be created by different suggester."""
        [other_suggester] = create_singers([2])
        with self.assertRaises(IntegrityError):
            SongSuggestion.objects.create(
                song_name='Defying Gravity',
                musical='Wicked',
                suggested_by=other_suggester
            )
    
    def test_same_song_different_musical_allowed(self):
        """Test that same song from different musical is allowed."""
        suggestion2 = SongSuggestion.objects.create(
            song_name='Defying Gravity',
            musical='Hamilton',  # Different musical
            suggested_by=self.suggester
        )
        # Should have 2 total: 1 from setUp + 1 from this test
        self.assertEqual(SongSuggestion.objects.count(), 2)
        self.assertEqual(suggestion2.song_name, 'Defying Gravity')
        self.assertEqual(suggestion2.musical, 'Hamilton')
    
    def test_different_song_same_musical_allowed(self):
        """Test that different song from same musical is allowed."""
        suggestion2 = SongSuggestion.objects.create(
            song_name='Popular',  # Different song
            musical='Wicked',
            suggested_by=self.suggester
        )
        # Should have 2 total: 1 from setUp + 1 from this test
        self.assertEqual(SongSuggestion.objects.count(), 2)
        self.assertEqual(suggestion2.song_name, 'Popular')
        self.assertEqual(suggestion2.musical, 'Wicked')


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





