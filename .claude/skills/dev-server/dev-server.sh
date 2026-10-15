#!/bin/bash
# Start, stop and inspect the twist Django dev server inside the docker stack.
# Driven by the dev-server skill; also fine to run by hand.

set -uo pipefail

PROJECT=/home/ubuntu/twist
CONTAINER=twist-django-1
COMPOSE="$PROJECT/docker-compose.dev.yml"
LOG="$PROJECT/twist-logs/runserver.log"

# The public IP changes on every stop/start, so ask EC2's instance metadata for the current one.
dev_url() {
    local token ip
    token=$(curl -s --max-time 2 -X PUT http://169.254.169.254/latest/api/token \
        -H "X-aws-ec2-metadata-token-ttl-seconds: 60")
    ip=$(curl -s --max-time 2 -H "X-aws-ec2-metadata-token: $token" \
        http://169.254.169.254/latest/meta-data/public-ipv4)
    [ -n "$ip" ] || ip=$(hostname -I | awk '{print $1}')
    echo "http://$ip:8000/"
}

container_up() {
    docker ps --format '{{.Names}}' 2>/dev/null | grep -qx "$CONTAINER"
}

server_up() {
    curl -s --max-time 3 -o /dev/null http://127.0.0.1:8000/
}

# On a cold boot sshd can answer before docker has finished starting the stack,
# so give restart:always a chance rather than reporting the stack as down.
require_container() {
    container_up && return 0
    for _ in $(seq 15); do
        sleep 2
        container_up && return 0
    done
    echo "twist: dev stack is down. Bring it up with: docker compose -f $COMPOSE up -d"
    return 1
}

cmd_start() {
    require_container || return 1
    if server_up; then
        echo "twist: Django already running at $(dev_url)"
        return 0
    fi
    docker exec -d "$CONTAINER" sh -c "./manage.py runserver 0.0.0.0:8000 > /twist/twist-logs/runserver.log 2>&1"
    for _ in $(seq 20); do
        if server_up; then
            echo "twist: started Django at $(dev_url)"
            return 0
        fi
        sleep 0.5
    done
    echo "twist: Django did not come up within 10s. Check $LOG"
    return 1
}

cmd_stop() {
    require_container || return 1
    if ! server_up; then
        echo "twist: Django is not running"
        return 0
    fi
    docker exec "$CONTAINER" pkill -f "manage.py runserver" >/dev/null 2>&1
    for _ in $(seq 10); do
        sleep 0.5
        server_up || { echo "twist: stopped Django"; return 0; }
    done
    echo "twist: Django still answering on :8000 after stop. Check $LOG"
    return 1
}

cmd_restart() {
    cmd_stop || return 1
    cmd_start
}

cmd_status() {
    if ! container_up; then
        echo "twist: dev stack is down ($CONTAINER not running)"
        return 0
    fi
    if server_up; then
        echo "twist: Django running at $(dev_url)"
    else
        echo "twist: stack is up, Django is not running"
    fi
}

cmd_logs() {
    tail -n "${1:-50}" "$LOG"
}

case "${1:-status}" in
    start)   cmd_start ;;
    stop)    cmd_stop ;;
    restart) cmd_restart ;;
    status)  cmd_status ;;
    logs)    cmd_logs "${2:-50}" ;;
    *)       echo "usage: dev-server.sh {start|stop|restart|status|logs [n]}"; exit 2 ;;
esac
