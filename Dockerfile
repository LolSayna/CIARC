FROM python:3.12-slim

RUN python -m pip install --upgrade pip

RUN apt-get update && apt-get install -y --no-install-recommends build-essential gcc

WORKDIR /app

ENV PYTHONPATH=/app

COPY poetry.lock pyproject.toml ./

RUN pip install poetry && poetry config virtualenvs.create false && poetry install --no-interaction --no-ansi --no-root

COPY . .

RUN poetry install --no-interaction

EXPOSE 8000

#CMD ["rift-console", "run-server"]
CMD ["gunicorn", "--pythonpath", "./src", "rift_console.__main__:app", "--workers", "4", "--bind", "0.0.0.0:8000"]
