from constance.test import override_config
from django.core.management import call_command
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone
from freezegun import freeze_time

from song_signup.models import Reaction, Singer, SongRequest
from song_signup.tests.utils_for_tests import (
    add_current_group_song, add_partners, create_singers, end_group_song, get_song, login_audience,
    set_performed, set_skipped,
)


def mark_peoples_choice(singer_id, song_id=1):
    SongRequest.objects.filter(pk=get_song(singer_id, song_id).pk).update(is_peoples_choice=True)


class CoronationTestCase(TestCase):
    """
    Three singers with one song each, singer 1's song current. self.client is an audience member's phone,
    self.admin the live lyrics screen and admin page.
    """
    def setUp(self):
        create_singers(3, num_songs=1)
        self.audience = login_audience(self)
        self.admin = Client()
        self.admin.force_login(Singer.objects.create_superuser(username='admin', password='admin'))

    def coronation(self):
        return self.client.get(reverse('coronation_started')).json()['coronation']

    def reactions_open(self):
        return self.client.get(reverse('reactions_state')).json()['open']

    def send(self, emojis=None, text=None, client=None, texts=None):
        body = {'emojis': emojis or {}, 'texts': texts or ([text] if text else [])}
        return (client or self.client).post(reverse('send_reaction'), body, content_type='application/json')

    def feed(self):
        return self.admin.get(reverse('reaction_feed')).json()['reactions']

    def admin_page(self):
        return self.admin.get('/admin/song_signup/songrequest/').content.decode()

    def run_admin_action(self, action, singer_id, song_id=1):
        self.admin.post('/admin/song_signup/songrequest/',
                        {'action': action, '_selected_action': [get_song(singer_id, song_id).pk]})


class TestCoronation(CoronationTestCase):
    def test_shows_for_current_peoples_choice_song(self):
        mark_peoples_choice(1)
        coronation = self.coronation()
        self.assertEqual(coronation['singers'], 'User_1 Last_name')
        self.assertEqual(coronation['song_name'], 'Song_1_1')
        self.assertEqual(coronation['musical'], 'Wicked')
        self.assertFalse(coronation['plural'])

    def test_partners_are_plural(self):
        add_partners(1, 2, 1)
        mark_peoples_choice(1)
        coronation = self.coronation()
        self.assertEqual(coronation['singers'], 'User_1 Last_name and User_2 Last_name')
        self.assertTrue(coronation['plural'])

    def test_not_for_regular_song(self):
        mark_peoples_choice(2)
        self.assertIsNone(self.coronation())

    def test_not_during_group_song(self):
        mark_peoples_choice(1)
        add_current_group_song('Group', 'Musical')
        self.assertIsNone(self.coronation())
        end_group_song()
        self.assertIsNotNone(self.coronation())

    def test_appears_when_song_becomes_current(self):
        mark_peoples_choice(2)
        set_performed(1, 1)
        self.assertEqual(self.coronation()['singers'], 'User_2 Last_name')

    def test_spotlight_song(self):
        mark_peoples_choice(3)
        SongRequest.objects.set_spotlight(get_song(3, 1))
        self.assertEqual(self.coronation()['singers'], 'User_3 Last_name')
        self.admin.get(reverse('end_coronation'))
        self.assertIsNone(self.coronation())
        self.assertTrue(get_song(3, 1).coronation_done)

    def test_regular_spotlight_song_over_peoples_choice_song(self):
        mark_peoples_choice(1)
        SongRequest.objects.set_spotlight(get_song(3, 1))
        self.assertIsNone(self.coronation())
        self.assertFalse(self.reactions_open())

    def test_skipped_song(self):
        mark_peoples_choice(1)
        mark_peoples_choice(2)
        set_skipped(1, 1)
        self.assertEqual(self.coronation()['singers'], 'User_2 Last_name')

    def test_end_coronation(self):
        mark_peoples_choice(1)
        mark_peoples_choice(2)
        self.admin.get(reverse('end_coronation'))
        self.assertIsNone(self.coronation())
        self.assertTrue(get_song(1, 1).coronation_done)
        self.assertFalse(get_song(2, 1).coronation_done)

    def test_ended_coronation_does_not_return(self):
        mark_peoples_choice(1)
        self.admin.get(reverse('end_coronation'))
        self.run_admin_action('unset_peoples_choice', 1)
        self.run_admin_action('set_peoples_choice', 1)
        self.assertIsNone(self.coronation())
        self.assertTrue(self.reactions_open())

    def test_end_coronation_requires_superuser(self):
        mark_peoples_choice(1)
        self.client.get(reverse('end_coronation'))
        self.assertIsNotNone(self.coronation())

    def test_admin_button_only_while_showing(self):
        self.assertNotIn('End Coronation', self.admin_page())
        mark_peoples_choice(1)
        self.assertIn('End Coronation', self.admin_page())
        self.admin.get(reverse('end_coronation'))
        self.assertNotIn('End Coronation', self.admin_page())


class TestMarking(CoronationTestCase):
    def test_mark_and_unmark(self):
        self.run_admin_action('set_peoples_choice', 1)
        self.assertIsNotNone(self.coronation())
        self.assertTrue(self.reactions_open())

        self.run_admin_action('unset_peoples_choice', 1)
        self.assertIsNone(self.coronation())
        self.assertFalse(self.reactions_open())

    def test_marking_changes_nothing_else(self):
        def other_fields():
            values = SongRequest.objects.filter(pk=get_song(1, 1).pk).values().get()
            del values['is_peoples_choice']
            return values

        before = other_fields()
        self.run_admin_action('set_peoples_choice', 1)
        self.assertTrue(get_song(1, 1).is_peoples_choice)
        self.assertEqual(other_fields(), before)
        self.run_admin_action('unset_peoples_choice', 1)
        self.assertFalse(get_song(1, 1).is_peoples_choice)
        self.assertEqual(other_fields(), before)


class TestReactionsState(CoronationTestCase):
    def test_closed_for_regular_song(self):
        self.assertFalse(self.reactions_open())

    def test_closed_during_group_song(self):
        mark_peoples_choice(1)
        add_current_group_song('Group', 'Musical')
        self.assertFalse(self.reactions_open())

    def test_open_through_coronation_and_song(self):
        mark_peoples_choice(1)
        self.assertTrue(self.reactions_open())
        self.admin.get(reverse('end_coronation'))
        self.assertTrue(self.reactions_open())
        set_performed(1, 1)
        self.assertFalse(self.reactions_open())


class TestSendReaction(CoronationTestCase):
    def test_emojis_saved_one_row_each(self):
        mark_peoples_choice(1)
        self.send(emojis={'👏': 3, '🔥': 1})
        reactions = Reaction.objects.filter(song=get_song(1, 1), user=self.audience)
        self.assertEqual(sorted(r.emoji for r in reactions), ['👏', '👏', '👏', '🔥'])

    def test_ignored_without_peoples_choice_song(self):
        self.assertEqual(self.send(emojis={'👏': 2}, text='hi').status_code, 200)
        mark_peoples_choice(1)
        add_current_group_song('Group', 'Musical')
        self.send(emojis={'👏': 2}, text='hi')
        self.assertFalse(Reaction.objects.exists())

    def test_emojis_and_text_in_one_batch(self):
        mark_peoples_choice(1)
        self.send(emojis={'💖': 1}, text='Bravo')
        self.assertEqual(Reaction.objects.filter(emoji='💖').count(), 1)
        self.assertEqual(Reaction.objects.filter(text='Bravo').count(), 1)

    def test_html_text_comes_back_as_is(self):
        mark_peoples_choice(1)
        self.send(text='<img src=x onerror=alert(1)>')
        self.assertEqual(self.feed(), [{'content': '<img src=x onerror=alert(1)>', 'is_text': True}])

    def test_every_text_is_saved(self):
        mark_peoples_choice(1)
        self.send(texts=['first', 'second'])
        self.send(text='third')
        self.assertEqual(sorted(Reaction.objects.values_list('text', flat=True)), ['first', 'second', 'third'])

    def test_requires_login(self):
        mark_peoples_choice(1)
        Client().post(reverse('send_reaction'), {'emojis': {'👏': 1}}, content_type='application/json')
        self.assertFalse(Reaction.objects.exists())


class TestReactionFeed(CoronationTestCase):
    def test_each_reaction_shown_once_oldest_first(self):
        mark_peoples_choice(1)
        with freeze_time(timezone.now()) as frozen_time:
            self.send(emojis={'👏': 1})
            frozen_time.tick(1)
            self.send(text='hello')
            self.assertEqual(self.feed(), [{'content': '👏', 'is_text': False}, {'content': 'hello', 'is_text': True}])
            self.assertEqual(self.feed(), [])
        self.assertFalse(Reaction.objects.filter(displayed_at__isnull=True).exists())

    def test_at_most_30_per_poll(self):
        mark_peoples_choice(1)
        self.send(emojis={'👏': 35})
        self.assertEqual(len(self.feed()), 30)
        self.assertEqual(len(self.feed()), 5)

    def test_older_than_10_seconds_never_shown(self):
        mark_peoples_choice(1)
        with freeze_time(timezone.now()) as frozen_time:
            self.send(emojis={'👏': 1})
            frozen_time.tick(11)
            self.assertEqual(self.feed(), [])

    def test_previous_song_never_shown(self):
        mark_peoples_choice(1)
        mark_peoples_choice(2)
        self.send(emojis={'👏': 1})
        set_performed(1, 1)
        self.assertEqual(self.feed(), [])

    def test_requires_superuser(self):
        mark_peoples_choice(1)
        self.send(emojis={'👏': 1})
        self.client.get(reverse('reaction_feed'))
        self.assertTrue(Reaction.objects.filter(displayed_at__isnull=True).exists())


class TestReactionAdmin(CoronationTestCase):
    def setUp(self):
        super().setUp()
        mark_peoples_choice(1)
        self.send(emojis={'👏': 1}, text='first song')
        set_performed(1, 1)
        mark_peoples_choice(2)
        self.send(text='second song')

    def test_filters(self):
        url = '/admin/song_signup/reaction/'
        page = self.admin.get(url).content.decode()
        self.assertIn('first song', page)
        self.assertIn('second song', page)

        page = self.admin.get(url, {'song__id__exact': get_song(2, 1).pk}).content.decode()
        self.assertNotIn('first song', page)
        self.assertIn('second song', page)

        page = self.admin.get(url, {'type': 'texts'}).content.decode()
        self.assertNotIn('👏', page)
        self.assertIn('first song', page)


class TestReset(CoronationTestCase):
    @override_config(PEOPLES_CHOICE_EVENT_DATE='1.1.26')
    def test_reset_removes_reactions(self):
        mark_peoples_choice(1)
        self.send(emojis={'👏': 2}, text='hi')
        call_command('reset_db')
        self.assertFalse(Reaction.objects.exists())


class TestNothingLive(TestCase):
    """
    The live lyrics screen polls coronation_started and reaction_feed every second all evening, inside the loop that
    updates the lyrics, so they must answer cleanly in every state, including when nothing is current.
    """
    def setUp(self):
        self.admin = Client()
        self.admin.force_login(Singer.objects.create_superuser(username='admin', password='admin'))

    def assert_nothing_live(self):
        for client in (self.admin, self.client):
            self.assertEqual(client.get(reverse('coronation_started')).json(), {'coronation': None})
            self.assertEqual(client.get(reverse('reactions_state')).json(), {'open': False})
        self.assertEqual(self.admin.get(reverse('reaction_feed')).json(), {'reactions': []})

    def test_empty_evening(self):
        self.assert_nothing_live()

    def test_singers_without_songs(self):
        create_singers(3)
        self.assert_nothing_live()

    def test_regular_song(self):
        create_singers(3, num_songs=1)
        self.assert_nothing_live()

    def test_everything_performed(self):
        create_singers(2, num_songs=1)
        mark_peoples_choice(1)
        mark_peoples_choice(2)
        set_performed(1, 1)
        set_performed(2, 1)
        self.assert_nothing_live()

    def test_everything_skipped(self):
        create_singers(2, num_songs=1)
        mark_peoples_choice(1)
        mark_peoples_choice(2)
        set_skipped(1, 1)
        set_skipped(2, 1)
        self.assert_nothing_live()

    def test_group_song_with_empty_lineup(self):
        add_current_group_song('Group', 'Musical')
        self.assert_nothing_live()
        end_group_song()
        self.assert_nothing_live()

    def test_end_coronation_with_nothing_current(self):
        self.assertEqual(self.admin.get(reverse('end_coronation')).status_code, 302)
        self.assert_nothing_live()

    def test_send_reaction_with_nothing_current(self):
        login_audience(self)
        response = self.client.post(reverse('send_reaction'), {'emojis': {'👏': 1}, 'texts': ['hi']},
                                    content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Reaction.objects.exists())
        self.assert_nothing_live()
