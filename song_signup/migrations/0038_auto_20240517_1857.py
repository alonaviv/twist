# Generated by Django 3.1.2 on 2024-05-17 18:57

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('song_signup', '0037_groupsongrequest_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='groupsongrequest',
            name='default_lyrics',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='groupsongrequest',
            name='found_music',
            field=models.BooleanField(default=False),
        ),
    ]