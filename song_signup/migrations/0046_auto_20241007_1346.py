# Generated by Django 3.1.2 on 2024-10-07 13:46

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('song_signup', '0045_triviaquestion_image'),
    ]

    operations = [
        migrations.AlterField(
            model_name='triviaquestion',
            name='image',
            field=models.ImageField(blank=True, null=True, upload_to=''),
        ),
    ]
