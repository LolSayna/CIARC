FROM python:3.12-slim

RUN python -m pip install --upgrade pip

RUN apt-get update && apt-get install -y --no-install-recommends build-essential gcc

WORKDIR /app

COPY poetry.lock pyproject.toml ./

RUN pip install poetry && poetry config virtualenvs.create false && poetry install --no-interaction --no-ansi

COPY . .

ENV PYTHONPATH=/app

EXPOSE 8000

CMD ["ciarc"]
