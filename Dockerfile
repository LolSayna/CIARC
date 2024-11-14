FROM python:3.12-slim

RUN python -m pip install --upgrade pip

RUN apt-get update && apt-get install -y --no-install-recommends build-essential gcc

WORKDIR /app

COPY poetry.lock pyproject.toml ./

RUN pip install poetry && poetry config virtualenvs.create false && poetry install --no-interaction --no-ansi --no-root

COPY . .

RUN poetry install

ENV PYTHONPATH=/app

EXPOSE 8000

CMD ["rift-console run-server"]
