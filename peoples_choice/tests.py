from rest_framework import status
from rest_framework.test import APITestCase

from .models import SongSuggestion


class SongSuggestionAPITests(APITestCase):
    def setUp(self):
        self.create_url = '/peoples-choice/create_song_suggestion'
        self.list_url = '/peoples-choice/list_song_suggestions/{sku}'
        self.vote_url = '/peoples-choice/vote_song_suggestion/{song_id}/'
        self.choose_url = '/peoples-choice/choose_song_suggestion/{song_id}/'

    def test_create_song_suggestion(self):
        payload = {
            'song_name': 'Defying Gravity',
            'musical': 'Wicked',
            'event_sku': 'SKU123',
        }
        response = self.client.post(self.create_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(SongSuggestion.objects.count(), 1)

    def test_vote_increments(self):
        song = SongSuggestion.objects.create(
            song_name='Cabaret',
            musical='Cabaret',
            event_sku='SKU1',
        )
        response = self.client.post(
            self.vote_url.format(song_id=song.id), {}, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        song.refresh_from_db()
        self.assertEqual(song.votes, 1)

    def assert_choice(self, song, chosen_by, in_app):
        """Checks a suggestion's whole choice state; an empty chosen_by means nobody chose it."""
        song.refresh_from_db()
        self.assertEqual(song.chosen, bool(chosen_by))
        self.assertEqual(song.chosen_by, chosen_by)
        self.assertEqual(song.chosen_in_app, in_app)

    def choose(self, song, **data):
        return self.client.post(self.choose_url.format(song_id=song.id), data, format='json')

    def test_choose_song(self):
        song = SongSuggestion.objects.create(song_name='One Day More', musical='Les Miserables', event_sku='SKU1')
        response = self.choose(song, chosen_by='Elphaba')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assert_choice(song, chosen_by='Elphaba', in_app=False)

    def test_choose_in_app(self):
        song = SongSuggestion.objects.create(song_name='Satisfied', musical='Hamilton', event_sku='SKU1')
        response = self.choose(song, chosen_by='Angelica Schuyler', in_app=True)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.json()['chosen_in_app'])
        self.assert_choice(song, chosen_by='Angelica Schuyler', in_app=True)

    def test_choosing_another_song_unchooses_the_in_app_choice(self):
        first = SongSuggestion.objects.create(song_name='Satisfied', musical='Hamilton', event_sku='SKU1')
        second = SongSuggestion.objects.create(song_name='Helpless', musical='Hamilton', event_sku='SKU1')
        self.choose(first, chosen_by='Angelica Schuyler', in_app=True)
        self.choose(second, chosen_by='Angelica Schuyler', in_app=True)
        self.assert_choice(first, chosen_by='', in_app=False)
        self.assert_choice(second, chosen_by='Angelica Schuyler', in_app=True)

    def test_choosing_own_song_again_in_app_keeps_it(self):
        song = SongSuggestion.objects.create(song_name='Satisfied', musical='Hamilton', event_sku='SKU1')
        self.choose(song, chosen_by='Angelica Schuyler', in_app=True)
        response = self.choose(song, chosen_by='Angelica Schuyler', in_app=True)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assert_choice(song, chosen_by='Angelica Schuyler', in_app=True)

    def test_unchoose_clears_in_app(self):
        song = SongSuggestion.objects.create(song_name='Satisfied', musical='Hamilton', event_sku='SKU1',
                                             chosen=True, chosen_by='Angelica Schuyler', chosen_in_app=True)
        response = self.choose(song, chosen_by='Angelica Schuyler', action='unchoose')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assert_choice(song, chosen_by='', in_app=False)

    def test_taking_over_a_website_choice_in_app(self):
        # The singer chose this song on the People's Choice website, typing just "Angelica". In the app, they tap
        # "That's mine" on it, which chooses it again under their app name. The choice then carries the app name and
        # is marked in-app, so the app recognises it as theirs (it finds a singer's choice by name).
        song = SongSuggestion.objects.create(song_name='Satisfied', musical='Hamilton', event_sku='SKU1',
                                             chosen=True, chosen_by='Angelica')
        self.choose(song, chosen_by='Angelica Schuyler', in_app=True)
        self.assert_choice(song, chosen_by='Angelica Schuyler', in_app=True)

    def test_choose_without_name_fails(self):
        song = SongSuggestion.objects.create(song_name='Satisfied', musical='Hamilton', event_sku='SKU1')
        response = self.choose(song, in_app=True)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assert_choice(song, chosen_by='', in_app=False)

    def test_choosing_a_chosen_song_on_site_takes_it_over(self):
        # The endpoint overwrites any choice; the site itself disables "Already chosen" songs
        song = SongSuggestion.objects.create(song_name='Memory', musical='Cats', event_sku='SKU1',
                                             chosen=True, chosen_by='Grizabella', chosen_in_app=True)
        response = self.choose(song, chosen_by='Old Deuteronomy')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assert_choice(song, chosen_by='Old Deuteronomy', in_app=False)

    def test_choosing_in_app_unchooses_a_website_choice_under_the_same_name(self):
        on_site = SongSuggestion.objects.create(song_name='Satisfied', musical='Hamilton', event_sku='SKU1',
                                                chosen=True, chosen_by='Angelica Schuyler')
        in_app = SongSuggestion.objects.create(song_name='Helpless', musical='Hamilton', event_sku='SKU1')
        self.choose(in_app, chosen_by='Angelica Schuyler', in_app=True)
        self.assert_choice(on_site, chosen_by='', in_app=False)
        self.assert_choice(in_app, chosen_by='Angelica Schuyler', in_app=True)

    def test_choosing_on_site_unchooses_an_in_app_choice_under_the_same_name(self):
        in_app = SongSuggestion.objects.create(song_name='Satisfied', musical='Hamilton', event_sku='SKU1',
                                               chosen=True, chosen_by='Angelica Schuyler', chosen_in_app=True)
        on_site = SongSuggestion.objects.create(song_name='Helpless', musical='Hamilton', event_sku='SKU1')
        self.choose(on_site, chosen_by='Angelica Schuyler')
        self.assert_choice(in_app, chosen_by='', in_app=False)
        self.assert_choice(on_site, chosen_by='Angelica Schuyler', in_app=False)

    def test_unchoosing_stays_within_the_event(self):
        other_event = SongSuggestion.objects.create(song_name='Satisfied', musical='Hamilton', event_sku='SKU2',
                                                    chosen=True, chosen_by='Angelica Schuyler', chosen_in_app=True)
        song = SongSuggestion.objects.create(song_name='Helpless', musical='Hamilton', event_sku='SKU1')
        self.choose(song, chosen_by='Angelica Schuyler', in_app=True)
        self.assert_choice(other_event, chosen_by='Angelica Schuyler', in_app=True)
        self.assert_choice(song, chosen_by='Angelica Schuyler', in_app=True)

    def test_unchoosing_leaves_other_names_alone(self):
        someone_else = SongSuggestion.objects.create(song_name='Satisfied', musical='Hamilton', event_sku='SKU1',
                                                     chosen=True, chosen_by='Eliza Hamilton', chosen_in_app=True)
        song = SongSuggestion.objects.create(song_name='Helpless', musical='Hamilton', event_sku='SKU1')
        self.choose(song, chosen_by='Angelica Schuyler', in_app=True)
        self.assert_choice(someone_else, chosen_by='Eliza Hamilton', in_app=True)
        self.assert_choice(song, chosen_by='Angelica Schuyler', in_app=True)

    def test_rechoosing_own_song_on_site_clears_in_app(self):
        song = SongSuggestion.objects.create(song_name='Satisfied', musical='Hamilton', event_sku='SKU1',
                                             chosen=True, chosen_by='Angelica Schuyler', chosen_in_app=True)
        self.choose(song, chosen_by='Angelica Schuyler')
        self.assert_choice(song, chosen_by='Angelica Schuyler', in_app=False)

    def test_unchoose_someone_elses_choice_fails(self):
        song = SongSuggestion.objects.create(song_name='Satisfied', musical='Hamilton', event_sku='SKU1',
                                             chosen=True, chosen_by='Angelica Schuyler', chosen_in_app=True)
        response = self.choose(song, chosen_by='Eliza Hamilton', action='unchoose')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assert_choice(song, chosen_by='Angelica Schuyler', in_app=True)

    def test_unchoose_an_unchosen_song_changes_nothing(self):
        song = SongSuggestion.objects.create(song_name='Satisfied', musical='Hamilton', event_sku='SKU1')
        response = self.choose(song, chosen_by='Angelica Schuyler', action='unchoose')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assert_choice(song, chosen_by='', in_app=False)

    def test_invalid_action_fails(self):
        song = SongSuggestion.objects.create(song_name='Satisfied', musical='Hamilton', event_sku='SKU1')
        response = self.choose(song, chosen_by='Angelica Schuyler', action='grab')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assert_choice(song, chosen_by='', in_app=False)

    def test_list_by_sku(self):
        SongSuggestion.objects.create(
            song_name='Popular',
            musical='Wicked',
            event_sku='EVT1',
            votes=5,
        )
        SongSuggestion.objects.create(
            song_name='No Good Deed',
            musical='Wicked',
            event_sku='EVT1',
            votes=2,
        )
        response = self.client.get(self.list_url.format(sku='EVT1'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]['votes'], 5)

    def test_list_empty_returns_404(self):
        response = self.client.get(self.list_url.format(sku='NONE'))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
