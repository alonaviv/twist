import filecmp
import os

from constance.test import override_config
from django.core.files import File
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from song_signup.models import (
    Singer, FilmingOptOut, SING_SKU, ATTN_SKU, event_date_slug, filming_opt_out_photo_path
)
from song_signup.tests.utils_for_tests import create_order

TEST_IMG_PATH = 'song_signup/tests/test_img.png'


def _create_person(name, order, is_audience=False, opt_out=False, with_selfie=False):
    kwargs = dict(
        username=name.lower().replace(' ', '_'),
        first_name=name.split()[0],
        last_name=name.split()[1],
        ticket_order=order,
        is_audience=is_audience,
        no_image_upload=opt_out,
    )
    if with_selfie:
        with open(TEST_IMG_PATH, 'rb') as image:
            kwargs['selfie'] = File(image, name=f'{kwargs["username"]}.png')
            return Singer.objects.create_user(**kwargs)
    return Singer.objects.create_user(**kwargs)


class TestEventDateSlug(TestCase):
    def test_slug_from_plain_date(self):
        self.assertEqual(event_date_slug('21.9.25'), '21-9-25')
        self.assertEqual(event_date_slug(''), 'unknown-event')
        self.assertEqual(event_date_slug(None), 'unknown-event')

    def test_slug_tolerates_a_compound_name(self):
        # Not the normal input anymore (config.PEOPLES_CHOICE_EVENT_DATE is just the date), but harmless if given one.
        self.assertEqual(event_date_slug('Open Mic - Babu Bar - 21.9.25'), '21-9-25')

    def test_photo_path_uses_event_folder(self):
        opt_out = FilmingOptOut(full_name='A B', event_date='21.9.25')
        self.assertEqual(filming_opt_out_photo_path(opt_out, '/tmp/selfies/a_b.png'),
                         os.path.join('no_filming', '21-9-25', 'a_b.png'))


class TestFilmingOptOutSnapshot(TestCase):
    def setUp(self):
        self.singer_order = create_order(3, SING_SKU, order_id=1111)
        self.audience_order = create_order(2, ATTN_SKU, order_id=2222)

    def tearDown(self):
        for opt_out in FilmingOptOut.objects.all():
            if opt_out.photo:
                opt_out.photo.delete(save=False)
        for singer in Singer.objects.all():
            if singer.selfie:
                singer.selfie.delete(save=False)

    @override_config(EVENT_SKU='EVT123', PEOPLES_CHOICE_EVENT_DATE='21.9.25')
    def test_reset_records_opt_outs_and_copies_photo(self):
        opted_out_singer = _create_person('Opted Singer', self.singer_order, opt_out=True, with_selfie=True)
        original_selfie_path = opted_out_singer.selfie.path
        _create_person('Happy Singer', self.singer_order, with_selfie=True)
        _create_person('Opted Audience', self.audience_order, is_audience=True, opt_out=True)

        call_command('reset_db')

        self.assertFalse(Singer.objects.filter(is_superuser=False).exists())
        self.assertEqual(FilmingOptOut.objects.count(), 2)

        singer_record = FilmingOptOut.objects.get(full_name='Opted Singer')
        self.assertFalse(singer_record.is_audience)
        self.assertEqual(singer_record.event_date, '21.9.25')
        self.assertEqual(singer_record.event_sku, 'EVT123')
        self.assertTrue(singer_record.photo)
        self.assertNotEqual(singer_record.photo.path, original_selfie_path)
        self.assertIn(os.path.join('no_filming', '21-9-25'), singer_record.photo.path)
        self.assertTrue(filecmp.cmp(TEST_IMG_PATH, singer_record.photo.path))

        audience_record = FilmingOptOut.objects.get(full_name='Opted Audience')
        self.assertTrue(audience_record.is_audience)
        self.assertFalse(audience_record.photo)

        self.assertFalse(FilmingOptOut.objects.filter(full_name='Happy Singer').exists())

    @override_config(PEOPLES_CHOICE_EVENT_DATE='21.9.25')
    def test_reset_without_opt_outs_records_nothing(self):
        _create_person('Happy Singer', self.singer_order, with_selfie=True)
        call_command('reset_db')
        self.assertEqual(FilmingOptOut.objects.count(), 0)

    def test_reset_refuses_and_changes_nothing_when_event_date_not_set(self):
        # PEOPLES_CHOICE_EVENT_DATE defaults to '' until someone sets it for the event.
        opted_out_singer = _create_person('Opted Singer', self.singer_order, opt_out=True)

        with self.assertRaises(CommandError):
            call_command('reset_db')

        self.assertEqual(FilmingOptOut.objects.count(), 0)
        self.assertTrue(Singer.objects.filter(pk=opted_out_singer.pk).exists())

    @override_config(PEOPLES_CHOICE_EVENT_DATE='21.9.25')
    def test_records_survive_a_second_reset(self):
        _create_person('Opted Singer', self.singer_order, opt_out=True, with_selfie=True)
        call_command('reset_db')
        photo_path = FilmingOptOut.objects.get().photo.path

        _create_person('Another Singer', self.singer_order, opt_out=True)
        call_command('reset_db')

        self.assertEqual(FilmingOptOut.objects.count(), 2)
        self.assertTrue(os.path.exists(photo_path))
