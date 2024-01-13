# Broadway With a Twist

This app is a sign up webiste for open mic nights

## Local development setup

Create a python3.10 virtualenv and install requirements

```sh
python3 -m venv .venv
source ./.venv/bin/activate
pip install -r requirements.txt
```

Run local postgres and redis. This can be done with docker

```sh
docker-compose up -d
```

Create postgres db

```sh
psql -h localhost -U twistdbadmin
(password from docker-compose)

create database twist_db;
```

Run migrations and create superuser

```sh
python manage.py migrate
python manage.py createsuperuser
```

Run local server

```sh
python manage.py runserver
```

Go to localhost:8000/admin, sign in as admin, create "singers" group with permissions "song_signup | song request | Can view"
Set passcode in constance settings, and under song requests select "ALLOW MORE SIGNUPS"

Go to localhost:8000, sign in to app as "Alon Aviv", logout, sign is as "Shani Wahrman", logout, sign in normally

To allow downloading lyrics in background task, run a celery worker:

```sh
celery -A twist worker -l INFO
```
