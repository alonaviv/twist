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

Run script to setup postgres admin, users, and put the site into a working state
```sh
./dev_setup.py
```

Run local server

```sh
python manage.py runserver
```

To allow downloading lyrics in background task, run a celery worker:

```sh
celery -A twist worker -l INFO
```
