from django.test import TestCase
from song_signup.tasks import GeniusParser, AllMusicalsParser

SONG_NAME = "Hello"
MUSICAL = "Book of Mormon"


class TestParsers(TestCase):
    # For live testing. Don't run this as automation - it charges you on Bing.
    def no_test_get_lyrics(self):
        parser = AllMusicalsParser()

        lyrics = list(parser.get_lyrics(SONG_NAME, MUSICAL))

    def no_test_get_lyrics_genius(self):
        # Uses dedicated API
        parser = GeniusParser()

        lyrics = list(parser.get_lyrics(SONG_NAME, MUSICAL))
