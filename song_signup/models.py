from django.db.models import (
    Model, CharField, TimeField, ForeignKey, CASCADE, ManyToManyField
)
from django.contrib.auth.models import User

User.add_to_class("__str__", lambda self: f'{self.first_name} {self.last_name}')


class SongRequest(Model):
    song_name = CharField(max_length=50)
    musical = CharField(max_length=50)
    request_time = TimeField(auto_now_add=True)
    performance_time = TimeField(default=None, null=True)
    singer = ForeignKey(User, on_delete=CASCADE)
    additional_singers = ManyToManyField(User, blank=True, related_name='songs')

    def get_additional_singers(self):
        return ", ".join([str(singer) for singer in self.additional_singers.all()])

    get_additional_singers.short_description = 'Additional Singers'

    class Meta:
        unique_together = ('song_name', 'musical', 'singer')


