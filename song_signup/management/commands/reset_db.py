from django.core.files.base import File
from django.core.management.base import BaseCommand, CommandError
from constance import config

from song_signup.models import (SongRequest, Singer, CurrentGroupSong, GroupSongRequest, Celebration,
                                FilmingOptOut)


class Command(BaseCommand):
    help = ('Removes all non superusers and all song requests from the database. '
            'People who asked not to be filmed are recorded in FilmingOptOut first. '
            "Refuses to run if PEOPLES_CHOICE_EVENT_DATE isn't set.")

    def handle(self, *args, **options):
        event_date = getattr(config, 'PEOPLES_CHOICE_EVENT_DATE', '') or ''
        if not event_date:
            raise CommandError(
                "PEOPLES_CHOICE_EVENT_DATE is not set in config. Set it (e.g. '21.9.25') before resetting - "
                "it's needed to file tonight's filming opt-outs under the right event. Nothing was reset."
            )

        self._record_filming_opt_outs(event_date)

        SongRequest.objects.all().delete()
        Singer.objects.filter(is_superuser=False).delete()
        # Leave only our permanent group songs. If a group song was changed to one of our types (adding to the
        # permanent group, it does so without the original suggestor).
        CurrentGroupSong.objects.all().delete()
        GroupSongRequest.objects.filter(type='USER').delete()
        GroupSongRequest.objects.update(suggested_by='-', performance_time=None)
        Celebration.objects.all().delete()

    def _record_filming_opt_outs(self, event_date):
        event_sku = getattr(config, 'EVENT_SKU', '') or ''

        num_recorded = 0
        for singer in Singer.objects.filter(is_superuser=False, no_image_upload=True).order_by('id'):
            opt_out = FilmingOptOut(
                full_name=singer.get_full_name() or singer.username,
                is_audience=singer.is_audience,
                event_date=event_date,
                event_sku=event_sku,
                phone_number=singer.ticket_order.phone_number if singer.ticket_order else None,
            )
            if singer.selfie:
                try:
                    with singer.selfie.open('rb') as selfie_file:
                        opt_out.photo.save(singer.selfie.name.rsplit('/', 1)[-1], File(selfie_file), save=False)
                except (FileNotFoundError, ValueError):
                    self.stderr.write(f"Selfie file missing for {opt_out.full_name}; "
                                      f"recording opt-out without a photo")
            opt_out.save()
            num_recorded += 1

        self.stdout.write(f"Recorded {num_recorded} filming opt-out(s)")
