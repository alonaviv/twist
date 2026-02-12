from django.urls import path

from . import views

app_name = 'pub_quiz'

urlpatterns = [
    path('', views.home, name='home'),
    path('round/<int:round_number>/check/', views.round_check_password, name='round_check_password'),
    path('no-link/', views.round_no_link, name='round_no_link'),
    path('no-link/<int:round_number>/', views.round_no_link, name='round_no_link_number'),
]

