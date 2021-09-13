from django.urls import path
from . import views

urlpatterns = [
    path('', views.singer_login, {'is_switching': False}, name='singer_login'),
    path('switch_singer', views.singer_login, {'is_switching': True}, name='switch_singer'),
    path('song_signup', views.song_signup, name='song_signup'),
    path('delete_song_request/<int:song_pk>', views.delete_song_request, name='delete_song_request')
]
