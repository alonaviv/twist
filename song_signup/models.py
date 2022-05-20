from django.contrib.auth.models import User
from django.contrib.postgres.fields import CITextField
from django.db.models import (
    Model, DateTimeField, ForeignKey, CASCADE, ManyToManyField, IntegerField, BooleanField, OneToOneField
)

User.add_to_class("__str__", lambda self: f'{self.first_name} {self.last_name}')


class NoUpload(Model):
    user = OneToOneField(User, on_delete=CASCADE, )
    no_image_upload = BooleanField()


class SongRequest(Model):
    song_name = CITextField(max_length=50)
    musical = CITextField(max_length=50)
    request_time = DateTimeField(auto_now_add=True)
    performance_time = DateTimeField(default=None, null=True, blank=True)
    singer = ForeignKey(User, on_delete=CASCADE)
    additional_singers = ManyToManyField(User, blank=True, related_name='songs')
    priority = IntegerField("Queue Order", blank=True, default=0)

    def get_additional_singers(self):
        return ", ".join([str(singer) for singer in self.additional_singers.all()])

    get_additional_singers.short_description = 'Additional Singers'

    @property
    def was_performed(self):
        return bool(self.performance_time)

    @property
    def all_singers(self):
        return User.objects.filter(pk=self.singer.pk) | self.additional_singers.all()

    def __str__(self):
        return f"Song request: {self.song_name} by {self.singer}"
    
    @property
    def basic_data(self):
        return {'name': self.song_name, 'singer': str(self.singer)}


    class Meta:
        unique_together = ('song_name', 'musical', 'singer')
        ordering = ['priority']
