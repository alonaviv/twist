# Generated by Django 3.2.13 on 2022-06-01 23:15

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('song_signup', '0007_songrequest_cycle'),
    ]

    operations = [
        migrations.AddField(
            model_name='songrequest',
            name='is_bonus',
            field=models.BooleanField(default=False),
        ),
    ]