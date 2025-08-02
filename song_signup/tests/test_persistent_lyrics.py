from django.test import TestCase

from song_signup.models import PersistentLyrics


class TestPersistentLyricsSimilarity(TestCase):
    def setUp(self):
        # Create test lyrics with different similarity levels
        self.exact_match = PersistentLyrics.objects.create(
            song_name="Defying Gravity",
            artist_name="Wicked",
            lyrics="Something has changed within me...",
            url="https://example.com/defying-gravity"
        )

        self.similar_match = PersistentLyrics.objects.create(
            song_name="Defying Gravity (Reprise)",
            artist_name="Wicked",
            lyrics="I'm defying gravity...",
            url="https://example.com/defying-gravity-reprise"
        )

        self.partial_match = PersistentLyrics.objects.create(
            song_name="Gravity",
            artist_name="John Mayer",
            lyrics="Gravity is working against me...",
            url="https://example.com/gravity"
        )

        self.no_match = PersistentLyrics.objects.create(
            song_name="Popular",
            artist_name="Wicked",
            lyrics="You're gonna be popular...",
            url="https://example.com/popular"
        )

    def test_find_similar_lyrics_exact_match(self):
        """Test finding lyrics with exact song name match"""
        results = PersistentLyrics.find_similar_lyrics("Defying Gravity", "Wicked")

        # Should find matches ordered by similarity
        self.assertGreater(len(results), 0)
        self.assertEqual(results.first(), self.exact_match)

    def test_find_similar_lyrics_partial_match(self):
        """Test finding lyrics with partial song name match"""
        results = PersistentLyrics.find_similar_lyrics("Gravity", "Various")

        # Should find both Gravity matches
        result_songs = [r.song_name for r in results]
        self.assertIn("Defying Gravity", result_songs)
        self.assertIn("Gravity", result_songs)

    def test_find_similar_lyrics_no_match(self):
        """Test finding lyrics when no similar matches exist"""
        results = PersistentLyrics.find_similar_lyrics("Completely Different Song", "Unknown Artist")

        # Should return empty queryset or very low similarity matches
        self.assertEqual(len(results), 0)
