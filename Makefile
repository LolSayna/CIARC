#author: Jonathan Decker

.PHONY: clean clean-test clean-pyc clean-build docs help
.DEFAULT_GOAL := help

define BROWSER_PYSCRIPT
import os, webbrowser, sys

from urllib.request import pathname2url

webbrowser.open("file://" + pathname2url(os.path.abspath(sys.argv[1])))
endef
export BROWSER_PYSCRIPT

define PRINT_HELP_PYSCRIPT
import re, sys

for line in sys.stdin:
	match = re.match(r'^([a-zA-Z_-]+):.*?## (.*)$$', line)
	if match:
		target, help = match.groups()
		print("%-20s %s" % (target, help))
endef
export PRINT_HELP_PYSCRIPT

BROWSER := python -c "$$BROWSER_PYSCRIPT"

help:
	@python -c "$$PRINT_HELP_PYSCRIPT" < $(MAKEFILE_LIST)

clean: clean-pyc clean-test ## remove all build, test, coverage and Python artifacts

clean-pyc: ## remove Python file artifacts
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +
	find . -name '__pycache__' -exec rm -fr {} +

clean-test: ## remove test and coverage artifacts
	rm -f .coverage
	rm -fr htmlcov/
	rm -fr .pytest_cache

lint: ## check style
	ruff format ./src ./tests
	ruff check ./src ./tests --fix

test: ## run tests quickly with the default Python
	pytest

test-melvonaut:
	pytest tests/test_melvonaut

test-rift-console:
	pytest tests/test_rift_console

test-all: ## run tests on every Python version with tox
	nox

coverage: ## check code coverage quickly with the default Python
	coverage run --source src -m pytest
	coverage report -m
	coverage html
	$(BROWSER) htmlcov/index.html

docs: ## generate Sphinx HTML documentation, including API docs
	nox -s docs-build
	-cp -r media html/media
	$(BROWSER) html/index.html

servedocs: docs ## compile the docs watching for changes
	watchmedo shell-command -p '*.rst' -c 'sphinx-build -C docs html' -R -D .

release: dist ## package and upload a release
	poetry publish

dist: clean ## builds source and wheel package
	poetry build

install: clean ## Install CIARC
	poetry install

run: ## Run CIARC
	PYTHONPATH=$(shell pwd) rift-console run-server

docker-build: clean ## Build docker image for CIARC
	docker build -t local/rift-console:latest .

docker-run: ## Run CIARC in docker
	docker run --rm -v $(shell pwd)/.env:/app/.env:ro local/rift-console:latest

docker-push: ## Push docker image to gitlab
	docker login docker.gitlab-ce.gwdg.de
	docker push docker.gitlab-ce.gwdg.de/Lolsayna/CIARC
