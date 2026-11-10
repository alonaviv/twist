from constance.test import override_config
from rest_framework import status
from rest_framework.test import APITestCase

from song_signup.models import SongRequest
from song_signup.tests.utils_for_tests import create_audience, create_singers
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

    def test_unchoose_clears_in_app(self):
        song = SongSuggestion.objects.create(song_name='Satisfied', musical='Hamilton', event_sku='SKU1',
                                             chosen=True, chosen_by='Angelica Schuyler', chosen_in_app=True)
        response = self.choose(song, chosen_by='Angelica Schuyler', action='unchoose')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assert_choice(song, chosen_by='', in_app=False)

    def test_choose_without_name_fails(self):
        song = SongSuggestion.objects.create(song_name='Satisfied', musical='Hamilton', event_sku='SKU1')
        response = self.choose(song)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assert_choice(song, chosen_by='', in_app=False)

    def test_choosing_a_chosen_song_on_site_takes_it_over(self):
        # The endpoint overwrites any choice; the site itself disables "Already chosen" songs
        song = SongSuggestion.objects.create(song_name='Memory', musical='Cats', event_sku='SKU1',
                                             chosen=True, chosen_by='Grizabella', chosen_in_app=True)
        response = self.choose(song, chosen_by='Old Deuteronomy')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assert_choice(song, chosen_by='Old Deuteronomy', in_app=False)

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
        self.choose(song, chosen_by='Angelica Schuyler')
        self.assert_choice(other_event, chosen_by='Angelica Schuyler', in_app=True)
        self.assert_choice(song, chosen_by='Angelica Schuyler', in_app=False)

    def test_unchoosing_leaves_other_names_alone(self):
        someone_else = SongSuggestion.objects.create(song_name='Satisfied', musical='Hamilton', event_sku='SKU1',
                                                     chosen=True, chosen_by='Eliza Hamilton', chosen_in_app=True)
        song = SongSuggestion.objects.create(song_name='Helpless', musical='Hamilton', event_sku='SKU1')
        self.choose(song, chosen_by='Angelica Schuyler')
        self.assert_choice(someone_else, chosen_by='Eliza Hamilton', in_app=True)
        self.assert_choice(song, chosen_by='Angelica Schuyler', in_app=False)

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


@override_config(PEOPLES_CHOICE_EVENT_SKU='SKU1')
class AppPeoplesChoiceSelectionTests(APITestCase):
    def setUp(self):
        self.singer, = create_singers(1)
        self.name = self.singer.get_full_name()
        self.client.force_login(self.singer)

    def suggestion(self, song_name, event_sku='SKU1', chosen_by='', in_app=False):
        return SongSuggestion.objects.create(song_name=song_name, musical='Hamilton', event_sku=event_sku,
                                             chosen=bool(chosen_by), chosen_by=chosen_by, chosen_in_app=in_app)

    def set_selection(self, song):
        return self.client.post(f'/peoples-choice/set_app_peoples_choice_selection/{song.id}/')

    def clear_selection(self):
        return self.client.post('/peoples-choice/clear_app_peoples_choice_selection/')

    def sign_up(self):
        SongRequest.objects.create(song_name='Wait For It', musical='Hamilton', singer=self.singer)

    def assert_choice(self, song, chosen_by, in_app):
        song.refresh_from_db()
        self.assertEqual((song.chosen, song.chosen_by, song.chosen_in_app), (bool(chosen_by), chosen_by, in_app))

    def test_set_chooses_the_song_in_app(self):
        song = self.suggestion('Satisfied')
        response = self.set_selection(song)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assert_choice(song, self.name, in_app=True)

    def test_set_unchooses_her_other_app_choice(self):
        first = self.suggestion('Satisfied')
        second = self.suggestion('Helpless')
        self.set_selection(first)
        self.set_selection(second)
        self.assert_choice(first, '', in_app=False)
        self.assert_choice(second, self.name, in_app=True)

    def test_set_keeps_a_song_someone_else_chose_but_unchooses_her_other_choice(self):
        mine = self.suggestion('Satisfied', chosen_by=self.name, in_app=True)
        on_website = self.suggestion('Helpless', chosen_by='Eliza')
        in_app = self.suggestion('Burn', chosen_by='Eliza Hamilton', in_app=True)
        self.set_selection(on_website)
        self.set_selection(in_app)
        self.assert_choice(mine, '', in_app=False)
        self.assert_choice(on_website, 'Eliza', in_app=False)
        self.assert_choice(in_app, 'Eliza Hamilton', in_app=True)

    def test_set_leaves_her_website_choice(self):
        on_website = self.suggestion('Satisfied', chosen_by=self.name)
        song = self.suggestion('Helpless')
        self.set_selection(song)
        self.assert_choice(on_website, self.name, in_app=False)
        self.assert_choice(song, self.name, in_app=True)

    def test_set_stays_within_the_event(self):
        other_event = self.suggestion('Satisfied', event_sku='SKU2', chosen_by=self.name, in_app=True)
        self.set_selection(self.suggestion('Helpless'))
        self.assert_choice(other_event, self.name, in_app=True)

    def test_set_with_an_unknown_song_fails(self):
        response = self.client.post('/peoples-choice/set_app_peoples_choice_selection/999/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_set_does_nothing_once_she_has_a_song_in_the_lineup(self):
        # Her first song's choice stays, and a second song gets none
        signed_up = self.suggestion('Satisfied', chosen_by=self.name, in_app=True)
        song = self.suggestion('Helpless')
        self.sign_up()
        response = self.set_selection(song)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assert_choice(signed_up, self.name, in_app=True)
        self.assert_choice(song, '', in_app=False)

    def test_clear_unchooses_her_app_choice_only(self):
        mine = self.suggestion('Satisfied', chosen_by=self.name, in_app=True)
        on_website = self.suggestion('Helpless', chosen_by=self.name)
        someone_else = self.suggestion('Burn', chosen_by='Eliza Hamilton', in_app=True)
        response = self.clear_selection()
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assert_choice(mine, '', in_app=False)
        self.assert_choice(on_website, self.name, in_app=False)
        self.assert_choice(someone_else, 'Eliza Hamilton', in_app=True)

    def test_clear_does_nothing_once_she_has_a_song_in_the_lineup(self):
        signed_up = self.suggestion('Satisfied', chosen_by=self.name, in_app=True)
        self.sign_up()
        self.clear_selection()
        self.assert_choice(signed_up, self.name, in_app=True)

    def test_both_need_a_singer_login(self):
        song = self.suggestion('Satisfied')
        self.client.logout()
        self.assertEqual(self.set_selection(song).status_code, status.HTTP_302_FOUND)
        self.assertEqual(self.clear_selection().status_code, status.HTTP_302_FOUND)
        audience, = create_audience(1)
        self.client.force_login(audience)
        self.assertEqual(self.set_selection(song).status_code, status.HTTP_302_FOUND)
        self.assertEqual(self.clear_selection().status_code, status.HTTP_302_FOUND)
        self.assert_choice(song, '', in_app=False)
