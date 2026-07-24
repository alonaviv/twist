from django.urls import path

from . import views

app_name = 'explanations'
urlpatterns = [
    path('singer-tickets/', views.singer_tickets, name='singer_tickets'),
]
