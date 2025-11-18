from django.shortcuts import get_object_or_404, render
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from titlecase import titlecase
from constance import config

from .models import SongSuggestion
from .serializers import SongSuggestionSerializer

DEV_EVENT_DATE = 'January 5, 2025'
DEV_SONG_SUGGESTIONS = [
    {'id': 1, 'title': 'Defying Gravity', 'show': 'Wicked', 'votes': 128},
    {'id': 2, 'title': 'One Day More', 'show': 'Les Misérables', 'votes': 114},
    {'id': 3, 'title': 'Wait For It', 'show': 'Hamilton', 'votes': 102},
    {'id': 4, 'title': "Don't Rain on My Parade", 'show': 'Funny Girl', 'votes': 96},
    {'id': 5, 'title': 'She Used to Be Mine', 'show': 'Waitress', 'votes': 92},
    {'id': 6, 'title': 'The Schuyler Sisters', 'show': 'Hamilton', 'votes': 88},
    {'id': 7, 'title': 'Waving Through a Window', 'show': 'Dear Evan Hansen', 'votes': 86},
    {'id': 8, 'title': "You'll Be Back", 'show': 'Hamilton', 'votes': 83},
    {'id': 9, 'title': 'Guns and Ships', 'show': 'Hamilton', 'votes': 79},
    {'id': 10, 'title': 'Gimme Gimme', 'show': 'Thoroughly Modern Millie', 'votes': 75},
    {'id': 11, 'title': 'Corner of the Sky', 'show': 'Pippin', 'votes': 74},
    {'id': 12, 'title': 'Maybe This Time', 'show': 'Cabaret', 'votes': 72},
    {'id': 13, 'title': 'The Wizard and I', 'show': 'Wicked', 'votes': 68},
    {'id': 14, 'title': 'My Shot', 'show': 'Hamilton', 'votes': 65},
    {'id': 15, 'title': 'Losing My Mind', 'show': 'Follies', 'votes': 61},
    {'id': 16, 'title': 'Satisfied', 'show': 'Hamilton', 'votes': 58},
    {'id': 17, 'title': 'Astonishing', 'show': 'Little Women', 'votes': 54},
    {'id': 18, 'title': 'No One Else', 'show': 'Natasha, Pierre & The Great Comet of 1812', 'votes': 51},
    {'id': 19, 'title': 'Being Alive', 'show': 'Company', 'votes': 48},
    {'id': 20, 'title': 'I’m Here', 'show': 'The Color Purple', 'votes': 45},
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
                'title': titlecase(song['title']),
                'show': titlecase(song['show']),
                'votes': song['votes'],
            }
            for song in DEV_SONG_SUGGESTIONS
        ]
        event_date = DEV_EVENT_DATE
    
    return Response(
        {'event_date': event_date, 'songs': songs_data},
        status=status.HTTP_200_OK,
    )


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
        ).exclude(pk=pk).update(chosen=False, chosen_by='')
        
        # Choose this song
        song.chosen = True
        song.chosen_by = chosen_by
        song.save()
    elif action == 'unchoose':
        # Only unchoose if this song was chosen by the same person
        if song.chosen and song.chosen_by == chosen_by:
            song.chosen = False
            song.chosen_by = ''
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
