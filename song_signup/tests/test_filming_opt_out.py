import os

from constance.test import override_config
from django.core.files import File
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from django.utils import timezone

from song_signup.models import Singer, SongRequest, FilmingOptOut, SING_SKU, ATTN_SKU
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


class TestFilmingOptOutSnapshot(TestCase):
    def setUp(self):
        self.singer_order = create_order(3, SING_SKU, order_id=1111)
        self.audience_order = create_order(2, ATTN_SKU, order_id=2222)

    def tearDown(self):
        # Clean up whichever selfie files tests actually created; FilmingOptOut.photo points at the same
        # files rather than owning separate ones, so deleting via Singer (where it still exists) is enough.
        for singer in Singer.objects.all():
            if singer.selfie:
                singer.selfie.delete(save=False)
        for opt_out in FilmingOptOut.objects.all():
            if opt_out.photo and os.path.exists(opt_out.photo.path):
                opt_out.photo.delete(save=False)

    @override_config(EVENT_SKU='EVT123', PEOPLES_CHOICE_EVENT_DATE='21.9.25')
    def test_reset_records_opt_outs_pointing_at_the_original_selfie(self):
        opted_out_singer = _create_person('Opted Singer', self.singer_order, opt_out=True, with_selfie=True)
        original_selfie_name = opted_out_singer.selfie.name
        _create_person('Happy Singer', self.singer_order, with_selfie=True)
        _create_person('Opted Audience', self.audience_order, is_audience=True, opt_out=True)

        call_command('reset_db')

        self.assertFalse(Singer.objects.filter(is_superuser=False).exists())
        self.assertEqual(FilmingOptOut.objects.count(), 2)

        singer_record = FilmingOptOut.objects.get(full_name='Opted Singer')
        self.assertFalse(singer_record.is_audience)
        self.assertEqual(singer_record.event_date, '21.9.25')
        self.assertEqual(singer_record.event_sku, 'EVT123')
        # Same underlying file, not a copy - the Singer row is gone but the file on disk isn't.
        self.assertEqual(singer_record.photo.name, original_selfie_name)
        self.assertTrue(os.path.exists(singer_record.photo.path))

        audience_record = FilmingOptOut.objects.get(full_name='Opted Audience')
        self.assertTrue(audience_record.is_audience)
        self.assertFalse(audience_record.photo)

        self.assertFalse(FilmingOptOut.objects.filter(full_name='Happy Singer').exists())

    @override_config(EVENT_SKU='EVT123', PEOPLES_CHOICE_EVENT_DATE='21.9.25')
    def test_songs_performed_lists_both_own_and_partner_songs_in_order(self):
        opted_out_singer = _create_person('Opted Singer', self.singer_order, opt_out=True)
        other_singer = _create_person('Other Singer', self.singer_order)

        second_song = SongRequest.objects.create(
            song_name='Second Song', musical='Hamilton', singer=opted_out_singer,
            performance_time=timezone.now()
        )
        first_song = SongRequest.objects.create(
            song_name='First Song', musical='Wicked', singer=opted_out_singer,
            performance_time=timezone.now() - timezone.timedelta(minutes=30)
        )
        partner_song = SongRequest.objects.create(
            song_name='Partner Song', musical='Rent', singer=other_singer,
            performance_time=timezone.now() - timezone.timedelta(minutes=15)
        )
        partner_song.partners.add(opted_out_singer)
        # Not performed yet - should not show up.
        SongRequest.objects.create(song_name='Unsung Song', musical='Cats', singer=opted_out_singer)

        call_command('reset_db')

        record = FilmingOptOut.objects.get(full_name='Opted Singer')
        self.assertEqual(
            record.songs_performed,
            'First Song (Wicked); Partner Song (Rent); Second Song (Hamilton)'
        )

    @override_config(PEOPLES_CHOICE_EVENT_DATE='21.9.25')
    def test_songs_performed_blank_when_nothing_was_performed(self):
        _create_person('Opted Singer', self.singer_order, opt_out=True)
        call_command('reset_db')
        record = FilmingOptOut.objects.get(full_name='Opted Singer')
        self.assertEqual(record.songs_performed, '')

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
