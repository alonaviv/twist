from django.db import models
from titlecase import titlecase


class SongSuggestion(models.Model):
    song_name = models.CharField(max_length=255)
    musical = models.CharField(max_length=255)
    event_sku = models.CharField(max_length=128)
    votes = models.PositiveIntegerField(default=0)
    chosen = models.BooleanField(default=False)
    chosen_by = models.CharField(max_length=255, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-votes', '-created_at')

    def __str__(self):
        return f"{self.song_name} ({self.event_sku})"

    def save(self, *args, **kwargs):
        self.song_name = titlecase(self.song_name)
        self.musical = titlecase(self.musical)
        super().save(*args, **kwargs)

    def increment_votes(self):
        self.votes += 1
        self.save()

    def decrement_votes(self):
        if self.votes > 0:
            self.votes -= 1
        self.save()
