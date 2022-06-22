from django.test import TestCase

from song_signup.models import Singer, SongRequest
from flags.state import enable_flag
from mock import patch


class AlgorithmTest(TestCase):
    def setUp(self):
        enable_flag('CAN_SIGNUP')
        for i in range(30):
            Singer.objects.create_user(
                username=f"user_{i}",
                first_name=f"user_{i}",
                last_name="last_name",
                is_staff=True,
            )

    def complete_cycle2(self):
        with patch('song_signup.managers.CycleManager.cy2_complete') as cy2_complete_mock:
            cy2_complete_mock.return_value = True
            Singer.cycles.seal_cycles()

    def singer_add_songs(self, singer_id, num_songs):
        singer = Singer.objects.get(username=f"user_{singer_id}")

        for song_id in range(num_songs):
            SongRequest.objects.create(song_name=f"song_{singer_id}_{song_id}", singer=singer)

    def test_round_1_few_singers(self):
        """
        Three users each ask for five songs. The order should be
        ABCABCABC...
        Then, 2 new singers add their songs, one each. They should be bumped to the top and the order should be
        ABCDEABCABC...
        """
        for singer_id in range(3):
            self.singer_add_songs(singer_id, 5)

        all_songs = SongRequest.objects.filter(position__isnull=False).order_by("position").all()
        singer_order = [(song.singer.username, song.cycle) for song in all_songs]
        self.assertEqual(singer_order, [("user_0", 1.0), ("user_1", 1.0), ("user_2", 1.0),
                                        ("user_0", 1.1), ("user_1", 1.1), ("user_2", 1.1),
                                        ("user_0", 1.2), ("user_1", 1.2), ("user_2", 1.2),
                                        ("user_0", 1.3)])

        # 2 new singers add single song
        self.singer_add_songs(3, 1)
        self.singer_add_songs(4, 1)
        all_songs = SongRequest.objects.filter(position__isnull=False).order_by("position").all()
        singer_order = [(song.singer.username, song.cycle) for song in all_songs]
        # TODO: Bug here - users 3 and 4 take their place in the 2nd subcycle, even though they don't have a song,
        # TODO: and then users 0 and 1 who do have songs aren't in the list. The list in this case is only of len 8.
        # self.assertEqual(singer_order, [("user_0", 1.0), ("user_1", 1.0), ("user_2", 1.0), ("user_3", 1.0),
        #                                 ("user_4", 1.0), ("user_0", 1.1),  ("user_1", 1.1),
        #                                 ("user_2", 1.1), ("user_0", 1.2), ("user_1", 1.2)])

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
        The first ten users (ABC...IJ) will get a song
        Then the next ten users (KLM...) should be interspersed with the first ten like
        KALBMC etc.
        Then the third cycle will only include (once) users who were not in the first two cycles (bug? feature?)

        Note that this is slow because for each added song we are going over all of the songs (N^2). Still, 90^2
        is a very small number so it should be much faster
        """
        SINGERS_WITH_4_SONGS = [24, 25, 0, 12, 2, 14]  # Expected order in cycle 3.1
        SINGERS_WITH_5_SONGS = [24, 0, 12] # Expected order in cycle 3.2
        assert set(SINGERS_WITH_5_SONGS).issubset(set(SINGERS_WITH_4_SONGS))

        # Cycle 1 singers
        for i in range(10):
            singer = Singer.objects.get(username=f"user_{i}")
            for song in range(3):
                SongRequest.objects.create(song_name=f"song_{i}_{song}", singer=singer)

        # Cycle 2 singers
        for i in range(10, 20):
            singer = Singer.objects.get(username=f"user_{i}")
            for song in range(2):
                SongRequest.objects.create(song_name=f"song_{i}_{song}", singer=singer)

        # Cycle 3 singers
        for i in range(20, 30):
            singer = Singer.objects.get(username=f"user_{i}")
            SongRequest.objects.create(song_name=f"song_{i}_1", singer=singer)

        # Add a 4th song to some singers from different cycles - for 3.1 cycle
        for i in SINGERS_WITH_4_SONGS:
            singer = Singer.objects.get(username=f"user_{i}")
            SongRequest.objects.create(song_name=f"song_{i}_4", singer=singer)

        # Add a 5th song to some singers from different cycles - for 3.2 cycle
        for i in SINGERS_WITH_5_SONGS:
            singer = Singer.objects.get(username=f"user_{i}")
            SongRequest.objects.create(song_name=f"song_{i}_5", singer=singer)

        self.complete_cycle2()
        all_songs = SongRequest.objects.filter(position__isnull=False).order_by("position").all()

        # Cycle 1
        for i in range(10):
            self.assertEqual(all_songs[i].singer.username, f"user_{i}")
            self.assertEqual(all_songs[i].cycle, 1.0)

        # Cycle 2
        for i in range(10):
            # New singers
            self.assertEqual(all_songs[10 + 2 * i].singer.username, f"user_{i + 10}")
            self.assertEqual(all_songs[10 + 2 * i].cycle, 2.0)

            # Singers from cycle 1
            self.assertEqual(all_songs[10 + 2 * i + 1].singer.username, f"user_{i}")
            self.assertEqual(all_songs[10 + 2 * i + 1].cycle, 2.0)

        # Cycle 3
        for i in range(10):
            # New singers
            self.assertEqual(all_songs[30 + i].singer.username, f"user_{i + 20}")
            self.assertEqual(all_songs[30 + i].cycle, 3.0)

            # Gen 2 singers
            self.assertEqual(all_songs[40 + 2 * i].singer.username, f"user_{i + 10}")
            self.assertEqual(all_songs[40 + 2 * i].cycle, 3.0)

            # Gen 3 singers
            self.assertEqual(all_songs[40 + 2 * i + 1].singer.username, f"user_{i}")
            self.assertEqual(all_songs[40 + 2 * i + 1].cycle, 3.0)

        # Cycle 3.1 (Repeat cycle 3 with whoever still has songs)
        for position, singer in enumerate(SINGERS_WITH_4_SONGS):
            self.assertEqual(all_songs[60 + position].singer.username, f"user_{singer}")
            self.assertEqual(all_songs[60 + position].cycle, 3.1)

        # Cycle 3.2 (Repeat cycle 3 with whoever still has songs)
        for position, singer in enumerate(SINGERS_WITH_5_SONGS):
            self.assertEqual(all_songs[60 + len(SINGERS_WITH_4_SONGS) + position].singer.username, f"user_{singer}")
            self.assertEqual(all_songs[60 + len(SINGERS_WITH_4_SONGS) + position].cycle, 3.2)

        self.assertEqual(len(all_songs), 10 + 20 + 30 + len(SINGERS_WITH_4_SONGS) + len(SINGERS_WITH_5_SONGS))
