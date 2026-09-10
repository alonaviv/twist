# Twist

Django app. The dev stack is docker (`docker-compose.dev.yml`): `twist-django-1`,
`twist-db-1`, `twist-redis-1`, `twist-celery-1`.

## Dev server

```
/dev-server start | stop | restart | status | logs [n]
```

It backgrounds the process, so there is no stdin. For interactive `ipdb`, run
`./run-dev.sh` in a terminal instead.

## Commands run in the container

The repo is bind-mounted at `/twist`, so code edits are live — no rebuild for a change.

```sh
docker exec -it twist-django-1 ./manage.py test song_signup
docker exec -it twist-django-1 ./manage.py <anything else>
```

Migrations: `./makemigrations.sh`, Ctrl-C when done, then `./start-dev.sh` to apply.

## Gotchas

- IMPORTANT: never pass `-v` to `start-dev.sh` or `stop-dev.sh`. It drops the postgres
  volume and the dev database with it.
- Never compile sass on the host — the container runs the watchers, and livereload.
- Log in as a singer with passcode `dev`, order number `123456`.
