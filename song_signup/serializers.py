from rest_framework.serializers import ModelSerializer, SerializerMethodField, CharField
from song_signup.models import SongSuggestion, Singer, SongRequest, SongLyrics, TriviaQuestion, TriviaResponse
from twist.utils import is_hebrew, format_commas


class SingerSerializer(ModelSerializer):
    class Meta:
        model = Singer
        fields = ['id', 'first_name', 'last_name', 'is_superuser']


class SongSuggestionSerializer(ModelSerializer):
    suggested_by = SingerSerializer(read_only=True)

    class Meta:
        model = SongSuggestion
        fields = "__all__"


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
        fields = ['question', 'choiceA', 'choiceB', 'choiceC', 'choiceD', 'winner', 'answer', 'answer_text', 'image',
                  'question_font_size', 'choices_font_size']


class TriviaResponseSerializer(ModelSerializer):
    class Meta:
        model = TriviaResponse
        fields = ['user', 'choice']


class RaffleWinnerSerializer(ModelSerializer):
    full_name = SerializerMethodField()

    def get_full_name(self, instance):
        return instance.get_full_name()

    class Meta:
        model = Singer
        fields = ['id', 'full_name']
