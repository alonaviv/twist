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
from django.urls import reverse
from flags.state import enable_flag, disable_flag, flag_disabled, flag_enabled
from openpyxl import load_workbook
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from titlecase import titlecase
from django.core.exceptions import ValidationError
from .forms import FileUploadForm
from .models import (
    GroupSongRequest,
    SongLyrics,
    SongRequest,
    Singer,
    SongSuggestion,
    TicketOrder,
    SING_SKU,
    ATTN_SKU,
    TicketsDepleted,
    AlreadyLoggedIn,
    CurrentGroupSong,
    TriviaQuestion,
    TriviaResponse,
)
from .serializers import (
    SongSuggestionSerializer,
    SongRequestSerializer,
    SingerSerializer,
    SongRequestLineupSerializer,
    GroupSongRequestLineupSerializer,
    LyricsSerializer,
    TriviaQuestionSerializer,
    TriviaResponseSerializer
)

logger = logging.getLogger(__name__)

class TwistApiException(Exception):
    pass


def bwt_login_required(login_url, singer_only=False):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated or (singer_only and request.user.is_audience):
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


def name_to_username(first_name, last_name):
    return f'{first_name.lower()}_{last_name.lower()}'


@bwt_login_required('login')
def home(request):
    song = request.GET.get('song')
    is_group_song = request.GET.get('is-group-song') == 'true'
    return render(request, 'song_signup/home.html', {
        "new_song": song,
        "is_group_song": is_group_song
    })


def spotlight_data(request):
    current_song, is_group_song = _get_current_song()

    if is_group_song:
        next_song = SongRequest.objects.current_song()
    else:
        next_song = SongRequest.objects.next_song()

    return JsonResponse(
        {
            "current_song": current_song and current_song.basic_data,
            "next_song": next_song and next_song.basic_data,
        })


def next_singer(request):
    """
    Return username of next singer
    """
    next_song = SongRequest.objects.current_song()
    username = next_song.singer.username if next_song is not None else None

    return JsonResponse({
        "next_singer": username
    })



def dashboard_data(request):
    singer = request.user
    user_next_song = singer.next_song

    return JsonResponse({"user_next_song": user_next_song and user_next_song.basic_data})


def _sanitize_string(name, title=False):
    sanitized = ' '.join(word.capitalize() for word in name.split())
    return titlecase(sanitized) if title else sanitized


@bwt_login_required('login', singer_only=True)
def add_song_request(request):
    current_user = request.user

    if request.method == 'POST':
        song_name = _sanitize_string(request.POST['song-name'], title=True)
        musical = _sanitize_string(request.POST['musical'], title=True)
        notes = request.POST.get('notes')
        partners = request.POST.getlist('partners')
        approve_duplicate = request.POST.get('approve-duplicate')

        song_request = SongRequest.objects.filter(song_name=song_name, musical=musical).first()
        if not song_request or approve_duplicate:
            with transaction.atomic(): # Abort object creation if validation fails
                new_song_request = SongRequest.objects.create(song_name=song_name, musical=musical,
                                                              singer=current_user, notes=notes)
                try:
                    new_song_request.partners.set(partners) # Runs validation function using signal
                except ValidationError as e:
                    return JsonResponse({"error": e.message}, status=400)

            Singer.ordering.calculate_positions()
            return JsonResponse({
                'requested_song': new_song_request.song_name,
            })

        else:
            if current_user in song_request.partners.all():
                return JsonResponse({"error": f"Apparently, {song_request.singer} already signed you up for this song"},
                                    status=400)
            elif song_request.singer == current_user:
                return JsonResponse({"error": "You already signed up with this song tonight"}, status=400)
            else:
                return JsonResponse({"duplicate": True}, status=202)


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
    current_song, is_group_song = _get_current_song()

    if is_group_song:
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
def update_song(request):
    song_id = request.data['song_id']
    song_name = _sanitize_string(request.data['song_name'], title=True)
    musical = _sanitize_string(request.data['musical'], title=True)
    notes = request.data.get('notes')
    partner_ids = request.data.get('partners', [])
    partners = list(Singer.objects.filter(id__in=partner_ids))

    if not song_name:
        return Response({'error': f"Song name can not empty"}, status=status.HTTP_400_BAD_REQUEST)

    if not musical:
        return Response({'error': f"Musical name can not empty"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        song_request = SongRequest.objects.get(pk=song_id)
        if song_request.song_name != song_name:
            song_request.found_music = False
            song_request.default_lyrics = False
        song_request.song_name = song_name
        song_request.musical = musical
        song_request.notes = notes
        song_request.partners.set(partners)
        song_request.save()

        serialized = SongRequestSerializer(song_request, read_only=True)
        return Response(serialized.data, status=status.HTTP_200_OK)

    except ValidationError as e:
        return JsonResponse({"error": e.message}, status=status.HTTP_400_BAD_REQUEST)

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
    return render(request, 'song_signup/add_song.html', {'possible_partners': _get_possible_partners(request)})

def _get_possible_partners(request):
    superusers = Singer.objects.filter(is_superuser=True).all()
    partner_options = Singer.objects.filter(is_active=True).exclude(pk=request.user.pk).exclude(is_superuser=True).order_by(
        'first_name')
    return list(superusers) + list(partner_options)

@api_view(["GET"])
def get_possible_partners(request):
    partners = _get_possible_partners(request)
    serialized = SingerSerializer(partners, many=True)
    return Response(serialized.data, status=status.HTTP_200_OK)


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

    if lyric.song_request:
        lyric.song_request.default_lyrics = True
        lyric.song_request.save()

    if lyric.group_song_request:
        lyric.group_song_request.default_lyrics = True
        lyric.group_song_request.save(get_lyrics=False)

    return Response({'is_group_song': bool(lyric.group_song_request)}, status=status.HTTP_200_OK)


def _get_current_song():
    """
    Return current_song, is_group_song
    """
    curr_group_song = CurrentGroupSong.objects.all().first()
    if curr_group_song and curr_group_song.is_active:
        return curr_group_song.group_song, True
    else:
        return SongRequest.objects.current_song(), False


@api_view(["GET"])
def get_current_lyrics(request):
    current, is_group_song = _get_current_song()
    lyrics = _sort_lyrics(current)
    serialized = LyricsSerializer(lyrics[0] if lyrics else None, many=False, read_only=True,
                                  context={'is_group_song': is_group_song})
    return Response(serialized.data, status=status.HTTP_200_OK)


@api_view(["GET"])
def get_active_question(request):
    active_question = TriviaQuestion.objects.filter(is_active=True).first()
    if active_question:
        serialized = TriviaQuestionSerializer(active_question)
        return Response(serialized.data, status=status.HTTP_200_OK)
    else:
        return Response({}, status=status.HTTP_204_NO_CONTENT)


@api_view(["POST"])
def select_trivia_answer(request):
    answer_id = request.data['answer-id']
    user = request.user
    active_question = TriviaQuestion.objects.filter(is_active=True).first()

    if active_question:
        if not user.trivia_responses.filter(question=active_question):
            TriviaResponse.objects.create(user=user, choice=answer_id, question=active_question)
            return Response({}, status=status.HTTP_201_CREATED)
        else:
            return Response({'error': "User already selected a question"},
                            status=status.HTTP_409_CONFLICT)
    else:
        return Response({'error': "No active question"},
                        status=status.HTTP_400_BAD_REQUEST)

@api_view(["GET"])
def get_selected_answer(request):
    user = request.user
    active_question = TriviaQuestion.objects.filter(is_active=True).first()
    if active_question:
        trivia_response = user.trivia_responses.filter(question=active_question).first()
        if trivia_response:
            serialized = TriviaResponseSerializer(trivia_response)
            return Response(serialized.data, status=status.HTTP_200_OK)

    return Response({'error': "User hasn't selected an answer for the active question"},
                    status=status.HTTP_404_NOT_FOUND)


@superuser_required('login')
def deactivate_trivia(request):
    TriviaQuestion.objects.all().update(is_active=False)
    return redirect('admin/song_signup/triviaquestion')


@superuser_required('login')
def start_group_song(request):
    CurrentGroupSong.start_song()
    return redirect('admin/song_signup/groupsongrequest')


@superuser_required('login')
def end_group_song(request):
    CurrentGroupSong.end_song()
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
        suggested_by = str(current_user)

        GroupSongRequest.objects.create(song_name=song_name, musical=musical, suggested_by=suggested_by)
        return redirect(f"{reverse('home')}?song={song_name}&is-group-song=true")

    else:
        return render(request, 'song_signup/suggest_group_song.html')


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


def _get_order(order_id, ticket_type):
    if config.FREEBIE_TICKET and order_id == config.FREEBIE_TICKET:
        return TicketOrder.objects.get_or_create(order_id=config.FREEBIE_TICKET,
                                                 event_sku=config.EVENT_SKU,
                                                 event_name='FREEBIE-ORDER',
                                                 num_tickets=-1,
                                                 customer_name='FREEBIE_ORDER',
                                                 ticket_type=SING_SKU,
                                                 is_freebie=True)[0]

    try:
        return TicketOrder.objects.get(order_id=order_id,
                                       event_sku=config.EVENT_SKU,
                                       ticket_type=ticket_type)
    except (TicketOrder.DoesNotExist, ValueError):
        ticket_str = 'a singer' if ticket_type == SING_SKU else 'an audience'
        raise TwistApiException(f"We can't find {ticket_str} ticket with that order number. Maybe you have a typo? "
                                "The number appears in the title of the tickets email")


def _login_new_singer(first_name, last_name, no_image_upload, order_id, uploaded_image):
    """
    Singer and audience are different ticket orders entries, both with the same order number
    """
    ticket_order = _get_order(order_id, SING_SKU)
    try:
        singer = Singer.objects.create_user(
            name_to_username(first_name, last_name),
            first_name=first_name,
            last_name=last_name,
            is_staff=False,
            no_image_upload=no_image_upload,
            ticket_order=ticket_order,
            selfie=uploaded_image
        )

    except (TicketsDepleted, AlreadyLoggedIn) as e:
        raise TwistApiException(str(e))
    return singer


def _login_existing_singer(first_name, last_name, no_image_upload, uploaded_image):
    try:
        singer = Singer.objects.get(first_name=first_name, last_name=last_name, is_audience=False, selfie=uploaded_image)
        singer.is_active = True
        singer.no_image_upload = no_image_upload
        singer.save()
        Singer.ordering.calculate_positions()
        return singer
    except Singer.DoesNotExist:
        raise TwistApiException("The name that you logged in with previously does not match your current one")


def _login_new_audience(first_name, last_name, no_image_upload, order_id, uploaded_image):
    ticket_order = _get_order(order_id, ATTN_SKU)
    try:
        singer = Singer.objects.create_user(
            name_to_username(first_name, last_name),
            first_name=first_name,
            last_name=last_name,
            is_staff=False,
            is_audience=True,
            ticket_order=ticket_order,
            no_image_upload=no_image_upload,
            selfie=uploaded_image
        )
    except (TicketsDepleted, AlreadyLoggedIn) as e:
        raise TwistApiException(str(e))
    return singer


def  _login_existing_audience(first_name, last_name, no_image_upload, uploaded_image):
    try:
        audience = Singer.objects.get(first_name=first_name, last_name=last_name, is_audience=True, selfie=uploaded_image)
        audience.is_active = True
        audience.no_image_upload = no_image_upload
        audience.save()
        return audience
    except Singer.DoesNotExist:
        raise TwistApiException("The name that you logged in with previously does not match your current one")


def login(request):
    # This is the root endpoint. If already logged in, go straight to home.
    constants_chosen = bool(config.PASSCODE) and bool(config.EVENT_SKU)
    if constants_chosen and request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        try:
            ticket_type = request.POST['ticket-type']
            first_name = _sanitize_string(request.POST['first-name'])
            last_name = _sanitize_string(request.POST['last-name'])
            logged_in = request.POST.get('logged-in') == 'on'
            passcode = _sanitize_string(request.POST['passcode'])
            order_id = request.POST['order-id']
            no_image_upload = request.POST.get('no-upload') == 'on'
            photo = request.FILES.get('upload-image')
            selfie = request.FILES.get('upload-selfie')

            uploaded_image = photo or selfie

            if passcode.lower() != config.PASSCODE.lower():
                raise TwistApiException("Wrong passcode - Shani will reveal tonight's passcode at the event")

            if ticket_type == 'audience':
                audience = _login_existing_audience(first_name, last_name, no_image_upload, uploaded_image) if logged_in else (
                    _login_new_audience(first_name, last_name, no_image_upload, order_id, uploaded_image))
                auth_login(request, audience)
                return JsonResponse({'success': True}, status=200)

            elif ticket_type == 'singer':
                singer = _login_existing_singer(first_name, last_name, no_image_upload, uploaded_image) if logged_in else (
                    _login_new_singer(first_name, last_name, no_image_upload, order_id, uploaded_image))
                auth_login(request, singer)
                return JsonResponse({'success': True}, status=200)
            else:
                raise TwistApiException("Invalid ticket type")

        except Exception as e:
            logger.exception("Exception: ")
            if isinstance(e, TwistApiException):
                msg = str(e)
            else:
                msg = "An unexpected error occurred (you can blame Alon..) Refreshing the page might help"
            return JsonResponse({'error': msg}, status=400)

    return render(request, 'song_signup/login.html', context={'evening_started': constants_chosen})


@bwt_login_required('login', singer_only=True)
def delete_song(request, song_pk):
    SongRequest.objects.filter(pk=song_pk).delete()
    Singer.ordering.calculate_positions()
    return HttpResponse()


@superuser_required('login')
def reset_database(request):
    call_command('dbbackup')
    call_command('reset_db')
    disable_flag('CAN_SIGNUP')
    disable_flag('STARTED')
    config.PASSCODE = ''
    config.DRINKING_WORDS = ''
    return redirect('admin/song_signup/songrequest')


@superuser_required('login')
def enable_signup(request):
    enable_flag('CAN_SIGNUP')
    Singer.ordering.calculate_positions()
    return redirect('admin/song_signup/songrequest')


@superuser_required('login')
def disable_signup(request):
    disable_flag('CAN_SIGNUP')
    config.PASSCODE = ''  # So it won't appear in live lyrics at the end of the evening.
    Singer.ordering.calculate_positions()
    return redirect('admin/song_signup/songrequest')


def signup_disabled(request):
    return JsonResponse({"result": flag_disabled('CAN_SIGNUP')})


@superuser_required('login')
def start_evening(request):
    enable_flag('STARTED')
    return redirect('admin/song_signup/songrequest')


@superuser_required('login')
def end_evening(request):
    disable_flag('STARTED')
    return redirect('admin/song_signup/songrequest')


@superuser_required('login')
def start_boho(request):
    enable_flag('BOHO')
    return redirect('admin/song_signup/songrequest')


@superuser_required('login')
def stop_boho(request):
    disable_flag('BOHO')
    return redirect('admin/song_signup/songrequest')


def evening_started(request):
    return JsonResponse({"started": flag_enabled('STARTED')})


def boho_started(request):
    return JsonResponse({"boho": flag_enabled('BOHO')})


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
        order_id, event_sku, event_name, num_tickets, ticket_type, first_name, last_name, phone_number = row
        orders.add(order_id)
        num_ticket_orders += 1

        ticket_order, created = TicketOrder.objects.get_or_create(
            order_id=order_id,
            event_sku=event_sku,
            ticket_type=ticket_type,
            event_name=event_name,
            num_tickets=num_tickets,
            customer_name=' '.join([first_name, last_name]),
            phone_number=phone_number
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
