# Generated by Django 3.1.2 on 2025-06-24 11:58

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('song_signup', '0060_auto_20250531_2008'),
    ]

    operations = [
        migrations.AddField(
            model_name='singer',
            name='active_raffle_winner',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='singer',
            name='raffle_participant',
            field=models.BooleanField(default=False),
        ),
    ]
