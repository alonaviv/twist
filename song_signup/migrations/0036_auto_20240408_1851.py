# Generated by Django 3.1.2 on 2024-04-08 18:51

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('song_signup', '0035_auto_20240408_1823'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='groupsongrequest',
            name='default_lyrics',
        ),
        migrations.RemoveField(
            model_name='groupsongrequest',
            name='found_music',
        ),
    ]