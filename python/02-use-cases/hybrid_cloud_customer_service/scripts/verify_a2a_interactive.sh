#!/usr/bin/env bash
# Verify direct and delegated A2A calls without persisting Runtime credentials.
set -euo pipefail
set +x

ask_url() {
  local variable_name="$1"
  local label="$2"
  local value="${!variable_name:-}"
  local entered=""
  if [[ -n "${value}" ]]; then
    read -r -p "${label} (Enter 复用当前终端值，或手动输入新地址): " entered
    value="${entered:-${value}}"
  else
    while [[ -z "${value}" ]]; do
      read -r -p "${label} (http:// or https://): " value
    done
  fi
  if [[ ! "${value}" =~ ^https?:// ]]; then
    echo "${label} must start with http:// or https://." >&2
    exit 2
  fi
  printf '%s' "${value%/}"
}

ask_key() {
  local variable_name="$1"
  local label="$2"
  local value="${!variable_name:-}"
  local entered=""
  if [[ -n "${value}" ]]; then
    read -r -s -p "${label} (输入不可见；Enter 复用当前终端值，或手动输入新值): " entered
    printf '\n' >&2
    value="${entered:-${value}}"
  else
    while [[ -z "${value}" ]]; do
      read -r -s -p "${label} (hidden input): " value
      printf '\n' >&2
    done
  fi
  printf '%s' "${value}"
}

main_endpoint="$(ask_url RUNTIME_ENDPOINT 'Main Runtime Endpoint')"
main_key="$(ask_key RUNTIME_API_KEY 'Main Runtime API Key')"
data_endpoint="$(ask_url A2A_AGENT_ENDPOINT 'Data Runtime Endpoint')"
data_key="$(ask_key A2A_AGENT_API_KEY 'Data Runtime API Key')"
read -r -p "A2A 中心选中的 Agent 名称 [hybrid-cloud-complaint-data-agent]: " agent_name
agent_name="${agent_name:-hybrid-cloud-complaint-data-agent}"
read -r -p "本次验证的 Skill ID [complaint-trend-analysis]: " skill_id
skill_id="${skill_id:-complaint-trend-analysis}"

RUNTIME_ENDPOINT="${main_endpoint}" RUNTIME_API_KEY="${main_key}" \
A2A_AGENT_ENDPOINT="${data_endpoint}" A2A_AGENT_API_KEY="${data_key}" \
A2A_EXPECTED_AGENT_NAME="${agent_name}" A2A_EXPECTED_SKILL_ID="${skill_id}" \
  uv run --frozen scripts/verify_a2a.py "$@"
