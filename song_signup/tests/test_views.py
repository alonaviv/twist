from urllib.parse import urlparse, parse_qs
from constance.test import override_config
from django.forms.models import model_to_dict
from django.http import HttpResponse
from django.test import TestCase, Client, TransactionTestCase
from django.urls import reverse
from freezegun import freeze_time
from mock import patch
from django.core.files import File
import glob
import os


from song_signup.models import (
    Singer, TicketOrder,
    CurrentGroupSong, GroupSongRequest,
    SongRequest, TriviaQuestion, SING_SKU, ATTN_SKU
)
from song_signup.tests.utils_for_tests import (
    EVENT_SKU,
    PASSCODE,
    create_order,
    create_singers,
    get_song_basic_data,
    remove_keys,
    get_json,
    add_songs_to_singer,
    set_performed,
    get_song_str,
    get_singer_str,
    set_skipped,
    set_unskipped,
    add_partners,
    add_current_group_song,
    get_song,
    get_singer,
    song_exists, login_singer, login_audience,
    remove_keys_list,
    get_audience_str,
    create_audience,
    select_trivia_answer,
    TEST_START_TIME
)
from twist.utils import format_commas

evening_started = override_config(PASSCODE=PASSCODE, EVENT_SKU=EVENT_SKU)

SINGER_FIELDS = ['id', 'first_name', 'last_name', 'is_superuser']

class TestViews(TestCase):
    def _assert_user_error(self, response, msg=None, status=None):
        if not msg:
            msg = "An unexpected error occurred (you can blame Alon..) Refreshing the page might help"
        if not status:
            status = 400
        self.assertEqual(response.status_code, status)
        self.assertJSONEqual(response.content, {'error': msg})


@evening_started
class TestLogin(TestViews):
    def test_singer_redirect(self):
        login_singer(self)
        response = self.client.get(reverse('login'))
        self.assertRedirects(response, reverse('home'))

    def test_audience_redirect(self):
        login_audience(self)
        response = self.client.get(reverse('login'))
        self.assertRedirects(response, reverse('home'))

    def test_not_logged_in(self):
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'song_signup/login.html')

    def test_invalid_ticket_type(self):
        response = self.client.post(reverse('login'), {'ticket-type': 'unexpected_error',
                                                       'first-name': 'John', 'last-name': 'Doe', 'passcode': 'dev',
                                                       'order-id': '123456'
                                                        })
        self._assert_user_error(response, 'Invalid ticket type')

    def test_wrong_passcode_singer(self):
        response = self.client.post(reverse('login'), {
            'ticket-type': ['singer'],
            'first-name': ['John'],
            'last-name': ['Doe'],
            'passcode': ['wrong_passcode'],
            'order-id': ['123456']
        })
        self._assert_user_error(response, "Wrong passcode - Shani will reveal tonight's passcode at the event")

    def test_wrong_passcode_audience(self):
        response = self.client.post(reverse('login'), {
            'ticket-type': ['audience'],
            'first-name': ['John'],
            'last-name': ['Doe'],
            'passcode': ['wrong_passcode'],
            'order-id': '12345'
        })
        self._assert_user_error(response, "Wrong passcode - Shani will reveal tonight's passcode at the event")

    def test_no_order_id(self):
        response = self.client.post(reverse('login'), {
            'ticket-type': ['singer'],
            'first-name': ['Jane'],
            'last-name': ['Doe'],
            'passcode': [PASSCODE],
            'order-id': ['']
        })
        self.assertEqual(response.status_code, 400)
        self._assert_user_error(response, "We can't find a singer ticket with that order number. "
                                          "Maybe you have a typo? The number appears in the title of the tickets email")

    def test_wrong_order_id(self):
        response = self.client.post(reverse('login'), {
            'ticket-type': ['singer'],
            'first-name': ['Jane'],
            'last-name': ['Doe'],
            'passcode': [PASSCODE],
            'order-id': ['4312']
        })
        self.assertEqual(response.status_code, 400)
        self._assert_user_error(response, "We can't find a singer ticket with that order number. "
                                          "Maybe you have a typo? The number appears in the title of the tickets email")

    def test_wrong_order_id_audience(self):
        response = self.client.post(reverse('login'), {
            'ticket-type': ['audience'],
            'first-name': ['Jane'],
            'last-name': ['Doe'],
            'passcode': [PASSCODE],
            'order-id': ['4312']
        })
        self.assertEqual(response.status_code, 400)
        self._assert_user_error(response, "We can't find an audience ticket with that order number. "
                                          "Maybe you have a typo? The number appears in the title of the tickets email")

    def test_bad_order_id(self):
        response = self.client.post(reverse('login'), {
            'ticket-type': ['singer'],
            'first-name': ['Jane'],
            'last-name': ['Doe'],
            'passcode': [PASSCODE],
            'order-id': ['4312awlekj']
        })
        self.assertEqual(response.status_code, 400)
        self._assert_user_error(response, "We can't find a singer ticket with that order number. "
                                          "Maybe you have a typo? The number appears in the title of the tickets email")

    def test_singer_valid_login(self):
        order = create_order(num_tickets=1,ticket_type=SING_SKU, order_id=12345)
        response = self.client.post(reverse('login'), {
            'ticket-type': ['singer'],
            'first-name': ['Valid'],
            'last-name': ['Singer'],
            'passcode': [PASSCODE],
            'order-id': ['12345']
        })
        self.assertEqual(response.status_code, 200)
        new_singer = Singer.objects.get(username='valid_singer')
        self.assertIsNotNone(new_singer)
        self.assertTrue(new_singer.is_active)
        self.assertFalse(new_singer.no_image_upload)
        self.assertFalse(new_singer.is_staff)
        self.assertEqual(new_singer.ticket_order, order)

    def test_audience_valid_login(self):
        order = create_order(num_tickets=1, ticket_type=ATTN_SKU, order_id=12345)
        response = self.client.post(reverse('login'), {
            'ticket-type': ['audience'],
            'first-name': ['Valid'],
            'last-name': ['Audience'],
            'passcode': [PASSCODE],
            'order-id': ['12345']
        })
        self.assertEqual(response.status_code, 200)
        new_audience = Singer.objects.get(username='valid_audience')
        self.assertIsNotNone(new_audience)
        self.assertTrue(new_audience.is_active)
        self.assertTrue(new_audience.is_audience)
        self.assertEqual(new_audience.ticket_order, order)
        self.assertFalse(new_audience.is_staff)

    def test_party_login(self):
        order = create_order(num_tickets=2, ticket_type=ATTN_SKU, order_id=12345)
        order = create_order(num_tickets=2, ticket_type=SING_SKU, order_id=12345)
        # First audience
        response = self.client.post(reverse('login'), {
            'ticket-type': ['audience'],
            'first-name': ['Valid'],
            'last-name': ['Audience1'],
            'passcode': [PASSCODE],
            'order-id': ['12345']
        })
        self.assertEqual(response.status_code, 200)
        new_audience = Singer.objects.get(username='valid_audience1')
        self.client.logout()

        # First singer
        response = self.client.post(reverse('login'), {
            'ticket-type': ['singer'],
            'first-name': ['Valid'],
            'last-name': ['Singer1'],
            'passcode': [PASSCODE],
            'order-id': ['12345']
        })
        self.assertEqual(response.status_code, 200)
        new_audience = Singer.objects.get(username='valid_singer1')
        self.client.logout()

        # Second audience
        response = self.client.post(reverse('login'), {
            'ticket-type': ['audience'],
            'first-name': ['Valid'],
            'last-name': ['Audience2'],
            'passcode': [PASSCODE],
            'order-id': ['12345']
        })
        self.assertEqual(response.status_code, 200)
        new_audience = Singer.objects.get(username='valid_audience2')
        self.client.logout()

        # Second singer
        response = self.client.post(reverse('login'), {
            'ticket-type': ['singer'],
            'first-name': ['Valid'],
            'last-name': ['Singer2'],
            'passcode': [PASSCODE],
            'order-id': ['12345']
        })
        self.assertEqual(response.status_code, 200)
        new_audience = Singer.objects.get(username='valid_singer2')
        self.client.logout()

        # Singer depleted
        response = self.client.post(reverse('login'), {
            'ticket-type': ['singer'],
            'first-name': ['Jane'],
            'last-name': ['Doe'],
            'passcode': [PASSCODE],
            'order-id': ['12345']
        })
        self.assertEqual(response.status_code, 400)
        self._assert_user_error(response, "Sorry, looks like all ticket holders for this order number already "
                                          "logged in. Are you sure your ticket is of type 'singer'?")

        # Audience depleted
        response = self.client.post(reverse('login'), {
            'ticket-type': ['audience'],
            'first-name': ['Jane'],
            'last-name': ['Doe'],
            'passcode': [PASSCODE],
            'order-id': ['12345']
        })
        self.assertEqual(response.status_code, 400)
        self._assert_user_error(response, "Sorry, looks like all ticket holders for this order number already "
                                          "logged in. Are you sure your ticket is of type 'audience'?")

    def test_hebrew_singer_valid_login(self):
        create_order(num_tickets=1, ticket_type=SING_SKU, order_id=12345)
        response = self.client.post(reverse('login'), {
            'ticket-type': ['singer'],
            'first-name': ['זמר'],
            'last-name': ['בעברית'],
            'passcode': [PASSCODE],
            'order-id': ['12345'],
            'no-upload': ['on']
        })
        self.assertEqual(response.status_code, 200)
        new_singer = Singer.objects.get(username='זמר_בעברית')
        self.assertIsNotNone(new_singer)
        self.assertTrue(new_singer.is_active)
        self.assertTrue(new_singer.no_image_upload)

    def test_lowcase_singer_valid_login(self):
        create_order(num_tickets=1, ticket_type=SING_SKU, order_id=12345)
        response = self.client.post(reverse('login'), {
            'ticket-type': ['singer'],
            'first-name': ['lowcase'],
            'last-name': ['person'],
            'passcode': [PASSCODE],
            'order-id': ['12345']
        })
        self.assertEqual(response.status_code, 200)
        new_singer = Singer.objects.get(username='lowcase_person')
        self.assertIsNotNone(new_singer)
        self.assertTrue(new_singer.is_active)
        self.assertEqual((new_singer.first_name, new_singer.last_name), ('Lowcase', 'Person'))

    def test_additional_singer_valid_login(self):
        order = create_order(num_tickets=2, ticket_type=SING_SKU, order_id=12345)
        create_singers(1, order=order)

        response = self.client.post(reverse('login'), {
            'ticket-type': ['singer'],
            'first-name': ['Valid'],
            'last-name': ['Singer'],
            'passcode': [PASSCODE],
            'order-id': ['12345']
        })
        self.assertEqual(response.status_code, 200)

    def test_additional_audience_valid_login(self):
        order = create_order(num_tickets=2, ticket_type=ATTN_SKU, order_id=4321)
        create_singers(1, order=order)

        response = self.client.post(reverse('login'), {
            'ticket-type': ['audience'],
            'first-name': ['Second'],
            'last-name': ['Audience'],
            'passcode': [PASSCODE],
            'order-id': ['4321']
        })
        self.assertEqual(response.status_code, 200)

    def test_additional_wrong_ticket_type(self):
        order = create_order(num_tickets=2, ticket_type=ATTN_SKU, order_id=4321)
        create_singers(1, order=order)

        response = self.client.post(reverse('login'), {
            'ticket-type': ['singer'],
            'first-name': ['Second'],
            'last-name': ['Audience'],
            'passcode': [PASSCODE],
            'order-id': ['4321']
        })
        self._assert_user_error(response, "We can't find a singer ticket with that order number. "
                                          "Maybe you have a typo? The number appears in the title of the tickets email")

    def test_singer_depleted_ticket(self):
        order = create_order(num_tickets=2, ticket_type=SING_SKU, order_id=12345)
        create_singers(2, order=order)

        response = self.client.post(reverse('login'), {
            'ticket-type': ['singer'],
            'first-name': ['Valid'],
            'last-name': ['Singer'],
            'passcode': [PASSCODE],
            'order-id': ['12345']
        })
        self._assert_user_error(response, "Sorry, looks like all ticket holders for this order number already "
                                          "logged in. Are you sure your ticket is of type 'singer'?")

    def test_audience_depleted_ticket(self):
        order = create_order(num_tickets=2, ticket_type=ATTN_SKU, order_id=12345)
        create_singers(2, order=order)

        response = self.client.post(reverse('login'), {
            'ticket-type': ['audience'],
            'first-name': ['Additional'],
            'last-name': ['Audience'],
            'passcode': [PASSCODE],
            'order-id': ['12345']
        })
        self._assert_user_error(response, "Sorry, looks like all ticket holders for this order number already "
                                          "logged in. Are you sure your ticket is of type 'audience'?")


    def test_singer_logged_in_box(self):
        user = login_singer(self)
        user.is_active = False
        user.save()

        response = self.client.post(reverse('login'), {
            'ticket-type': ['singer'],
            'first-name': [user.first_name],
            'last-name': [user.last_name],
            'passcode': [PASSCODE],
            'order-id': [user.ticket_order.order_id],
            'logged-in': ['on']
        })
        self.assertEqual(response.status_code, 200)

        user.refresh_from_db()
        self.assertTrue(user.is_active)

    def test_singer_already_exists(self):
        user = login_singer(self)
        user.is_active = False
        user.save()

        response = self.client.post(reverse('login'), {
            'ticket-type': ['singer'],
            'first-name': [user.first_name],
            'last-name': [user.last_name],
            'passcode': [PASSCODE],
            'order-id': [user.ticket_order.order_id],
        })
        self._assert_user_error(response,
                "The name that you're trying to login with already exists. Did you already "
                "login with us tonight? If so, check the box below.")

    def test_audience_already_exists(self):
        user = login_audience(self)
        user.is_active = False
        user.save()

        response = self.client.post(reverse('login'), {
            'ticket-type': ['audience'],
            'first-name': [user.first_name],
            'last-name': [user.last_name],
            'passcode': [PASSCODE],
            'order-id': [user.ticket_order.order_id],
        })
        self._assert_user_error(response,
                                "The name that you're trying to login with already exists. Did you already "
                                "login with us tonight? If so, check the box below.")

    def test_audience_logged_in_box(self):
        user = login_audience(self)
        user.is_active = False
        user.save()

        response = self.client.post(reverse('login'), {
            'ticket-type': ['audience'],
            'first-name': [user.first_name],
            'last-name': [user.last_name],
            'passcode': [PASSCODE],
            'logged-in': ['on'],
            'order-id': [user.ticket_order.order_id],
        })
        self.assertEqual(response.status_code, 200)

        user.refresh_from_db()
        self.assertTrue(user.is_active)

    def test_new_singer_logged_in_box(self):
        response = self.client.post(reverse('login'), {
            'ticket-type': ['singer'],
            'first-name': ["doesn't"],
            'last-name': ['exist'],
            'passcode': [PASSCODE],
            'order-id': ['12345'],
            'logged-in': ['on']
        })
        self._assert_user_error(response, "The name that you logged in with previously does not match your current one")

    def test_new_audience_logged_in_box(self):
        response = self.client.post(reverse('login'), {
            'ticket-type': ['audience'],
            'first-name': ["doesn't"],
            'last-name': ['exist'],
            'passcode': [PASSCODE],
            'logged-in': ['on'],
            'order-id': '12345'
        })
        self._assert_user_error(response, "The name that you logged in with previously does not match your current one")

    def test_login_logout_login(self):
        create_order(num_tickets=1, ticket_type=SING_SKU, order_id=12345)
        self.client.post(reverse('login'), {
            'ticket-type': ['singer'],
            'first-name': ['Valid'],
            'last-name': ['Singer'],
            'passcode': [PASSCODE],
            'order-id': ['12345']
        })
        response = self.client.post(reverse('add_song_request'), {
            'song-name': ["defying gravity"],
            'musical': ['wicked'],
            'notes': ['']
        })
        singer = Singer.objects.get(first_name='Valid', last_name='Singer')
        all_songs = SongRequest.objects.filter(position__isnull=False).order_by('position')
        self.assertEqual([song.song_name for song in all_songs], ['Defying Gravity'])

        self.client.get(reverse('logout'))
        all_songs = SongRequest.objects.filter(position__isnull=False).order_by('position')
        self.assertEqual([song.song_name for song in all_songs], [])

        response = self.client.post(reverse('login'), {
            'ticket-type': ['singer'],
            'first-name': ['Valid'],
            'last-name': ['Singer'],
            'passcode': [PASSCODE],
            'order-id': ['12345'],
            'logged-in': ['on']
        })
        all_songs = SongRequest.objects.filter(position__isnull=False).order_by('position')
        self.assertEqual([song.song_name for song in all_songs], ['Defying Gravity'])

    @override_config(FREEBIE_TICKET='54321')
    def test_freebie_singers(self):
        client1 = Client()
        client2 = Client()

        response = client1.post(reverse('login'), {
            'ticket-type': 'singer',
            'first-name': 'Freebie',
            'last-name': 'singer',
            'passcode': PASSCODE,
            'order-id': '54321'
        })

        self.assertEqual(response.status_code, 200)
        new_singer = Singer.objects.get(username='freebie_singer')
        self.assertIsNotNone(new_singer)
        self.assertTrue(new_singer.is_active)

        response = client2.post(reverse('login'), {
            'ticket-type': 'singer',
            'first-name': 'Another Freebie',
            'last-name': 'singer',
            'passcode': PASSCODE,
            'order-id': '54321'
        })
        self.assertEqual(response.status_code, 200)
        another_new_singer = Singer.objects.get(username='another freebie_singer')
        self.assertIsNotNone(new_singer)
        self.assertTrue(another_new_singer.is_active)

        freebie_query = TicketOrder.objects.filter(is_freebie=True)
        self.assertEqual(freebie_query.count(), 1)
        self.assertTrue(freebie_query.first().is_freebie)

    def test_singer_change_video(self):
        create_order(num_tickets=1, ticket_type=SING_SKU, order_id=12345)
        response = self.client.post(reverse('login'), {
            'ticket-type': ['singer'],
            'first-name': ['Valid'],
            'last-name': ['Singer'],
            'passcode': [PASSCODE],
            'order-id': ['12345']
        })
        self.assertEqual(response.status_code, 200)
        new_singer = Singer.objects.get(username='valid_singer')
        self.assertIsNotNone(new_singer)
        self.assertTrue(new_singer.is_active)
        self.assertFalse(new_singer.no_image_upload)

        # Login again with still no video checkbox
        self.client.get(reverse('logout'))
        response = self.client.post(reverse('login'), {
            'ticket-type': ['singer'],
            'first-name': ['Valid'],
            'last-name': ['Singer'],
            'passcode': [PASSCODE],
            'order-id': ['12345'],
            'logged-in': ['on']
        })
        self.assertEqual(response.status_code, 200)
        new_singer = Singer.objects.get(username='valid_singer')
        self.assertIsNotNone(new_singer)
        self.assertTrue(new_singer.is_active)
        self.assertFalse(new_singer.no_image_upload)

        # Login again and add video checkbox
        self.client.get(reverse('logout'))
        response = self.client.post(reverse('login'), {
            'ticket-type': ['singer'],
            'first-name': ['Valid'],
            'last-name': ['Singer'],
            'passcode': [PASSCODE],
            'order-id': ['12345'],
            'no-upload': ['on'],
            'logged-in': ['on']
        })
        self.assertEqual(response.status_code, 200)
        new_singer = Singer.objects.get(username='valid_singer')
        self.assertIsNotNone(new_singer)
        self.assertTrue(new_singer.is_active)
        self.assertTrue(new_singer.no_image_upload)

    def test_audience_change_video(self):
        create_order(num_tickets=1, ticket_type=ATTN_SKU, order_id=4321)
        response = self.client.post(reverse('login'), {
            'ticket-type': ['audience'],
            'first-name': ['Valid'],
            'last-name': ['Audience'],
            'passcode': [PASSCODE],
            'order-id': ['4321']
        })
        self.assertEqual(response.status_code, 200)
        new_audience = Singer.objects.get(username='valid_audience')
        self.assertIsNotNone(new_audience)
        self.assertTrue(new_audience.is_active)
        self.assertFalse(new_audience.no_image_upload)

        # Login again and add video checkbox
        self.client.get(reverse('logout'))
        response = self.client.post(reverse('login'), {
            'ticket-type': ['audience'],
            'first-name': ['Valid'],
            'last-name': ['Audience'],
            'passcode': [PASSCODE],
            'order-id': ['4321'],
            'no-upload': ['on'],
            'logged-in': ['on']
        })
        self.assertEqual(response.status_code, 200)
        new_audience = Singer.objects.get(username='valid_audience')
        self.assertIsNotNone(new_audience)
        self.assertTrue(new_audience.is_active)
        self.assertTrue(new_audience.no_image_upload)


class TestJsonRes(TestViews):
    IGNORE_SONG_KEYS = ['id', 'wait_amount']

    def _remove_song_keys(self, json):
        return remove_keys(json, keys=self.IGNORE_SONG_KEYS)

    def test_spotlight_empty(self):
        response = self.client.get(reverse('spotlight_data'))
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {"current_song": None, "next_song": None})

    def test_spotlight(self):
        create_singers(2, num_songs=1)
        response = self.client.get(reverse('spotlight_data'))
        self.assertEqual(response.status_code, 200)

        res_json = get_json(response)
        expected_json = {
            "current_song": get_song_basic_data(1, 1),
            "next_song": get_song_basic_data(2, 1)
        }
        self.assertDictEqual(self._remove_song_keys(res_json), self._remove_song_keys(expected_json))

    def test_spotlight_single_song(self):
        create_singers(1, num_songs=1)
        response = self.client.get(reverse('spotlight_data'))
        self.assertEqual(response.status_code, 200)

        res_json = get_json(response)
        expected_json = {
            "current_song": get_song_basic_data(1, 1),
            "next_song": None
        }

        self.assertDictEqual(self._remove_song_keys(res_json), self._remove_song_keys(expected_json))

    def test_dashboard_empty(self):
        login_singer(self)
        response = self.client.get(reverse('dashboard_data'))
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {"user_next_song": None})

    def test_dashboard_one_song(self):
        user = login_singer(self, user_id=1)
        add_songs_to_singer(1, 1)
        response = self.client.get(reverse('dashboard_data'))
        self.assertEqual(response.status_code, 200)

        res_json = get_json(response)
        expected_json = {'user_next_song': get_song_basic_data(1, 1)}
        self.assertDictEqual(self._remove_song_keys(res_json), self._remove_song_keys(expected_json))

    def test_dashboard_two_songs(self):
        user = login_singer(self, user_id=1)
        add_songs_to_singer(1, 2)
        response = self.client.get(reverse('dashboard_data'))
        self.assertEqual(response.status_code, 200)

        res_json = get_json(response)
        expected_json = {'user_next_song': get_song_basic_data(1, 1)}
        self.assertDictEqual(self._remove_song_keys(res_json), self._remove_song_keys(expected_json))

    def test_dashboard_one_performed(self):
        create_singers(singer_ids=[1, 2], num_songs=3)
        user = login_singer(self, user_id=3)
        add_songs_to_singer(3, 2)
        set_performed(3, 1)
        response = self.client.get(reverse('dashboard_data'))
        self.assertEqual(response.status_code, 200)

        res_json = get_json(response)
        expected_json = {'user_next_song': get_song_basic_data(3, 2)}
        self.assertDictEqual(self._remove_song_keys(res_json), self._remove_song_keys(expected_json))


class SongRequestSerializeTestCase(TestViews):
    IGNORE_SONG_KEYS = ['request_time']

    def _remove_song_keys(self, json):
        if isinstance(json, list):
            return remove_keys_list(json, keys=self.IGNORE_SONG_KEYS)
        else:
            return remove_keys(json, keys=self.IGNORE_SONG_KEYS)

    def _get_song_json(self, singer_id, song_id, partner_ids=None):
        song = get_song(singer_id, song_id)
        singer = get_singer(singer_id)
        song_json = model_to_dict(song)
        song_json['singer'] = model_to_dict(singer, fields=SINGER_FIELDS)

        if partner_ids:
            partners = []
            partners_strs = []
            for partner_id in partner_ids:
                partner = get_singer(partner_id)
                partners.append(model_to_dict(partner, fields=SINGER_FIELDS))
                partners_strs.append(f"{partner.first_name} {partner.last_name}")

            song_json['partners'] = partners
            song_json['partners_str'] = format_commas(partners_strs)
        else:
            song_json['partners_str'] = ''

        return song_json


class GetCurrentSongs(SongRequestSerializeTestCase):
    def test_no_songs(self):
        user = login_singer(self, user_id=1)

        response = self.client.get(reverse('get_current_songs'))
        self.assertEqual(response.status_code, 200)

        res_json = get_json(response)
        self.assertEqual(res_json, [])

    def test_current_songs(self):
        user = login_singer(self, user_id=1, num_songs=3)

        response = self.client.get(reverse('get_current_songs'))
        self.assertEqual(response.status_code, 200)

        res_json = get_json(response)

        expected_json = [
            self._get_song_json(1, 1),
            self._get_song_json(1, 2),
            self._get_song_json(1, 3)
        ]

        self.assertEqual(self._remove_song_keys(res_json), self._remove_song_keys(expected_json))

    def test_songs_w_partners(self):
        user = login_singer(self, user_id=1, num_songs=3)
        create_singers([2, 3])
        add_partners(1, [2], 1)
        add_partners(1, [2, 3], 2)

        response = self.client.get(reverse('get_current_songs'))
        self.assertEqual(response.status_code, 200)

        res_json = get_json(response)

        expected_json = [
            self._get_song_json(1, 1, partner_ids=[2]),
            self._get_song_json(1, 2, partner_ids=[2, 3]),
            self._get_song_json(1, 3)
        ]

        self.assertEqual(self._remove_song_keys(res_json), self._remove_song_keys(expected_json))


class TestGetSong(SongRequestSerializeTestCase):
    def test_not_found(self):
        res = self.client.get(reverse('get_song', args=[9]))
        self.assertEqual(res.status_code, 400)

        res_json = get_json(res)
        self.assertEqual(res_json, {'error': 'Song with ID 9 does not exist'})

    def test_get_song(self):
        user = login_singer(self, user_id=1, num_songs=1)

        song_1 = get_song(1, 1)
        res = self.client.get(reverse('get_song', args=[song_1.id]))
        self.assertEqual(res.status_code, 200)

        res_json = get_json(res)
        expected_json = self._get_song_json(1, 1)

        self.assertEqual(self._remove_song_keys([res_json]), self._remove_song_keys([expected_json]))

    def test_w_partners(self):
        user = login_singer(self, user_id=1, num_songs=1)
        create_singers([2, 3])
        add_partners(1, [2, 3], 1)

        song_1 = get_song(1, 1)
        response = self.client.get(reverse('get_song', args=[song_1.id]))
        self.assertEqual(response.status_code, 200)

        res_json = get_json(response)
        expected_json = self._get_song_json(1, 1, partner_ids=[2, 3])

        self.assertEqual(self._remove_song_keys(res_json), self._remove_song_keys(expected_json))


class TestUpdateSong(SongRequestSerializeTestCase):
    IGNORE_SONG_KEYS = ['request_time', 'partners_str']

    def _get_expected_song_json(self, song_name, musical, singer, id):
        song_json = model_to_dict(SongRequest(id=id or 1,
                                         song_name='New Song Name', musical='New Musical',
                                         singer=singer,
                                         priority=1, position=1))
        song_json['singer'] =model_to_dict(singer, fields=SINGER_FIELDS)
        return song_json

    def test_not_found(self):
        data = {
            'song_id': 9,
            'song_name': 'New Song Name',
            'musical': 'New Musical'
        }

        response = self.client.put(reverse('update_song'), data, content_type='application/json')
        self.assertEqual(response.status_code, 400)

        res_json = get_json(response)
        self.assertEqual(res_json, {'error': 'Song with ID 9 does not exist'})

    def test_empty_name(self):
        user = login_singer(self, user_id=1, num_songs=1)

        data = {
            'song_id': 1,
            'song_name': '',
            'musical': 'New Musical'
        }

        response = self.client.put(reverse('update_song'), data, content_type='application/json')
        self.assertEqual(response.status_code, 400)

        res_json = get_json(response)
        self.assertEqual(res_json, {'error': 'Song name can not empty'})

    def test_empty_musical(self):
        user = login_singer(self, user_id=1, num_songs=1)

        data = {
            'song_id': 1,
            'song_name': 'New Song Name',
            'musical': ''
        }

        response = self.client.put(reverse('update_song'), data, content_type='application/json')
        self.assertEqual(response.status_code, 400)

        res_json = get_json(response)
        self.assertEqual(res_json, {'error': 'Musical name can not empty'})

    def test_update_success(self):
        user = login_singer(self, user_id=1, num_songs=1)
        song = user.songs.first()
        song.notes = "Some note someone wrote"
        song.found_music = True
        song.default_lyrics = True

        create_singers([2, 3])

        data = {
            'song_id': song.id,
            'song_name': 'new Song name',
            'musical': 'New musical',
            'partners': ['2', '3']

        }

        response = self.client.put(reverse('update_song'), data, content_type='application/json')
        self.assertEqual(response.status_code, 200)

        res_json = get_json(response)
        expected_json = self._get_expected_song_json(song_name='New Song Name', musical='New Musical', singer=user,
                                                     id=song.id)

        self.assertEqual(self._remove_song_keys(res_json), self._remove_song_keys(expected_json))

        song.refresh_from_db()
        self.assertIsNone(song.notes)
        self.assertFalse(song.found_music)
        self.assertFalse(song.default_lyrics)

    def _test_update_same(self, song_name=False, musical=False):
        user = login_singer(self, user_id=1, num_songs=1)

        song = get_song(1, 1)
        original_notes = song.notes
        original_found_music = song.found_music
        original_default_lyrics = song.default_lyrics

        data = {
            'song_id': song.id,
            'song_name': song.song_name if song_name else 'New Song',
            'musical': song.musical if musical else 'New Musical'
        }

        response = self.client.put(reverse('update_song'), data, content_type='application/json')
        self.assertEqual(response.status_code, 200)

        song.refresh_from_db()  # Reload from the database

        self.assertEqual(song.notes, original_notes)
        self.assertEqual(song.found_music, original_found_music)
        self.assertEqual(song.default_lyrics, original_default_lyrics)

    def test_update_same_name(self):
        self._test_update_same(song_name=True)

    def test_update_same_musical(self):
        self._test_update_same(musical=True)

    def test_update_same_all(self):
        self._test_update_same(musical=True, song_name=True)


class TestRestApi(TestViews):
    def test_drinking_words_empty(self):
        with override_config(DRINKING_WORDS=''):
            response = self.client.get(reverse('drinking_words'))
            self.assertEqual(response.status_code, 200)
            self.assertJSONEqual(response.content, {'drinking_words': []})

    def test_drinking_words_single(self):
        with override_config(DRINKING_WORDS='cheers'):
            response = self.client.get(reverse('drinking_words'))
            self.assertEqual(response.status_code, 200)
            self.assertJSONEqual(response.content, {'drinking_words': ['cheers']})

    def test_drinking_words_multiple(self):
        with override_config(DRINKING_WORDS='cheers;salud;prost'):
            response = self.client.get(reverse('drinking_words'))
            self.assertEqual(response.status_code, 200)
            self.assertJSONEqual(response.content, {'drinking_words': ['cheers', 'salud', 'prost']})

    def test_passcode(self):
        user = login_singer(self)
        user.is_staff = True  # Superuser is always staff
        user.save()

        with override_config(PASSCODE='protests'):
            response = self.client.get(reverse('passcode'))
            self.assertEqual(response.status_code, 200)
            self.assertJSONEqual(response.content, {'passcode': 'protests'})

    def test_passcode_no_superuser(self):
        user = login_singer(self)
        response = self.client.get(reverse('passcode'))
        self.assertEqual(response.status_code, 403)

    def test_get_lineup_empty(self):
        response = self.client.get(reverse('get_lineup'))
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {
            'current_song': {'position': None, 'song_name': '', 'musical': ''},
            'next_songs': []
        })

    def test_get_lineup_single_song(self):
        create_singers(1, num_songs=1)
        response = self.client.get(reverse('get_lineup'))
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {
            'current_song': {
                'position': 1, 'song_name': get_song_str(1, 1),
                'singers': get_singer_str(1), 'musical': 'Wicked'
            },
            'next_songs': []
        })

    def test_get_lineup_mutli_songs(self):
        # Starting position
        with freeze_time(auto_tick_seconds=5) as frozen_time:
            create_singers(4, num_songs=2, frozen_time=frozen_time)
            response = self.client.get(reverse('get_lineup'))
            self.assertEqual(response.status_code, 200)
            self.assertJSONEqual(response.content, {
                'current_song': {
                    'position': 1, 'song_name': get_song_str(1, 1),
                    'singers': get_singer_str(1), 'musical': 'Wicked'
                },
                'next_songs': [
                    {
                        'position': 2, 'song_name': get_song_str(2, 1),
                        'singers': get_singer_str(2), 'musical': 'Wicked'
                    },
                    {
                        'position': 3, 'song_name': get_song_str(3, 1),
                        'singers': get_singer_str(3), 'musical': 'Wicked'
                    },
                    {
                        'position': 4, 'song_name': get_song_str(4, 1),
                        'singers': get_singer_str(4), 'musical': 'Wicked'
                    }
                ]
            })
            # After first performed
            set_performed(1, 1, frozen_time=frozen_time)
            response = self.client.get(reverse('get_lineup'))
            self.assertEqual(response.status_code, 200)
            self.assertJSONEqual(response.content, {
                'current_song': {
                    'position': 1, 'song_name': get_song_str(2, 1),
                    'singers': get_singer_str(2), 'musical': 'Wicked'
                },
                'next_songs': [
                    {
                        'position': 2, 'song_name': get_song_str(3, 1),
                        'singers': get_singer_str(3), 'musical': 'Wicked'
                    },
                    {
                        'position': 3, 'song_name': get_song_str(4, 1),
                        'singers': get_singer_str(4), 'musical': 'Wicked'
                    },
                    {
                        'position': 4, 'song_name': get_song_str(1, 2),
                        'singers': get_singer_str(1), 'musical': 'Wicked'
                    },
                ]
            })

            # Song from end performed
            set_performed(1, 2, frozen_time=frozen_time)
            response = self.client.get(reverse('get_lineup'))
            self.assertEqual(response.status_code, 200)
            self.assertJSONEqual(response.content, {
                'current_song': {
                    'position': 1, 'song_name': get_song_str(2, 1),
                    'singers': get_singer_str(2), 'musical': 'Wicked'
                },
                'next_songs': [
                    {
                        'position': 2, 'song_name': get_song_str(3, 1),
                        'singers': get_singer_str(3), 'musical': 'Wicked'
                    },
                    {
                        'position': 3, 'song_name': get_song_str(4, 1),
                        'singers': get_singer_str(4), 'musical': 'Wicked'
                    },
                ]
            })

            # Start group song
            add_current_group_song('so long, farewell', 'the sound of music')
            response = self.client.get(reverse('get_lineup'))
            self.assertEqual(response.status_code, 200)
            self.assertJSONEqual(response.content, {
                'current_song': {
                    'song_name': "So Long, Farewell",
                    'singers': "Group Song", 'musical': 'The Sound of Music'
                },
                'next_songs': [
                    {
                        'position': 1, 'song_name': get_song_str(2, 1),
                        'singers': get_singer_str(2), 'musical': 'Wicked'
                    },
                    {
                        'position': 2, 'song_name': get_song_str(3, 1),
                        'singers': get_singer_str(3), 'musical': 'Wicked'
                    },
                    {
                        'position': 3, 'song_name': get_song_str(4, 1),
                        'singers': get_singer_str(4), 'musical': 'Wicked'
                    },
                ]
            })

            # End group song
            CurrentGroupSong.objects.all().delete()
            response = self.client.get(reverse('get_lineup'))
            self.assertEqual(response.status_code, 200)
            self.assertJSONEqual(response.content, {
                'current_song': {
                    'position': 1, 'song_name': get_song_str(2, 1),
                    'singers': get_singer_str(2), 'musical': 'Wicked'
                },
                'next_songs': [
                    {
                        'position': 2, 'song_name': get_song_str(3, 1),
                        'singers': get_singer_str(3), 'musical': 'Wicked'
                    },
                    {
                        'position': 3, 'song_name': get_song_str(4, 1),
                        'singers': get_singer_str(4), 'musical': 'Wicked'
                    },
                ]
            })

            # Song marked as skipped
            set_skipped(2, 1)
            response = self.client.get(reverse('get_lineup'))
            self.assertEqual(response.status_code, 200)
            self.assertJSONEqual(response.content, {
                'current_song': {
                    'position': 2, 'song_name': get_song_str(3, 1),
                    'singers': get_singer_str(3), 'musical': 'Wicked'
                },
                'next_songs': [
                    {
                        'position': 3, 'song_name': get_song_str(4, 1),
                        'singers': get_singer_str(4), 'musical': 'Wicked'
                    },
                ]
            })

            # Perform song while skipped
            set_performed(3, 1)
            response = self.client.get(reverse('get_lineup'))
            self.assertEqual(response.status_code, 200)
            self.assertJSONEqual(response.content, {
                'current_song': {
                    'position': 2, 'song_name': get_song_str(4, 1),
                    'singers': get_singer_str(4), 'musical': 'Wicked'
                },
                'next_songs': [
                    {
                        'position': 3, 'song_name': get_song_str(3, 2),
                        'singers': get_singer_str(3), 'musical': 'Wicked'
                    },
                ]
            })

            # Return skipped song
            set_unskipped(2, 1)
            response = self.client.get(reverse('get_lineup'))
            self.assertEqual(response.status_code, 200)
            self.assertJSONEqual(response.content, {
                'current_song': {
                    'position': 1, 'song_name': get_song_str(2, 1),
                    'singers': get_singer_str(2), 'musical': 'Wicked'
                },
                'next_songs': [
                    {
                        'position': 2, 'song_name': get_song_str(4, 1),
                        'singers': get_singer_str(4), 'musical': 'Wicked'
                    },
                    {
                        'position': 3, 'song_name': get_song_str(3, 2),
                        'singers': get_singer_str(3), 'musical': 'Wicked'
                    },
                ]
            })

    def test_get_lineup_duets(self):
        create_singers(2, num_songs=1)
        add_partners(1, 2, 1)
        response = self.client.get(reverse('get_lineup'))
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {
            'current_song': {
                'position': 1, 'song_name': get_song_str(1, 1),
                'singers': f"{get_singer_str(1)} and {get_singer_str(2)}"
                , 'musical': 'Wicked'
            },
            'next_songs': [
                {
                    'position': 2, 'song_name': get_song_str(2, 1),
                    'singers': get_singer_str(2), 'musical': 'Wicked'
                },
            ]
        })

    def test_get_lineup_duets_hebrew(self):
        create_singers(2, num_songs=1, hebrew=True)
        add_partners(1, 2, 1, hebrew=True)
        response = self.client.get(reverse('get_lineup'))
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {
            'current_song': {
                'position': 1, 'song_name': get_song_str(1, 1),
                'singers': f"{get_singer_str(1, hebrew=True)} and {get_singer_str(2, hebrew=True)}"
                , 'musical': 'Wicked'
            },
            'next_songs': [
                {
                    'position': 2, 'song_name': get_song_str(2, 1),
                    'singers': get_singer_str(2, hebrew=True), 'musical': 'Wicked'
                },
            ]
        })

class TestDecorators(TestCase):
    def test_bwt_required_w_singer(self):
        login_singer(self, 1)
        response = self.client.get(reverse('view_suggestions'))  # @bwt_login_required('login')
        self.assertEqual(response.status_code, 200)

    def test_bwt_required_w_audience(self):
        login_audience(self)
        response = self.client.get(reverse('view_suggestions'))  # @bwt_login_required('login')
        self.assertEqual(response.status_code, 200)

    def test_bwt_required_w_none(self):
        response = self.client.get(reverse('view_suggestions'))  # @bwt_login_required('login')
        self.assertRedirects(response, reverse('login'))

    def test_bwt_required_singer_only_w_singer(self):
        login_singer(self)
        response = self.client.get(reverse('manage_songs'))  # @bwt_login_required('login', singer_only=True)
        self.assertEqual(response.status_code, 200)

    def test_bwt_required_singer_only_w_none(self):
        response = self.client.get(reverse('manage_songs'))  # @bwt_login_required('login', singer_only=True)
        self.assertRedirects(response, reverse('login'))

    def test_bwt_required_singer_only_w_audience(self):
        login_audience(self)
        response = self.client.get(reverse('manage_songs'))  # @bwt_login_required('login', singer_only=True)
        self.assertRedirects(response, reverse('login'), fetch_redirect_response=False)

    def test_superuser_required_w_superuser(self):
        user = login_singer(self)
        user.is_superuser = True
        user.save()
        response = self.client.get(reverse('lyrics', kwargs={'song_pk': 1}))  # @bwt_superuser_required('login')
        self.assertEqual(response.status_code, 400)  # No song

    def test_superuser_required_wo_superuser(self):
        user = login_singer(self)
        response = self.client.get(reverse('lyrics', kwargs={'song_pk': 1}))  # @bwt_superuser_required('login')
        self.assertRedirects(response, reverse('login'), fetch_redirect_response=False)


class TestSuggestGroupSong(TestCase):
    @patch('song_signup.views.home', return_value=HttpResponse())
    def test_singer(self, home_mock):
        login_singer(self, user_id=1)
        response = self.client.post(reverse('suggest_group_song'), {
            'song-name': ["Brotherhood of man"],
            'musical': ['How to succeed in business without '
                        'really trying']
        })
        self.assertEqual(GroupSongRequest.objects.count(), 1)
        created_song = GroupSongRequest.objects.first()
        self.assertEqual(created_song.song_name, 'Brotherhood of Man')
        self.assertEqual(created_song.musical, 'How to Succeed in Business Without Really Trying')
        self.assertEqual(created_song.suggested_by, get_singer_str(1))

        parsed_url = urlparse(response.url)
        query_params = parse_qs(parsed_url.query)

        self.assertEqual(query_params['song'][0], 'Brotherhood of Man')
        self.assertEqual(query_params['is-group-song'][0], 'true')

    def test_audience(self):
        login_audience(self, user_id=1)
        response = self.client.post(reverse('suggest_group_song'), {
            'song-name': ["Brotherhood of man"],
            'musical': ['How to succeed in business without '
                        'really trying'],
        })
        self.assertEqual(GroupSongRequest.objects.count(), 1)
        created_song = GroupSongRequest.objects.first()
        self.assertEqual(created_song.suggested_by, get_audience_str(1))

    def test_get(self):
        login_audience(self)
        response = self.client.get(reverse('suggest_group_song'))
        self.assertTemplateUsed(response, 'song_signup/suggest_group_song.html')


class TestAddSongRequest(TransactionTestCase):
    def test_only_required_fields(self):
        singer = login_singer(self, user_id=1)
        response = self.client.post(reverse('add_song_request'), {
            'song-name': ["defying gravity"],
            'musical': ['wicked'],
            'notes': ['']
        })
        self.assertEqual(SongRequest.objects.count(), 1)
        created_song = SongRequest.objects.first()
        self.assertEqual(created_song.song_name, 'Defying Gravity')
        self.assertEqual(created_song.musical, 'Wicked')
        self.assertEqual(created_song.singer.id, singer.id)
        self.assertFalse(created_song.skipped)
        self.assertEqual(created_song.notes, '')
        self.assertEqual(created_song.partners.count(), 0)
        self.assertJSONEqual(response.content, {'requested_song': 'Defying Gravity'})
        self.assertEqual(response.status_code, 200)

    def test_all_fields(self):
        user = login_singer(self, user_id=1)
        s2, s3, s4 = create_singers([2, 3, 4])
        response = self.client.post(reverse('add_song_request'), {
            'song-name': ["defying gravity"],
            'musical': ['wicked'],
            'notes': ["solo version"],
            'partners': [str(s2.id), str(s3.id), str(s4.id)]
        })
        self.assertEqual(SongRequest.objects.count(), 1)
        created_song = SongRequest.objects.first()
        self.assertEqual(created_song.song_name, 'Defying Gravity')
        self.assertEqual(created_song.musical, 'Wicked')
        self.assertEqual(created_song.singer.id, user.id)
        self.assertFalse(created_song.skipped)
        self.assertEqual(created_song.notes, 'solo version')
        self.assertEqual(set(created_song.partners.values_list('id', flat=True)), {s2.id, s3.id, s4.id})
        self.assertJSONEqual(response.content, {'requested_song': 'Defying Gravity'})
        self.assertEqual(response.status_code, 200)

    def test_existing_partner(self):
        user = login_singer(self, user_id=1)
        s2, s3, s4 = create_singers([2, 3, 4], num_songs=1)
        add_partners(3, ['4'], 1)
        response = self.client.post(reverse('add_song_request'), {
            'song-name': ["defying gravity"],
            'musical': ['wicked'],
            'partners': [str(s2.id), str(s3.id), str(s4.id)]
        })
        self.assertFalse(song_exists('Defying Gravity'))
        self.assertEqual(response.status_code, 400)
        self.assertJSONEqual(response.content,
                             {'error': f"A singer can be selected as partner once per night, "
                                                      f"and {s4} already used his/her slot."})

    def test_superuser_partner(self):
        user = login_singer(self, user_id=1)
        s2, s3, s4 = create_singers([2, 3, 4], num_songs=3)
        add_partners(3, ['4'], 1)
        add_partners(3, ['4'], 2)
        add_partners(2, ['4'], 1)

        s4.is_superuser = True
        s4.save()

        add_partners(3, ['4'], 1)
        response = self.client.post(reverse('add_song_request'), {
            'song-name': ["defying gravity"],
            'musical': ['wicked'],
            'partners': [str(s2.id), str(s3.id), str(s4.id)]
        })
        self.assertTrue(song_exists('defying gravity'))
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {'requested_song': 'Defying Gravity'})

    def test_partner_not_found(self):
        user = login_singer(self, user_id=1)
        response = self.client.post(reverse('add_song_request'), {
            'song-name': ["defying gravity"],
            'musical': ['wicked'],
            'partners': ['2']
        })
        self.assertFalse(song_exists('defying gravity'))
        self.assertEqual(response.status_code, 400)
        self.assertJSONEqual(response.content,
                             {'error': "Partner with id 2 does not exist. "
                                 f"Show this to Alon - it seems like a bug.. :("})

    def test_duet_singer_signed(self):
        user = login_singer(self, user_id=1)
        singer2, singer3, singer4 = create_singers([2, 3, 4])
        existing_song = SongRequest.objects.create(song_name='Defying Gravity', musical='Wicked', singer=singer2,
                                                   notes='Duet partner signed up first')
        existing_song.partners.set([user, singer2, singer3])

        response = self.client.post(reverse('add_song_request'), {
            'song-name': ["defying gravity"],
            'musical': ['wicked'],
            'notes': ["solo version"],
        })
        self.assertEqual(response.status_code, 400)
        self.assertJSONEqual(response.content,
                             {'error': f'Apparently, {get_singer_str(2)} already signed you up for this song'})

    def test_signed_up_twice(self):
        user = login_singer(self, user_id=1)
        dueter, *_ = create_singers([2, 3, 4])
        response = self.client.post(reverse('add_song_request'), {
            'song-name': ["Defying Gravity"],
            'musical': ['Wicked']
        })

        response = self.client.post(reverse('add_song_request'), {
            'song-name': ["defying gravity"],
            'musical': ['wicked'],
            'notes': ["solo version"],
            'duet-partner': ['2'],
            'additional-singers': ['3', '4']
        })
        self.assertEqual(response.status_code, 400)
        self.assertJSONEqual(response.content, {'error': f'You already signed up with this song tonight'})

    def test_duplicate_song(self):
        user = login_singer(self, user_id=1)
        [other_singer] = create_singers([2])
        SongRequest.objects.create(song_name='Defying Gravity', musical='Wicked', singer=other_singer,
                                   notes='Other singer signed up first')

        response = self.client.post(reverse('add_song_request'), {
            'song-name': ["defying gravity"],
            'musical': ['wicked'],
            'notes': ["solo version"]
        })
        self.assertEqual(response.status_code, 202)
        self.assertJSONEqual(response.content, {'duplicate': True})

    def test_duplicate_song_approve(self):
        user = login_singer(self, user_id=1)
        [other_singer] = create_singers([2])
        SongRequest.objects.create(song_name='Defying Gravity', musical='Wicked', singer=other_singer,
                                   notes='Other singer signed up first')

        response = self.client.post(reverse('add_song_request'), {
            'song-name': ["defying gravity"],
            'musical': ['wicked'],
            'notes': ["solo version"],
            'approve-duplicate': [True]
        })
        self.assertEqual(SongRequest.objects.count(), 2)
        created_song1, created_song2 = SongRequest.objects.all()
        self.assertEqual(created_song1.song_name, created_song2.song_name, 'Defying Gravity')
        self.assertEqual(created_song1.musical, created_song2.musical, 'Wicked')
        self.assertEqual(created_song2.singer.id, user.id)
        self.assertEqual(created_song1.singer.id, other_singer.id)
        self.assertJSONEqual(response.content, {'requested_song': 'Defying Gravity'})
        self.assertEqual(response.status_code, 200)


class TestAddSongView(TestViews):
    def setUp(self):
        self.shani = Singer.objects.create_user(username='shani_wahrman', first_name='Shani', last_name='Wahrman',
                                                is_audience=False, is_superuser=True)
        self.alon = Singer.objects.create_user(username='alon_aviv', first_name='Alon', last_name='Aviv', is_audience=False,
                                          is_superuser=True)
        self.user = login_singer(self, user_id=99)

    def test_add_song(self):
        [singer2] = create_singers([2], num_songs=2)
        create_audience([3])

        response = self.client.get(reverse('add_song'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'song_signup/add_song.html')

        self.assertListEqual(response.context['other_singers'], [self.shani, self.alon, singer2])

        [singer3, singer4, singer5] = create_singers([3, 4, 5], num_songs=2)
        create_audience([6, 7, 8, 9, 10])
        singer4.is_active = False
        singer4.save()

        response = self.client.get(reverse('add_song'))
        self.assertEqual(response.status_code, 200)
        self.assertListEqual(response.context['other_singers'],
                             [self.shani,
                              self.alon,
                              singer2,
                              singer3,
                              singer5
                              ])

class TestTrivia(TestViews):
    def setUp(self):
        self.question_data = dict(
            question="When was Disney founded?",
            choiceA="1948",
            choiceB="1923",
            choiceC="1918",
            choiceD="1939",
            answer=2,
        )
        self.question = TriviaQuestion.objects.create(**self.question_data)
        self.basic_expected_question = dict(**self.question_data,
            winner=None,
            answer_text="1923",
            image=None
        )
class TestGetActiveQuestion(TestTrivia):
    def test_get_active_question(self):
        self.question.is_active = True
        self.question.save()

        expected_data = self.basic_expected_question
        response = self.client.get(reverse('get_active_question'))
        self.assertEqual(response.status_code, 200)
        self.assertDictEqual(response.data, expected_data)

    def test_no_active_question(self):
        response = self.client.get(reverse('get_active_question'))
        self.assertEqual(response.status_code, 204)
        self.assertDictEqual(response.data, {})

    @patch.object(TriviaQuestion, 'WINNER_DISPLAY_DELAY', 0)
    def test_winner(self):
        self.question.is_active = True
        self.question.save()

        # No winners yet
        select_trivia_answer(self.question, 1, user_id=1)
        select_trivia_answer(self.question, 1, user_id=2, is_audience=True)
        select_trivia_answer(self.question, 3, user_id=3, is_audience=True)
        select_trivia_answer(self.question, 4, user_id=4)

        expected_data = self.basic_expected_question
        response = self.client.get(reverse('get_active_question'))
        self.assertEqual(response.status_code, 200)
        self.assertDictEqual(response.data, expected_data)

        [winner] = create_singers(singer_ids=[5])
        select_trivia_answer(self.question, 2, user=winner)

        expected_data['winner'] = winner.get_full_name()
        response = self.client.get(reverse('get_active_question'))
        self.assertEqual(response.status_code, 200)
        self.assertDictEqual(response.data, expected_data)

    def test_question_image(self):
        [os.remove(file) for file in glob.glob('media/trivia-questions/test_img*')]

        self.question.is_active = True
        with open('song_signup/tests/test_img.png', 'rb') as img:
            self.question.image = File(img, name='test_img.png')
            self.question.save()

            expected_data = self.basic_expected_question
            expected_data['image'] = "/media/trivia-questions/test_img.png"

            response = self.client.get(reverse('get_active_question'))
            self.assertEqual(response.status_code, 200)
            self.assertDictEqual(response.data, expected_data)

    def test_several_winners(self):
        """
        Only the first person to select the answer is the winner
        """
        with freeze_time(time_to_freeze=TEST_START_TIME) as frozen_time:
            self.question.is_active = True
            self.question.save()

            winner1, winner2 = create_singers(singer_ids=[1, 2])
            winner3 = create_audience(audience_ids=[3])

            select_trivia_answer(self.question, 2, user=winner1)
            frozen_time.tick(2)
            select_trivia_answer(self.question, 2, user=winner1)
            frozen_time.tick(7)
            select_trivia_answer(self.question, 2, user=winner1)

            expected_data = self.basic_expected_question  # winner=None
            response = self.client.get(reverse('get_active_question'))
            self.assertEqual(response.status_code, 200)
            self.assertDictEqual(response.data, expected_data)

            frozen_time.tick(6)  # 15 seconds after the first winner selected the question

            expected_data['winner'] = winner1.get_full_name()
            response = self.client.get(reverse('get_active_question'))
            self.assertEqual(response.status_code, 200)
            self.assertDictEqual(response.data, expected_data)


    @patch.object(TriviaQuestion, 'WINNER_DISPLAY_DELAY', 0)
    def test_several_questions(self):
        singer1, singer2 = create_singers(singer_ids=[1, 2])
        audience3, audience4, audience5 = create_audience(audience_ids=[3, 4, 5])

        # First question
        self.question.is_active = True
        self.question.save()

        select_trivia_answer(self.question, 1, user=singer1)
        select_trivia_answer(self.question, 2, user=singer2)
        select_trivia_answer(self.question, 3, user=audience3)
        select_trivia_answer(self.question, 4, user=audience4)
        select_trivia_answer(self.question, 4, user=audience5)

        expected_data = self.basic_expected_question
        expected_data['winner'] = singer2.get_full_name()

        response = self.client.get(reverse('get_active_question'))
        self.assertEqual(response.status_code, 200)
        self.assertDictEqual(response.data, expected_data)

        # Second question
        self.question.is_active = False
        self.question.save()

        question_data2 = dict(
            question="Who's afraid of the big bad wolf?",
            choiceA="The pigs",
            choiceB="The cars",
            choiceC="The toys",
            choiceD="The feelings",
            answer=1,
        )
        question2 = TriviaQuestion.objects.create(**question_data2, is_active=True)
        select_trivia_answer(question2, 1, user=singer1)
        select_trivia_answer(question2, 2, user=singer2)
        select_trivia_answer(question2, 3, user=audience3)
        select_trivia_answer(question2, 4, user=audience4)
        select_trivia_answer(question2, 4, user=audience5)

        expected_data = dict(**question_data2,
                             winner=singer1.get_full_name(),
                             answer_text="The pigs",
                             image=None
                             )
        response = self.client.get(reverse('get_active_question'))
        self.assertEqual(response.status_code, 200)
        self.assertDictEqual(response.data, expected_data)

        # Third question
        question2.is_active = False
        question2.save()

        question_data3 = dict(
            question="Which of these characters is NOT voiced by the same actor?",
            choiceA="Winnie the Pooh",
            choiceB="Kaa",
            choiceC="The Chesier Cat",
            choiceD="The White Rabbit",
            answer=4,
        )
        question3 = TriviaQuestion.objects.create(**question_data3, is_active=True)
        select_trivia_answer(question3, 1, user=singer1)
        select_trivia_answer(question3, 2, user=singer2)
        select_trivia_answer(question3, 3, user=audience3)
        select_trivia_answer(question3, 3, user=audience4)
        select_trivia_answer(question3, 4, user=audience5)

        expected_data = dict(**question_data3,
                             winner=audience5.get_full_name(),
                             answer_text="The White Rabbit",
                             image=None
                             )
        response = self.client.get(reverse('get_active_question'))
        self.assertEqual(response.status_code, 200)
        self.assertDictEqual(response.data, expected_data)


class TestSelectTriviaAnswer(TestTrivia):
    def test_select_answer(self):
        self.question.is_active = True
        self.question.save()
        user = login_singer(self)

        response = self.client.post(reverse('select_trivia_answer'), data={'answer-id': 1})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data, {})
        self.assertEqual(user.trivia_responses.count(), 1)

        trivia_response = user.trivia_responses.first()
        self.assertEqual(trivia_response.question, self.question)
        self.assertEqual(trivia_response.user, user)
        self.assertEqual(trivia_response.choice, 1)
        self.assertFalse(trivia_response.is_correct)

    def test_select_correct_answer(self):
        self.question.is_active = True
        self.question.save()
        user = login_audience(self)

        response = self.client.post(reverse('select_trivia_answer'), data={'answer-id': 2})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data, {})

        trivia_response = user.trivia_responses.first()
        self.assertTrue(trivia_response.is_correct)

        response = self.client.post(reverse('select_trivia_answer'), data={'answer-id': 3})
        self._assert_user_error(response, "User already selected a question", status=409)

    def test_no_question(self):
        user = login_singer(self)

        response = self.client.post(reverse('select_trivia_answer'), data={'answer-id': 3})
        self._assert_user_error(response, "No active question")


class TestGetSelectedAnswer(TestTrivia):
    def test_get_answer(self):
        self.question.is_active = True
        self.question.save()
        user = login_audience(self)

        select_trivia_answer(self.question, 3, user=user)

        response = self.client.get(reverse('get_selected_answer'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['choice'], 3)

    def test_no_answer(self):
        self.question.is_active = True
        self.question.save()
        user = login_audience(self)

        response = self.client.get(reverse('get_selected_answer'))
        self._assert_user_error(response, "User hasn't selected an answer for the active question", status=404)

    def test_no_question(self):
        self.question.is_active = True
        self.question.save()
        user = login_audience(self)

        select_trivia_answer(self.question, 3, user=user)
        self.question.is_active = False
        self.question.save()

        response = self.client.get(reverse('get_selected_answer'))
        self._assert_user_error(response, "User hasn't selected an answer for the active question", status=404)


class TestTriviaTemplates(TestTrivia):
    def test_deactivate_trivia(self):
        self.question.is_active = True
        self.question.save()
        user = login_singer(self)
        user.is_superuser = True
        user.save()

        response = self.client.get(reverse('deactivate_trivia'))
        self.assertRedirects(response, '/admin/song_signup/triviaquestion', target_status_code=301)

        self.question.refresh_from_db()
        self.assertFalse(self.question.is_active)
