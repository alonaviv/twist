from django.test import TestCase
from song_signup.tasks import (GeniusExaParser, GeniusApiParser, AllMusicalsParser, ShironetParser,
                               AzLyricsParser, LyricsTranslateParser, TheMusicalLyricsParser)


SONG_NAME = "Hello"
MUSICAL = "Book of Mormon"


class TestParsers(TestCase):
    # For live testing. Don't run this as automation - it charges you on Bing.
    def no_test_get_lyrics_allmusicals_parser(self):
        parser = AllMusicalsParser()

        lyrics = list(parser.get_lyrics(SONG_NAME, MUSICAL))
        breakpoint()

    def no_test_get_lyrics_genius_exa(self):
        # Uses Exa search to scrape website
        parser = GeniusExaParser()

        lyrics = list(parser.get_lyrics(SONG_NAME, MUSICAL))
        breakpoint()

    def no_test_get_lyrics_genius_api(self):
        # Uses dedicated API
        parser = GeniusApiParser()

        lyrics = list(parser.get_lyrics(SONG_NAME, MUSICAL))
        breakpoint()

    def no_test_get_lyrics_shironet_parser(self):
        parser = ShironetParser()

        lyrics = list(parser.get_lyrics(SONG_NAME, MUSICAL))
        breakpoint()

    def no_test_get_lyrics_azlyrics_parser(self):
        parser = AzLyricsParser()

        lyrics = list(parser.get_lyrics(SONG_NAME, MUSICAL))
        breakpoint()

    def no_test_get_lyrics_lyricstranslate_parser(self):
        parser = LyricsTranslateParser()

        lyrics = list(parser.get_lyrics(SONG_NAME, MUSICAL))
        breakpoint()

    def no_test_get_lyrics_themusicallyrics_parser(self):
        parser = TheMusicalLyricsParser()

        lyrics = list(parser.get_lyrics(SONG_NAME, MUSICAL))
        breakpoint()

