from django.urls import path
from . import views

urlpatterns = [
    path('', views.login, name='login'),
    path('login', views.login, name='login'),
    path('home', views.home, name='home'),
    path('home/<str:new_song>', views.home, name='home'),
    path('dashboard_data', views.dashboard_data, name='dashboard_data'),
    path('faq', views.faq, name='faq'),
    path('tip_us', views.tip_us, name='tip_us'),
    path('logout', views.logout, name='logout'),
    path('manage_songs', views.manage_songs, name='manage_songs'),
    path('add_song_request', views.add_song_request, name='add_song_request'),
    path('get_current_songs', views.get_current_songs, name='get_current_songs'),
    path('delete_song/<int:song_pk>', views.delete_song, name='delete_song'),
    path('get_song/<int:song_pk>', views.get_song, name='get_song'),
    path('reset_database', views.reset_database, name='reset_database'),
    path('enable_signup', views.enable_signup, name='enable_signup'),
    path('disable_signup', views.disable_signup, name='disable_signup'),
    path('signup_disabled', views.signup_disabled, name='signup_disabled'),
    path('recalculate_priorities', views.recalculate_priorities, name='recalculate_priorities'),
]
