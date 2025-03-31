# CIARC - Riftonauts

[![Web](https://img.shields.io/badge/Web-blue)](https://c103-219.cloud.gwdg.de/)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)][pre-commit]

[pre-commit]: https://github.com/pre-commit/pre-commit


## Overview

This is the [Riftonaut's CIARC](https://github.com/Lolsayna/CIARC) repository.
It implements software for MELVIN and the Operator Console for the
ESA [Computer In A Room Challenge 3](https://www.esa.int/Education/Engagement/Applications_are_now_open_for_the_ESA_Academy_s_Computer_In_A_Room_Challenge_CIARC_3).

The project implements two packages: `melvonaut` and `rift-console`.

The Operator Console, referred to as _Rift-Console_, implements a web application based on Quart,
which provides an interface to visualize and control MELVIN in the satellite simulation.
Moreover, it implements background tasks to monitor MELVIN and to retrieve data from it.

The driver software for MELVIN, referred to as _Melvonaut_, implements an async Python service,
which continuously operates MELVIN towards the completion of its tasks.
Moreover, it provides endpoints to retrieve the collected data to the Rift-Console.

## Requirements

The implementation uses Python 3.12.
To install the requirements use [Poetry](https://python-poetry.org/).

The easiest way to set up Poetry is to use [pipx](https://pipx.pypa.io/)
and then to run

```bash
pipx install poetry
```

## Installation

### Melvonaut

For deployment of Melvonaut on Melvin, Python 3.12 is required.
In order to provide an isolated installation that persists across reboots, we compile Python 3.12 in user space.

SSH into Melvin and execute the following commands:
```
cd /home

apt update
apt install git nano

# Install Python 3.12 build dependencies
apt -y install build-essential zlib1g-dev libncurses5-dev libgdbm-dev libnss3-dev libssl-dev libreadline-dev libffi-dev libsqlite3-dev wget libbz2-dev

# Get and build Python 3.12.9, newest 3.12 at the time of writing
wget https://www.python.org/ftp/python/3.12.9/Python-3.12.9.tgz
tar xzf Python-3.12.9.tgz
rm Python-3.12.9.tgz
cd Python-3.12.9
./configure --enable-optimizations

# This takes some time
make -j 16

# Verify that it worked
./python --version

# Install Melvonaut
cd /home
git clone https://github.com/LolSayna/CIARC
cd CIARC
../Python-3.12.9/python -m venv venv
source venv/bin/activate
pip install poetry
poetry install --with melvonaut

# Optional, reset the container to remove the build dependencies
kill 1

# Run Melvonaut with
./start-melvonaut.sh
# To let it run in the background use
./start-melvonaut.sh & disown

# To follow the logs
cd /home/CIARC/logs/melvonaut
# Replace yyyy-mm-dd-hh with the current date or look for the newest file
tail -f log_melvonaut_yyyy-mm-dd-hh.log

# To stop Melvonaut restart the container
kill 1

# To update
git pull

# To be able to update after restarting the container, git must be reinstalled
apt update
apt install git
```

Melvonaut supports sending error messages via Discord while network simulation is deactivated
or during communication windows.
To use this, a Discord webhook must be set via the environment variable `DISCORD_WEBHOOK_TOKEN`.
This can be done by copying the `.env.example` file to `.env` and inserting the token retrieved from Discord.
Also `DISCORD_ALERTS_ENABLED` must be set to True in the `.env` file.

### Rift-Console

Rift-Console is intended to be deployed via docker-compose on a node
running a wire-guard connection to MELVIN.

Ensure that docker and docker-compose are installed.
Rift-console is intended to be deployed on a public domain.
If available edit `nginx.conf` to add the public domain under `map "" $domain` and the IP of the host under `map "" $host_ip`.

To run the application via TLS, lets encrypt may be used.
Edit the file `letsencrypt-config.sh` and add your domain and IP address.
It is recommended to test with the staging environment active first.
Then run `./init-letsencrypt.sh` to generate the initial certificates.
The host must be publicly reachable on port 80 and 443.

Rift-console is protected via HTTP Basic Authentication.
Valid username and password pairs are read from `.http-pass`.
Install `htpasswd` via the respective package, e.g., `apt install apache2-utils`.
Run `htpasswd .http-pass username` to create a new user.
You will be prompted for a password.

To deploy the Rift-Console using docker-compose, run `make docker-compose-up`.
This builds the image and starts the containers.
Follow the logs with `docker-compose logs -f`.
To stop the containers run `docker-compose down`.

If no public domain is available, Rift-Console can also be run locally.
Run `docker-compose up --build -d rift-console` to start the container.
Rift-Console is available at `http://localhost:3000/`

The docker-compose setup also includes mkdocs.
The docs can be found at `https://<domain>/docs`.

## Usage

### Melvonaut
Run `melvonaut` to start the service.
Run `melvonaut --help` for more information.

For production deployment use the `start-melvonaut.sh` script.
This includes automatic restarts on crashes.

### Rift-Console
Run `rift-console` to start the service locally.
Rift-Console can then be controlled from the web interface.

## Development



## Conventions
### Logging Level
- Debug: some basic function is executed
- Info: DEFAULT state - only important transitions
- Warning: something noteworthy/important that should stand out from the logs
- Error: something that should never have happened
- CRITICAL: reserved for debugging


## Usefule API cmds
Reset
```
curl -X 'GET' \
  'http://10.100.10.11:33000/reset' \
  -H 'accept: application/json'
```
Observe
```
curl -X 'GET' \
  'http://10.100.10.11:33000/observation' \
  -H 'accept: application/json'
```
Simulation
```
curl -X 'PUT' \
  'http://10.100.10.11:33000/simulation?is_network_simulation=false&user_speed_multiplier=20' \
  -H 'accept: application/json'
```
First state
```
curl -X 'PUT' \
  'http://10.100.10.11:33000/control' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "vel_x": 4.35,
  "vel_y": 5.49,
  "camera_angle": "narrow",
  "state": "charge"
}'
```
Second
```
curl -X 'PUT' \
  'http://10.100.10.11:33000/control' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "vel_x": 4.35,
  "vel_y": 5.49,
  "camera_angle": "narrow",
  "state": "acquisition"
}'
```

## License

Distributed under the terms of the [MIT license][license],
_Ciarc_ is free and open source software.


[license]: https://github.com/Lolsayna/CIARC/blob/main/LICENSE
