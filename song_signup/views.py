import logging

from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.db import IntegrityError
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect
from flags.state import enable_flag, disable_flag, flag_disabled
from titlecase import titlecase

from .models import GroupSongRequest, SongRequest, Singer

logger = logging.getLogger(__name__)


def _name_to_username(first_name, last_name):
    return f'{first_name.lower()}_{last_name.lower()}'


@login_required(login_url='login')
def home(request, new_song=None):
    is_group_song = request.GET.get('group_song') == 'true'
    return render(request, 'song_signup/home.html', {
        "new_song": new_song,
        "is_group_song": is_group_song
    })


def dashboard_data(request):
    singer = request.user

    user_next_song = singer.next_song
    current_song = SongRequest.objects.current_song()
    next_song = SongRequest.objects.next_song()

    return JsonResponse(
        {
            "current_song": current_song and current_song.basic_data,
            "next_song": next_song and next_song.basic_data,
            "user_next_song": user_next_song and user_next_song.basic_data,
        })


def _sanitize_string(name, title=False):
    sanitized = ' '.join(word.capitalize() for word in name.split())
    return titlecase(sanitized) if title else sanitized


def add_song_request(request):
    current_user = request.user

    if request.method == 'POST':
        song_name = _sanitize_string(request.POST['song-name'], title=True)
        musical = _sanitize_string(request.POST['musical'], title=True)
        duet_partner = request.POST.get('duet-partner')

        if duet_partner == 'group-song':
            GroupSongRequest.objects.create(song_name=song_name, musical=musical, requested_by=current_user)
            return JsonResponse({'requested_song': song_name, 'group_song': True})

        try:
            song_request = SongRequest.objects.get(song_name=song_name, musical=musical)
            if current_user == song_request.duet_partner:
                return JsonResponse({"error": f"Apparently, {song_request.singer} already signed you up for this song"},
                                    status=400)
            elif song_request.singer == current_user:
                return JsonResponse({"error": "You already signed up with this song tonight"}, status=400)
            else:
                song_request = SongRequest.objects.create(song_name=song_name, musical=musical, singer=current_user,
                                                          duet_partner_id=duet_partner)
                Singer.ordering.calculate_positions()

        except SongRequest.DoesNotExist:
            song_request = SongRequest.objects.create(song_name=song_name, musical=musical, singer=current_user,
                                                      duet_partner_id=duet_partner)
            Singer.ordering.calculate_positions()

    return JsonResponse({
        'requested_song': song_request.song_name,
        'group_song': False
    })


def get_current_songs(request):
    singer = request.user
    songs_dict = []

    for song in singer.pending_songs:
        songs_dict.append({
            'name': song.song_name, 'duet_partner': song.duet_partner and str(song.duet_partner),
            'primary_singer': str(song.singer), 'user_song': song.singer == singer, 'pk': song.pk
        })

    return JsonResponse({'current_songs': songs_dict})


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

    alon = HostSinger(Singer.objects.get(username='alon_aviv'))
    shani = HostSinger(Singer.objects.get(username='shani_wahrman'))

    other_singers = Singer.objects.all().exclude(pk=request.user.pk).exclude(pk=alon.id).exclude(pk=shani.id).order_by(
        'first_name')
    return render(request, 'song_signup/manage_songs.html', {'other_singers': [shani, alon] + list(other_singers)})


def logout(request):
    auth_logout(request)
    return redirect('login')


def faq(request):
    return render(request, 'song_signup/faq.html')


def tip_us(request):
    return render(request, 'song_signup/tip_us.html')


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
                singer = Singer.objects.get(first_name=first_name, last_name=last_name)
            except Singer.DoesNotExist:
                return JsonResponse(
                    {'error': "The name that you logged in with previously does not match your current one"},
                    status=400)

        else:
            try:
                singer = Singer.objects.create_user(
                    _name_to_username(first_name, last_name),
                    first_name=first_name,
                    last_name=last_name,
                    is_staff=True,
                    no_image_upload=no_image_upload
                )
            except IntegrityError:
                return JsonResponse({
                    'error': "The name that you're trying to login with already exists.\n"
                             "Did you already login with us tonight? If so, check the box below."
                }, status=400)

        group = Group.objects.get(name='singers')
        group.user_set.add(singer)
        auth_login(request, singer)
        return HttpResponse()

    return render(request, 'song_signup/login.html')


def delete_song(request, song_pk):
    SongRequest.objects.filter(pk=song_pk).delete()
    Singer.ordering.calculate_positions()
    return HttpResponse()


def reset_database(request):
    call_command('dbbackup')
    call_command('reset_db')
    enable_flag('CAN_SIGNUP')
    return redirect('admin/song_signup/songrequest')


def enable_signup(request):
    enable_flag('CAN_SIGNUP')
    Singer.ordering.calculate_positions()
    return redirect('admin/song_signup/songrequest')


def disable_signup(request):
    disable_flag('CAN_SIGNUP')
    Singer.ordering.calculate_positions()
    return redirect('admin/song_signup/songrequest')


def signup_disabled(request):
    return JsonResponse({"result": flag_disabled('CAN_SIGNUP')})


def recalculate_priorities(request):
    Singer.ordering.calculate_positions()
    return redirect('admin/song_signup/songrequest')
