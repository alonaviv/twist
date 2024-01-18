#!/bin/bash
git pull

docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.prod.yml build

if [ "$1" = "init" ]; then
    INIT=true docker compose -f docker-compose.prod.yml up -d
else
    docker compose -f docker-compose.prod.yml up -d
fi
