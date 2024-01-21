#!/bin/bash
docker compose -f docker-compose.dev.yml down
docker compose -f docker-compose.dev.yml build
docker compose -f docker-compose.dev.yml up -d
docker exec -it twist-django-1 bash -c "./manage.py runserver 0.0.0.0:8000"

