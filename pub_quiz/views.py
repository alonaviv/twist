from django.shortcuts import render

from .models import Round


def home(request):
    """
    Landing page for the Pub Quiz event. Round buttons use URLs from admin.
    """
    rounds = list(Round.objects.all().order_by('round_number'))
    # Ensure we have 6 slots (1–6); missing rounds get empty url
    round_by_number = {r.round_number: r for r in rounds}
    round_links = [
        {'number': i, 'url': round_by_number[i].url if i in round_by_number else ''}
        for i in range(1, 7)
    ]
    return render(request, 'pub_quiz/home.html', {'round_links': round_links})


def round_no_link(request, round_number=None):
    """
    Shown when a round button has no link configured. Same look as home, friendly message.
    """
    return render(request, 'pub_quiz/no_link.html', {'round_number': round_number})

