# Generated by Django 3.1.2 on 2025-07-12 11:14

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('song_signup', '0062_auto_20250712_1048'),
    ]

    operations = [
        migrations.RenameField(
            model_name='triviaquestion',
            old_name='question_font_size',
            new_name='question_font_size_mobile',
        ),
        migrations.AddField(
            model_name='triviaquestion',
            name='question_font_size_live_lyrics',
            field=models.IntegerField(default=60),
        ),
    ]
