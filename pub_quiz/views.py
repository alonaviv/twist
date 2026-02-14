from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json

from .models import Round


def home(request):
    """
    Landing page for the Pub Quiz event. Round buttons use URLs from admin.
    """
    rounds = list(Round.objects.all().order_by('round_number'))
    # Map by round number
    round_by_number = {r.round_number: r for r in rounds}
    round_links = []
    for i in range(1, 7):
        r = round_by_number.get(i)
        configured = bool(r and r.url and r.password)
        round_links.append({'number': i, 'configured': configured})

    return render(request, 'pub_quiz/home.html', {'round_links': round_links})


def round_no_link(request, round_number=None):
    """
    Shown when a round button has no link configured. Same look as home, friendly message.
    """
    return render(request, 'pub_quiz/no_link.html', {'round_number': round_number})


@csrf_exempt
def round_check_password(request, round_number):
    """
    JSON endpoint used by the JS prompt to validate the password and get the URL.
    """
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Invalid method'}, status=405)

    try:
        round_obj = Round.objects.get(round_number=round_number)
    except Round.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Round does not exist'}, status=404)

    if not (round_obj.url and round_obj.password):
        return JsonResponse({'ok': False, 'error': 'Round not configured'}, status=400)

    try:
        data = json.loads(request.body.decode() or '{}')
    except ValueError:
        data = {}

    entered = (data.get('password', '') or '').strip().lower()
    expected = ((round_obj.password or '').strip().lower() or None)
    if entered == expected:
        return JsonResponse({'ok': True, 'url': round_obj.url})

    return JsonResponse(
        {'ok': False, 'error': "That's not the right password for this round. Try again!"},
        status=400,
    )

