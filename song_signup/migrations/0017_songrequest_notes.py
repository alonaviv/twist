# Generated by Django 3.1.2 on 2022-08-27 13:30

import django.contrib.postgres.fields.citext
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('song_signup', '0016_auto_20220716_1207'),
    ]

    operations = [
        migrations.AddField(
            model_name='songrequest',
            name='notes',
            field=django.contrib.postgres.fields.citext.CITextField(default='', max_length=1000),
            preserve_default=False,
        ),
    ]
