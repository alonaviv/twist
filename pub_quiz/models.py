from django.db import models
from django.core.exceptions import ValidationError


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
    password = models.CharField(
        max_length=128,
        blank=True,
        help_text='Password required to open this round link.',
    )

    class Meta:
        ordering = ['round_number']
        verbose_name = 'Round link'
        verbose_name_plural = 'Round links'

    def __str__(self):
        return f'Round {self.round_number}'

    def clean(self):
        super().clean()
        has_url = bool(self.url)
        has_password = bool(self.password)
        # Either both set or both empty
        if has_url != has_password:
            raise ValidationError('You must either set BOTH URL and password, or leave BOTH empty for each round.')
