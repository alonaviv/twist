from django.db.models import (
    Model, CharField, DateTimeField, ForeignKey, CASCADE, ManyToManyField, IntegerField,
)
from django.contrib.auth.models import User
from django.contrib.postgres.fields import CITextField

User.add_to_class("__str__", lambda self: f'{self.first_name} {self.last_name}')


class SongRequest(Model):
    song_name = CITextField(max_length=50)
    musical = CITextField(max_length=50)
    request_time = DateTimeField(auto_now_add=True)
    performance_time = DateTimeField(default=None, null=True)
    singer = ForeignKey(User, on_delete=CASCADE)
    additional_singers = ManyToManyField(User, blank=True, related_name='songs')
    priority = IntegerField()

    def get_additional_singers(self):
        return ", ".join([str(singer) for singer in self.additional_singers.all()])

    get_additional_singers.short_description = 'Additional Singers'

    @property
    def was_performed(self):
        return bool(self.performance_time)

    def __str__(self):
        return f"Song request: {self.song_name} by {self.singer}"

    class Meta:
        unique_together = ('song_name', 'musical', 'singer')
        ordering = ['priority']
