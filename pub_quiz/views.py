from django.shortcuts import render


def home(request):
    """
    Simple landing page for the Pub Quiz event.
    """
    return render(request, 'pub_quiz/home.html')

