#!/bin/sh
set -eu

: "${MODEL_AGENT_API_BASE:=${ARK_BASE_URL:-https://ark.cn-beijing.volces.com/api/v3}}"
: "${MODEL_AGENT_API_KEY:=${ARK_API_KEY:-}}"
: "${MODEL_AGENT_NAME:=${ARK_MODEL:-deepseek-v4-pro-260425}}"
: "${ARK_BASE_URL:=${MODEL_AGENT_API_BASE}}"
: "${ARK_API_KEY:=${MODEL_AGENT_API_KEY}}"
: "${ARK_MODEL:=${MODEL_AGENT_NAME}}"
: "${DEMO_MODE:=auto}"
: "${PORT:=8000}"
: "${AGENT_APP_MODE:=customer_service}"

if [ "${AGENT_APP_MODE}" = "customer_service" ] && [ "${DEMO_MODE}" = "live" ] && [ -z "${MODEL_AGENT_API_KEY}" ]; then
  echo "MODEL_AGENT_API_KEY is required in live mode." >&2
  exit 1
fi
export MODEL_AGENT_API_BASE MODEL_AGENT_API_KEY MODEL_AGENT_NAME
export ARK_BASE_URL ARK_API_KEY ARK_MODEL DEMO_MODE PORT AGENT_APP_MODE

case "${AGENT_APP_MODE}" in
  customer_service)
    exec python /app/agent.py
    ;;
  a2a_data_analyst)
    exec python /app/a2a_data_agent.py
    ;;
  *)
    echo "Unsupported AGENT_APP_MODE: ${AGENT_APP_MODE}" >&2
    exit 1
    ;;
esac
