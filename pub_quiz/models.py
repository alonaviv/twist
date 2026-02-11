from django.db import models


class Round(models.Model):
    """Stores the URL for each pub quiz round (1–6). Edited in admin."""
    round_number = models.PositiveSmallIntegerField(
        unique=True,
        choices=[(i, f'Round {i}') for i in range(1, 7)],
        help_text='Round 1 through 6.',
    )
    url = models.URLField(
        blank=True,
        help_text='Link for this round. Leave blank to keep the button as a placeholder.',
    )

    class Meta:
        ordering = ['round_number']
        verbose_name = 'Round link'
        verbose_name_plural = 'Round links'

    def __str__(self):
        return f'Round {self.round_number}'
