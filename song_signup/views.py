import logging
import traceback
from openpyxl import load_workbook
from constance import config
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.db import IntegrityError
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect
from flags.state import enable_flag, disable_flag, flag_disabled
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from titlecase import titlecase

from .forms import FileUploadForm
from .models import GroupSongRequest, SongLyrics, SongRequest, Singer, SongSuggestion
from .serializers import SongSuggestionSerializer, SongRequestSerializer, SingerSerializer

logger = logging.getLogger(__name__)


def _is_superuser(user):
    return user.is_authenticated and user.is_superuser


def name_to_username(first_name, last_name):
    return f'{first_name.lower()}_{last_name.lower()}'


@login_required(login_url='login')
def home(request, new_song=None, is_group_song=False):
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
        notes = request.POST.get('notes')
        duet_partner = request.POST.get('duet-partner')
        additional_singers = request.POST.getlist('additional-singers')
        suggested_by = request.POST.get('suggested_by')

        try:
            song_request = SongRequest.objects.get(song_name=song_name, musical=musical)
            if current_user == song_request.duet_partner:
                return JsonResponse({"error": f"Apparently, {song_request.singer} already signed you up for this song"},
                                    status=400)
            elif song_request.singer == current_user:
                return JsonResponse({"error": "You already signed up with this song tonight"}, status=400)

        except SongRequest.DoesNotExist:
            song_request = SongRequest.objects.create(song_name=song_name, musical=musical, singer=current_user,
                                                      duet_partner_id=duet_partner, notes=notes,
                                                      suggested_by_id=suggested_by)
            song_request.additional_singers.set(additional_singers)

            Singer.ordering.calculate_positions()
            SongSuggestion.objects.check_used_suggestions()

        return JsonResponse({
            'requested_song': song_request.song_name,
        })


@api_view(["GET"])
def get_current_songs(request):
    singer = request.user
    serialized = SongRequestSerializer(singer.pending_songs, many=True, read_only=True)
    return Response(serialized.data, status=status.HTTP_200_OK)


@api_view(["GET"])
def get_suggested_songs(request):
    serialized = SongSuggestionSerializer(SongSuggestion.objects.all().order_by('is_used', '-request_time'),
                                          many=True, read_only=True)
    return Response(serialized.data, status=status.HTTP_200_OK)


@api_view(["GET"])
def get_current_user(request):
    serialized = SingerSerializer(request.user, read_only=True)
    return Response(serialized.data, status=status.HTTP_200_OK)


@api_view(["GET"])
def get_song(request, song_pk):
    try:
        song_request = SongRequest.objects.get(pk=song_pk)
        serialized = SongRequestSerializer(song_request, read_only=True)
        return Response(serialized.data, status=status.HTTP_200_OK)
    except SongRequest.DoesNotExist:
        return Response({'error': f"Song with ID {song_pk} does not exist"}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["PUT"])
def rename_song(request):
    song_id = request.data['song_id']
    new_name = _sanitize_string(request.data['song_name'], title=True)
    new_musical = _sanitize_string(request.data['musical'], title=True)

    if not new_name:
        return Response({'error': f"Song name can not empty"}, status=status.HTTP_400_BAD_REQUEST)

    if not new_musical:
        return Response({'error': f"Musical name can not empty"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        song_request = SongRequest.objects.get(pk=song_id)
        serialized = SongRequestSerializer(song_request, read_only=True)
        song_request.song_name = new_name
        song_request.musical = new_musical
        song_request.save()
        return Response(serialized.data, status=status.HTTP_200_OK)
    except SongRequest.DoesNotExist:
        return Response({'error': f"Song with ID {song_id} does not exist"}, status=status.HTTP_400_BAD_REQUEST)


@login_required(login_url='login')
def manage_songs(request):
    return render(request, 'song_signup/manage_songs.html')


@login_required(login_url='login')
def view_suggestions(request):
    return render(request, 'song_signup/view_suggestions.html')


@login_required(login_url='login')
def add_song(request):
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
    return render(request, 'song_signup/add_song.html', {'other_singers': [shani, alon] + list(other_singers)})


def _sort_lyrics(song: SongRequest | GroupSongRequest):
    """
    Sort the lyrics based on our best guess of how well they match
    Tried a few algorithms here but this relatively simple one worked best:

    1) If default is selected order first
    2) Songs with exact name matches
    3) Songs with left matches (input song name is included in full song name)
    4) Songs with right matches (full song name is included in input song name)
    5) Everything else

    Within each group just order by ID for consistency.
    """
    lyrics = song.lyrics.order_by('id').all()

    default = [lyric for lyric in lyrics if lyric.default]
    lyrics = [lyric for lyric in lyrics if lyric not in default]

    exact_matches = [lyric for lyric in lyrics if song.song_name.lower() == lyric.song_name.lower()]
    lyrics = [lyric for lyric in lyrics if lyric not in exact_matches]

    left_matches = [lyric for lyric in lyrics if song.song_name.lower() in lyric.song_name.lower()]
    lyrics = [lyric for lyric in lyrics if lyric not in left_matches]

    right_matches = [lyric for lyric in lyrics if lyric.song_name.lower() in song.song_name.lower()]
    lyrics = [lyric for lyric in lyrics if lyric not in right_matches]

    return default + exact_matches + left_matches + right_matches + lyrics


@login_required(login_url='login')
def lyrics(request, song_pk):
    try:
        song_request = SongRequest.objects.get(pk=song_pk)
    except SongRequest.DoesNotExist:
        return JsonResponse({'error': f"Song with ID {song_pk} does not exist"}, status=status.HTTP_400_BAD_REQUEST)

    lyrics = _sort_lyrics(song_request)
    return render(request, 'song_signup/lyrics.html', {"lyrics": lyrics and lyrics[0], "song": song_request})


@login_required(login_url='login')
def group_lyrics(request, song_pk):
    try:
        song_request = GroupSongRequest.objects.get(pk=song_pk)
    except GroupSongRequest.DoesNotExist:
        return JsonResponse({'error': f"Group song with ID {song_pk} does not exist"}, status=status.HTTP_400_BAD_REQUEST)

    lyrics = _sort_lyrics(song_request)
    return render(request, 'song_signup/lyrics.html', {"lyrics": lyrics and lyrics[0], "group_song": song_request})


@login_required(login_url='login')
def lyrics_by_id(request, lyrics_id):
    try:
        lyrics = SongLyrics.objects.get(id=lyrics_id)
    except SongLyrics.DoesNotExist:
        return JsonResponse({'error': f"Lyrics with ID {lyrics_id} does not exist"}, status=status.HTTP_400_BAD_REQUEST)

    return render(request, 'song_signup/lyrics.html', {
        "lyrics": lyrics,
        "song": lyrics.song_request,
        "group_song": lyrics.group_song_request
    })


@login_required(login_url='login')
def alternative_lyrics(request, song_pk):
    try:
        song_request = SongRequest.objects.get(pk=song_pk)
    except GroupSongRequest.DoesNotExist:
        return JsonResponse({'error': f"Group song with ID {song_pk} does not exist"}, status=status.HTTP_400_BAD_REQUEST)

    lyrics = _sort_lyrics(song_request)
    return render(request, 'song_signup/alternative_lyrics.html', {"lyrics": lyrics, "song": song_request})


@login_required(login_url='login')
def alternative_group_lyrics(request, song_pk):
    try:
        song_request = GroupSongRequest.objects.get(pk=song_pk)
    except GroupSongRequest.DoesNotExist:
        return JsonResponse({'error': f"Group song with ID {song_pk} does not exist"}, status=status.HTTP_400_BAD_REQUEST)

    lyrics = _sort_lyrics(song_request)
    return render(request, 'song_signup/alternative_lyrics.html', {"lyrics": lyrics, "song": song_request})


@api_view(["PUT"])
def default_lyrics(request):
    lyrics_id = request.data['lyricsId']

    lyric = SongLyrics.objects.get(id=lyrics_id)

    if not (request.user.is_superuser or (lyric.song_request and lyric.song_request.singer == request.user)):
        return Response({"error": "Only original singer can set default lyrics"}, status=status.HTTP_401_UNAUTHORIZED)

    lyric.default = True
    lyric.save()
    return Response({}, status=status.HTTP_200_OK)


@login_required(login_url='login')
def suggest_song(request):
    current_user = request.user

    if request.method == 'POST':
        song_name = _sanitize_string(request.POST['song-name'], title=True)
        musical = _sanitize_string(request.POST['musical'], title=True)

        if request.POST.get('group-song') == 'on':
            GroupSongRequest.objects.create(song_name=song_name, musical=musical, suggested_by=current_user)
            return home(request, song_name, is_group_song=True)

        _, created = SongSuggestion.objects.get_or_create(song_name=song_name, musical=musical,
                                                          suggested_by=current_user)
        if created:
            SongSuggestion.objects.check_used_suggestions()

        return redirect('view_suggestions')

    else:
        return render(request, 'song_signup/suggest_song.html')


def logout(request):
    user = request.user
    if not user.is_superuser:
        user.is_active = False
    user.save()
    auth_logout(request)
    Singer.ordering.calculate_positions()
    return redirect('login')


def faq(request):
    return render(request, 'song_signup/faq.html')


def tip_us(request):
    return render(request, 'song_signup/tip_us.html')


def login(request):
    # This is the root endpoint. If already logged in, go straight to home.
    evening_started = bool(config.PASSCODE)
    if request.user.is_authenticated and not request.user.is_anonymous and evening_started:
        return redirect('home')

    if request.method == 'POST':
        first_name = _sanitize_string(request.POST['first-name'])
        last_name = _sanitize_string(request.POST['last-name'])
        passcode = _sanitize_string(request.POST['passcode'])
        logged_in = request.POST.get('logged-in') == 'on'
        no_image_upload = request.POST.get('no-upload') == 'on'

        if passcode.lower() != config.PASSCODE.lower():
            return JsonResponse({
                'error': "Wrong passcode - Shani will reveal tonight's passcode at the event"
            }, status=400)

        if logged_in:
            try:
                singer = Singer.objects.get(first_name=first_name, last_name=last_name)
                singer.is_active = True
                singer.save()
            except Singer.DoesNotExist:
                return JsonResponse(
                    {'error': "The name that you logged in with previously does not match your current one"},
                    status=400)

        else:
            try:
                singer = Singer.objects.create_user(
                    name_to_username(first_name, last_name),
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

    return render(request, 'song_signup/login.html', context={'evening_started': evening_started})


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


@user_passes_test(_is_superuser)
def upload_lineapp_orders(request):
    if request.method == 'POST' and 'file' in request.FILES:
        try:
            orders_processed = _process_orders(request.FILES['file'])
        except Exception as e:
            return render(request, 'song_signup/upload_lineapp_orders.html', {'form': FileUploadForm(), 'error_message': traceback.format_exc()})

        return HttpResponse(f'PROCESSED {orders_processed} orders successfully')

    return render(request, 'song_signup/upload_lineapp_orders.html', {'form': FileUploadForm()})


def _process_orders(spreadsheet_file):
    # TODO Count how many orders (not sub ticket types) were processed as well, so I can compare to the excel. And say how many are duplicates and how many new.
    # TODO, Also say how many were singing tickets and how many regular.
    orders_processed = 0
    worksheet = load_workbook(spreadsheet_file).active
    for row in worksheet.iter_rows(min_row=2, values_only=2):
        order_id, event_sku, event_name, ticket_type_name, num_tickets, ticket_type_sku = row
        print(f"Order ID: {order_id}, Event SKU: {event_sku}, Event Name: {event_name}, Ticket Type Name: {ticket_type_name}, Num Tickets: {num_tickets}, Ticket Type SKU: {ticket_type_sku}")
        orders_processed += 1

    return orders_processed
