from django.db.models import (
    Model, CharField, TimeField, ManyToManyField, BooleanField
)


class Singer(Model):
    first_name = CharField(max_length=20)
    last_name = CharField(max_length=30)

    class Meta:
        unique_together = ['first_name', 'last_name']

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


class SongRequest(Model):
    song_name = CharField(max_length=50)
    musical = CharField(max_length=50)
    request_time = TimeField(auto_now_add=True)
    performance_time = TimeField(default=None)
    singers = ManyToManyField(Singer, related_name='song_requests')

