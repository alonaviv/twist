import csv
from django.core.management.base import BaseCommand
from song_signup.models import GroupSongRequest

DEFAULT_PATH = '/twist/group-songs.csv'

class Command(BaseCommand):
    help = "Add group songs from a csv file"

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, default=DEFAULT_PATH, nargs='?')

    def handle(self, *args, **options):
        with open(options['csv_file'], mode='r') as f:
            reader = csv.reader(f)
            next(reader, None)  # Skip the headers

            for song in reader:
                song_name, musical, song_type = song
                GroupSongRequest.objects.update_or_create(song_name=song_name,
                                                          musical=musical,
                                                          type=song_type)
