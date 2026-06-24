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

## Loading DB backup file db live DB
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

Use `twist/jmeter/money-time.jmx` — it reproduces "money time": 40 singers signing up at the
**exact same instant** (a JMeter rendezvous on `POST /add_song_request`) plus 60 audience members
polling the live endpoints = 100 concurrent users. It drives load **only from outside over HTTP**
(never SSH/exec into the prod box). Pass/fail is built in via a per-request response-time SLA + HTTP-200
assertion. Regenerate it with `python3 gen_money_time.py` if you tweak the generator.

### 1. Configure a throwaway event (from outside — browser admin)
Set these so the hardcoded defaults in the JMX just work (no `-J` flags needed):
- Constance `PASSCODE` = `dev`
- Constance `EVENT_SKU` = `LOADTEST` (any non-empty value — required to open the app)
- Constance `FREEBIE_TICKET` = `123456` (must match the order-id baked into the JMX; lets all 100 log in, bypassing ticket limits)
- Enable feature flag `CAN_SIGNUP`

### 2. Functional check from your laptop (does it work?)
Small + short — confirms logins/signups succeed. NOT a tier verdict (a laptop can't honestly push 100 TLS users).
```
cd twist/jmeter
jmeter -n -t money-time.jmx -Jsingers=5 -Jaudience=5 -Jduration=30 -Jrun_id=$(date +%s) -l val.jtl -e -o val_report
python3 verdict.py val.jtl      # expect PASS, ~0% errors
```

### 3. The real tier benchmark (from the cloud, in-region)
AWS instance `bwt-stress` (Israel region) is purpose-built for this — jmeter is installed. It's already
configured in `~/.ssh/config`, so you can connect with `ssh bwt-stress` (no IP/key setup needed).
**TURN OFF INSTANCE WHEN DONE.**
Tier note: a 2-vCPU burstable box (e.g. t3.medium) is marginal for generating 100 HTTPS threads —
under a sustained run it can exhaust CPU credits and throttle, making the GENERATOR the bottleneck.
Use T3 Unlimited mode or a non-burstable box (c7i.large / t3.large), and watch the generator's own CPU
during the run (`top`, or CloudWatch CPUUtilization + CPUCreditBalance). If it pegs ~100%, the run is invalid.

One-time setup on the box (the twist repo is already cloned there):
```
sudo apt-get update && sudo apt-get install -y default-jre python3-pip   # Java for JMeter, pip for the checker
pip3 install requests                                                     # needed by check_lyrics.py
# install Apache JMeter 5.6.x and put it on PATH:
curl -LO https://dlcdn.apache.org//jmeter/binaries/apache-jmeter-5.6.3.tgz && tar xf apache-jmeter-5.6.3.tgz
export PATH=$PATH:~/apache-jmeter-5.6.3/bin     # add to ~/.bashrc to persist
```
Run it (NO scp — files are in the cloned repo). Run before AND after the resize, capture the run_id:
```
cd ~/twist/jmeter
RID=$(date +%s)
jmeter -n -t money-time.jmx -Jsingers=40 -Jaudience=60 -Jduration=300 -Jramp=1 -Jrun_id=$RID -l result.jtl -j jmeter.log
python3 verdict.py result.jtl          # expect FAIL on the smaller tier, PASS on c8i.4xlarge
```
By default it targets `broadwaywithatwist.xyz` over HTTPS; override with `-Jhost=` if prod moved.
Pass/fail defaults: error rate < 1%, p99 (all requests) < 2000 ms, signup-burst p95 < 3000 ms.
Tune with `-Jsla=`, `-Jpoll_interval=` (lower = more pressure per user), `-Jsingers=`, `-Jaudience=`, `-Jduration=`.

### 3b. Validate lyrics/exa actually worked
Each singer edits to a real song from `songs.csv`, which fires the `get_lyrics` Celery task → exa.ai.
Celery is async + rate-limited, so give it a minute. From outside (no box access — it logs in as a
superuser by name with the event passcode, then reads the superuser lyrics page):
```
python3 check_lyrics.py --run-id $RID --count 10   # PASS if the sampled songs got >=1 lyric each
```

### 4. When done
- **TURN OFF the bwt-stress INSTANCE!!**
- Reset the production DB (admin "reset database" button) to clear the test singers/songs.
- The signup burst fires lyric Celery tasks — let it settle / restart the app so celery isn't churning.

Note: the old `stress-test.jmx` / `singer-signup-exa-test.jmx` (Chrome-recorded, CSV names, audience disabled) are
superseded by `money-time.jmx`.





