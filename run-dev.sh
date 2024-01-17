#!/bin/bash
docker compose -f docker-compose.dev.yml down
docker volume rm twist_redis twist_db 2> /dev/null
docker compose -f docker-compose.dev.yml build
docker compose -f docker-compose.dev.yml up
