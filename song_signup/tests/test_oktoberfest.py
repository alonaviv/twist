from constance.test import override_config
from django.test import TestCase
from django.urls import reverse
from flags.state import flag_enabled

from song_signup.models import Singer


# Constance reads the dev Redis, so each test sets OKTOBERFEST rather than relying on its default.
@override_config(OKTOBERFEST=False)
class TestOktoberfest(TestCase):
    def setUp(self):
        self.admin = Singer.objects.create_superuser(username='admin', password='admin')
        self.client.force_login(self.admin)

    def _oktoberfest_started(self):
        return self.client.get(reverse('oktoberfest_started')).json()['oktoberfest']

    def _admin_page(self):
        return self.client.get('/admin/song_signup/songrequest/').content.decode()

    def test_off(self):
        self.assertNotIn('Start Oktoberfest', self._admin_page())
        self.assertFalse(self._oktoberfest_started())

    @override_config(OKTOBERFEST=True)
    def test_toggle(self):
        self.assertIn('Start Oktoberfest', self._admin_page())

        self.client.get(reverse('start_oktoberfest'))
        self.assertTrue(self._oktoberfest_started())
        self.assertIn('Stop Oktoberfest', self._admin_page())

        self.client.get(reverse('stop_oktoberfest'))
        self.assertFalse(self._oktoberfest_started())
        self.assertIn('Start Oktoberfest', self._admin_page())

    def test_flag_left_on_is_ignored_when_config_is_off(self):
        with override_config(OKTOBERFEST=True):
            self.client.get(reverse('start_oktoberfest'))
        self.assertTrue(flag_enabled('OKTOBERFEST'))
        self.assertFalse(self._oktoberfest_started())

    def test_toggle_requires_superuser(self):
        self.client.logout()
        self.client.get(reverse('start_oktoberfest'))
        self.assertFalse(flag_enabled('OKTOBERFEST'))

    def test_logos(self):
        self.assertNotIn('logo-oktoberfest.png', self._admin_page())
        self.assertNotIn('logo-oktoberfest.png', self.client.get(reverse('live_lyrics')).content.decode())

        with override_config(OKTOBERFEST=True):
            live_lyrics = self.client.get(reverse('live_lyrics')).content.decode()
        self.assertIn('data-big-logo="/static//img/logo-oktoberfest.png"', live_lyrics)
        self.assertIn('data-small-logo="/static//img/logo-oktoberfest.png"', live_lyrics)
        self.assertNotIn('logo-ai.png', live_lyrics)
