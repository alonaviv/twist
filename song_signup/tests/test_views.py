from django.test import TestCase, Client
from django.urls import reverse
from constance.test import override_config
from song_signup.tests.test_utils import (
    create_temp_singer,
    EVENT_SKU,
    PASSCODE,
    create_order,
    get_temp_singer
)
from song_signup.views import AUDIENCE_SESSION
from song_signup.models import Singer, TicketOrder

evening_started = override_config(PASSCODE=PASSCODE, EVENT_SKU=EVENT_SKU)


@evening_started
class TestLogin(TestCase):
    def _assert_user_error(self, response, msg=None):
        if not msg:
            msg = "An unexpected error occurred (you can blame Alon..) Refreshing the page might help"
        self.assertEqual(response.status_code, 400)
        self.assertJSONEqual(str(response.content, encoding='utf8'),
                             {
                                 'error': msg
                             })

    def test_singer_redirect(self):
        temp_singer = create_temp_singer()
        self.client.force_login(temp_singer)

        response = self.client.get(reverse('login'))
        self.assertRedirects(response, reverse('home'))

    def test_audience_redirect(self):
        session = self.client.session
        session[AUDIENCE_SESSION] = True
        session.save()
        response = self.client.get(reverse('login'))
        self.assertRedirects(response, reverse('home'))

    def test_not_logged_in(self):
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'song_signup/login.html')

    def test_invalid_ticket_type(self):
        response = self.client.post(reverse('login'), {'ticket-type': 'unexpected_error'})
        self._assert_user_error(response)

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
        create_temp_singer(order)

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
        create_temp_singer(order)
        create_temp_singer(order)

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
        temp_singer = create_temp_singer()
        temp_singer.is_active = False
        temp_singer.save()

        self.client.force_login(temp_singer)

        response = self.client.post(reverse('login'), {
            'ticket-type': ['singer'],
            'first-name': [temp_singer.first_name],
            'last-name': [temp_singer.last_name],
            'passcode': [PASSCODE],
            'order-id': [temp_singer.ticket_order.order_id],
            'logged-in': ['on']
        })
        self.assertRedirects(response, reverse('home'))
        self.assertTrue(get_temp_singer(temp_singer).is_active)


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
