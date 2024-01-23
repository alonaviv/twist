#!/bin/bash
# If -v is passed to the script, docker volumes will be erased
if [ "$1" == "-v" ]; then
    docker compose -f docker-compose.dev.yml down -v
else
    docker compose -f docker-compose.dev.yml down
fi
