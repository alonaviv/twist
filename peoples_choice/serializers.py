from rest_framework import serializers

from .models import SongSuggestion


class SongSuggestionSerializer(serializers.ModelSerializer):

    class Meta:
        model = SongSuggestion
        fields = (
            'id',
            'song_name',
            'musical',
            'event_sku',
            'votes',
            'chosen',
            'chosen_by',
            'chosen_in_app',
            'created_at',
        )
