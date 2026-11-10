from django.shortcuts import get_object_or_404, render
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from titlecase import titlecase
from constance import config

from song_signup.models import SongRequest
from song_signup.views import bwt_login_required

from .models import SongSuggestion
from .serializers import SongSuggestionSerializer

DEV_EVENT_DATE = 'January 5, 2025'
DEV_SONG_SUGGESTIONS = [
    {'id': 1, 'song_name': 'Defying Gravity', 'musical': 'Wicked', 'votes': 128},
    {'id': 2, 'song_name': 'One Day More', 'musical': 'Les Misérables', 'votes': 114},
    {'id': 3, 'song_name': 'Wait For It', 'musical': 'Hamilton', 'votes': 102},
    {'id': 4, 'song_name': "Don't Rain on My Parade", 'musical': 'Funny Girl', 'votes': 96},
    {'id': 5, 'song_name': 'She Used to Be Mine', 'musical': 'Waitress', 'votes': 92},
    {'id': 6, 'song_name': 'The Schuyler Sisters', 'musical': 'Hamilton', 'votes': 88},
    {'id': 7, 'song_name': 'Waving Through a Window', 'musical': 'Dear Evan Hansen', 'votes': 86},
    {'id': 8, 'song_name': "You'll Be Back", 'musical': 'Hamilton', 'votes': 83},
    {'id': 9, 'song_name': 'Guns and Ships', 'musical': 'Hamilton', 'votes': 79},
    {'id': 10, 'song_name': 'Gimme Gimme', 'musical': 'Thoroughly Modern Millie', 'votes': 75},
    {'id': 11, 'song_name': 'Corner of the Sky', 'musical': 'Pippin', 'votes': 74},
    {'id': 12, 'song_name': 'Maybe This Time', 'musical': 'Cabaret', 'votes': 72},
    {'id': 13, 'song_name': 'The Wizard and I', 'musical': 'Wicked', 'votes': 68},
    {'id': 14, 'song_name': 'My Shot', 'musical': 'Hamilton', 'votes': 65},
    {'id': 15, 'song_name': 'Losing My Mind', 'musical': 'Follies', 'votes': 61},
    {'id': 16, 'song_name': 'Satisfied', 'musical': 'Hamilton', 'votes': 58},
    {'id': 17, 'song_name': 'Astonishing', 'musical': 'Little Women', 'votes': 54},
    {'id': 18, 'song_name': 'No One Else', 'musical': 'Natasha, Pierre & The Great Comet of 1812', 'votes': 51},
    {'id': 19, 'song_name': 'Being Alive', 'musical': 'Company', 'votes': 48},
    {'id': 20, 'song_name': 'I’m Here', 'musical': 'The Color Purple', 'votes': 45},
]


def audience_suggestions_page(request):
    event_date = getattr(config, 'PEOPLES_CHOICE_EVENT_DATE', '')
    event_sku = getattr(config, 'PEOPLES_CHOICE_EVENT_SKU', '')
    is_active = bool(event_date and event_sku)
    
    return render(request, 'peoples_choice/audience_suggestions.html', {
        'is_active': is_active,
        'event_date': event_date,
        'event_sku': event_sku,
    })


@api_view(['POST'])
def create_song_suggestion(request):
    serializer = SongSuggestionSerializer(data=request.data)
    if serializer.is_valid():
        # Check for duplicates before saving
        song_name = titlecase(serializer.validated_data['song_name'])
        musical = titlecase(serializer.validated_data['musical'])
        event_sku = serializer.validated_data['event_sku']
        
        existing = SongSuggestion.objects.filter(
            song_name=song_name,
            musical=musical,
            event_sku=event_sku
        ).first()
        
        if existing:
            return Response(
                {'detail': 'A song with this name and musical already exists for this event.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
def list_song_suggestions(request, event_sku):
    songs = SongSuggestion.objects.filter(event_sku=event_sku).order_by(
        '-votes', '-created_at'
    )
    if not songs.exists():
        return Response(
            {'detail': 'No songs found for this SKU.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    serializer = SongSuggestionSerializer(songs, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['POST'])
def vote_song_suggestion(request, pk):
    song = get_object_or_404(SongSuggestion, pk=pk)
    action = request.data.get('action', 'increment')
    
    if action == 'increment':
        song.increment_votes()
    elif action == 'decrement':
        song.decrement_votes()
    
    serializer = SongSuggestionSerializer(song)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['GET'])
def dev_song_suggestions(_request):
    event_date = getattr(config, 'PEOPLES_CHOICE_EVENT_DATE', '')
    event_sku = getattr(config, 'PEOPLES_CHOICE_EVENT_SKU', '')
    
    # If constants are set, use real data, otherwise use dev data
    if event_date and event_sku:
        songs = SongSuggestion.objects.filter(event_sku=event_sku).order_by(
            '-votes', '-created_at'
        )
        serializer = SongSuggestionSerializer(songs, many=True)
        songs_data = serializer.data
    else:
        # Dev fallback
        songs_data = [
            {
                'id': song['id'],
                'song_name': titlecase(song['song_name']),
                'musical': titlecase(song['musical']),
                'votes': song['votes'],
            }
            for song in DEV_SONG_SUGGESTIONS
        ]
        event_date = DEV_EVENT_DATE
    
    return Response(
        {'event_date': event_date, 'songs': songs_data},
        status=status.HTTP_200_OK,
    )


# The People's Choice website's endpoint. There is no login: chosen_by is the name typed on the site, and its choices
# are website choices (chosen_in_app false). The signup page uses the app endpoints below.
@api_view(['POST'])
def choose_song_suggestion(request, pk):
    action = request.data.get('action', 'choose')  # 'choose' or 'unchoose'
    chosen_by = request.data.get('chosen_by', '')
    
    song = get_object_or_404(SongSuggestion, pk=pk)
    
    if action == 'choose':
        if not chosen_by:
            return Response(
                {'detail': "'chosen_by' is required when choosing a song."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        # Unchoose any previously chosen song by the same singer
        SongSuggestion.objects.filter(
            chosen=True,
            chosen_by=chosen_by,
            event_sku=song.event_sku
        ).exclude(pk=pk).update(chosen=False, chosen_by='', chosen_in_app=False)
        
        # Choose this song
        song.chosen = True
        song.chosen_by = chosen_by
        song.chosen_in_app = False
        song.save()
    elif action == 'unchoose':
        # Only unchoose if this song was chosen by the same person
        if song.chosen and song.chosen_by == chosen_by:
            song.chosen = False
            song.chosen_by = ''
            song.chosen_in_app = False
            song.save()
        elif song.chosen:
            return Response(
                {'detail': 'This song was chosen by someone else.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
    else:
        return Response(
            {'detail': "Invalid action. Use 'choose' or 'unchoose'."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    serializer = SongSuggestionSerializer(song)
    return Response(serializer.data, status=status.HTTP_200_OK)


# The signup page's endpoints, for what other singers see. When a singer taps "I'll sing this!" (or types a list song),
# her People's Choice card shows "Chosen by you!" and her "Your song" card shows the song. Both come from her signup
# form, kept in the browser's sessionStorage, never from here. These endpoints only make every other singer's list show
# that card at the bottom as "Chosen by <her name>", so they don't pick it too.
# Whenever her form's song changes, the page calls set with the new list song, which unchooses her previous one, or
# clear when it's no list song. A song someone else already chose stays theirs.
# Once she has a song in the lineup, both do nothing. When she comes back to the signup page for a second song, the song
# she signed up with stays "Chosen by <her name>" for the night, and the second song she picks isn't shown as chosen to
# anyone else: second songs are rarely sung, so two singers picking the same one is left as a regular duplicate.

def _clear_app_choices(singer, keep_pk=None):
    SongSuggestion.objects.filter(
        event_sku=config.PEOPLES_CHOICE_EVENT_SKU, chosen=True, chosen_by=singer.get_full_name(), chosen_in_app=True,
    ).exclude(pk=keep_pk).update(chosen=False, chosen_by='', chosen_in_app=False)


@bwt_login_required('login', singer_only=True)
@api_view(['POST'])
def set_app_peoples_choice_selection(request, pk):
    """Chooses this song for the singer, unless someone else already chose it, and unchooses her other app choices."""
    try:
        song = SongSuggestion.objects.get(pk=pk)
    except SongSuggestion.DoesNotExist:
        return Response({'error': f"Song suggestion with ID {pk} does not exist"}, status=status.HTTP_400_BAD_REQUEST)
    # Already signed up: the song she signed up with keeps its choice, and a second song gets none
    if not SongRequest.objects.filter(singer=request.user).exists():
        _clear_app_choices(request.user, keep_pk=pk)
        if not song.chosen:
            song.chosen = True
            song.chosen_by = request.user.get_full_name()
            song.chosen_in_app = True
            song.save()
    return Response(status=status.HTTP_204_NO_CONTENT)


@bwt_login_required('login', singer_only=True)
@api_view(['POST'])
def clear_app_peoples_choice_selection(request):
    """Unchooses the singer's app choices: her form holds no People's Choice song."""
    # Already signed up: the song she signed up with keeps its choice, and a second song gets none
    if not SongRequest.objects.filter(singer=request.user).exists():
        _clear_app_choices(request.user)
    return Response(status=status.HTTP_204_NO_CONTENT)
