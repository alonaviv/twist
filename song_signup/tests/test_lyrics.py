from django.test import TestCase
from song_signup.tasks import GenuisParser

SONG_NAME = "Mama I'm a Big Girl Now"
MUSICAL = "Hairspray"

class TestParsers(TestCase):
    def interactive_test_get_lyrics(self):
        # For live testing. Don't run this as automation - it charges you on Bing.
        parser = GenuisParser()

        lyrics = list(parser.get_lyrics(SONG_NAME, MUSICAL))
        3
