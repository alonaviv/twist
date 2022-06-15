from django.test import TestCase
from song_signup.managers import FIRST_CYCLE_LEN

from song_signup.models import Singer, SongRequest


class AlgorithmTest(TestCase):
    def setUp(self):
        for i in range(30):
            Singer.objects.create_user(
                username=f"user_{i}",
                first_name=f"user_{i}",
                last_name="last_name",
                is_staff=True,
            )

    def test_round_1_few_singers(self):
        """
        Three users each ask for five songs. The order should be
        ABCABCABC...
        """
        for i in range(3):
            singer = Singer.objects.get(username=f"user_{i}")
            for song in range(5):
                SongRequest.objects.create(song_name=f"song_{i}_{song}", singer=singer)

        all_songs = SongRequest.objects.order_by("position").all()
        for i, song in enumerate(all_songs):
            self.assertEqual(song.singer.username, f"user_{i%3}")

            if i >= FIRST_CYCLE_LEN - 1:
                # There is a bug for now where if there are less than 10 singers who request songs
                # we get stuck after 10 songs because the second cycle hasn't started yet
                break

    def test_duet_round_1(self):
        """
        Two users ask for songs, then one of them requests a duet.
        It should count as both of their songs so the first user should sing again
        """
        s1 = Singer.objects.get(username="user_1")
        s2 = Singer.objects.get(username="user_2")
        SongRequest.objects.create(song_name="song_1_0", singer=s1)
        SongRequest.objects.create(song_name="song_2_0", singer=s2)
        SongRequest.objects.create(song_name="song_1_1", singer=s1, duet_partner=s2)
        SongRequest.objects.create(song_name="song_2_2", singer=s2)
        SongRequest.objects.create(song_name="song_1_2", singer=s1)

        all_songs = SongRequest.objects.order_by("position").all()
        self.assertEqual(all_songs[0].singer.id, s1.id)
        self.assertEqual(all_songs[1].singer.id, s2.id)
        self.assertEqual(all_songs[2].singer.id, s1.id)
        self.assertEqual(all_songs[3].singer.id, s1.id)  # <- This is what we're actually checking
        self.assertEqual(all_songs[4].singer.id, s2.id)

    def test_duet_round_1_skips_to_third_person(self):
        """
        Three users in round 1, one of them requests a duet.
        It should count as both of their songs so the order should skip to the third user sing again
        """
        s1 = Singer.objects.get(username="user_1")
        s2 = Singer.objects.get(username="user_2")
        s3 = Singer.objects.get(username="user_3")
        SongRequest.objects.create(song_name="song_1_0", singer=s1)
        SongRequest.objects.create(song_name="song_2_0", singer=s2)
        SongRequest.objects.create(song_name="song_3_0", singer=s3)
        SongRequest.objects.create(song_name="song_1_1", singer=s1, duet_partner=s2)
        SongRequest.objects.create(song_name="song_2_1", singer=s2)
        SongRequest.objects.create(song_name="song_3_1", singer=s3)

        all_songs = SongRequest.objects.order_by("position").all()
        self.assertEqual(all_songs[0].singer.id, s1.id)
        self.assertEqual(all_songs[1].singer.id, s2.id)
        self.assertEqual(all_songs[2].singer.id, s3.id)
        self.assertEqual(all_songs[3].singer.id, s1.id)
        self.assertEqual(all_songs[4].singer.id, s3.id)  # <- This is what we're actually checking
        self.assertEqual(all_songs[5].singer.id, s2.id)

    def test_round_2_and_3(self):
        """
        Each of 30 users requests 3 songs
        The first ten users (ABC...IJ) will get a song
        Then the next ten users (KLM...) should be interspersed with the first ten like
        KALBMC etc.
        Then the third cycle will only include (once) users who were not in the first two cycles (bug? feature?)

        Note that this is slow because for each added song we are going over all of the songs (N^2). Still, 90^2
        is a very small number so it should be much faster
        """
        for i in range(30):
            singer = Singer.objects.get(username=f"user_{i}")
            for song in range(3):
                SongRequest.objects.create(song_name=f"song_{i}_{song}", singer=singer)

        all_songs = SongRequest.objects.order_by("position").all()
        # Cycle 1
        for i in range(10):
            self.assertEqual(all_songs[i].singer.username, f"user_{i}")

        # Cycle 2
        for i in range(10):
            self.assertEqual(all_songs[10 + 2 * i].singer.username, f"user_{i+10}")
            self.assertEqual(all_songs[10 + 2 * i + 1].singer.username, f"user_{i}")

        for i in range(10):
            self.assertEqual(all_songs[30 + i].singer.username, f"user_{i+20}")
