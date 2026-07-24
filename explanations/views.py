from django.shortcuts import render

PRACTICE_TICKETS_URL = 'https://tic.li/gBqLGKy'


def singer_tickets(request):
    return render(request, 'explanations/singer_tickets.html', {
        'practice_url': PRACTICE_TICKETS_URL,
    })
