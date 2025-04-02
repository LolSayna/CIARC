FROM python:3.12-slim

RUN python -m pip install --upgrade pip

RUN apt-get update && apt-get install -y --no-install-recommends build-essential gcc sshpass openssh-client lftp rsync

WORKDIR /app

ENV PYTHONPATH=/app

COPY poetry.lock pyproject.toml ./

RUN pip install poetry && poetry config virtualenvs.create false && poetry install --no-interaction --no-ansi --no-root --with rift_console

COPY . .

RUN poetry install --no-interaction

EXPOSE 3000

CMD ["poetry", "run", "rift-console", "run-server"]