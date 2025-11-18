from rest_framework import status
from rest_framework.test import APITestCase

from .models import SongSuggestion


class SongSuggestionAPITests(APITestCase):
    def setUp(self):
        self.create_url = '/peoples-choice/create_song_suggestion'
        self.list_url = '/peoples-choice/list_song_suggestions/{sku}'
        self.vote_url = '/peoples-choice/vote_song_suggestion/{song_id}'
        self.choose_url = '/peoples-choice/choose_song_suggestion/{song_id}'

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

    def test_choose_song(self):
        song = SongSuggestion.objects.create(
            song_name='One Day More',
            musical='Les Miserables',
            event_sku='SKU1',
        )
        response = self.client.post(
            self.choose_url.format(song_id=song.id),
            {'chosen_by': 'Elphaba'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        song.refresh_from_db()
        self.assertTrue(song.chosen)
        self.assertEqual(song.chosen_by, 'Elphaba')

    def test_choose_song_twice_fails(self):
        song = SongSuggestion.objects.create(
            song_name='Memory',
            musical='Cats',
            event_sku='SKU1',
            chosen=True,
            chosen_by='Grizabella',
        )
        response = self.client.post(
            self.choose_url.format(song_id=song.id),
            {'chosen_by': 'Old Deuteronomy'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

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
