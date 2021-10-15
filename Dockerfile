FROM python:3.7-alpine AS base
WORKDIR /usr/src/app
RUN apk update && \
  apk add \
  build-base \
  curl \
  git \
  libffi-dev \
  openssh-client \
  postgresql-dev

ENV POETRY_HOME=/opt/poetry \
    VENV=/usr/src/app/.venv
ENV PATH="$POETRY_HOME/bin:$VENV/bin:$PATH"

RUN curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/master/install-poetry.py | python -
RUN poetry config virtualenvs.create true; poetry config virtualenvs.in-project true

COPY ./pyproject.toml ./poetry.lock ./
RUN mkdir echo_agent && touch echo_agent/__init__.py
RUN poetry install --no-dev
RUN poetry run pip install uvicorn

FROM python:3.7-alpine as main
WORKDIR /usr/src/app
COPY --from=base /usr/src/app /usr/src/app
ENV PATH="/usr/src/app/.venv/bin:$PATH"

COPY ./echo_agent/ ./echo_agent/
ENTRYPOINT ["/bin/sh", "-c", "python -m \"$@\"", "--"]
CMD ["uvicorn", "echo_agent:app", "--host", "0.0.0.0", "--port", "80"]
