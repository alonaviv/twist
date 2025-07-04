# Broadway With a Twist

This app accompanies the Broadway With a Twist open mic nights. 
It allows singers to sign up for songs, organizes the lineup in a fair manner, 
searches for song lyrics and allows people to suggest individual and group songs.  

## Local development setup

1. Create a python3.10 virtualenv and install requirements (If you want to run directly on host system and not only with docker)
```sh
python3 -m venv .venv
source ./.venv/bin/activate
pip install -r requirements.txt
```

2. Run docker-compose to spin up dev environment. Containers include django, postgres database, redis database, and celery workers. The following script destroys the containers spins them back up, and sets up two superusers (`Alon` and `Shani`) along with all other settings required for running the site. Passing `-v` to the script will destroy the docker volumes as well. 

```sh
./start-dev.sh [-v]
```

3. Run django server in a separate terminal (so you can use pdb interactively):
```shell
./run-dev.sh
```

Django server is now accessible on localhost:8000. Login as a singer with passcod 'dev' and order number '123456'

4. Stop containers in the same way:
```sh
./stop-dev.sh [-v]
```

5. In order to make migrations, run the following script and exit with Ctrl-C when done.
You can then run `start-dev.sh` to apply migrations.
```sh
./makemigrations.sh
```
If make migrations requires interactive input, run `docker exec -it twist-django-1 /bin/bash` while the containers 
are running, and run `./manage.py makemigrations` within the container. Then rerun `start-dev.sh` to apply migrations. 

6. Connect PyCharm to Docker to run tests:
   * Settings -> Python interpreter -> Add interpreter -> On docker-compose.
   * Select Docker service, add `docker-compose.dev.yml` as configuration file, and select `django` container as service.
   * Select python interpreter within the container, and run tests from within IDE.


## Production environment inital setup

1. Verify that docker and docker-compose (version 2) are installed on production host.
2. Run as sudoer user (not root) for improved security.
3. Clone repo to user homedir.
4. Create dir `twist-logs` in project root.
5. Create file `.env` in project root. It should look like this (with real passwords):
```sh
POSTGRES_USER=twistdbadmin
POSTGRES_PASSWORD=123456
EMAIL_HOST_USER=broadwaywithatwist@gmail.com
EMAIL_HOST_PASSWORD=123456
ALON_PASSWORD=123456
SHANI_PASSWORD=123456
```
6. Create file `twist/local_settings.py` in project root with the following content. Replace with relevant server IP and domain name, and use django's get_random_secret_key function to generate a new key: 
```sh
ALLOWED_HOSTS = ['138.68.64.78', 'broadwaywithatwist.xyz', 'www.broadwaywithatwist.xyz']
DOMAIN = 'http://broadwaywithatwist.xyz'
DEBUG=False
SECRET_KEY = xxxxxxxxxxxxxx
```
7. Create dir `/home/alona/db_backups` (in soduer user homedir). DB backups will be saved here (persistent across docker restarts). If you change this path name, change the path in `docker-compose.prod.yml` as well.
8. Run `sudo ./deploy.sh init`. This will spin up the docker containers, setup superusers `Alon` and `Shani` according to the `.env` passwords, and perform db migration. Website will now be live on port 80.
9. Harden server security:
    * In `/etc/ssh/sshd_config` set `PermitRootLogin no`, `PasswordAuthentication no`
and choose a different SSH port number (not 22).
    * Enable `ufw`, and only allow incoming TCP port 80 and the custom SSH port.

## Production environment deploy changes
1. Push changes to git branch
2. Run migration with `sudo ./migrate.sh`
3. If needed, delete all docker volumes with `sudo  docker compose -f docker-compose.prod.yml down -v`. This shouldn't delete the db backups mounted locally, but best make copies first.
4. Run `sudo ./deploy` to pull branch changes, rebuild docker images and run docker-compose. 
5. If you run out of space at any point - run `sudo docker system prune -a` and then `sudo ./deploy` (It won't 
   delete your volumes, will just re-download the images). 

## Testing
1. Run song_signup/tests from pycharm after selecting the docker compose file.
2. If you get the error `database "test_twist_db" already exists`, delete all volumes with the command `./stop-dev.sh -v`
3. A better option, without interfering with local server - enter the django container, and type this for a specific 
   test: `./manage.py test song_signup.tests.test_models.TestSingerModel.test_already_sang` or to run all of them: `./manage.py test song_signup`


## Testing with coverage
1. Start containers with `./start-dev.sh`
3. Connect to django container with `docker exec -it twist-django-1  /bin/bash`
4. In container, run `coverage run --source='.' manage.py test song_signup && coverage html --omit=song_signup/tests/interactive_test_real_dbs.py,song_signup/management/*,dev_setup.py,prod_setup.py,twist/asgi.py,twist/wsgi.py,song_signup/tests/*,manage.py,twist/celery.py`
5. Exit container and run `open ./htmlcov/index.html` locally


## Adding group songs from csv
1. We saved our group songs list on a Google Drive spreadsheet in `Broadway With a Twist/Good Group Songs` 
2. Download as CSV (make sure you filled the type with the correct option) to `/twist/group-songs.csv`
3. Push to origin and restart container (the files need to be recopyied into the container)
3. Connect to django container with `docker exec -it twist-django-1  /bin/bash`
4. Run `./manage.py import_group_songs` to import from the path above. Can also pass in a custom path.

## Loading DB backup to local env
1. Download DB backup from server to twist/db_backups:
```sh
$twist git:(master): scp digital-ocean-twist:~/db_backups/default-5e939168e488-2024-05-06-112039.psql 
db_backups/16-4-24-friends.psql
```
2. Connect to running django container:
`docker exec -it twist-django-1 /bin/bash`
3. Run restore:
`./manage.py dbrestore -I db_backups/16-4-24-friends.psql`
4. Use restored DB on local system. Remember that your admin pass is now the production one.

## Stress testing production
1. For editing the test: Run JMeter (`jmeter` from terminal) and open the JMX file in twist/jmeter
2. Reset production DB and set passcode to `dev`
3. Play on JMeter, and 100 threads (40 singers and 60 audience) will run. Singers use different names for each and 
sign up with 2 different songs each (all data taken from CSV files in the twist/jmeter dir).
4. I have an AWS instance for this - `bwt-stress` (in N. Virginia). May need to change the IP in the hosts file when 
   after you turn it on. Has jmeter installed. TURN OFF INSTANCE WHEN 
   DONE.
5. If you made changes, scp the file `twist/jmeter.stress-test.jmx` to the instance's home path (user ubuntu). 
6. Run the test from the instance like this: `jmeter -n -t stress-test.jmx  -l result.jtl -j jmeter.log`
7. View failures in `jmeter.log`
8. TURN OFF INSTANCE!!
9. Restart app when done - otherwise celery will keep working hard

Note: The audience part of the test is depricated since audiences log in. For now I disabled it
and doubled the number of singers instead (I'm just testing lyrics stress). In the future you'll probably want to 
re-record and create the audience test again. 





