#!/bin/bash
echo -e "\033[0;31mThis will reset all config values. Re-add them now so People's Choice site will keep working.\033[0m"
git pull

docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.prod.yml build

if [ "$1" = "init" ]; then
    INIT=true docker compose -f docker-compose.prod.yml up -d
else
    docker compose -f docker-compose.prod.yml up -d
fi
