from django.core.management.base import BaseCommand
from song_signup.models import SongRequest


class Command(BaseCommand):
    help = 'Removes all song requests from the database'

    def handle(self, *args, **options):
        SongRequest.objects.all().delete()
