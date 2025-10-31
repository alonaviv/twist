from urllib.parse import urlparse, parse_qs
from constance.test import override_config
from django.forms.models import model_to_dict
from django.http import HttpResponse
from django.test import TestCase, Client, TransactionTestCase
from django.urls import reverse
from django.core.files.storage import default_storage
from freezegun import freeze_time
from mock import patch
from django.core.files import File
import glob
import os
import filecmp
from song_signup.views import _get_current_song


from song_signup.models import (
    Singer, TicketOrder,
    CurrentGroupSong, GroupSongRequest,
    SongRequest, SongSuggestion, TriviaQuestion, SING_SKU, ATTN_SKU
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
    add_songs_to_singers,
    set_performed,
    get_song_str,
    get_singer_str,
    set_skipped,
    set_unskipped,
    add_partners,
    add_current_group_song,
    get_song,
    get_singer,
    get_audience,
    song_exists, login_singer, login_audience,
    remove_keys_list,
    get_audience_str,
    create_audience,
    select_trivia_answer,
    TEST_START_TIME,
    end_group_song,
    participate_in_raffle,
    unparticipate_in_raffle
)
from twist.utils import format_commas

evening_started = override_config(PASSCODE=PASSCODE, EVENT_SKU=EVENT_SKU)

SINGER_FIELDS = ['id', 'first_name', 'last_name', 'is_superuser']

class TestViews(TransactionTestCase):
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

    def test_singer_upload_image(self):
        test_img_path = 'song_signup/tests/test_img.png'
        order = create_order(num_tickets=1, ticket_type=SING_SKU, order_id=12345)
        with open(test_img_path, 'rb') as image:
            response = self.client.post(reverse('login'), {
                'ticket-type': ['singer'],
                'first-name': ['Valid'],
                'last-name': ['Singer'],
                'passcode': [PASSCODE],
                'order-id': ['12345'],
                'upload-image': image
            })

        self.assertEqual(response.status_code, 200)
        singer = Singer.objects.get(username='valid_singer')
        self.assertTrue(filecmp.cmp(test_img_path, singer.selfie.path))

    def test_singer_upload_selfie(self):
        test_img_path = 'song_signup/tests/test_img.png'
        order = create_order(num_tickets=1, ticket_type=SING_SKU, order_id=12345)
        with open(test_img_path, 'rb') as image:
            response = self.client.post(reverse('login'), {
                'ticket-type': ['singer'],
                'first-name': ['Valid'],
                'last-name': ['Singer'],
                'passcode': [PASSCODE],
                'order-id': ['12345'],
                'upload-selfie': image
            })

        self.assertEqual(response.status_code, 200)
        singer = Singer.objects.get(username='valid_singer')
        self.assertTrue(filecmp.cmp(test_img_path, singer.selfie.path))

    def test_existing_singer_upload_selfie(self):
        order = create_order(num_tickets=1, ticket_type=SING_SKU, order_id=12345)
        Singer.objects.create_user(
            username="valid_singer",
            first_name="Valid",
            last_name="Singer",
            is_staff=False,
            is_audience=False,
            ticket_order=order,
        )
        test_img_path = 'song_signup/tests/test_img.png'
        with open(test_img_path, 'rb') as image:
            response = self.client.post(reverse('login'), {
                'ticket-type': ['singer'],
                'first-name': ['Valid'],
                'last-name': ['Singer'],
                'passcode': [PASSCODE],
                'order-id': ['12345'],
                'logged-in': ['on'],
                'upload-selfie': image
            })

        self.assertEqual(response.status_code, 200)
        singer = Singer.objects.get(username='valid_singer')
        self.assertTrue(filecmp.cmp(test_img_path, singer.selfie.path))

    def test_existing_audience_upload_selfie(self):
        order = create_order(num_tickets=1, ticket_type=ATTN_SKU, order_id=12345)
        Singer.objects.create_user(
            username="valid_audience",
            first_name="Valid",
            last_name="Audience",
            is_staff=False,
            is_audience=True,
            ticket_order=order,
        )
        test_img_path = 'song_signup/tests/test_img.png'
        with open(test_img_path, 'rb') as image:
            response = self.client.post(reverse('login'), {
                'ticket-type': ['audience'],
                'first-name': ['Valid'],
                'last-name': ['Audience'],
                'passcode': [PASSCODE],
                'order-id': ['12345'],
                'logged-in': ['on'],
                'upload-selfie': image
            })

        self.assertEqual(response.status_code, 200)
        singer = Singer.objects.get(username='valid_audience')
        self.assertTrue(filecmp.cmp(test_img_path, singer.selfie.path))

    def test_audience_upload_image(self):
        test_img_path = 'song_signup/tests/test_img.png'
        order = create_order(num_tickets=1, ticket_type=ATTN_SKU, order_id=12345)
        with open(test_img_path, 'rb') as image:
            response = self.client.post(reverse('login'), {
                'ticket-type': ['audience'],
                'first-name': ['Valid'],
                'last-name': ['Audience'],
                'passcode': [PASSCODE],
                'order-id': ['12345'],
                'upload-image': image
            })

        self.assertEqual(response.status_code, 200)
        audience = Singer.objects.get(username='valid_audience')
        self.assertTrue(filecmp.cmp(test_img_path, audience.selfie.path))

    def test_audience_upload_selfie(self):
        test_img_path = 'song_signup/tests/test_img.png'
        order = create_order(num_tickets=1, ticket_type=ATTN_SKU, order_id=12345)
        with open(test_img_path, 'rb') as image:
            response = self.client.post(reverse('login'), {
                'ticket-type': ['audience'],
                'first-name': ['Valid'],
                'last-name': ['Audience'],
                'passcode': [PASSCODE],
                'order-id': ['12345'],
                'upload-selfie': image
            })

        self.assertEqual(response.status_code, 200)
        audience = Singer.objects.get(username='valid_audience')
        self.assertTrue(filecmp.cmp(test_img_path, audience.selfie.path))

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

    def test_spotlight_song_skipped(self):
        create_singers(singer_ids=[1, 2, 3], num_songs=1)
        user = login_singer(self, user_id=3)

        set_skipped(1, 1)

        response = self.client.get(reverse('spotlight_data'))
        self.assertEqual(response.status_code, 200)

        res_json = get_json(response)
        expected_json = {
            "current_song": get_song_basic_data(2, 1),
            "next_song": get_song_basic_data(3, 1)
        }

        self.assertDictEqual(self._remove_song_keys(res_json), self._remove_song_keys(expected_json))

    def test_spotlight_group_song(self):
        create_singers(2, num_songs=1)
        user = login_singer(self, user_id=1)

        add_current_group_song('Hello', "Book of Mormon")

        response = self.client.get(reverse('spotlight_data'))
        self.assertEqual(response.status_code, 200)

        res_json = get_json(response)
        expected_json = {
            "current_song": {'name': 'Hello', 'singer': 'GROUP SONG'},
            "next_song": get_song_basic_data(1, 1)
        }
        self.assertDictEqual(self._remove_song_keys(res_json), self._remove_song_keys(expected_json))

        end_group_song()

        response = self.client.get(reverse('spotlight_data'))
        self.assertEqual(response.status_code, 200)

        res_json = get_json(response)
        expected_json = {
            "current_song": get_song_basic_data(1, 1),
            "next_song": get_song_basic_data(2, 1)
        }
        self.assertDictEqual(self._remove_song_keys(res_json), self._remove_song_keys(expected_json))

    def test_dashboard_empty(self):
        login_singer(self)
        response = self.client.get(reverse('dashboard_data'))
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {"user_next_song": None, "raffle_winner_already_sang": False})

    def test_dashboard_one_song(self):
        user = login_singer(self, user_id=1)
        add_songs_to_singer(1, 1)
        response = self.client.get(reverse('dashboard_data'))
        self.assertEqual(response.status_code, 200)

        res_json = get_json(response)
        expected_json = {'user_next_song': get_song_basic_data(1, 1), "raffle_winner_already_sang": False}
        self.assertDictEqual(self._remove_song_keys(res_json), self._remove_song_keys(expected_json))

    def test_dashboard_two_songs(self):
        user = login_singer(self, user_id=1)
        add_songs_to_singer(1, 2)
        response = self.client.get(reverse('dashboard_data'))
        self.assertEqual(response.status_code, 200)

        res_json = get_json(response)
        expected_json = {'user_next_song': get_song_basic_data(1, 1), "raffle_winner_already_sang": False}
        self.assertDictEqual(self._remove_song_keys(res_json), self._remove_song_keys(expected_json))

    def test_dashboard_one_performed(self):
        create_singers(singer_ids=[1, 2], num_songs=3)
        user = login_singer(self, user_id=3)
        add_songs_to_singer(3, 2)
        set_performed(3, 1)
        response = self.client.get(reverse('dashboard_data'))
        self.assertEqual(response.status_code, 200)

        res_json = get_json(response)
        expected_json = {'user_next_song': get_song_basic_data(3, 2), "raffle_winner_already_sang": False}
        self.assertDictEqual(self._remove_song_keys(res_json), self._remove_song_keys(expected_json))



class SongRequestSerializeTestCase(TestViews):
    IGNORE_SONG_KEYS = ['request_time']

    def _remove_song_keys(self, json):
        if isinstance(json, list):
            return remove_keys_list(json, keys=self.IGNORE_SONG_KEYS)
        else:
            return remove_keys(json, keys=self.IGNORE_SONG_KEYS)

    def _get_song_json(self, singer_id, song_id, partner_ids=None, audience_partner_ids=None):
        song = get_song(singer_id, song_id)
        singer = get_singer(singer_id)
        song_json = model_to_dict(song)
        song_json['singer'] = model_to_dict(singer, fields=SINGER_FIELDS)

        if partner_ids or audience_partner_ids:
            partner_ids = partner_ids or []
            audience_partner_ids = audience_partner_ids or []
            partners = []
            partners_strs = []

            for partner_id in partner_ids:
                partner = get_singer(partner_id)
                partners.append(model_to_dict(partner, fields=SINGER_FIELDS))
                partners_strs.append(f"{partner.first_name} {partner.last_name}")

            for partner_id in audience_partner_ids:
                partner = get_audience(partner_id)
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
        create_singers([2, 3, 4])
        create_audience([5, 6])
        add_partners(1, [2], 1, audience_partner_ids=[5])
        add_partners(1, [3, 4], 2, audience_partner_ids=[6])

        response = self.client.get(reverse('get_current_songs'))
        self.assertEqual(response.status_code, 200)

        res_json = get_json(response)

        expected_json = [
            self._get_song_json(1, 1, partner_ids=[2], audience_partner_ids=[5]),
            self._get_song_json(1, 2, partner_ids=[3, 4], audience_partner_ids=[6]),
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
        create_audience([4, 5])
        add_partners(1, [2, 3], 1, audience_partner_ids=[4, 5])

        song_1 = get_song(1, 1)
        response = self.client.get(reverse('get_song', args=[song_1.id]))
        self.assertEqual(response.status_code, 200)

        res_json = get_json(response)
        expected_json = self._get_song_json(1, 1, partner_ids=[2, 3], audience_partner_ids=[4, 5])

        self.assertDictEqual(self._remove_song_keys(res_json), self._remove_song_keys(expected_json))


class TestUpdateSong(SongRequestSerializeTestCase):
    IGNORE_SONG_KEYS = ['request_time', 'partners_str']

    def _get_expected_song_json(self, song_name, musical, singer, id, partners, note):
        song_json = model_to_dict(SongRequest(id=id or 1,
                                         song_name=song_name, musical=musical,
                                         singer=singer,
                                         priority=1,
                                         position=1,
                                         notes=note))
        song_json['singer'] = model_to_dict(singer, fields=SINGER_FIELDS)
        song_json['partners'] = [model_to_dict(partner, fields=SINGER_FIELDS) for partner in partners]
        return song_json

    def test_not_found(self):
        data = {
            'song_id': 9,
            'song_name': 'New Song Name',
            'musical': 'New Musical',
            'partners': ['4']
        }

        response = self.client.put(reverse('update_song'), data, content_type='application/json')
        self.assertEqual(response.status_code, 400)

        res_json = get_json(response)
        self.assertEqual(res_json, {'error': 'Song with ID 9 does not exist'})

    def test_empty_name(self):
        user = login_singer(self, user_id=1, num_songs=1)
        create_singers([2, 3])

        data = {
            'song_id': 1,
            'song_name': '',
            'musical': 'New Musical',
            'partners': ['2', '3']
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
            'musical': '',
            'partners': ''
        }

        response = self.client.put(reverse('update_song'), data, content_type='application/json')
        self.assertEqual(response.status_code, 400)

        res_json = get_json(response)
        self.assertEqual(res_json, {'error': 'Musical name can not empty'})

    def test_update_success(self):
        user = login_singer(self, user_id=1, num_songs=1)
        song = user.songs.first()
        song.found_music = True
        song.default_lyrics = True
        song.save()

        singer2, singer3 = create_singers([2, 3])
        [audience4] = create_audience([4])

        data = {
            'song_id': song.id,
            'song_name': 'new Song name',
            'musical': 'New musical',
            'partners': [str(singer2.id), str(singer3.id), str(audience4.id)],
            'notes': "Adding notes"
        }

        response = self.client.put(reverse('update_song'), data, content_type='application/json')
        self.assertEqual(response.status_code, 200)

        res_json = get_json(response)
        expected_json = self._get_expected_song_json(song_name='New Song Name', musical='New Musical', singer=user,
                                                     id=song.id, partners=[singer2, singer3, audience4],
                                                     note="Adding notes")

        self.assertDictEqual(self._remove_song_keys(res_json), self._remove_song_keys(expected_json))

        song.refresh_from_db()
        self.assertEqual(song.notes, "Adding notes")
        self.assertFalse(song.found_music)
        self.assertFalse(song.default_lyrics)
        self.assertEqual(song.song_name, 'New Song Name')
        self.assertEqual(song.musical, 'New Musical')
        self.assertListEqual(list(song.partners.all()), [singer2, singer3, audience4])

    def test_append_partner(self):
        user = login_singer(self, user_id=1, num_songs=1)
        singer2, singer3, singer4 = create_singers([2, 3, 4])
        audience5, audience6 = create_audience([5, 6])

        song = user.songs.first()
        song.partners.set([singer2, singer3, audience5, audience6])
        self.assertListEqual(list(song.partners.all()), [singer2, singer3, audience5, audience6])

        data = {
            'song_id': song.id,
            'song_name': song.song_name,
            'musical': song.musical,
            'partners': [str(singer2.id), str(singer3.id), str(singer4.id), str(audience5.id), str(audience6.id)]
        }

        response = self.client.put(reverse('update_song'), data, content_type='application/json')
        self.assertEqual(response.status_code, 200)

        song.refresh_from_db()
        self.assertListEqual(list(song.partners.all()), [singer2, singer3, singer4, audience5, audience6])

    def test_replace_partners(self):
        user = login_singer(self, user_id=1, num_songs=1)
        singer2, singer3, singer4, singer5 = create_singers([2, 3, 4, 5])
        audience6, audience7 = create_audience([6, 7])

        song = user.songs.first()
        song.partners.set([singer2, singer3, audience6, audience7])
        self.assertListEqual(list(song.partners.all()), [singer2, singer3, audience6, audience7])

        data = {
            'song_id': song.id,
            'song_name': song.song_name,
            'musical': "New Musical",
            'partners': [str(singer4.id), str(singer5.id), str(audience6.id), str(audience7.id)]
        }

        response = self.client.put(reverse('update_song'), data, content_type='application/json')
        self.assertEqual(response.status_code, 200)

        song.refresh_from_db()
        self.assertEqual(song.musical, "New Musical")
        self.assertListEqual(list(song.partners.all()), [singer4, singer5, audience6, audience7])

    def test_duplicate_partner(self):
        user = login_singer(self, user_id=1, num_songs=2)
        singer2, singer3  = create_singers([2, 3])
        [audience4] = create_audience([4])

        song1 = get_song(1, 1)
        song2 = get_song(1, 2)

        song1.partners.set([singer2, audience4])

        # Try to add singer2 to as a partner to another song
        data = {
            'song_id': song2.id,
            'song_name': song2.song_name,
            'musical': song2.musical,
            'partners': [str(singer2.id), str(singer3.id)]
        }

        response = self.client.put(reverse('update_song'), data, content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertJSONEqual(response.content,
                             {'error': f"A person can be selected as partner once per night, "
                                       f"and {singer2} already used his/her slot."})

        song2.refresh_from_db()
        self.assertListEqual(list(song2.partners.all()), [])

        # Try to add audience4 to as a partner to another song
        data = {
            'song_id': song2.id,
            'song_name': song2.song_name,
            'musical': song2.musical,
            'partners': [str(audience4.id)]
        }

        response = self.client.put(reverse('update_song'), data, content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertJSONEqual(response.content,
                             {'error': f"A person can be selected as partner once per night, "
                                       f"and {audience4} already used his/her slot."})

        song2.refresh_from_db()
        self.assertListEqual(list(song2.partners.all()), [])

        # Remove singer2 from the first song and try again
        data = {
            'song_id': song1.id,
            'song_name': song1.song_name,
            'musical': song1.musical,
            'partners': []
        }
        response = self.client.put(reverse('update_song'), data, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        song1.refresh_from_db()
        self.assertListEqual(list(song1.partners.all()), [])

        data = {
            'song_id': song2.id,
            'song_name': song2.song_name,
            'musical': song2.musical,
            'partners': [str(singer2.id), str(singer3.id)]
        }
        response = self.client.put(reverse('update_song'), data, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        song2.refresh_from_db()
        self.assertListEqual(list(song2.partners.all()), [singer2, singer3])

    def test_empty_note(self):
        user = login_singer(self, user_id=1, num_songs=1)
        song = user.songs.first()

        data = {
            'song_id': song.id,
            'song_name': song.song_name,
            'musical': song.musical,
            'partners': []
        }

        response = self.client.put(reverse('update_song'), data, content_type='application/json')
        self.assertEqual(response.status_code, 200)

        res_json = get_json(response)
        expected_json = self._get_expected_song_json(song_name=song.song_name, musical=song.musical, singer=user,
                                                     id=song.id, partners=[],
                                                     note=None)

        self.assertDictEqual(self._remove_song_keys(res_json), self._remove_song_keys(expected_json))

        song.refresh_from_db()
        self.assertIsNone(song.notes)

    def test_replace_note(self):
        user = login_singer(self, user_id=1, num_songs=1)
        song = user.songs.first()
        song.notes = "Old note"
        song.save()

        data = {
            'song_id': song.id,
            'song_name': song.song_name,
            'musical': song.musical,
            'partners': [],
            'notes': "New note"
        }

        response = self.client.put(reverse('update_song'), data, content_type='application/json')
        self.assertEqual(response.status_code, 200)

        res_json = get_json(response)
        expected_json = self._get_expected_song_json(song_name=song.song_name, musical=song.musical, singer=user,
                                                     id=song.id, partners=[],
                                                     note="New note")

        self.assertDictEqual(self._remove_song_keys(res_json), self._remove_song_keys(expected_json))

        song.refresh_from_db()
        self.assertEqual(song.notes, "New note")

    def test_update_same_song(self):
        self._update_same_song()

    def test_update_same_song_and_musical(self):
        self._update_same_song(same_musical=True)

    def _update_same_song(self, same_musical=False):
        """
        Verify that found music and default lyrics don't change when the song is the same.
        """
        user = login_singer(self, user_id=1, num_songs=1)
        singer2, singer3 = create_singers([2, 3])
        song = get_song(1, 1)
        song.found_music = True
        song.default_lyrics = True
        song.partners.set([singer2, singer3])
        song.save()

        original_id = song.id
        original_song_name = song.song_name
        original_musical = song.musical
        original_partners = list(song.partners.all())

        data = {
            'song_id': song.id,
            'song_name': song.song_name,
            'musical': song.musical if same_musical else 'New Musical',
            'partners': [str(singer2.id), str(singer3.id)]
        }

        response = self.client.put(reverse('update_song'), data, content_type='application/json')
        self.assertEqual(response.status_code, 200)

        song.refresh_from_db()  # Reload from the database

        self.assertTrue(song.found_music)
        self.assertTrue(song.default_lyrics)
        self.assertEqual(song.id, original_id)
        self.assertEqual(song.song_name, original_song_name)
        self.assertEqual(song.musical, original_musical if same_musical else "New Musical")
        self.assertListEqual(list(song.partners.all()), original_partners)


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
        response = self.client.post(reverse('suggest_song'), {
            'song-name': ["Brotherhood of man"],
            'musical': ['How to succeed in business without '
                        'really trying'],
            'group-song': 'on'
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
        response = self.client.post(reverse('suggest_song'), {
            'song-name': ["Brotherhood of man"],
            'musical': ['How to succeed in business without '
                        'really trying'],
            'group-song': 'on'
        })
        self.assertEqual(GroupSongRequest.objects.count(), 1)
        created_song = GroupSongRequest.objects.first()
        self.assertEqual(created_song.suggested_by, get_audience_str(1))

    def test_get(self):
        login_audience(self)
        response = self.client.get(reverse('suggest_song'))
        self.assertTemplateUsed(response, 'song_signup/suggest_song.html')


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
                             {'error': f"A person can be selected as partner once per night, "
                                                      f"and {s4} already used his/her slot."})

    def test_existing_partner_audience(self):
        user = login_singer(self, user_id=1)
        s2, s3, s4 = create_singers([2, 3, 4], num_songs=1)
        [a5] = create_audience([5])
        add_partners(3, [], 1, audience_partner_ids=['5'])
        response = self.client.post(reverse('add_song_request'), {
            'song-name': ["defying gravity"],
            'musical': ['wicked'],
            'partners': [str(s2.id), str(s3.id), str(s4.id), str(a5.id)]
        })
        self.assertFalse(song_exists('Defying Gravity'))
        self.assertEqual(response.status_code, 400)
        self.assertJSONEqual(response.content,
                             {'error': f"A person can be selected as partner once per night, "
                                       f"and {a5} already used his/her slot."})

    def test_superuser_partner(self):
        user = login_singer(self, user_id=1)
        s2, s3, s4 = create_singers([2, 3, 4], num_songs=3)

        s4.is_superuser = True
        s4.save()

        add_partners(3, ['4'], 1)
        add_partners(3, ['4'], 2)
        add_partners(2, ['4'], 1)


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
    
    def test_suggestion_marked_used_on_add(self):
        """Test that matching suggestions are marked as used when a song request is added."""
        # Create a suggestion first
        [suggester] = create_singers(1)
        suggestion = SongSuggestion.objects.create(
            song_name='Defying Gravity',
            musical='Wicked',
            suggested_by=suggester
        )
        self.assertFalse(suggestion.is_used)
        
        # Now add a matching song request
        login_singer(self, user_id=2)
        self.client.post(reverse('add_song_request'), {
            'song-name': ["Defying Gravity"],
            'musical': ['Wicked'],
            'notes': ['']
        })
        
        # The suggestion should now be marked as used
        suggestion.refresh_from_db()
        self.assertTrue(suggestion.is_used)


class TestDeleteSong(TransactionTestCase):
    """Tests for delete_song view."""
    
    def test_suggestion_unmarked_on_delete(self):
        """Test that matching suggestions are unmarked when a song request is deleted."""
        # Create a suggestion
        [suggester] = create_singers(1)
        suggestion = SongSuggestion.objects.create(
            song_name='Defying Gravity',
            musical='Wicked',
            suggested_by=suggester
        )
        
        # Create a matching song request (marks suggestion as used)
        user = login_singer(self, user_id=2)
        song = SongRequest.objects.create(
            song_name='Defying Gravity',
            musical='Wicked',
            singer=user
        )
        SongSuggestion.objects.check_used_suggestions()
        suggestion.refresh_from_db()
        self.assertTrue(suggestion.is_used)
        
        # Delete the song request
        response = self.client.post(reverse('delete_song', args=[song.id]))
        self.assertEqual(response.status_code, 200)
        
        # The suggestion should now be unmarked
        suggestion.refresh_from_db()
        self.assertFalse(suggestion.is_used)
        
        # Verify song was actually deleted
        self.assertEqual(SongRequest.objects.count(), 0)


class TestHelpers(TestCase):
    def test_get_current_song(self):
        # Regular setlist order
        create_singers(3)
        song1, song2, song3 = add_songs_to_singers(3, 1)
        curr, is_group_song = _get_current_song()
        self.assertEqual(curr, song1)
        self.assertFalse(is_group_song)

        set_performed(1, 1)
        curr, is_group_song = _get_current_song()
        self.assertEqual(curr, song2)
        self.assertFalse(is_group_song)

        # Spotlight song #3
        SongRequest.objects.set_spotlight(song3)
        curr, is_group_song = _get_current_song()
        self.assertEqual(curr, song3)
        self.assertFalse(is_group_song)

        # Start a group songs (gets precedence)
        current_group_song = add_current_group_song("group", "song")
        curr, is_group_song = _get_current_song()
        self.assertEqual(curr, current_group_song.group_song)
        self.assertTrue(is_group_song)

        # Stop group song - go back to spotlit song
        current_group_song.end_song()
        curr, is_group_song = _get_current_song()
        self.assertEqual(curr, song3)
        self.assertFalse(is_group_song)

        # Stop spotlight - go back to regular order
        SongRequest.objects.remove_spotlight()
        curr, is_group_song = _get_current_song()
        self.assertEqual(curr, song2)
        self.assertFalse(is_group_song)


class TestAddSongView(TestViews):
    def setUp(self):
        self.shani = Singer.objects.create_user(username='shani_wahrman', first_name='Shani', last_name='Wahrman',
                                                is_audience=False, is_superuser=True)
        self.alon = Singer.objects.create_user(username='alon_aviv', first_name='Alon', last_name='Aviv', is_audience=False,
                                          is_superuser=True)
        self.user = login_singer(self, user_id=99)

    def test_add_song(self):
        [singer2] = create_singers([2], num_songs=2)
        audience3, audience4 = create_audience([3, 4])

        response = self.client.get(reverse('add_song'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'song_signup/add_song.html')

        self.assertListEqual(response.context['possible_partners'],
                             [self.shani, self.alon, audience3, audience4, singer2])

        [singer5, singer6, singer7] = create_singers([5, 6, 7], num_songs=2)
        audience8, audience9 = create_audience([8, 9])
        singer6.is_active = False
        singer6.save()

        audience9.is_active = False
        audience9.save()


        response = self.client.get(reverse('add_song'))
        self.assertEqual(response.status_code, 200)
        self.assertListEqual(response.context['possible_partners'],
                             [self.shani,
                              self.alon,
                              audience3,
                              audience4,
                              audience8,
                              singer2,
                              singer5,
                              singer7
                              ])

class TestTrivia(TestViews):
    def setUp(self):
        self.default_fonts = dict(
            question_font_size_mobile=25,
            question_font_size_live_lyrics=60,
            choices_font_size=20
        )
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
            image=None,
            **self.default_fonts
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
        self.assertEqual(response.status_code, 200)
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
            **self.default_fonts
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
            **self.default_fonts
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

class TestRaffle(TestViews):
    def setUp(self):
        # Log in as superuser
        user = login_singer(self, user_id=999)
        user.is_superuser = True
        user.save()

    def _end_raffle_assert_winner(self, winner, winner_name):
        self.assertEqual(str(winner), winner_name)
        self.assertTrue(winner.is_audience)
        self.assertTrue(winner.raffle_winner)
        self.assertTrue(winner.active_raffle_winner)

        response = self.client.get(reverse('get_active_raffle_winner'))
        self.assertEqual(response.status_code, 200)
        self.assertDictEqual(response.data, dict(id=winner.id, full_name=winner.get_full_name()))

        res = self.client.get(reverse('end_raffle'))
        self.assertRedirects(res, '/admin/song_signup/songrequest', target_status_code=301)
        winner.refresh_from_db()
        self.assertFalse(winner.active_raffle_winner)

        response = self.client.get(reverse('get_active_raffle_winner'))
        self.assertEqual(response.status_code, 200)
        self.assertDictEqual(response.data, {})

    def _assert_no_participants(self):
        res = self.client.get(reverse('start_raffle'))
        self.assertRedirects(res, '/admin/song_signup/songrequest', target_status_code=301)
        self.assertEqual(self.client.session['raffle_winner'], 'NO RAFFLE PARTICIPANTS')

        winners = Singer.objects.filter(raffle_winner=True)
        self.assertFalse(winners.exists())

        response = self.client.get(reverse('get_active_raffle_winner'))
        self.assertEqual(response.status_code, 200)
        self.assertDictEqual(response.data, {})

    def test_raffle(self):
        participants = set(create_audience(3))
        participate_in_raffle(participants)
        create_singers(3)
        create_audience([4, 5, 6])
        winners = set()

        res = self.client.get(reverse('start_raffle'))
        self.assertRedirects(res, '/admin/song_signup/songrequest', target_status_code=301)
        winner1_name = self.client.session['raffle_winner']

        [winner1] = Singer.objects.filter(active_raffle_winner=True)
        self._end_raffle_assert_winner(winner1, winner1_name)
        winners.add(winner1)

        res = self.client.get(reverse('start_raffle'))
        self.assertRedirects(res, '/admin/song_signup/songrequest', target_status_code=301)
        winner2_name = self.client.session['raffle_winner']

        [winner2] = Singer.objects.filter(active_raffle_winner=True)
        self._end_raffle_assert_winner(winner2, winner2_name)
        winners.add(winner2)

        res = self.client.get(reverse('start_raffle'))
        self.assertRedirects(res, '/admin/song_signup/songrequest', target_status_code=301)
        winner3_name = self.client.session['raffle_winner']

        [winner3] = Singer.objects.filter(active_raffle_winner=True)
        self._end_raffle_assert_winner(winner3, winner3_name)
        winners.add(winner3)

        self.assertSetEqual(participants, winners)

    def test_no_participants(self):
        singers = create_singers(3)
        participate_in_raffle(singers) # Verify that singers can never be winners
        create_audience(3)

        self._assert_no_participants()

    def test_no_active_participants(self):
        singers = create_singers(3)
        participate_in_raffle(singers) # Verify that singers can never be winners
        audiences = create_audience(3)
        participate_in_raffle(audiences)

        for audience in audiences:
            audience.is_active = False
            audience.save()

        self._assert_no_participants()


class TestSongSuggestionSerializer(TestViews):
    """Tests for SongSuggestionSerializer field structure and nested objects."""
    
    def test_serializer_all_fields_present(self):
        """Test that all expected fields are present in serialized data."""
        suggester, voter1, voter2 = create_singers(3)
        suggestion = SongSuggestion.objects.create(
            song_name='Defying Gravity',
            musical='Wicked',
            suggested_by=suggester
        )
        suggestion.voters.set([voter1, voter2])
        
        response = self.client.get(reverse('get_suggested_songs'))
        self.assertEqual(response.status_code, 200)
        
        data = response.data[0]
        # Basic fields from model
        self.assertEqual(data['id'], suggestion.id)
        self.assertEqual(data['song_name'], 'Defying Gravity')
        self.assertEqual(data['musical'], 'Wicked')
        self.assertFalse(data['is_used'])
        self.assertIsNotNone(data['request_time'])
        
        # SerializerMethodFields
        self.assertEqual(data['vote_count'], 2)
        self.assertFalse(data['user_voted'])  # Not authenticated
        
        # Nested objects
        self.assertIn('suggested_by', data)
        self.assertIn('voters', data)
    
    def test_serializer_suggested_by_structure(self):
        """Test that suggested_by contains proper nested Singer data."""
        [suggester] = create_singers(1)
        SongSuggestion.objects.create(
            song_name='Defying Gravity',
            musical='Wicked',
            suggested_by=suggester
        )
        
        response = self.client.get(reverse('get_suggested_songs'))
        suggested_by = response.data[0]['suggested_by']
        
        self.assertEqual(suggested_by['id'], suggester.id)
        self.assertEqual(suggested_by['first_name'], suggester.first_name)
        self.assertEqual(suggested_by['last_name'], suggester.last_name)
        self.assertIn('is_superuser', suggested_by)
    
    def test_serializer_voters_list_structure(self):
        """Test that voters list contains proper nested Singer data."""
        suggester, voter1, voter2 = create_singers(3)
        suggestion = SongSuggestion.objects.create(
            song_name='Defying Gravity',
            musical='Wicked',
            suggested_by=suggester
        )
        suggestion.voters.set([voter1, voter2])
        
        response = self.client.get(reverse('get_suggested_songs'))
        voters = response.data[0]['voters']
        
        self.assertEqual(len(voters), 2)
        voter_ids = {v['id'] for v in voters}
        self.assertEqual(voter_ids, {voter1.id, voter2.id})
        
        # Check that each voter has complete Singer data
        for voter_data in voters:
            self.assertIn('id', voter_data)
            self.assertIn('first_name', voter_data)
            self.assertIn('last_name', voter_data)
            self.assertIn('is_superuser', voter_data)
    
    def test_serializer_empty_voters_and_zero_votes(self):
        """Test that voters list is empty and vote_count is 0 when no votes."""
        [suggester] = create_singers(1)
        SongSuggestion.objects.create(
            song_name='Defying Gravity',
            musical='Wicked',
            suggested_by=suggester
        )
        
        response = self.client.get(reverse('get_suggested_songs'))
        data = response.data[0]
        
        self.assertEqual(data['vote_count'], 0)
        self.assertEqual(len(data['voters']), 0)
        self.assertIsInstance(data['voters'], list)


class TestToggleVote(TestViews):
    """Tests for the toggle_vote endpoint."""
    
    def setUp(self):
        [self.suggester] = create_singers(1)
        self.suggestion = SongSuggestion.objects.create(
            song_name='Defying Gravity',
            musical='Wicked',
            suggested_by=self.suggester
        )
        self.voter = login_singer(self, user_id=2)
    
    def test_vote_unauthenticated(self):
        """Test that unauthenticated users cannot vote."""
        self.client.logout()
        response = self.client.post(reverse('toggle_vote', args=[self.suggestion.id]))
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data['error'], 'User must be authenticated to vote')
    
    def test_vote_nonexistent_suggestion(self):
        """Test voting for non-existent suggestion returns 404."""
        response = self.client.post(reverse('toggle_vote', args=[999]))
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data['error'], 'Song suggestion with ID 999 does not exist')
    
    def test_add_vote(self):
        """Test adding a vote to a suggestion."""
        response = self.client.post(reverse('toggle_vote', args=[self.suggestion.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['voted'])
        
        self.suggestion.refresh_from_db()
        self.assertEqual(self.suggestion.vote_count, 1)
        self.assertTrue(self.suggestion.user_voted(self.voter))
    
    def test_remove_vote(self):
        """Test removing a vote from a suggestion."""
        # First add a vote
        self.suggestion.voters.add(self.voter)
        self.assertEqual(self.suggestion.vote_count, 1)
        
        # Then remove it
        response = self.client.post(reverse('toggle_vote', args=[self.suggestion.id]))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['voted'])
        
        self.suggestion.refresh_from_db()
        self.assertEqual(self.suggestion.vote_count, 0)
        self.assertFalse(self.suggestion.user_voted(self.voter))
    
    def test_toggle_vote_multiple_times(self):
        """Test toggling vote multiple times."""
        # Vote
        response = self.client.post(reverse('toggle_vote', args=[self.suggestion.id]))
        self.assertTrue(response.data['voted'])
        
        # Unvote
        response = self.client.post(reverse('toggle_vote', args=[self.suggestion.id]))
        self.assertFalse(response.data['voted'])
        
        # Vote again
        response = self.client.post(reverse('toggle_vote', args=[self.suggestion.id]))
        self.assertTrue(response.data['voted'])
        
        self.suggestion.refresh_from_db()
        self.assertEqual(self.suggestion.vote_count, 1)
    
    def test_vote_with_audience_user(self):
        """Test that audience members can vote."""
        self.client.logout()
        audience = login_audience(self, user_id=3)
        
        response = self.client.post(reverse('toggle_vote', args=[self.suggestion.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['voted'])
        
        self.suggestion.refresh_from_db()
        self.assertTrue(self.suggestion.user_voted(audience))
    
    def test_multiple_users_vote(self):
        """Test that multiple users can vote on the same suggestion."""
        # First user votes
        response = self.client.post(reverse('toggle_vote', args=[self.suggestion.id]))
        self.assertTrue(response.data['voted'])
        
        # Second user votes
        self.client.logout()
        user2 = login_singer(self, user_id=3)
        response = self.client.post(reverse('toggle_vote', args=[self.suggestion.id]))
        self.assertTrue(response.data['voted'])
        
        # Third user votes
        self.client.logout()
        user3 = login_audience(self, user_id=4)
        response = self.client.post(reverse('toggle_vote', args=[self.suggestion.id]))
        self.assertTrue(response.data['voted'])
        
        self.suggestion.refresh_from_db()
        self.assertEqual(self.suggestion.vote_count, 3)
        self.assertTrue(self.suggestion.user_voted(self.voter))
        self.assertTrue(self.suggestion.user_voted(user2))
        self.assertTrue(self.suggestion.user_voted(user3))


class TestGetSuggestedSongs(TestViews):
    """Tests for the get_suggested_songs endpoint with voting."""
    
    def setUp(self):
        [self.suggester] = create_singers(1)
        with freeze_time(TEST_START_TIME) as frozen_time:
            self.suggestion1 = SongSuggestion.objects.create(
                song_name='Defying Gravity',
                musical='Wicked',
                suggested_by=self.suggester
            )
            frozen_time.tick()
            self.suggestion2 = SongSuggestion.objects.create(
                song_name='Seasons Of Love',
                musical='Rent',
                suggested_by=self.suggester
            )
            frozen_time.tick()
            self.suggestion3 = SongSuggestion.objects.create(
                song_name='On My Own',
                musical='Les Misérables',
                suggested_by=self.suggester
            )
    
    def test_get_suggestions_empty(self):
        """Test getting suggestions when none exist."""
        SongSuggestion.objects.all().delete()
        response = self.client.get(reverse('get_suggested_songs'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)
    
    def test_get_suggestions_no_votes(self):
        """Test suggestions are ordered by recency when no votes."""
        response = self.client.get(reverse('get_suggested_songs'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 3)
        
        # Most recent first when no votes
        self.assertEqual(response.data[0]['song_name'], 'On My Own')
        self.assertEqual(response.data[0]['vote_count'], 0)
        self.assertEqual(response.data[1]['song_name'], 'Seasons Of Love')
        self.assertEqual(response.data[1]['vote_count'], 0)
        self.assertEqual(response.data[2]['song_name'], 'Defying Gravity')
        self.assertEqual(response.data[2]['vote_count'], 0)
    
    def test_get_suggestions_ordered_by_votes(self):
        """Test suggestions are ordered by vote count descending."""
        voter1, voter2, voter3 = create_singers([2, 3, 4])
        
        # suggestion1: 3 votes
        self.suggestion1.voters.set([voter1, voter2, voter3])
        # suggestion2: 1 vote
        self.suggestion2.voters.set([voter1])
        # suggestion3: 2 votes
        self.suggestion3.voters.set([voter2, voter3])
        
        response = self.client.get(reverse('get_suggested_songs'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 3)
        
        self.assertEqual(response.data[0]['song_name'], 'Defying Gravity')  # 3 votes
        self.assertEqual(response.data[0]['vote_count'], 3)
        
        self.assertEqual(response.data[1]['song_name'], 'On My Own')  # 2 votes
        self.assertEqual(response.data[1]['vote_count'], 2)
        
        self.assertEqual(response.data[2]['song_name'], 'Seasons Of Love')  # 1 vote
        self.assertEqual(response.data[2]['vote_count'], 1)
    
    def test_get_suggestions_mixed_votes_and_no_votes(self):
        """Test ordering when some suggestions have votes and others don't."""
        voter1, voter2 = create_singers([5, 6])
        
        # suggestion1: 2 votes
        self.suggestion1.voters.set([voter1, voter2])
        # suggestion2: 0 votes
        # suggestion3: 1 vote
        self.suggestion3.voters.add(voter1)
        
        response = self.client.get(reverse('get_suggested_songs'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 3)
        
        # Verify ordering: votes desc, then time desc
        # suggestion1: 2 votes
        self.assertEqual(response.data[0]['song_name'], 'Defying Gravity')
        self.assertEqual(response.data[0]['musical'], 'Wicked')
        self.assertEqual(response.data[0]['vote_count'], 2)
        self.assertFalse(response.data[0]['is_used'])
        self.assertIsNotNone(response.data[0]['id'])
        self.assertIsNotNone(response.data[0]['request_time'])
        self.assertIn('suggested_by', response.data[0])
        self.assertEqual(response.data[0]['suggested_by']['id'], self.suggester.id)
        self.assertIn('voters', response.data[0])
        self.assertEqual(len(response.data[0]['voters']), 2)
        
        # suggestion3: 1 vote
        self.assertEqual(response.data[1]['song_name'], 'On My Own')
        self.assertEqual(response.data[1]['musical'], 'Les Misérables')
        self.assertEqual(response.data[1]['vote_count'], 1)
        self.assertFalse(response.data[1]['is_used'])
        
        # suggestion2: 0 votes (most recent of the 0-vote suggestions)
        self.assertEqual(response.data[2]['song_name'], 'Seasons Of Love')
        self.assertEqual(response.data[2]['musical'], 'Rent')
        self.assertEqual(response.data[2]['vote_count'], 0)
        self.assertFalse(response.data[2]['is_used'])
        self.assertEqual(len(response.data[2]['voters']), 0)
    
    def test_get_suggestions_same_votes_ordered_by_time(self):
        """Test suggestions with same vote count are ordered by recency."""
        voter1, voter2 = create_singers([7, 8])
        
        # Both have 1 vote, so order by time (most recent first)
        self.suggestion1.voters.set([voter1])
        self.suggestion3.voters.set([voter2])
        
        response = self.client.get(reverse('get_suggested_songs'))
        self.assertEqual(response.status_code, 200)
        
        # suggestion3 is most recent
        self.assertEqual(response.data[0]['song_name'], 'On My Own')
        self.assertEqual(response.data[0]['vote_count'], 1)
        
        # suggestion1 is older
        self.assertEqual(response.data[1]['song_name'], 'Defying Gravity')
        self.assertEqual(response.data[1]['vote_count'], 1)
    
    def test_user_voted_authenticated(self):
        """Test user_voted field is correct for authenticated user."""
        user = login_singer(self, user_id=2)
        self.suggestion1.voters.add(user)
        self.suggestion3.voters.add(user)
        
        response = self.client.get(reverse('get_suggested_songs'))
        self.assertEqual(response.status_code, 200)
        
        suggestions_by_name = {s['song_name']: s for s in response.data}
        
        self.assertTrue(suggestions_by_name['Defying Gravity']['user_voted'])
        self.assertFalse(suggestions_by_name['Seasons Of Love']['user_voted'])
        self.assertTrue(suggestions_by_name['On My Own']['user_voted'])
    
    def test_user_voted_unauthenticated(self):
        """Test user_voted is False for unauthenticated users."""
        response = self.client.get(reverse('get_suggested_songs'))
        self.assertEqual(response.status_code, 200)
        
        for suggestion in response.data:
            self.assertFalse(suggestion['user_voted'])
    
    def test_user_voted_audience(self):
        """Test user_voted works for audience members."""
        audience = login_audience(self, user_id=2)
        self.suggestion2.voters.add(audience)
        
        response = self.client.get(reverse('get_suggested_songs'))
        self.assertEqual(response.status_code, 200)
        
        suggestions_by_name = {s['song_name']: s for s in response.data}
        
        self.assertFalse(suggestions_by_name['Defying Gravity']['user_voted'])
        self.assertTrue(suggestions_by_name['Seasons Of Love']['user_voted'])
        self.assertFalse(suggestions_by_name['On My Own']['user_voted'])
    
    def test_voters_list_included(self):
        """Test that voters list is included in response."""
        voter1, voter2 = create_singers([9, 10])
        self.suggestion1.voters.set([voter1, voter2])
        
        response = self.client.get(reverse('get_suggested_songs'))
        self.assertEqual(response.status_code, 200)
        
        suggestion1_data = response.data[0]  # Has most votes
        self.assertEqual(len(suggestion1_data['voters']), 2)
        voter_ids = {v['id'] for v in suggestion1_data['voters']}
        self.assertEqual(voter_ids, {voter1.id, voter2.id})
    
    def test_is_used_ordering(self):
        """Test that unused suggestions appear before used ones."""
        [voter] = create_singers([11])
        
        # Give all equal votes
        self.suggestion1.voters.add(voter)
        self.suggestion2.voters.add(voter)
        self.suggestion3.voters.add(voter)
        
        # Mark suggestion1 as used
        self.suggestion1.is_used = True
        self.suggestion1.save()
        
        response = self.client.get(reverse('get_suggested_songs'))
        self.assertEqual(response.status_code, 200)
        
        # Used suggestion should be last
        self.assertFalse(response.data[0]['is_used'])
        self.assertFalse(response.data[1]['is_used'])
        self.assertTrue(response.data[2]['is_used'])
        self.assertEqual(response.data[2]['song_name'], 'Defying Gravity')


class TestSuggestSong(TestViews):
    """Tests for the suggest_song view (creating song suggestions)."""
    
    def test_suggest_song_get(self):
        """Test GET request renders the template."""
        login_singer(self, user_id=1)
        response = self.client.get(reverse('suggest_song'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'song_signup/suggest_song.html')
    
    def test_suggest_song_post_singer(self):
        """Test creating a song suggestion as a singer."""
        user = login_singer(self, user_id=1)
        
        response = self.client.post(reverse('suggest_song'), {
            'song-name': 'defying gravity',
            'musical': 'wicked'
        })
        
        self.assertRedirects(response, reverse('view_suggestions'))
        
        self.assertEqual(SongSuggestion.objects.count(), 1)
        suggestion = SongSuggestion.objects.first()
        self.assertEqual(suggestion.song_name, 'Defying Gravity')
        self.assertEqual(suggestion.musical, 'Wicked')
        self.assertEqual(suggestion.suggested_by, user)
        self.assertFalse(suggestion.is_used)
        self.assertEqual(suggestion.vote_count, 0)
    
    def test_suggest_song_post_audience(self):
        """Test creating a song suggestion as an audience member."""
        user = login_audience(self, user_id=1)
        
        response = self.client.post(reverse('suggest_song'), {
            'song-name': 'the wizard and i',
            'musical': 'wicked'
        })
        
        self.assertRedirects(response, reverse('view_suggestions'))
        
        self.assertEqual(SongSuggestion.objects.count(), 1)
        suggestion = SongSuggestion.objects.first()
        self.assertEqual(suggestion.song_name, 'The Wizard and I')
        self.assertEqual(suggestion.suggested_by, user)
    
    def test_suggest_song_titlecase(self):
        """Test that song names and musicals are properly titlecased."""
        login_singer(self, user_id=1)
        
        self.client.post(reverse('suggest_song'), {
            'song-name': 'for GOOD',
            'musical': 'wicked'
        })
        
        suggestion = SongSuggestion.objects.first()
        self.assertEqual(suggestion.song_name, 'For Good')
        self.assertEqual(suggestion.musical, 'Wicked')
    
    def test_suggest_song_duplicate(self):
        """Test suggesting an existing song doesn't create duplicate."""
        [suggester] = create_singers(1)
        SongSuggestion.objects.create(
            song_name='Defying Gravity',
            musical='Wicked',
            suggested_by=suggester
        )
        
        login_singer(self, user_id=2)
        response = self.client.post(reverse('suggest_song'), {
            'song-name': 'defying gravity',
            'musical': 'wicked'
        })
        
        # Should still redirect successfully
        self.assertRedirects(response, reverse('view_suggestions'))
        
        # Should not create a duplicate
        self.assertEqual(SongSuggestion.objects.count(), 1)
        suggestion = SongSuggestion.objects.first()
        # Original suggester should remain
        self.assertEqual(suggestion.suggested_by, suggester)
    
    def test_suggest_song_case_insensitive(self):
        """Test that duplicate detection is case-insensitive."""
        [suggester] = create_singers(1)
        SongSuggestion.objects.create(
            song_name='Defying Gravity',
            musical='Wicked',
            suggested_by=suggester
        )
        
        login_singer(self, user_id=2)
        self.client.post(reverse('suggest_song'), {
            'song-name': 'DEFYING GRAVITY',
            'musical': 'WICKED'
        })
        
        # Should not create duplicate
        self.assertEqual(SongSuggestion.objects.count(), 1)
    
    def test_suggest_multiple_songs(self):
        """Test that multiple different suggestions can be created."""
        user = login_singer(self, user_id=1)
        
        self.client.post(reverse('suggest_song'), {
            'song-name': 'Defying Gravity',
            'musical': 'Wicked'
        })
        
        self.client.post(reverse('suggest_song'), {
            'song-name': 'Popular',
            'musical': 'Wicked'
        })
        
        self.client.post(reverse('suggest_song'), {
            'song-name': 'For Good',
            'musical': 'Wicked'
        })
        
        self.assertEqual(SongSuggestion.objects.count(), 3)
        song_names = set(SongSuggestion.objects.values_list('song_name', flat=True))
        self.assertEqual(song_names, {'Defying Gravity', 'Popular', 'For Good'})
        
        # Verify all suggestions were created by the logged-in user
        for suggestion in SongSuggestion.objects.all():
            self.assertEqual(suggestion.suggested_by, user)
    
    def test_suggest_song_timestamp(self):
        """Test that suggestions have proper timestamps."""
        login_singer(self, user_id=1)
        
        with freeze_time(TEST_START_TIME) as frozen_time:
            self.client.post(reverse('suggest_song'), {
                'song-name': 'Defying Gravity',
                'musical': 'Wicked'
            })
            
            suggestion1 = SongSuggestion.objects.first()
            time1 = suggestion1.request_time
            
            frozen_time.tick()
            
            self.client.post(reverse('suggest_song'), {
                'song-name': 'Popular',
                'musical': 'Wicked'
            })
            
            suggestion2 = SongSuggestion.objects.get(song_name='Popular')
            time2 = suggestion2.request_time
            
            self.assertLess(time1, time2)
    
    def test_suggestion_checked_for_use_on_create(self):
        """Test that suggestions are checked and marked as used when created if matching request exists."""
        # Create a singer with a song request
        [singer] = create_singers(1)
        SongRequest.objects.create(
            song_name='Defying Gravity',
            musical='Wicked',
            singer=singer
        )
        
        # Now suggest the same song
        login_singer(self, user_id=2)
        self.client.post(reverse('suggest_song'), {
            'song-name': 'Defying Gravity',
            'musical': 'Wicked'
        })
        
        # The suggestion should be marked as used
        suggestion = SongSuggestion.objects.get(song_name='Defying Gravity', musical='Wicked')
        self.assertTrue(suggestion.is_used)
    
    def test_suggestion_not_marked_used_if_no_matching_request(self):
        """Test that new suggestions are not marked as used if no matching request exists."""
        login_singer(self, user_id=1)
        
        self.client.post(reverse('suggest_song'), {
            'song-name': 'Defying Gravity',
            'musical': 'Wicked'
        })
        
        # The suggestion should NOT be marked as used
        suggestion = SongSuggestion.objects.get(song_name='Defying Gravity', musical='Wicked')
        self.assertFalse(suggestion.is_used)


class TestVotingIntegration(TestViews):
    """Integration tests for the full voting workflow."""
    
    def test_full_voting_workflow(self):
        """Test complete workflow: suggest, vote, check ordering."""
        # Create suggestions
        [suggester] = create_singers(1)
        suggestion1 = SongSuggestion.objects.create(
            song_name='Song A',
            musical='Musical',
            suggested_by=suggester
        )
        suggestion2 = SongSuggestion.objects.create(
            song_name='Song B',
            musical='Musical',
            suggested_by=suggester
        )
        suggestion3 = SongSuggestion.objects.create(
            song_name='Song C',
            musical='Musical',
            suggested_by=suggester
        )
        
        # User 1 votes for suggestion1 and suggestion2
        user1 = login_singer(self, user_id=2)
        self.client.post(reverse('toggle_vote', args=[suggestion1.id]))
        self.client.post(reverse('toggle_vote', args=[suggestion2.id]))
        
        # User 2 votes for suggestion1
        self.client.logout()
        user2 = login_singer(self, user_id=3)
        self.client.post(reverse('toggle_vote', args=[suggestion1.id]))
        
        # Check ordering: suggestion1 (2 votes), suggestion2 (1 vote), suggestion3 (0 votes)
        response = self.client.get(reverse('get_suggested_songs'))
        self.assertEqual(response.data[0]['song_name'], 'Song A')
        self.assertEqual(response.data[0]['vote_count'], 2)
        self.assertEqual(response.data[1]['song_name'], 'Song B')
        self.assertEqual(response.data[1]['vote_count'], 1)
        self.assertEqual(response.data[2]['song_name'], 'Song C')
        self.assertEqual(response.data[2]['vote_count'], 0)
        
        # User 2 changes their vote
        self.client.post(reverse('toggle_vote', args=[suggestion1.id]))  # Unvote
        self.client.post(reverse('toggle_vote', args=[suggestion3.id]))  # Vote for suggestion3
        
        # Check new ordering: all have 1 vote, should be ordered by recency
        response = self.client.get(reverse('get_suggested_songs'))
        vote_counts = [s['vote_count'] for s in response.data]
        self.assertEqual(vote_counts, [1, 1, 1])
    
    def test_vote_persistence_across_sessions(self):
        """Test that votes persist when user logs out and back in."""
        [suggester] = create_singers(1)
        suggestion = SongSuggestion.objects.create(
            song_name='Test Song',
            musical='Musical',
            suggested_by=suggester
        )
        
        # User votes
        user = login_singer(self, user_id=2)
        self.client.post(reverse('toggle_vote', args=[suggestion.id]))
        
        # Check vote is recorded
        response = self.client.get(reverse('get_suggested_songs'))
        self.assertTrue(response.data[0]['user_voted'])
        
        # Logout and login again
        self.client.logout()
        login_singer(self, user_id=2)
        
        # Vote should still be there
        response = self.client.get(reverse('get_suggested_songs'))
        self.assertTrue(response.data[0]['user_voted'])
        self.assertEqual(response.data[0]['vote_count'], 1)


class TestSuggestionPositions(TestViews):
    """Tests for suggestion position calculation and pinning behavior."""

    def test_ordering_by_votes_then_time(self):
        # Create suggester and voters
        suggester, v1, v2, v3, v4, v5, v6 = create_singers(7)

        # Create three suggestions at staggered times
        with freeze_time(auto_tick_seconds=1) as frozen:
            a = SongSuggestion.objects.create(song_name="A", musical="M", suggested_by=suggester)
            frozen.tick()
            b = SongSuggestion.objects.create(song_name="B", musical="M", suggested_by=suggester)
            frozen.tick()
            c = SongSuggestion.objects.create(song_name="C", musical="M", suggested_by=suggester)

        # Votes: C(3), B(3 but older than C), A(2)
        a.voters.set([v1, v2])
        b.voters.set([v1, v2, v3])
        c.voters.set([v1, v2, v4])

        SongSuggestion.objects.recalculate_positions()
        a.refresh_from_db(); b.refresh_from_db(); c.refresh_from_db()

        self.assertEqual(c.position, 1)
        self.assertEqual(b.position, 2)
        self.assertEqual(a.position, 3)

    def test_used_with_existing_position_is_pinned(self):
        suggester, v1, v2, v3, v4, v5 = create_singers(6)

        # Control recency so A is the most recent among A/B (for tie-breaks)
        with freeze_time(auto_tick_seconds=1) as frozen:
            b = SongSuggestion.objects.create(song_name="B", musical="M", suggested_by=suggester)
            frozen.tick()
            c = SongSuggestion.objects.create(song_name="C", musical="M", suggested_by=suggester)
            frozen.tick()
            a = SongSuggestion.objects.create(song_name="A", musical="M", suggested_by=suggester)

        a.voters.set([v1])          # 1
        b.voters.set([v1, v2, v3])  # 3
        c.voters.set([v1, v2])      # 2

        SongSuggestion.objects.recalculate_positions()
        a.refresh_from_db(); b.refresh_from_db(); c.refresh_from_db()

        # Mark C as used but keep its existing calculated position
        c.is_used = True
        c.save()

        # Boost A to become top
        a.voters.add(v4, v5)

        SongSuggestion.objects.recalculate_positions()
        a.refresh_from_db(); b.refresh_from_db(); c.refresh_from_db()

        self.assertEqual(c.position, 2)
        self.assertEqual(a.position, 1)
        self.assertEqual(b.position, 3)

    def test_newly_used_without_position_gets_current_rank_slot(self):
        suggester, v1, v2, v3 = create_singers(4)

        a = SongSuggestion.objects.create(song_name="A", musical="M", suggested_by=suggester)
        b = SongSuggestion.objects.create(song_name="B", musical="M", suggested_by=suggester)
        c = SongSuggestion.objects.create(song_name="C", musical="M", suggested_by=suggester)

        a.voters.set([v1, v2])      # 2
        b.voters.set([v1])          # 1
        c.voters.set([v1, v2, v3])  # 3

        SongSuggestion.objects.recalculate_positions()
        a.refresh_from_db(); b.refresh_from_db(); c.refresh_from_db()

        # Mark A as used (no preset position); recalc should pin it at current slot = 2
        a.is_used = True
        a.save()

        SongSuggestion.objects.recalculate_positions()
        a.refresh_from_db(); b.refresh_from_db(); c.refresh_from_db()

        self.assertEqual(c.position, 1)
        self.assertEqual(a.position, 2)
        self.assertEqual(b.position, 3)

    def test_multiple_used_with_gaps_filled(self):
        suggester, v1, v2, v3, v4 = create_singers(5)

        a = SongSuggestion.objects.create(song_name="A", musical="M", suggested_by=suggester)
        b = SongSuggestion.objects.create(song_name="B", musical="M", suggested_by=suggester)
        c = SongSuggestion.objects.create(song_name="C", musical="M", suggested_by=suggester)
        d = SongSuggestion.objects.create(song_name="D", musical="M", suggested_by=suggester)

        # Votes base order: D(4), C(3), B(2), A(1)
        a.voters.set([v1])
        b.voters.set([v1, v2])
        c.voters.set([v1, v2, v3])
        d.voters.set([v1, v2, v3, v4])

        SongSuggestion.objects.recalculate_positions()
        a.refresh_from_db(); b.refresh_from_db(); c.refresh_from_db(); d.refresh_from_db()

        # Mark B and C as used at their current positions (do not set position manually)
        # Base positions should be: D=1, C=2, B=3, A=4
        self.assertEqual(d.position, 1)
        self.assertEqual(c.position, 2)
        self.assertEqual(b.position, 3)
        self.assertEqual(a.position, 4)

        b.is_used = True; b.save()
        c.is_used = True; c.save()

        # Recalculate (positions for used stay pinned; others fill around)
        SongSuggestion.objects.recalculate_positions()
        a.refresh_from_db(); b.refresh_from_db(); c.refresh_from_db(); d.refresh_from_db()

        self.assertEqual(d.position, 1)
        self.assertEqual(c.position, 2)
        self.assertEqual(b.position, 3)
        self.assertEqual(a.position, 4)

    def test_get_suggested_songs_calls_recalculate_positions(self):
        # Build a full scenario with votes and used items (no manual position setting)
        suggester, v1, v2, v3, v4, v5 = create_singers(6)

        # Control recency; B, C, D, then A
        with freeze_time(auto_tick_seconds=1) as frozen:
            b = SongSuggestion.objects.create(song_name='B', musical='M', suggested_by=suggester)
            frozen.tick()
            c = SongSuggestion.objects.create(song_name='C', musical='M', suggested_by=suggester)
            frozen.tick()
            d = SongSuggestion.objects.create(song_name='D', musical='M', suggested_by=suggester)
            frozen.tick()
            a = SongSuggestion.objects.create(song_name='A', musical='M', suggested_by=suggester)

        # Votes base rank: D(4), C(3), B(2), A(1)
        a.voters.set([v1])
        b.voters.set([v1, v2])
        c.voters.set([v1, v2, v3])
        d.voters.set([v1, v2, v3, v4])

        SongSuggestion.objects.recalculate_positions()
        a.refresh_from_db(); b.refresh_from_db(); c.refresh_from_db(); d.refresh_from_db()
        # Mark B and C as used at their current slots (3 and 2 respectively)
        b.is_used = True; b.save()
        c.is_used = True; c.save()

        # Change votes significantly: make A the top by adding voters
        a.voters.add(v2, v3, v4, v5)

        # Now expected order after fetching suggestions: A(1), C(2 pinned), B(3 pinned), D(4)
        response = self.client.get(reverse('get_suggested_songs'))
        self.assertEqual(response.status_code, 200)
        names_in_order = [item['song_name'] for item in response.data]
        self.assertEqual(names_in_order, ['A', 'C', 'B', 'D'])

    def test_used_locked_after_multiple_vote_changes(self):
        # Create five suggestions and pin middle two by marking used
        suggester, v1, v2, v3, v4, v5, v6 = create_singers(7)
        with freeze_time(auto_tick_seconds=1) as frozen:
            s1 = SongSuggestion.objects.create(song_name='S1', musical='M', suggested_by=suggester)
            frozen.tick()
            s2 = SongSuggestion.objects.create(song_name='S2', musical='M', suggested_by=suggester)
            frozen.tick()
            s3 = SongSuggestion.objects.create(song_name='S3', musical='M', suggested_by=suggester)
            frozen.tick()
            s4 = SongSuggestion.objects.create(song_name='S4', musical='M', suggested_by=suggester)
            frozen.tick()
            s5 = SongSuggestion.objects.create(song_name='S5', musical='M', suggested_by=suggester)

        # Base votes: S5(5), S4(4), S3(3), S2(2), S1(1)
        s1.voters.set([v1])
        s2.voters.set([v1, v2])
        s3.voters.set([v1, v2, v3])
        s4.voters.set([v1, v2, v3, v4])
        s5.voters.set([v1, v2, v3, v4, v5])

        SongSuggestion.objects.recalculate_positions()
        s1.refresh_from_db(); s2.refresh_from_db(); s3.refresh_from_db(); s4.refresh_from_db(); s5.refresh_from_db()
        # Pin S3 and S2 at their current slots (3 and 4 or 2 and 4 depending on tie-breaks); assert now
        self.assertEqual(s5.position, 1)
        self.assertEqual(s4.position, 2)
        self.assertEqual(s3.position, 3)
        self.assertEqual(s2.position, 4)
        self.assertEqual(s1.position, 5)

        s3.is_used = True; s3.save()
        s2.is_used = True; s2.save()

        # Round 1 vote changes: make S1 very popular, reduce S5 popularity relative by adding to others
        s1.voters.add(v2, v3, v4, v5, v6)  # S1 now top
        s4.voters.add(v5)

        SongSuggestion.objects.recalculate_positions()
        s1.refresh_from_db(); s2.refresh_from_db(); s3.refresh_from_db(); s4.refresh_from_db(); s5.refresh_from_db()

        # Used S3 and S2 should remain at 3 and 4; others move around them
        self.assertEqual(s3.position, 3)
        self.assertEqual(s2.position, 4)
        # S1 should now be 1; S4 or S5 fill remaining slot 2/5 based on votes/time
        self.assertEqual(s1.position, 1)
        self.assertIn(s4.position, (2, 5))
        self.assertIn(s5.position, (2, 5))

    def test_add_song_request_does_not_recalculate_positions_directly(self):
        singer = login_singer(self, user_id=1)
        # Pre-create suggestion that will be marked as used by add_song_request
        SongSuggestion.objects.create(song_name='Defying Gravity', musical='Wicked', suggested_by=singer)

        with patch('song_signup.views.SongSuggestion.objects.recalculate_positions') as recalc:
            # Add a matching song request
            response = self.client.post(reverse('add_song_request'), {
                'song-name': ["defying gravity"],
                'musical': ['wicked'],
                'notes': ['']
            })
            self.assertEqual(response.status_code, 200)
            # View should not call recalc here; calculation happens when fetching suggestions
            recalc.assert_not_called()

        # Now fetching suggestions should call recalc
        with patch('song_signup.views.SongSuggestion.objects.recalculate_positions') as recalc:
            response = self.client.get(reverse('get_suggested_songs'))
            self.assertEqual(response.status_code, 200)
            recalc.assert_called_once()

    def test_delete_song_then_fetch_suggestions(self):
        # Create a suggestion and matching request
        singer = login_singer(self, user_id=1)
        SongSuggestion.objects.create(song_name='A', musical='M', suggested_by=singer)
        song = SongRequest.objects.create(song_name='A', musical='M', singer=singer)
        SongSuggestion.objects.check_used_suggestions()

        # Deleting a song should succeed
        response = self.client.post(reverse('delete_song', args=[song.id]))
        self.assertEqual(response.status_code, 200)

        # Fetching suggestions should succeed and reflect current ordering (implicitly recalculated by the view)
        response = self.client.get(reverse('get_suggested_songs'))
        self.assertEqual(response.status_code, 200)
