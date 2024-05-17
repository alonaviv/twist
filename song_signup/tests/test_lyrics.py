from django.test import TestCase
from song_signup.tasks import GenuisParser, AllMusicalsParser

SONG_NAME = "Hello"
MUSICAL = "Book of Mormon"


class TestParsers(TestCase):
    # For live testing. Don't run this as automation - it charges you on Bing.
    def test_get_lyrics(self):
        parser = AllMusicalsParser()

        lyrics = list(parser.get_lyrics(SONG_NAME, MUSICAL))
        3

    def test_get_lyrics_genius(self):
        # Uses dedicated API
        parser = GenuisParser()

        lyrics = list(parser.get_lyrics(SONG_NAME, MUSICAL))
        3
