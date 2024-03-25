import logging
import traceback
from functools import wraps

import constance
from constance import config
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.core.management import call_command
from django.db import transaction
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect
from flags.state import enable_flag, disable_flag, flag_disabled, flag_enabled
from openpyxl import load_workbook
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from titlecase import titlecase

from .forms import FileUploadForm
from .models import (
    GroupSongRequest,
    SongLyrics,
    SongRequest,
    Singer,
    SongSuggestion,
    TicketOrder,
    SING_SKU,
    TicketsDepleted,
    AlreadyLoggedIn,
    CurrentGroupSong
)
from .serializers import (
    SongSuggestionSerializer,
    SongRequestSerializer,
    SingerSerializer,
    SongRequestLineupSerializer,
    GroupSongRequestLineupSerializer,
    LyricsSerializer,
)

logger = logging.getLogger(__name__)

AUDIENCE_SESSION = 'audience-logged-in'


def bwt_login_required(login_url, singer_only=False):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not (request.user.is_authenticated or (not singer_only and request.session.get(AUDIENCE_SESSION))):
                return redirect(login_url)

            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


def superuser_required(login_url):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_superuser:
                return redirect(login_url)

            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


def _is_superuser(user):
    return user.is_authenticated and user.is_superuser


def name_to_username(first_name, last_name):
    return f'{first_name.lower()}_{last_name.lower()}'


@bwt_login_required('login')
def home(request, new_song=None, is_group_song=False):
    return render(request, 'song_signup/home.html', {
        "new_song": new_song,
        "is_group_song": is_group_song
    })


def spotlight_data(request):
    current_song = SongRequest.objects.current_song()
    next_song = SongRequest.objects.next_song()

    return JsonResponse(
        {
            "current_song": current_song and current_song.basic_data,
            "next_song": next_song and next_song.basic_data,
        })


def dashboard_data(request):
    singer = request.user
    user_next_song = singer.next_song

    return JsonResponse({"user_next_song": user_next_song and user_next_song.basic_data})


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
def get_drinking_words(request):
    drinking_words = constance.config.DRINKING_WORDS
    return Response({'drinking_words': drinking_words.split(';') if drinking_words else []},
                    status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([IsAdminUser])
def get_passcode(request):
    passcode = constance.config.PASSCODE
    return Response({'passcode': passcode}, status=status.HTTP_200_OK)


@api_view(["GET"])
def get_song(request, song_pk):
    try:
        song_request = SongRequest.objects.get(pk=song_pk)
        serialized = SongRequestSerializer(song_request, read_only=True)
        return Response(serialized.data, status=status.HTTP_200_OK)
    except SongRequest.DoesNotExist:
        return Response({'error': f"Song with ID {song_pk} does not exist"}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET"])
def get_lineup(request):
    song_requests = SongRequest.objects.filter(position__isnull=False, skipped=False).order_by('position')
    current_song = _get_current_song()

    if isinstance(current_song, GroupSongRequest):
        current_song_data = GroupSongRequestLineupSerializer(current_song).data
        next_songs_data = SongRequestLineupSerializer(song_requests, many=True).data
    else:
        current_song_data = SongRequestLineupSerializer(current_song).data
        next_songs_data = SongRequestLineupSerializer(song_requests[1:], many=True).data

    return Response({
        'current_song': current_song_data,
        'next_songs': next_songs_data
    }, status=status.HTTP_200_OK)


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


@bwt_login_required('login', singer_only=True)
def manage_songs(request):
    return render(request, 'song_signup/manage_songs.html')


@bwt_login_required('login')
def view_suggestions(request):
    return render(request, 'song_signup/view_suggestions.html')


@bwt_login_required('login', singer_only=True)
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
    if not song:
        return

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


@superuser_required('login')
def lyrics(request, song_pk):
    try:
        song_request = SongRequest.objects.get(pk=song_pk)
    except SongRequest.DoesNotExist:
        return JsonResponse({'error': f"Song with ID {song_pk} does not exist"}, status=status.HTTP_400_BAD_REQUEST)

    lyrics = _sort_lyrics(song_request)
    return render(request, 'song_signup/lyrics.html', {"lyrics": lyrics and lyrics[0], "song": song_request})


@superuser_required('login')
def group_lyrics(request, song_pk):
    try:
        song_request = GroupSongRequest.objects.get(pk=song_pk)
    except GroupSongRequest.DoesNotExist:
        return JsonResponse({'error': f"Group song with ID {song_pk} does not exist"},
                            status=status.HTTP_400_BAD_REQUEST)

    lyrics = _sort_lyrics(song_request)
    return render(request, 'song_signup/lyrics.html', {"lyrics": lyrics and lyrics[0], "group_song": song_request})


@superuser_required('login')
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


@superuser_required('login')
def alternative_lyrics(request, song_pk):
    try:
        song_request = SongRequest.objects.get(pk=song_pk)
    except GroupSongRequest.DoesNotExist:
        return JsonResponse({'error': f"Group song with ID {song_pk} does not exist"},
                            status=status.HTTP_400_BAD_REQUEST)

    lyrics = _sort_lyrics(song_request)
    return render(request, 'song_signup/alternative_lyrics.html', {"lyrics": lyrics, "song": song_request})


@superuser_required('login')
def alternative_group_lyrics(request, song_pk):
    try:
        song_request = GroupSongRequest.objects.get(pk=song_pk)
    except GroupSongRequest.DoesNotExist:
        return JsonResponse({'error': f"Group song with ID {song_pk} does not exist"},
                            status=status.HTTP_400_BAD_REQUEST)

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


def _get_current_song():
    curr_group_song = CurrentGroupSong.objects.all().first()
    if curr_group_song:
        return curr_group_song.group_song
    else:
        return SongRequest.objects.current_song()


@api_view(["GET"])
def get_current_lyrics(request):
    current = _get_current_song()
    lyrics = _sort_lyrics(current)

    serialized = LyricsSerializer(lyrics[0] if lyrics else None, many=False, read_only=True)
    return Response(serialized.data, status=status.HTTP_200_OK)


def end_group_song(request):
    CurrentGroupSong.objects.all().delete()
    return redirect('admin/song_signup/groupsongrequest')


@bwt_login_required('login')
def live_lyrics(request):
    return render(request, 'song_signup/live_lyrics.html')


@bwt_login_required('login')
def lineup(request):
    return render(request, 'song_signup/lineup.html')


@bwt_login_required('login')
def suggest_group_song(request):
    current_user = request.user

    if request.method == 'POST':
        song_name = _sanitize_string(request.POST['song-name'], title=True)
        musical = _sanitize_string(request.POST['musical'], title=True)

        if current_user.is_authenticated:
            suggested_by = str(current_user)
        else:
            suggested_by = request.POST.get('suggested_by') or '-'

        GroupSongRequest.objects.create(song_name=song_name, musical=musical, suggested_by=suggested_by)
        return home(request, song_name, is_group_song=True)

    else:
        return render(request, 'song_signup/suggest_group_song.html')


def logout(request):
    user = request.user
    if user.is_anonymous:
        del request.session[AUDIENCE_SESSION]
        return redirect('login')

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
    evening_started = bool(config.PASSCODE) and bool(config.EVENT_SKU)
    if evening_started and (request.user.is_authenticated or request.session.get(AUDIENCE_SESSION)):
        return redirect('home')

    if request.method == 'POST':
        try:
            ticket_type = request.POST['ticket-type']

            if ticket_type == 'audience':
                request.session[AUDIENCE_SESSION] = True
                return redirect('home')

            elif ticket_type == 'singer':
                first_name = _sanitize_string(request.POST['first-name'])
                last_name = _sanitize_string(request.POST['last-name'])
                passcode = _sanitize_string(request.POST['passcode'])
                order_id = request.POST['order-id']
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
                    if config.FREEBIE_TICKET and order_id == config.FREEBIE_TICKET:
                        ticket_order, _ = TicketOrder.objects.get_or_create(order_id=config.FREEBIE_TICKET,
                                                                            event_sku=config.EVENT_SKU,
                                                                            event_name='FREEBIE-ORDER',
                                                                            num_tickets=-1,
                                                                            customer_name='FREEBIE_ORDER',
                                                                            ticket_type=SING_SKU,
                                                                            is_freebie=True)

                    else:
                        try:
                            ticket_order = TicketOrder.objects.get(order_id=order_id,
                                                                   event_sku=config.EVENT_SKU,
                                                                   ticket_type=SING_SKU)
                        except (TicketOrder.DoesNotExist, ValueError):
                            return JsonResponse({
                                'error': "Your order number is incorrect. "
                                         "It should be in the title of the tickets email"
                            }, status=400)

                    try:
                        singer = Singer.objects.create_user(
                            name_to_username(first_name, last_name),
                            first_name=first_name,
                            last_name=last_name,
                            is_staff=False,
                            no_image_upload=no_image_upload,
                            ticket_order=ticket_order
                        )
                    except (TicketsDepleted, AlreadyLoggedIn) as e:
                        return JsonResponse({
                            'error': str(e)
                        }, status=400)

                auth_login(request, singer)
                return redirect('home')

            else:
                raise ValueError("Invalid ticket type")

        except Exception as e:
            logger.exception("Exception: ")
            return JsonResponse(
                {'error': "An unexpected error occurred (you can blame Alon..) Refreshing the page might help"},
                status=400)
    return render(request, 'song_signup/login.html', context={'evening_started': evening_started})


def delete_song(request, song_pk):
    SongRequest.objects.filter(pk=song_pk).delete()
    Singer.ordering.calculate_positions()
    return HttpResponse()


def reset_database(request):
    call_command('dbbackup')
    call_command('reset_db')
    enable_flag('CAN_SIGNUP')
    disable_flag('STARTED')
    CurrentGroupSong.objects.all().delete()
    config.PASSCODE = ''
    config.EVENT_SKU = ''
    config.DRINKING_WORDS = ''
    config.FREEBIE_TICKET = ''
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


def start_evening(request):
    enable_flag('STARTED')
    return redirect('admin/song_signup/songrequest')


def end_evening(request):
    disable_flag('STARTED')
    return redirect('admin/song_signup/songrequest')


def evening_started(request):
    return JsonResponse({"started": flag_enabled('STARTED')})


def recalculate_priorities(request):
    Singer.ordering.calculate_positions()
    return redirect('admin/song_signup/songrequest')


@superuser_required('login')
def upload_lineapp_orders(request):
    if request.method == 'POST' and 'file' in request.FILES:
        try:
            processing_data = _process_orders(request.FILES['file'])
        except Exception as e:
            return render(request, 'song_signup/upload_lineapp_orders.html',
                          {'form': FileUploadForm(), 'error_message': traceback.format_exc()})

        return HttpResponse(f"""
<h3>{processing_data['num_orders']} Orders Processed Successfully</h3>
<ul>
<li>Num orders: {processing_data['num_orders']}</li>
<li> Num ticket orders (lines in spreadsheet): {processing_data['num_ticket_orders']}</li>
<br>
<li> Num ticket orders that already existed in DB: {processing_data['num_existing_ticket_orders']}</li>
<li> Num new ticket orders added to DB: {processing_data['num_new_ticket_orders']}</li>
<br>
<li> Num singing tickets in spreadsheet: {processing_data['num_singing_tickets']}</li>
<li> Num audience tickets in spreadsheet: {processing_data['num_audience_tickets']}</li>
""")

    return render(request, 'song_signup/upload_lineapp_orders.html', {'form': FileUploadForm()})


@transaction.atomic
def _process_orders(spreadsheet_file):
    orders = set()  # Order made by a single person
    num_ticket_orders = 0  # Groups of ticket types within the orders
    num_existing_ticket_orders = 0
    num_new_ticket_orders = 0
    num_singing_tickets = 0
    num_audience_tickets = 0

    worksheet = load_workbook(spreadsheet_file).active
    for row in worksheet.iter_rows(min_row=2, values_only=2):
        order_id, event_sku, event_name, num_tickets, ticket_type, first_name, last_name = row
        orders.add(order_id)
        num_ticket_orders += 1

        ticket_order, created = TicketOrder.objects.get_or_create(
            order_id=order_id,
            event_sku=event_sku,
            ticket_type=ticket_type,
            event_name=event_name,
            num_tickets=num_tickets,
            customer_name=' '.join([first_name, last_name])
        )
        if created:
            num_new_ticket_orders += 1
        else:
            num_existing_ticket_orders += 1

        if ticket_type == SING_SKU:
            num_singing_tickets += num_tickets
        else:
            num_audience_tickets += num_tickets

        ticket_order.save()

    return dict(num_orders=len(orders),
                num_ticket_orders=num_ticket_orders,
                num_new_ticket_orders=num_new_ticket_orders,
                num_existing_ticket_orders=num_existing_ticket_orders,
                num_singing_tickets=num_singing_tickets,
                num_audience_tickets=num_audience_tickets
                )
