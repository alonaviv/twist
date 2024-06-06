# Make sure to load the DB that you want to export from

import csv
from django.core.management.base import BaseCommand
from django.conf import settings
from song_signup.models import SongRequest, GroupSongRequest
from pathlib import Path

class Command(BaseCommand):
    help = 'Export all performed songs to CSV'

    def add_arguments(self, parser):
        parser.add_argument('filename', type=str, help='The CSV file name to export to')

    def handle(self, *args, **kwargs):
        filename = kwargs['filename']
        file_path = Path(settings.BASE_DIR) / Path('song_lists') / Path(filename)

        with open(file_path, mode='w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(['', 'Singers', 'Song', 'Musical'])

            songs = SongRequest.objects.filter(performance_time__isnull=False).order_by('performance_time')
            group_songs = GroupSongRequest.objects.filter(performance_time__isnull=False).order_by('performance_time')

            all_songs = sorted(
                list(songs) + list(group_songs),
                key=lambda x: x.performance_time
            )

            for i, song in enumerate(all_songs, start=1):
                if isinstance(song, SongRequest):
                    singer = song.singer.get_full_name()
                    if song.duet_partner:
                        dueter = song.duet_partner.get_full_name()
                        singer += f" and {dueter}"
                    writer.writerow([i, singer, song.song_name, song.musical])
                elif isinstance(song, GroupSongRequest):
                    writer.writerow([i, 'Group Song', song.song_name, song.musical])

        self.stdout.write(self.style.SUCCESS(f'Successfully exported performed songs to {file_path}'))
