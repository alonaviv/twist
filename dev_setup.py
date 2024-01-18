#!/usr/bin/env python
import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "twist.settings")
django.setup()

import constance
from django.core.management import call_command
from django.contrib.auth import get_user_model
from flags.state import enable_flag

from song_signup.views import name_to_username
from django.contrib.auth.models import Group, Permission

ALON_USER = ('Alon', 'Aviv', os.environ.get('ALON_PASSWORD'))
SHANI_USER = ('Shani', 'Wahrman', os.environ.get('SHANI_PASSWORD'))


def create_superuser(first_name, last_name, password):
    User = get_user_model()
    username = name_to_username(first_name, last_name)
    if not User.objects.filter(username=username).exists():
        User.objects.create_superuser(
            username=username,
            email='',
            password=password,
            first_name=first_name,
            last_name=last_name
        )


if __name__ == '__main__':
    call_command('migrate')
    create_superuser(*ALON_USER)
    create_superuser(*SHANI_USER)

    singers_group, _ = Group.objects.get_or_create(name='singers')
    singers_group.permissions.add(Permission.objects.get(codename='view_songrequest'))
    constance.config.PASSCODE = 'dev'
    enable_flag('CAN_SIGNUP')
