from datetime import datetime
from itertools import cycle
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.db import IntegrityError
from django.shortcuts import render, redirect, HttpResponse

from .forms import SingerForm, SongRequestForm
from .models import SongRequest


def _name_to_username(first_name, last_name):
    return f'{first_name.lower()}_{last_name.lower()}'


def get_all_songs(singer):
    songs_as_main_singer = singer.songrequest_set.all()
    songs_as_additional_singer = singer.songs.all()
    return songs_as_main_singer | songs_as_additional_singer


def get_all_songs_performed(singer):
    return get_all_songs(singer).exclude(performance_time=None)


def get_num_songs_performed(singer):
    return get_all_songs_performed(singer).count()


def get_how_long_waiting(singer):
    ordered_songs_performed = get_all_songs_performed(singer).order_by('-performance_time')

    if ordered_songs_performed:
        time_waiting = datetime.now() - datetime.combine(datetime.now(), ordered_songs_performed[0].performance_time)
    else:
        time_waiting = datetime.utcnow() - singer.date_joined.replace(tzinfo=None)

    return time_waiting.total_seconds()


def get_singers_next_songs(singer):
    return list(get_all_songs(singer).filter(performance_time=None).order_by('-request_time'))


def calculate_singer_priority(singer):
    return pow(4, 1 / (get_num_songs_performed(singer) + 1)) * get_how_long_waiting(singer)


def assign_song_priorities():
    current_priority = 1
    singer_queryset = User.objects.all()

    singers_dict = dict()
    for singer in singer_queryset:
        singer.priority = calculate_singer_priority(singer)
        next_songs = get_singers_next_songs(singer)
        for song in next_songs:
            song.priority = 0
            song.save()
        singers_dict[singer.username] = next_songs

    prioritized_singers = [singer.username for singer in sorted(singer_queryset, key=lambda singer: singer.priority,
                                                                reverse=True)]
    print("Singer priority is", prioritized_singers)
    for singer_username in cycle(prioritized_singers):
        if not singers_dict:
            break

        if singer_username not in singers_dict:
            continue

        if not singers_dict[singer_username]:
            del singers_dict[singer_username]
            continue

        song = singers_dict[singer_username].pop()
        if not SongRequest.objects.get(pk=song.pk).priority:
            song.priority = current_priority
            current_priority += 1
            song.save()


def song_signup(request):
    current_user = request.user

    if not current_user.is_authenticated:
        return redirect('singer_login')

    if request.method == 'POST':
        form = SongRequestForm(request.POST, request=request)

        if form.is_valid():
            song_name = form.cleaned_data['song_name']
            musical = form.cleaned_data['musical']
            additional_singers = form.cleaned_data['additional_singers']
            song_request = SongRequest(song_name=song_name, musical=musical, singer=current_user)
            song_request.priority = 0

            try:
                song_request.save()
                song_request.additional_singers.set(additional_singers)
                song_request.save()
                assign_song_priorities()
                return HttpResponse("You are all signed up!")

            except IntegrityError:
                messages.error(request, "You already signed up with this song tonight.")
                return render(request, 'song_signup/song_signup.html', {'form': form})

    else:
        form = SongRequestForm(request=request)

    return render(request, 'song_signup/song_signup.html', {'form': form})


def singer_login(request, is_switching):
    if request.user.is_authenticated and not request.user.is_anonymous and not is_switching:
        return redirect('song_signup')

    if request.method == 'POST':
        form = SingerForm(request.POST)

        if form.is_valid():
            first_name = form.cleaned_data['first_name']
            last_name = form.cleaned_data['last_name']
            already_logged_in = form.cleaned_data['i_already_logged_in_tonight']

            if already_logged_in:
                try:
                    singer = User.objects.get(first_name=first_name, last_name=last_name)
                except User.DoesNotExist:
                    messages.error(request, "The name that you logged in with previously does not match your current "
                                            "name.\nCould there be a typo somewhere?")
                    return render(request, 'song_signup/singer_login.html', {'form': form})
            else:
                try:
                    singer = User.objects.create_user(
                        _name_to_username(first_name, last_name),
                        first_name=first_name,
                        last_name=last_name
                    )
                except IntegrityError:
                    messages.error(request, "The name that you're trying to login with already exists.\n"
                                            "Did you already login with us tonight? If so, check the box below.")
                    return render(request, 'song_signup/singer_login.html', {'form': form})

            login(request, singer)
            return redirect('song_signup')

    else:
        form = SingerForm()

    return render(request, 'song_signup/singer_login.html', {'form': form})
