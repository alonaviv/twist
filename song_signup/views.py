import logging
from datetime import datetime, timezone

from django.contrib import messages
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.models import User, Group
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.http import HttpResponseRedirect, JsonResponse, HttpResponse
from django.shortcuts import render, redirect
from django.core.management import call_command
from numpy import blackman

from .forms import SingerForm, SongRequestForm
from django.forms.models import model_to_dict
from django.core import serializers
from .models import SongRequest, NoUpload
from flags.state import enable_flag, disable_flag

from titlecase import titlecase

logger = logging.getLogger(__name__)


def _name_to_username(first_name, last_name):
    return f'{first_name.lower()}_{last_name.lower()}'


def _get_all_songs(singer):
    songs_as_main_singer = singer.songrequest_set.all()
    songs_as_additional_singer = singer.songs.all()
    return (songs_as_main_singer | songs_as_additional_singer).distinct()


def _get_all_songs_performed(singer):
    return _get_all_songs(singer).exclude(performance_time=None)


def _get_num_songs_performed(singer):
    return _get_all_songs_performed(singer).count()


def _get_how_long_waiting(singer):
    ordered_songs_performed = _get_all_songs_performed(singer).order_by('-performance_time')

    if ordered_songs_performed:
        time_waiting = datetime.now(timezone.utc) - ordered_songs_performed[0].performance_time
    else:
        time_waiting = datetime.now(timezone.utc) - singer.date_joined

    return time_waiting.total_seconds()


def _get_singers_next_songs(singer):
    # I'm using reverse request time, since we will eventually pop from the end of the list to get the earliest song.
    return list(_get_all_songs(singer).filter(performance_time=None).order_by('-request_time'))


def _calculate_singer_priority(singer):
    priority = pow(4, 1 / (_get_num_songs_performed(singer) + 1)) * _get_how_long_waiting(singer)
    logger.debug(f"Priority of {singer} is {priority}. Num songs performed: {_get_num_songs_performed(singer)}. "
                 f"How long waiting: {_get_how_long_waiting(singer)}")
    return priority


def _assign_song_priorities():
    logger.info(" =====  START PRIORITISING PROCESS ========")
    current_priority = 1
    singer_queryset = User.objects.filter(is_superuser=False)  # Superusers don't need to be given priority

    songs_of_singers_dict = dict()
    for singer in singer_queryset:
        singer.priority = _calculate_singer_priority(singer)
        next_songs = _get_singers_next_songs(singer)
        for song in next_songs:
            song.priority = 0
            song.save()
        songs_of_singers_dict[singer.username] = next_songs

    prioritized_singers = [singer.username for singer in sorted(singer_queryset, key=lambda singer: singer.priority,
                                                                reverse=True)]
    logger.info(f"DONE PRIORITISING SINGERS: Singers priority is {prioritized_singers}")

    while songs_of_singers_dict:
        logger.info("* Staring singer cycle")
        singers_that_got_a_song = []
        for singer_username in prioritized_singers:
            if singer_username not in songs_of_singers_dict:
                continue

            # If a singer already got a song in this cycle (because he's singing with someone else), skipping this cycle
            if singer_username in singers_that_got_a_song:
                logger.info(f"Skipping {singer_username} as they already have a song in this cycle")
                continue

            if not songs_of_singers_dict[singer_username]:
                logger.debug(f"{singer_username} doesn't have songs left. Removing from cycle")
                del songs_of_singers_dict[singer_username]
                continue

            # Pop songs until we get a song that hasn't been assigned yet
            while songs_of_singers_dict[singer_username]:
                song = songs_of_singers_dict[singer_username].pop()
                if not SongRequest.objects.get(pk=song.pk).priority:
                    song.priority = current_priority
                    logger.debug(f"Dealing with {singer_username}: Setting priority of {song} to {current_priority}")
                    current_priority += 1
                    song.save()
                    singers_that_got_a_song.extend([singer.username for singer in song.additional_singers.all()])
                    break
                else:
                    logger.debug(
                        f"The song for {singer_username} ({song}) was already chosen, moving to singer's next song")

    logger.info("========== END PRIORITISING PROCESS ======")


def _get_pending_songs_and_other_singers(user):
    songs_dict = []

    for song in _get_all_songs(user).filter(performance_time=None):
        additional_singers = [str(singer) for singer in song.additional_singers.all().exclude(pk=user.pk).order_by('first_name', 'last_name')]

        additional_singers_text = ', '.join(additional_singers[:-2] + [" and ".join(additional_singers[-2:])])
        songs_dict.append({'name': song.song_name, 'singers': additional_singers_text,
         'primary_singer': str(song.singer), 'user_song': song.singer == user, 'pk': song.pk})

    return songs_dict

@login_required(login_url='login')
def home(request, new_song=None):
    return render(request, 'song_signup/home.html', {"new_song": new_song})


def dashboard_data(request):
    try:
        current_song = SongRequest.objects.get(priority=1).basic_data
    except SongRequest.DoesNotExist:
        current_song = None

    try:
        next_song = SongRequest.objects.get(priority=2).basic_data
    except SongRequest.DoesNotExist:
        next_song = None

    user_next_songs = _get_singers_next_songs(request.user)
    user_next_song = user_next_songs[-1].basic_data if user_next_songs else None


    return JsonResponse(
        {
        "current_song": current_song,
        "next_song": next_song,
        "user_next_song": user_next_song
        })


def _sanitize_string(name, title=False):
    sanitized =  ' '.join(word.capitalize() for word in name.split())
    return titlecase(sanitized) if title else sanitized
    

def add_song_request(request):
    current_user = request.user
    
    if request.method == 'POST':
        song_name = _sanitize_string(request.POST['song-name'], title=True)
        musical = _sanitize_string(request.POST['musical'], title=True)
        additional_singers = request.POST.getlist('additional-singers')

        try:
            song_request = SongRequest.objects.get(song_name=song_name, musical=musical)
            if current_user in song_request.additional_singers.all():
                return JsonResponse({"error": f"Apparently, {song_request.singer} already signed you up for this song"}, status=400)
            elif song_request.singer == current_user:
                return JsonResponse({"error": "You already signed up with this song tonight"}, status=400)

        except SongRequest.DoesNotExist:
            song_request = SongRequest(song_name=song_name, musical=musical, singer=current_user)
            song_request.priority = 0

            song_request.save()
            try:
                song_request.additional_singers.set(additional_singers)
                song_request.save()
            except Exception:
                song_request.delete()
                raise

            _assign_song_priorities()

    return JsonResponse({
        'requested_song': song_request.song_name,
    })


def get_current_songs(request):
    return JsonResponse({'current_songs': _get_pending_songs_and_other_singers(request.user)})

def get_song(request, song_pk):
    try:
        song_request = SongRequest.objects.get(pk=song_pk)
    except SongRequest.DoesNotExist:
        return JsonResponse({'error': f"Song with ID {song_pk} does not exist, and cannot be deleted"}, status=403)

    return JsonResponse({"name": song_request.song_name})
    

@login_required(login_url='login')
def manage_songs(request):
    class HostSinger:
        def __init__(self, user_obj):
            self.name = user_obj.first_name
            self.id = user_obj.id
        
        def __str__(self):
            return self.name
    

    alon = HostSinger(User.objects.get(username='alon_aviv'))
    shani = HostSinger(User.objects.get(username='shani_wahrman'))

    other_singers = User.objects.all().exclude(pk=request.user.pk).exclude(pk=alon.id).exclude(pk=shani.id).order_by('first_name')
    return render(request, 'song_signup/manage_songs.html', {'other_singers': [shani,  alon] + list(other_singers)})

def logout(request):
    auth_logout(request)
    return redirect('login')


def login(request):
    # This is the root endpoint. If already logged in, go straight to home. 
    if request.user.is_authenticated and not request.user.is_anonymous:
        return redirect('home')

    if request.method == 'POST':
        first_name = _sanitize_string(request.POST['first-name'])
        last_name = _sanitize_string(request.POST['last-name'])
        logged_in = request.POST.get('logged-in') == 'on'
        no_image_upload = request.POST.get('no-upload') == 'on'

        if logged_in:
            try:
                singer = User.objects.get(first_name=first_name, last_name=last_name)
            except User.DoesNotExist:
                messages.error(request, "The name that you logged in with previously does not match your current "
                                        "name.\nCould there be a typo somewhere?")
                return render(request, 'song_signup/login.html')
                
        else:
            try:
                singer = User.objects.create_user(
                    _name_to_username(first_name, last_name),
                    first_name=first_name,
                    last_name=last_name,
                    is_staff=True
                )
                NoUpload.objects.create(user=singer, no_image_upload=no_image_upload)
            except IntegrityError:
                messages.error(request, "The name that you're trying to login with already exists.\n"
                                        "Did you already login with us tonight? If so, check the box below.")
                return render(request, 'song_signup/login.html')

        group = Group.objects.get(name='singers')
        group.user_set.add(singer)
        auth_login(request, singer)
        return redirect('home')

    return render(request, 'song_signup/login.html')


def delete_song(request, song_pk):
    SongRequest.objects.filter(pk=song_pk).delete()
    _assign_song_priorities()
    return HttpResponse()


def reset_database(request):
    call_command('dbbackup')
    call_command('reset_db')
    return redirect('admin/song_signup/songrequest')


def enable_signup(request):
    enable_flag('CAN_SIGNUP')
    return redirect('admin/song_signup/songrequest')


def disable_signup(request):
    disable_flag('CAN_SIGNUP')
    return redirect('admin/song_signup/songrequest')


def recalculate_priorities(request):
    _assign_song_priorities()
    return redirect('admin/song_signup/songrequest')






