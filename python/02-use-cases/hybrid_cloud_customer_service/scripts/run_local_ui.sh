#!/bin/sh
set -eu

: "${UI_PORT:=8000}"

# Keep Runtime credentials in the ignored project-local .env.
if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

exec uv run --frozen --extra dev uvicorn local_ui:app --host 127.0.0.1 --port "${UI_PORT}"
