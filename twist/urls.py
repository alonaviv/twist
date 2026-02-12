"""twist URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include, reverse
from django.conf.urls.static import static
from django.conf import settings
from constance import config
from django.http import HttpResponseRedirect


def root_router(request):
    """
    Decide what the site root (/) should show based on the configured event type.

    When EVENING_TYPE is 'pub_quiz' we send visitors to the Pub Quiz landing page.
    Otherwise we send them to the open mic login.
    """
    if getattr(config, 'EVENING_TYPE', 'open_mic') == 'pub_quiz':
        return HttpResponseRedirect(reverse('pub_quiz:home'))

    return HttpResponseRedirect(reverse('login'))
urlpatterns = [
    path('admin/', admin.site.urls, name='admin'),
    path('', root_router, name='root'),
    path('', include('song_signup.urls')),
    path('peoples-choice/', include('peoples_choice.urls')),
    path('pub-quiz/', include('pub_quiz.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
