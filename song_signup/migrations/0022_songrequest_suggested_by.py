# Generated by Django 3.1.2 on 2022-08-31 21:18

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('song_signup', '0021_auto_20220828_1607'),
    ]

    operations = [
        migrations.AddField(
            model_name='songrequest',
            name='suggested_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='suggested_songs_claimed', to=settings.AUTH_USER_MODEL),
        ),
    ]
