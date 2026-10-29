#!/bin/bash
echo -e "\033[0;31mThis will reset all config values. Re-add them now so People's Choice site will keep working.\033[0m"
# The People's Choice values to re-add, read from the running site before it goes down (there is none on init)
if [ "$1" != "init" ]; then
    docker compose -f docker-compose.prod.yml exec -T django python manage.py shell -c \
        "from constance import config; print('PEOPLES_CHOICE_EVENT_DATE:', config.PEOPLES_CHOICE_EVENT_DATE); print('PEOPLES_CHOICE_EVENT_SKU:', config.PEOPLES_CHOICE_EVENT_SKU)"
fi
sudo -u ubuntu git pull

docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.prod.yml build

if [ "$1" = "init" ]; then
    INIT=true docker compose -f docker-compose.prod.yml up -d
else
    docker compose -f docker-compose.prod.yml up -d
fi
