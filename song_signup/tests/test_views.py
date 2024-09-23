from constance.test import override_config
from django.http import HttpResponse
from django.test import TestCase, Client
from django.urls import reverse
from django.forms.models import model_to_dict
from freezegun import freeze_time
from mock import patch

from song_signup.models import Singer, TicketOrder, CurrentGroupSong, GroupSongRequest, SongRequest
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
    get_singer
)
from song_signup.views import AUDIENCE_SESSION

evening_started = override_config(PASSCODE=PASSCODE, EVENT_SKU=EVENT_SKU)


def login_singer(testcase, user_id=1, num_songs=None):
    [user] = create_singers([user_id], num_songs=num_songs)
    testcase.client.force_login(user)
    return user

def login_audience(testcase):
    session = testcase.client.session
    session[AUDIENCE_SESSION] = True
    session.save()


@evening_started
class TestLogin(TestCase):
    def _assert_user_error(self, response, msg=None):
        if not msg:
            msg = "An unexpected error occurred (you can blame Alon..) Refreshing the page might help"
        self.assertEqual(response.status_code, 400)
        self.assertJSONEqual(response.content, {'error': msg})

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
        response = self.client.post(reverse('login'), {'ticket-type': 'unexpected_error'})
        self._assert_user_error(response, 'Invalid ticket type')

    def test_wrong_passcode(self):
        response = self.client.post(reverse('login'), {
            'ticket-type': ['singer'],
            'first-name': ['John'],
            'last-name': ['Doe'],
            'passcode': ['wrong_passcode'],
            'order-id': ['123456']
        })
        self._assert_user_error(response, "Wrong passcode - Shani will reveal tonight's passcode at the event")

    def test_audience_login(self):
        self.assertFalse(AUDIENCE_SESSION in self.client.session)
        response = self.client.post(reverse('login'), {'ticket-type': 'audience'})
        self.assertRedirects(response, reverse('home'))
        self.assertTrue(self.client.session[AUDIENCE_SESSION])

    def test_no_order_id(self):
        response = self.client.post(reverse('login'), {
            'ticket-type': ['singer'],
            'first-name': ['Jane'],
            'last-name': ['Doe'],
            'passcode': [PASSCODE],
            'order-id': ['']
        })
        self.assertEqual(response.status_code, 400)
        self._assert_user_error(response, "Your order number is incorrect. "
                                          "It should be in the title of the tickets email")

    def test_wrong_order_id(self):
        response = self.client.post(reverse('login'), {
            'ticket-type': ['singer'],
            'first-name': ['Jane'],
            'last-name': ['Doe'],
            'passcode': [PASSCODE],
            'order-id': ['4312']
        })
        self.assertEqual(response.status_code, 400)
        self._assert_user_error(response, "Your order number is incorrect. "
                                          "It should be in the title of the tickets email")

    def test_bad_order_id(self):
        response = self.client.post(reverse('login'), {
            'ticket-type': ['singer'],
            'first-name': ['Jane'],
            'last-name': ['Doe'],
            'passcode': [PASSCODE],
            'order-id': ['4312awlekj']
        })
        self.assertEqual(response.status_code, 400)
        self._assert_user_error(response, "Your order number is incorrect. "
                                          "It should be in the title of the tickets email")

    def test_singer_valid_login(self):
        create_order(num_singers=1, order_id=12345)
        response = self.client.post(reverse('login'), {
            'ticket-type': ['singer'],
            'first-name': ['Valid'],
            'last-name': ['Singer'],
            'passcode': [PASSCODE],
            'order-id': ['12345']
        })
        self.assertRedirects(response, reverse('home'))
        new_singer = Singer.objects.get(username='valid_singer')
        self.assertIsNotNone(new_singer)
        self.assertTrue(new_singer.is_active)
        self.assertFalse(new_singer.no_image_upload)

    def test_hebrew_singer_valid_login(self):
        create_order(num_singers=1, order_id=12345)
        response = self.client.post(reverse('login'), {
            'ticket-type': ['singer'],
            'first-name': ['זמר'],
            'last-name': ['בעברית'],
            'passcode': [PASSCODE],
            'order-id': ['12345'],
            'no-upload': ['on']
        })
        self.assertRedirects(response, reverse('home'))
        new_singer = Singer.objects.get(username='זמר_בעברית')
        self.assertIsNotNone(new_singer)
        self.assertTrue(new_singer.is_active)
        self.assertTrue(new_singer.no_image_upload)

    def test_lowcase_singer_valid_login(self):
        create_order(num_singers=1, order_id=12345)
        response = self.client.post(reverse('login'), {
            'ticket-type': ['singer'],
            'first-name': ['lowcase'],
            'last-name': ['person'],
            'passcode': [PASSCODE],
            'order-id': ['12345']
        })
        self.assertRedirects(response, reverse('home'))
        new_singer = Singer.objects.get(username='lowcase_person')
        self.assertIsNotNone(new_singer)
        self.assertTrue(new_singer.is_active)
        self.assertEqual((new_singer.first_name, new_singer.last_name), ('Lowcase', 'Person'))

    def test_additional_singer_valid_login(self):
        order = create_order(num_singers=2, order_id=12345)
        create_singers(1, order=order)

        response = self.client.post(reverse('login'), {
            'ticket-type': ['singer'],
            'first-name': ['Valid'],
            'last-name': ['Singer'],
            'passcode': [PASSCODE],
            'order-id': ['12345']
        })
        self.assertRedirects(response, reverse('home'))

    def test_additional_singer_depleted_ticket(self):
        order = create_order(num_singers=2, order_id=12345)
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
        self.assertRedirects(response, reverse('home'))

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

        self.assertRedirects(response, reverse('home'))
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
        self.assertRedirects(response, reverse('home'))
        another_new_singer = Singer.objects.get(username='another freebie_singer')
        self.assertIsNotNone(new_singer)
        self.assertTrue(another_new_singer.is_active)

        freebie_query = TicketOrder.objects.filter(is_freebie=True)
        self.assertEqual(freebie_query.count(), 1)
        self.assertTrue(freebie_query.first().is_freebie)

    def test_singer_change_video(self):
        create_order(num_singers=1, order_id=12345)
        response = self.client.post(reverse('login'), {
            'ticket-type': ['singer'],
            'first-name': ['Valid'],
            'last-name': ['Singer'],
            'passcode': [PASSCODE],
            'order-id': ['12345']
        })
        self.assertRedirects(response, reverse('home'))
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
        self.assertRedirects(response, reverse('home'))
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
        self.assertRedirects(response, reverse('home'))
        new_singer = Singer.objects.get(username='valid_singer')
        self.assertIsNotNone(new_singer)
        self.assertTrue(new_singer.is_active)
        self.assertTrue(new_singer.no_image_upload)


def remove_song_keys(content, keys):
    if isinstance(content, dict):
        songs = content.values()
    else:
        songs = content

    for song in songs:
        if song:
            remove_keys(song, keys)

    return content


class TestJsonRes(TestCase):
    IGNORE_SONG_KEYS = ['id', 'wait_amount']
    def _remove_song_keys(self, json):
        return remove_song_keys(json, keys=self.IGNORE_SONG_KEYS)

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

class TestGetCurrentSongs(TestCase):
    IGNORE_SONG_KEYS = ['request_time']
    def _remove_song_keys(self, json):
        return remove_song_keys(json, keys=self.IGNORE_SONG_KEYS)

    def _get_song_json(self, singer_id, song_id, partner_ids=None):
        SINGER_FIELDS = ['id', 'first_name', 'last_name']

        song = get_song(singer_id, song_id)
        singer = get_singer(singer_id)
        song_json = model_to_dict(song)
        song_json['singer'] = model_to_dict(singer, fields=SINGER_FIELDS)

        if partner_ids:
            partners = []
            for partner_id in partner_ids:
                partner = get_singer(partner_id)
                partners.append(model_to_dict(partner, fields=SINGER_FIELDS))

            song_json['partners'] = partners

        return song_json

    def test_no_songs(self):
        user = login_singer(self, user_id=1)

        response = self.client.get(reverse('get_current_songs'))
        self.assertEqual(response.status_code, 200)

        res_json = get_json(response)
        self.assertEqual(res_json, [])

    def test_get_current_songs(self):
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
        # TODO: Strange problem - response returns 4 songs (1_2 appears twice) even though that doesn't seem to happen
        # TODO in the model

        expected_json = [
            self._get_song_json(1, 1, partner_ids=[2]),
            self._get_song_json(1, 2, partner_ids=[2, 3]),
            self._get_song_json(1, 3)
        ]

        self.assertEqual(self._remove_song_keys(res_json), self._remove_song_keys(expected_json))

class TestRestApi(TestCase):
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
                'singers': get_singer_str(1), 'musical': ''
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
                    'singers': get_singer_str(1), 'musical': ''
                },
                'next_songs': [
                    {
                        'position': 2, 'song_name': get_song_str(2, 1),
                        'singers': get_singer_str(2), 'musical': ''
                    },
                    {
                        'position': 3, 'song_name': get_song_str(3, 1),
                        'singers': get_singer_str(3), 'musical': ''
                    },
                    {
                        'position': 4, 'song_name': get_song_str(4, 1),
                        'singers': get_singer_str(4), 'musical': ''
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
                    'singers': get_singer_str(2), 'musical': ''
                },
                'next_songs': [
                    {
                        'position': 2, 'song_name': get_song_str(3, 1),
                        'singers': get_singer_str(3), 'musical': ''
                    },
                    {
                        'position': 3, 'song_name': get_song_str(4, 1),
                        'singers': get_singer_str(4), 'musical': ''
                    },
                    {
                        'position': 4, 'song_name': get_song_str(1, 2),
                        'singers': get_singer_str(1), 'musical': ''
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
                    'singers': get_singer_str(2), 'musical': ''
                },
                'next_songs': [
                    {
                        'position': 2, 'song_name': get_song_str(3, 1),
                        'singers': get_singer_str(3), 'musical': ''
                    },
                    {
                        'position': 3, 'song_name': get_song_str(4, 1),
                        'singers': get_singer_str(4), 'musical': ''
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
                        'singers': get_singer_str(2), 'musical': ''
                    },
                    {
                        'position': 2, 'song_name': get_song_str(3, 1),
                        'singers': get_singer_str(3), 'musical': ''
                    },
                    {
                        'position': 3, 'song_name': get_song_str(4, 1),
                        'singers': get_singer_str(4), 'musical': ''
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
                    'singers': get_singer_str(2), 'musical': ''
                },
                'next_songs': [
                    {
                        'position': 2, 'song_name': get_song_str(3, 1),
                        'singers': get_singer_str(3), 'musical': ''
                    },
                    {
                        'position': 3, 'song_name': get_song_str(4, 1),
                        'singers': get_singer_str(4), 'musical': ''
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
                    'singers': get_singer_str(3), 'musical': ''
                },
                'next_songs': [
                    {
                        'position': 3, 'song_name': get_song_str(4, 1),
                        'singers': get_singer_str(4), 'musical': ''
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
                    'singers': get_singer_str(4), 'musical': ''
                },
                'next_songs': [
                    {
                        'position': 3, 'song_name': get_song_str(3, 2),
                        'singers': get_singer_str(3), 'musical': ''
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
                    'singers': get_singer_str(2), 'musical': ''
                },
                'next_songs': [
                    {
                        'position': 2, 'song_name': get_song_str(4, 1),
                        'singers': get_singer_str(4), 'musical': ''
                    },
                    {
                        'position': 3, 'song_name': get_song_str(3, 2),
                        'singers': get_singer_str(3), 'musical': ''
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
                , 'musical': ''
            },
            'next_songs': [
                {
                    'position': 2, 'song_name': get_song_str(2, 1),
                    'singers': get_singer_str(2), 'musical': ''
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
                , 'musical': ''
            },
            'next_songs': [
                {
                    'position': 2, 'song_name': get_song_str(2, 1),
                    'singers': get_singer_str(2, hebrew=True), 'musical': ''
                },
            ]
        })


class TestDecorators(TestCase):
    def test_bwt_required_w_singer(self):
        login_singer(self, 1)
        response = self.client.get(reverse('view_suggestions')) # @bwt_login_required('login')
        self.assertEqual(response.status_code, 200)

    def test_bwt_required_w_audience(self):
        login_audience(self)
        response = self.client.get(reverse('view_suggestions')) # @bwt_login_required('login')
        self.assertEqual(response.status_code, 200)

    def test_bwt_required_w_none(self):
        response = self.client.get(reverse('view_suggestions')) # @bwt_login_required('login')
        self.assertRedirects(response, reverse('login'))

    def test_bwt_required_singer_only_w_singer(self):
        login_singer(self, 1)
        response = self.client.get(reverse('manage_songs')) # @bwt_login_required('login', singer_only=True)
        self.assertEqual(response.status_code, 200)

    def test_bwt_required_singer_only_w_none(self):
        response = self.client.get(reverse('manage_songs')) # @bwt_login_required('login', singer_only=True)
        self.assertRedirects(response, reverse('login'))

    def test_bwt_required_singer_only_w_audience(self):
        login_audience(self)
        response = self.client.get(reverse('manage_songs')) # @bwt_login_required('login', singer_only=True)
        self.assertEqual(response.status_code, 302)

    def test_superuser_required_w_superuser(self):
        user = login_singer(self)
        user.is_superuser = True
        user.save()
        response = self.client.get(reverse('lyrics', kwargs={'song_pk': 1})) # @bwt_superuser_required('login')
        self.assertEqual(response.status_code, 400) # No song

    def test_superuser_required_wo_superuser(self):
        user = login_singer(self)
        response = self.client.get(reverse('lyrics', kwargs={'song_pk': 1})) # @bwt_superuser_required('login')
        self.assertEqual(response.status_code, 302)


class TestSuggestGroupSong(TestCase):
    @patch('song_signup.views.home', return_value=HttpResponse())
    def test_singer(self, home_mock):
        login_singer(self, user_id=1)
        response = self.client.post(reverse('suggest_group_song'), {'song-name': ["Brotherhood of man"],
                                                                    'musical': ['How to succeed in business without '
                                                                               'really trying']})
        self.assertEqual(GroupSongRequest.objects.count(), 1)
        created_song = GroupSongRequest.objects.first()
        self.assertEqual(created_song.song_name, 'Brotherhood of Man')
        self.assertEqual(created_song.musical, 'How to Succeed in Business Without Really Trying')
        self.assertEqual(created_song.suggested_by, get_singer_str(1))

        call_args, call_kwargs = home_mock.call_args
        self.assertIn('Brotherhood of Man', call_args)
        self.assertTrue(call_kwargs['is_group_song'])


    def test_audience(self):
        login_audience(self)
        response = self.client.post(reverse('suggest_group_song'), {'song-name': ["Brotherhood of man"],
                                                                    'musical': ['How to succeed in business without '
                                                                               'really trying'],
                                                                    'suggested_by': ['']
        })
        self.assertEqual(GroupSongRequest.objects.count(), 1)
        created_song = GroupSongRequest.objects.first()
        self.assertEqual(created_song.suggested_by, '-')


    def test_named_audience(self):
        login_audience(self)
        response = self.client.post(reverse('suggest_group_song'), {'song-name': ["Brotherhood of man"],
                                                                    'musical': ['How to succeed in business without '
                                                                               'really trying'],
                                                                    'suggested_by': ["some audience person"]
        })
        self.assertEqual(GroupSongRequest.objects.count(), 1)
        created_song = GroupSongRequest.objects.first()
        self.assertEqual(created_song.suggested_by, 'some audience person')

    def test_get(self):
        login_audience(self)
        response = self.client.get(reverse('suggest_group_song'))
        self.assertTemplateUsed(response, 'song_signup/suggest_group_song.html')


class TestAddSongRequest(TestCase):
    def test_only_required_fields(self):
        singer = login_singer(self, user_id=1)
        response = self.client.post(reverse('add_song_request'), {'song-name': ["defying gravity"],
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
        response = self.client.post(reverse('add_song_request'), {'song-name': ["defying gravity"],
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

    def test_duet_singer_signed(self):
        user = login_singer(self, user_id=1)
        singer2, singer3, singer4 = create_singers([2, 3, 4])
        existing_song = SongRequest.objects.create(song_name='Defying Gravity', musical='Wicked', singer=singer2,
                                                    notes='Duet partner signed up first')
        existing_song.partners.set([user, singer2, singer3])

        response = self.client.post(reverse('add_song_request'), {'song-name': ["defying gravity"],
                                                                  'musical': ['wicked'],
                                                                  'notes': ["solo version"],
        })
        self.assertEqual(response.status_code, 400)
        self.assertJSONEqual(response.content, {'error': f'Apparently, {get_singer_str(2)} already signed you up for this song'})


    def test_signed_up_twice(self):
        user = login_singer(self, user_id=1)
        dueter, *_ = create_singers([2, 3, 4])
        response = self.client.post(reverse('add_song_request'), {'song-name': ["Defying Gravity"],
                                                                  'musical': ['Wicked']
        })

        response = self.client.post(reverse('add_song_request'), {'song-name': ["defying gravity"],
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

        response = self.client.post(reverse('add_song_request'), {'song-name': ["defying gravity"],
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

        response = self.client.post(reverse('add_song_request'), {'song-name': ["defying gravity"],
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
