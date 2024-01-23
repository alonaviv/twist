#!/bin/bash
docker compose -f docker-compose.dev.yml down
docker compose -f docker-compose.makemigrations.yml up
