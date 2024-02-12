from rest_framework.serializers import ModelSerializer, SerializerMethodField
from song_signup.models import SongSuggestion, Singer, SongRequest
from twist.utils import is_hebrew


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


class SongRequestLineupSerializer(ModelSerializer):
    singers = SerializerMethodField()

    def get_singers(self, obj):
        if obj.duet_partner:
            if is_hebrew(obj.duet_partner.get_full_name()):
                connector = 'ו'
            else:
                connector = 'and '

            return f"{obj.singer.get_full_name()} {connector}{obj.duet_partner.get_full_name()}"

        else:
            return obj.singer.get_full_name()

    class Meta:
        model = SongRequest
        fields = ['position', 'singers', 'song_name', 'musical']
