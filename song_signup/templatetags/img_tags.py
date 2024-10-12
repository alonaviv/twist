from django import template
from django.conf import settings

register = template.Library()


@register.simple_tag
def bwt_small_logo():
    if settings.DISNEY_EVENT:
        logo_name = 'mickey-ears-logo.png'
    else:
        logo_name = 'logo.png'

    return f'{settings.STATIC_URL}/img/{logo_name}'

@register.simple_tag
def bwt_big_logo():
    if settings.DISNEY_EVENT:
        logo_name = 'minnie-ears-logo.png'
    else:
        logo_name = 'logo.png'

    return f'{settings.STATIC_URL}/img/{logo_name}'
