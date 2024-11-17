# CIARC - Riftonauts

[![Web](https://img.shields.io/badge/Web-blue)](https://c103-219.cloud.gwdg.de/)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)][pre-commit]

[pre-commit]: https://github.com/pre-commit/pre-commit

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

To install the requirements run `poetry install`.
This provides the `melvonaut` and `rift-console` commands.
Use `poetry shell` to get a python shell with the virtual environment activated.
Then the commands can be used.

The rift-console can be deployed as a docker container.
Use the `docker-compose up --build -d` command to start it.
Or refer to `make docker-compose-up` in the Makefile.

## Usage

- TODO

## License

Distributed under the terms of the [MIT license][license],
_Ciarc_ is free and open source software.


[license]: https://github.com/Lolsayna/CIARC/blob/main/LICENSE
