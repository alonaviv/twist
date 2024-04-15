from django.core.management.base import BaseCommand
from song_signup.models import SongRequest, Singer, CurrentGroupSong, GroupSongRequest


class Command(BaseCommand):
    help = 'Removes all non superusers and all song requests from the database'

    def handle(self, *args, **options):
        SongRequest.objects.all().delete()
        Singer.objects.filter(is_superuser=False).delete()
        # Leave only our permanent group songs. If a group song was changed to one of our types (adding to the
        # permanent group, it does so without the original suggestor).
        CurrentGroupSong.objects.all().delete()
        GroupSongRequest.objects.filter(type='USER').delete()
        GroupSongRequest.objects.update(suggested_by='-', performance_time=None)
