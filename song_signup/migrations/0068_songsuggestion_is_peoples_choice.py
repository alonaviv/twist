
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('song_signup', '0067_songsuggestion_position'),
    ]

    operations = [
        migrations.AddField(
            model_name='songsuggestion',
            name='is_peoples_choice',
            field=models.BooleanField(default=False),
        ),
    ]
