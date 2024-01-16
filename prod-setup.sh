#!/bin/bash
python manage.py migrate
gunicorn twist.wsgi:application --bind 0.0.0.0:8000

