from django.core.management.base import BaseCommand
from song_signup.models import SongRequest
from django.contrib.auth.models import User


class Command(BaseCommand):
    help = 'Removes all non superusers and all song requests from the database'

    def handle(self, *args, **options):
        SongRequest.objects.all().delete()
        User.objects.filter(is_superuser=False).delete()
