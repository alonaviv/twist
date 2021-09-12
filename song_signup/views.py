from django.shortcuts import render, redirect, HttpResponse
from django.contrib.auth.models import User
from django.contrib.auth import login
from django.contrib import messages
from django.db import IntegrityError
from .forms import SingerForm, SongRequestForm
from .models import SongRequest


def _name_to_username(first_name, last_name):
    return f'{first_name.lower()}_{last_name.lower()}'


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
            try:
                song_request.save()
                song_request.additional_singers.set(additional_singers)
                song_request.save()
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
                    user = User.objects.get(first_name=first_name, last_name=last_name)
                except User.DoesNotExist:
                    messages.error(request, "The name that you logged in with previously does not match your current "
                                            "name.\nCould there be a typo somewhere?")
                    return render(request, 'song_signup/singer_login.html', {'form': form})
            else:
                try:
                    user = User.objects.create_user(
                        _name_to_username(first_name, last_name),
                        first_name=first_name,
                        last_name=last_name
                    )
                except IntegrityError:
                    messages.error(request, "The name that you're trying to login with already exists.\n"
                                   "Did you already login with us tonight? If so, check the box below.")
                    return render(request, 'song_signup/singer_login.html', {'form': form})

            login(request, user)
            return redirect('song_signup')

    else:
        form = SingerForm()

    return render(request, 'song_signup/singer_login.html', {'form': form})


