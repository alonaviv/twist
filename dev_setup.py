#!/usr/bin/env python
import subprocess
import os
import django
import constance
from django.core.management import call_command
from django.contrib.auth import get_user_model
from flags.state import enable_flag

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "twist.settings")
django.setup()
from song_signup.views import name_to_username
from django.contrib.auth.models import Group, Permission

PG_USER = 'twistdbadmin'
PG_PASSWORD = '76697421'
ALON_USER = ('Alon', 'Aviv', '76697421')
SHANI_USER = ('Shani', 'Wahrman', '76697421')


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
    try:
        result = subprocess.run(f"PGPASSWORD={PG_PASSWORD} psql -U {PG_USER} -h localhost -c \"CREATE DATABASE twist_db\"",
                                shell=True, check=True, text=True, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as e:
        if 'already exists' in e.stderr:
            pass
        else:
            raise

    call_command('migrate')
    create_superuser(*ALON_USER)
    create_superuser(*SHANI_USER)

    singers_group, _ = Group.objects.get_or_create(name='singers')
    singers_group.permissions.add(Permission.objects.get(codename='view_songrequest'))
    constance.config.PASSCODE = 'dev'
    enable_flag('CAN_SIGNUP')
