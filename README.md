# CIARC - Riftonauts

[![Web](https://img.shields.io/badge/Web-blue)](https://c103-219.cloud.gwdg.de/)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)][pre-commit]

[pre-commit]: https://github.com/pre-commit/pre-commit

# MAIN TODO LIST
## Melvonaut
- machen unsere Speeds so sinn? zu schnell in wide mode?
  - wie oft oberserven, wie oft Fotos machen
- Box Erkennung, im Objective modus nur dann auch Fotos machen

## Riftconsole
- karte updaten, das trajektorie besser visualisert wird
  - velocity in px/s, beschleuniung ist 0.02 px/s**2, dazu simulation speed
- beim cli stitching nudigen als parameter

## Sonstiges
- Tried "coverage_required": 0 / 0.0 -> führt zum crash beim komplet
- Alles darüber wird nie erfüllt



## Overview

This is the [Riftonaut's CIARC](https://github.com/Lolsayna/CIARC) repository.
It implements software for MELVIN and the Operator Console of the
ESA [Computer In A Room Challenge 3](https://www.esa.int/Education/Engagement/Applications_are_now_open_for_the_ESA_Academy_s_Computer_In_A_Room_Challenge_CIARC_3).

The Operator Console, referred to as _Rift-Console_, implements a web application based on Flask,
which provides an interface to visualize and control the MELVIN in the satellite simulation.
Moreover, it implements background tasks to monitor MELVIN and to retrieve data from it.

The driver software for MELVIN, referred to as _Melvonaut_, implements an async python service,
which continuously operates MELVIN towards the completion of its tasks.
Moreover, it provides endpoints to retrieve the collected data to the Rift-Console.

## Requirements

The implementation uses Python 3.12.
To install the requirements use [Poetry](https://python-poetry.org/).
In order to run the test suite, [Nox](https://nox.thea.codes/) is required.

The easiest way to set up both Nox and Poetry is to use [pipx](https://pipx.pypa.io/)
and then to run

```bash
pipx install poetry
pipx install nox
pipx inject nox nox-poetry
```

## Installation

To install the requirements run `poetry install`. Afterwards run `poetry shell` to activate the virtual environment in your shell.
This provides the `melvonaut` and `rift-console` commands.
Then the commands can be used, make sure to run them in the main project folder.

The rift-console can be deployed as a docker container.
Use the `docker-compose up --build -d` command to start it. Run `docker-compose down` inside the repository to stop them.
Or refer to `make docker-compose-up` in the Makefile.

To use the Image Processing, make sure an `.ssh/config` for the entry `console` exists.

Inside `poetry shell` run `make myps` to check for type errors or run `make lint` to check linting before commiting. Use `poetry add NAME` to add librarys.

## Usage

- TODO


## Conventions
### Logging Level
- Debug: some basic function is executed
- Info: DEFAULT state - only important transitions
- Warning: something notworthy/important that should stand out from the logs
- Error: something that should never have happend
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
