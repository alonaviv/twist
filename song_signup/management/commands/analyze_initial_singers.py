"""
Django management command to process database backup files:
1. Remove SET transaction_timeout = 0; line from psql file
2. Load the database using dbrestore
3. Count group songs and raffled songs performed that evening
4. Output results to a file
"""

import os
import subprocess
import pytz
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.db.models import Q, Exists, OuterRef
from django.db.models.functions import Extract
from song_signup.models import GroupSongRequest, SongRequest, Singer


class Command(BaseCommand):
    help = 'Process a database backup file and analyze group songs and raffled songs performed'

    def add_arguments(self, parser):
        parser.add_argument(
            'filepath',
            type=str,
            help='Path to the .psql backup file to process'
        )

    def remove_transaction_timeout(self, filepath):
        """Remove SET transaction_timeout = 0; line from psql file if it exists."""
        subprocess.run(
            ['sed', '-i', '/SET transaction_timeout = 0;/d', filepath],
            check=True
        )

    def load_database(self, filepath):
        """Load database using dbrestore command, bypassing confirmation."""
        process = subprocess.Popen(
            ['./manage.py', 'dbrestore', '-I', filepath],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        stdout, stderr = process.communicate(input='yes\n')
        
        if process.returncode != 0:
            raise Exception(f"Failed to load database: {stderr}")
        
        # Run migrations to ensure schema matches current code
        subprocess.run(['./manage.py', 'migrate'], check=True)

    def get_event_date(self, filepath):
        """Extract event date from filename (format: bwt-M-D-YY.psql)."""
        filename = os.path.basename(filepath)
        # Remove .psql extension and extract date part after 'bwt-'
        date_part = filename.replace('.psql', '').replace('bwt-', '')
        return date_part

    def count_performed_songs(self):
        """Count group songs and raffled songs that were performed (have performance_time)."""
        # Count group songs performed
        group_songs_count = GroupSongRequest.objects.filter(
            performance_time__isnull=False
        ).count()
        
        # Count raffled songs performed (songs performed by raffle winners)
        raffled_songs_count = SongRequest.objects.filter(
            performance_time__isnull=False,
            singer__raffle_winner=True
        ).count()
        
        return group_songs_count, raffled_songs_count

    def count_early_signups(self):
        """Count singers whose initial signup time (date_joined) is before the first request_time."""
        israel_tz = pytz.timezone('Israel')
        
        # Find the first request_time (cutoff time)
        first_request = SongRequest.objects.filter(
            placeholder=False,
            request_time__isnull=False,
            singer__isnull=False
        ).order_by('request_time').first()
        
        if not first_request:
            return 0, None
        
        cutoff_time = first_request.request_time
        
        # Get all singers and check their initial signup time (date_joined)
        all_singers = Singer.objects.filter(
            songs__placeholder=False,
            songs__request_time__isnull=False
        ).distinct()
        
        early_singer_data = []
        
        for singer in all_singers:
            # Use singer's date_joined as initial_signup
            initial_signup = singer.date_joined
            if initial_signup and initial_signup <= cutoff_time:
                initial_signup_israel = initial_signup.astimezone(israel_tz)
                early_singer_data.append((initial_signup, singer, initial_signup_israel))
        
        early_signups = len(early_singer_data)
        
        # Find the singer whose first song's performance_time was the latest
        # Only consider singers whose first song's request_time is within 10 minutes of cutoff
        # Exclude raffle winners
        request_cutoff = cutoff_time + timedelta(minutes=10)
        valid_performance_times = []
        
        for initial_signup, singer, initial_signup_israel in early_singer_data:
            # Skip raffle winners
            if singer.raffle_winner:
                continue
                
            # Find singer's first song by performance_time (earliest performed)
            first_song = singer.songs.filter(
                performance_time__isnull=False
            ).order_by('performance_time').first()
            
            if first_song and first_song.request_time and first_song.request_time <= request_cutoff:
                # Only consider if request_time is within 10 minutes of cutoff
                if first_song.performance_time:
                    valid_performance_times.append(first_song.performance_time)
        
        # Get the latest (maximum) performance_time
        latest_first_performance = max(valid_performance_times) if valid_performance_times else None
        
        if latest_first_performance:
            latest_performance_israel = latest_first_performance.astimezone(israel_tz)
            latest_time_str = latest_performance_israel.strftime('%H:%M')
        else:
            latest_time_str = None
        
        return early_signups, latest_time_str

    def handle(self, *args, **options):
        filepath = options['filepath']
        
        # Step 1: Remove SET transaction_timeout line
        self.remove_transaction_timeout(filepath)
        
        # Step 2: Load database
        self.load_database(filepath)
        
        # Step 3: Get event date and count songs
        event_date = self.get_event_date(filepath)
        group_songs_count, raffled_songs_count = self.count_performed_songs()
        early_signups_count, latest_first_performance_time = self.count_early_signups()
        
        # Step 4: Create results
        results = {
            'file': os.path.basename(filepath),
            'event_date': event_date,
            'group_songs_performed': group_songs_count,
            'raffled_songs_performed': raffled_songs_count,
            'early_signups': early_signups_count,
            'latest_first_performance_time': latest_first_performance_time,
        }
        
        # Print summary
        print(f"\nResults:")
        print(f"  Event Date: {event_date}")
        print(f"  Singers with Initial Signup Before First Request: {early_signups_count}")
        print(f"  Latest First Song Performance Time: {latest_first_performance_time or 'N/A'}")
        print(f"  Group Songs Performed: {group_songs_count}")
        print(f"  Raffled Songs Performed: {raffled_songs_count}")
        
        # Write to file (append mode)
        output_file = 'analysis_results.txt'
        with open(output_file, 'a') as f:
            f.write(f"\n{'='*60}\n")
            f.write(f"Event Date: {event_date}\n")
            f.write(f"File: {os.path.basename(filepath)}\n")
            f.write(f"{'='*60}\n")
            f.write(f"Singers with Initial Signup Before First Request: {early_signups_count}\n")
            f.write(f"Latest First Song Performance Time: {latest_first_performance_time or 'N/A'}\n")
            f.write(f"Group Songs Performed: {group_songs_count}\n")
            f.write(f"Raffled Songs Performed: {raffled_songs_count}\n")

