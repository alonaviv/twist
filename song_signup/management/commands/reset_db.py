from django.core.management.base import BaseCommand
from song_signup.models import (SongRequest, Singer, CurrentGroupSong, GroupSongRequest, Celebration,
                                FilmingOptOut)


class Command(BaseCommand):
    help = ('Removes all non superusers and all song requests from the database. '
            'People who asked not to be filmed are recorded in FilmingOptOut first.')

    def handle(self, *args, **options):
        num_opt_outs = FilmingOptOut.snapshot()
        self.stdout.write(f"Recorded {num_opt_outs} filming opt-out(s)")

        SongRequest.objects.all().delete()
        Singer.objects.filter(is_superuser=False).delete()
        # Leave only our permanent group songs. If a group song was changed to one of our types (adding to the
        # permanent group, it does so without the original suggestor).
        CurrentGroupSong.objects.all().delete()
        GroupSongRequest.objects.filter(type='USER').delete()
        GroupSongRequest.objects.update(suggested_by='-', performance_time=None)
        Celebration.objects.all().delete()
