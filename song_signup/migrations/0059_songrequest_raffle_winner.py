# Generated by Django 3.1.2 on 2025-05-31 20:02

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('song_signup', '0058_songrequest_standby'),
    ]

    operations = [
        migrations.AddField(
            model_name='songrequest',
            name='raffle_winner',
            field=models.BooleanField(default=False),
        ),
    ]
