# Generated by Django 3.1.2 on 2024-10-07 05:44

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('song_signup', '0044_singer_is_audience'),
    ]

    operations = [
        migrations.AddField(
            model_name='triviaquestion',
            name='image',
            field=models.ImageField(blank=True, null=True, upload_to='trivia-questions/'),
        ),
    ]