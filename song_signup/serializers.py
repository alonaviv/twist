from rest_framework.serializers import ModelSerializer
from song_signup.models import SongSuggestion, Singer, SongRequest


class SingerSerializer(ModelSerializer):
    class Meta:
        model = Singer
        fields = ['id', 'first_name', 'last_name']


class SongSuggestionSerializer(ModelSerializer):
    suggested_by = SingerSerializer(read_only=True)

    class Meta:
        model = SongSuggestion
        fields = "__all__"


class SongRequestSerializer(ModelSerializer):
    singer = SingerSerializer(read_only=True)
    duet_partner = SingerSerializer(read_only=True)

    class Meta:
        model = SongRequest
        fields = "__all__"
