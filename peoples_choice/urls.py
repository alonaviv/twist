from django.urls import path
from . import views

app_name = 'peoples_choice'
urlpatterns = [
    path('', views.audience_suggestions_page, name='audience_suggestions'),
    path('dev-song-suggestions/', views.dev_song_suggestions, name='dev_song_suggestions'),
    path('current_event', views.current_event, name='current_event'),
    path('create_song_suggestion', views.create_song_suggestion, name='create_song_suggestion'),
    path('list_song_suggestions/<str:event_sku>', views.list_song_suggestions, name='list_song_suggestions'),
    path('vote_song_suggestion/<int:pk>/', views.vote_song_suggestion, name='vote_song_suggestion'),
    path('choose_song_suggestion/<int:pk>/', views.choose_song_suggestion, name='choose_song_suggestion'),
    path('set_app_peoples_choice_selection/<int:pk>/', views.set_app_peoples_choice_selection,
         name='set_app_peoples_choice_selection'),
    path('clear_app_peoples_choice_selection/', views.clear_app_peoples_choice_selection,
         name='clear_app_peoples_choice_selection'),
]

