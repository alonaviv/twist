from django.shortcuts import render
from django.http import HttpResponse
from rest_framework.decorators import api_view


@api_view(["POST"])
def update_transaction(request):
    """
    To be used by the Meshulam API, when a transaction is complete
    """
