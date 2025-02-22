from rest_framework.serializers import ModelSerializer, SerializerMethodField, CharField, BooleanField
from song_signup.models import Singer, SongRequest, SongLyrics, TriviaQuestion, TriviaResponse, GroupSongRequest
from twist.utils import is_hebrew, format_commas


class SingerSerializer(ModelSerializer):
    class Meta:
        model = Singer
        fields = ['id', 'first_name', 'last_name', 'is_superuser']


class SongRequestSerializer(ModelSerializer):
    singer = SingerSerializer(read_only=True)
    partners = SingerSerializer(many=True, read_only=True)
    partners_str = SerializerMethodField()

    def get_partners_str(self, obj):
        return format_commas([singer.get_full_name() for singer in obj.partners.all()])

    class Meta:
        model = SongRequest
        fields = "__all__"


class SongRequestLineupSerializer(ModelSerializer):
    singers = SerializerMethodField()

    def get_singers(self, obj):
        return format_commas([obj.singer.get_full_name()] + [singer.get_full_name() for singer in obj.partners.all()])

    class Meta:
        model = SongRequest
        fields = ['position', 'singers', 'song_name', 'musical']


class GroupSongRequestLineupSerializer(ModelSerializer):
    singers = CharField(default="Group Song", read_only=True)

    class Meta:
        model = SongRequest
        fields = ['singers', 'song_name', 'musical']


class GroupSongRequestSerializer(ModelSerializer):
    """"
    Used to return the list of suggested group songs, and whether the given user ("singer") voted for each one or not
    """
    voted = SerializerMethodField()

    class Meta:
        model = GroupSongRequest
        fields = ['id', 'song_name', 'musical', 'voted']

    def get_voted(self, obj):
        return bool(obj.singer_votes)

class LyricsSerializer(ModelSerializer):
    is_group_song = SerializerMethodField()

    def get_is_group_song(self, instance):
        return self.context.get('is_group_song', False)

    class Meta:
        model = SongLyrics
        fields = ['song_name', 'artist_name', 'lyrics', 'is_group_song']


class TriviaQuestionSerializer(ModelSerializer):
    winner = SerializerMethodField()
    answer_text = SerializerMethodField()

    def get_winner(self, instance):
        winner = instance.winner
        if winner:
            return winner.get_full_name()
        else:
            return None

    def get_answer_text(self, instance):
        return instance.answer_text

    class Meta:
        model = TriviaQuestion
        fields = ['question', 'choiceA', 'choiceB', 'choiceC', 'choiceD', 'winner', 'answer', 'answer_text', 'image']


class TriviaResponseSerializer(ModelSerializer):
    class Meta:
        model = TriviaResponse
        fields = ['user', 'choice']
