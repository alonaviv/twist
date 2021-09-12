from django.contrib import admin
from .models import SongRequest


class SongRequestAdmin(admin.ModelAdmin):
    list_display = ('song_name', 'musical', 'request_time', 'singer', 'get_additional_singers')


admin.site.register(SongRequest, SongRequestAdmin)
