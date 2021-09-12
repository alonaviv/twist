from django.contrib.auth.models import User
from django.forms import (
    Form, CharField, BooleanField, ModelMultipleChoiceField
)


class SingerForm(Form):
    first_name = CharField(max_length=20)
    last_name = CharField(max_length=30)
    i_already_logged_in_tonight = BooleanField(initial=False, required=False)


class SongRequestForm(Form):
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request")
        super().__init__(*args, **kwargs)
        self.fields['additional_singers'].queryset = User.objects.all().exclude(pk=self.request.user.pk)

    song_name = CharField(max_length=50)
    musical = CharField(max_length=50)
    additional_singers = ModelMultipleChoiceField(queryset=None,
                                                  required=False)
