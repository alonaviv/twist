from rest_framework import serializers

from .models import SongSuggestion


class SongSuggestionSerializer(serializers.ModelSerializer):
    title = serializers.CharField(source='song_name', read_only=True)
    show = serializers.CharField(source='musical', read_only=True)

    class Meta:
        model = SongSuggestion
        fields = (
            'id',
            'title',
            'show',
            'song_name',
            'musical',
            'event_sku',
            'votes',
            'chosen',
            'chosen_by',
            'created_at',
        )
