FROM python:3.10-slim-buster AS base
WORKDIR /usr/src/app
RUN apt-get update && apt-get install -y curl git && apt-get clean

# Install and configure poetry
ENV POETRY_VERSION=1.1.11
ENV POETRY_HOME=/opt/poetry
RUN curl -sSL https://install.python-poetry.org | python -

ENV PATH="/opt/poetry/bin:$PATH"
RUN poetry config virtualenvs.in-project true

COPY ./pyproject.toml ./poetry.lock ./
RUN mkdir echo_agent && touch echo_agent/__init__.py
RUN poetry install --no-dev -E server
RUN poetry run pip install uvicorn

FROM python:3.10-slim-buster AS main
WORKDIR /usr/src/app
COPY --from=base /usr/src/app /usr/src/app
ENV PATH="/usr/src/app/.venv/bin:$PATH"

COPY ./echo_agent/ ./echo_agent/
ENTRYPOINT ["/bin/sh", "-c", "python -m uvicorn echo_agent:app \"$@\"", "--"]
CMD ["--host", "0.0.0.0", "--port", "80"]
