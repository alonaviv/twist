from django.urls import path
from . import views

urlpatterns = [
    path('', views.singer_login, {'is_switching': False}, name='singer_login'),
    path('switch_singer', views.singer_login, {'is_switching': True}, name='switch_singer'),
    path('song_signup', views.song_signup, name='song_signup'),
    path('delete_song_request/<int:song_pk>', views.delete_song_request, name='delete_song_request'),
    path('reset_database', views.reset_database, name='reset_database'),
    path('enable_signup', views.enable_signup, name='enable_signup'),
    path('disable_signup', views.disable_signup, name='disable_signup'),
    path('recalculate_priorities', views.recalculate_priorities, name='recalculate_priorities'),
]
