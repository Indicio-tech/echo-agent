#!/usr/bin/env bash

cd "$(dirname "$0")" || exit
if [ -z "$1" ]; then
    echo 'Must specify "generate" or "update" as first argument'
    exit 1
fi

CONTAINER_RUNTIME=${CONTAINER_RUNTIME:-docker}

${CONTAINER_RUNTIME} build -t openapi-generator -f ./Dockerfile.openapi-generator .

${CONTAINER_RUNTIME} run --rm \
    -v "$(realpath "$PWD/../"):/usr/src/app:z" \
    openapi-generator generate --path ./scripts/openapi.json

mv "$PWD/../echo-agent-client/echo_agent_client" "$PWD/echo/client"
rm -rf --preserve-root "$PWD/../echo-agent-client"
