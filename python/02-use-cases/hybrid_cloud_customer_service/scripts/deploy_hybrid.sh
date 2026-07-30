#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_FILE="${AGENTKIT_CONFIG_FILE:-${PROJECT_ROOT}/agentkit.yaml}"
DEPLOY_MODE="${AGENTKIT_DEPLOY_MODE:-live}"
MODEL_REQUIRED="${AGENTKIT_MODEL_REQUIRED:-1}"
POST_DEPLOY_INVOKE="${AGENTKIT_POST_DEPLOY_INVOKE:-1}"
DEPLOY_CONFIG_FILE=""
LAUNCH_LOG_FILE=""
RUNTIME_LIST_FILE=""
PING_RESPONSE_FILE=""

cleanup() {
  if [[ -n "${DEPLOY_CONFIG_FILE}" && -f "${DEPLOY_CONFIG_FILE}" ]]; then
    rm -f -- "${DEPLOY_CONFIG_FILE}"
  fi
  if [[ -n "${LAUNCH_LOG_FILE}" && -f "${LAUNCH_LOG_FILE}" ]]; then
    rm -f -- "${LAUNCH_LOG_FILE}"
  fi
  if [[ -n "${RUNTIME_LIST_FILE}" && -f "${RUNTIME_LIST_FILE}" ]]; then
    rm -f -- "${RUNTIME_LIST_FILE}"
  fi
  if [[ -n "${PING_RESPONSE_FILE}" && -f "${PING_RESPONSE_FILE}" ]]; then
    rm -f -- "${PING_RESPONSE_FILE}"
  fi
}
trap cleanup EXIT

cd "${PROJECT_ROOT}"

for command_name in uv docker curl; do
  if ! command -v "${command_name}" >/dev/null 2>&1; then
    echo "缺少命令：${command_name}" >&2
    exit 1
  fi
done

case "${DEPLOY_MODE}" in
  live|demo) ;;
  *)
    echo "AGENTKIT_DEPLOY_MODE 只支持 live 或 demo；默认是 live。" >&2
    exit 1
    ;;
esac

case "${MODEL_REQUIRED}" in
  0|1) ;;
  *)
    echo "AGENTKIT_MODEL_REQUIRED 只支持 0 或 1；默认是 1。" >&2
    exit 1
    ;;
esac

case "${POST_DEPLOY_INVOKE}" in
  0|1) ;;
  *)
    echo "AGENTKIT_POST_DEPLOY_INVOKE 只支持 0 或 1；默认是 1。" >&2
    exit 1
    ;;
esac

case "${AGENTKIT_ALLOW_HTTP_OIDC:-0}" in
  0|1) ;;
  *)
    echo "AGENTKIT_ALLOW_HTTP_OIDC 只支持 0 或 1；默认是 0。" >&2
    exit 1
    ;;
esac

MODEL_AGENT_NAME="${MODEL_AGENT_NAME:-${ARK_MODEL:-deepseek-v4-pro-260425}}"
MODEL_AGENT_API_KEY="${MODEL_AGENT_API_KEY:-${ARK_API_KEY:-}}"
MODEL_AGENT_API_BASE="${MODEL_AGENT_API_BASE:-${ARK_BASE_URL:-https://ark.cn-beijing.volces.com/api/v3}}"

# AgentKit 0.5.5 automatically merges every assignment from a project .env
# into Runtime envs. Refuse ambiguous local-UI files instead of accidentally
# sending RUNTIME_API_KEY, control-plane credentials, or unrelated secrets.
if [[ -f "${PROJECT_ROOT}/.env" ]] && grep -Eq '^[[:space:]]*[A-Za-z_][A-Za-z0-9_]*=' "${PROJECT_ROOT}/.env"; then
  echo "检测到项目 .env。AgentKit 0.5.5 会把其中所有变量注入 Runtime；为避免泄露，本脚本拒绝继续。" >&2
  echo "请把部署所需模型变量仅导出到当前终端，并暂时移走 .env 后重试。" >&2
  exit 1
fi

if [[ "${DEPLOY_MODE}" = "live" && "${MODEL_REQUIRED}" = "1" ]]; then
  missing_model_vars=()
  for variable_name in MODEL_AGENT_API_KEY; do
    if [[ -z "${!variable_name:-}" ]]; then
      missing_model_vars+=("${variable_name}")
    fi
  done
  if [[ "${#missing_model_vars[@]}" -gt 0 ]]; then
    echo "默认部署模式为 live，但缺少：${missing_model_vars[*]}" >&2
    echo "请在当前终端安全导出模型配置后重试；如只验证基础链路，请显式执行 AGENTKIT_DEPLOY_MODE=demo ./scripts/deploy_hybrid.sh。" >&2
    exit 1
  fi
fi

echo "Syncing the shared uv environment ..."
uv sync --frozen --extra dev
export PATH="${PROJECT_ROOT}/.venv/bin:${PATH}"

for command_name in agentkit python; do
  if ! command -v "${command_name}" >/dev/null 2>&1; then
    echo "缺少命令：${command_name}" >&2
    exit 1
  fi
done

run_project_agentkit() {
  if [[ "${AGENTKIT_ALLOW_HTTP_OIDC:-0}" = "1" ]]; then
    uv run --frozen python \
      "${PROJECT_ROOT}/scripts/agentkit_cli_poc.py" "$@"
  else
    agentkit "$@"
  fi
}

if [[ ! -f "${CONFIG_FILE}" ]]; then
  cp "${PROJECT_ROOT}/agentkit.yaml.example" "${CONFIG_FILE}"
  chmod 600 "${CONFIG_FILE}"
  echo "Created ${CONFIG_FILE} from the public template."
fi

control_plane_vars=(
  AGENTKIT_OPENAPI_HOST
  VOLCENGINE_ACCESS_KEY
  VOLCENGINE_SECRET_KEY
)
configured_count=0
for variable_name in "${control_plane_vars[@]}"; do
  if [[ -n "${!variable_name:-}" ]]; then
    configured_count=$((configured_count + 1))
  fi
done

if [[ "${configured_count}" -eq "${#control_plane_vars[@]}" ]]; then
  bash "${PROJECT_ROOT}/scripts/configure_agentkit_cli.sh.example"
elif [[ "${configured_count}" -ne 0 ]]; then
  echo "控制面环境变量只设置了一部分；请全部设置或全部省略以复用已有全局配置。" >&2
  exit 1
else
  echo "Reusing existing AgentKit global control-plane configuration."
  read -r configured_scheme configured_host < <(
    python - <<'PY'
from pathlib import Path

import yaml

config_path = Path.home() / ".agentkit" / "config.yaml"
config = yaml.safe_load(config_path.read_text()) if config_path.exists() else {}
service = ((config or {}).get("services") or {}).get("agentkit") or {}
print(service.get("scheme") or "", service.get("host") or "")
PY
  )
  if [[ -z "${configured_scheme}" || -z "${configured_host}" ]]; then
    echo "全局 AgentKit OpenAPI host/scheme 不完整；请设置控制面变量后重试。" >&2
    exit 1
  fi
  echo "Checking configured ${configured_scheme}://${configured_host}/ping ..."
  PING_RESPONSE_FILE="$(mktemp "${TMPDIR:-/tmp}/agentkit-ping.XXXXXX")"
  chmod 600 "${PING_RESPONSE_FILE}"
  if ! curl --fail --silent --show-error \
    --connect-timeout 10 \
    --max-time 20 \
    "${configured_scheme}://${configured_host}/ping" >"${PING_RESPONSE_FILE}"; then
    echo "当前全局 AgentKit OpenAPI /ping 网络预检失败。" >&2
    exit 1
  fi
  if ! grep --quiet '"pong"' "${PING_RESPONSE_FILE}"; then
    echo "当前全局 AgentKit OpenAPI /ping 响应不符合预期。" >&2
    exit 1
  fi
  if ! agentkit runtime list >/dev/null 2>&1; then
    echo "AgentKit 控制面鉴权验证失败；详细 CLI 错误可能包含 Access Key，已隐藏。" >&2
    echo "请在当前终端安全设置完整控制面变量，重新运行脚本以刷新全局配置。" >&2
    exit 1
  fi
fi

PROJECT_REGION="${VOLCENGINE_REGION:-}"
if [[ -z "${PROJECT_REGION}" ]]; then
  detected_global_region="$(
    python - <<'PY'
from pathlib import Path

import yaml

config_path = Path.home() / ".agentkit" / "config.yaml"
if config_path.exists():
    config = yaml.safe_load(config_path.read_text()) or {}
    print(config.get("region") or "")
PY
  )"
  if [[ -n "${detected_global_region}" ]]; then
    echo "检测到全局 Region=${detected_global_region}，但不会静默用于本次 Runtime 部署。" >&2
  fi
  echo "请显式设置 VOLCENGINE_REGION，或运行 ./scripts/deploy_interactive.sh 逐项确认。" >&2
  exit 1
fi

# AgentKit 0.5.5 does not inherit the global region into an existing project
# config. Persist it explicitly so CreateRuntime does not fall back to
# cn-beijing while CR and control-plane calls use the delivered region.
if ! run_project_agentkit config \
  --config "${CONFIG_FILE}" \
  --region "${PROJECT_REGION}" >/dev/null; then
  echo "项目 Runtime Region 写入失败；未创建或更新任何 Runtime。" >&2
  if [[ "${AGENTKIT_ALLOW_HTTP_OIDC:-0}" = "1" ]]; then
    echo "HTTP OIDC POC 兼容入口未能通过 AgentKit 配置校验。" >&2
  fi
  exit 1
fi
echo "Project Runtime region set to ${PROJECT_REGION}."

read -r PROJECT_RUNTIME_NAME CONFIGURED_RUNTIME_ID < <(
  python - "${CONFIG_FILE}" <<'PY'
import sys
from pathlib import Path

import yaml

config = yaml.safe_load(Path(sys.argv[1]).read_text()) or {}
hybrid = (config.get("launch_types") or {}).get("hybrid") or {}
print(hybrid.get("runtime_name") or "", hybrid.get("runtime_id") or "")
PY
)
if [[ -z "${PROJECT_RUNTIME_NAME}" ]]; then
  echo "项目配置缺少 launch_types.hybrid.runtime_name。" >&2
  exit 1
fi

RESOLVED_RUNTIME_NAME="${PROJECT_RUNTIME_NAME}"
RESOLVED_RUNTIME_ID="${AGENTKIT_RUNTIME_ID:-${CONFIGURED_RUNTIME_ID}}"
if [[ -z "${RESOLVED_RUNTIME_ID}" ]]; then
  RUNTIME_LIST_FILE="$(mktemp "${TMPDIR:-/tmp}/agentkit-runtime-list.XXXXXX")"
  chmod 600 "${RUNTIME_LIST_FILE}"
  if ! agentkit runtime list \
    --name "${PROJECT_RUNTIME_NAME}" \
    --region "${PROJECT_REGION}" \
    --all \
    --quiet >"${RUNTIME_LIST_FILE}" 2>/dev/null; then
    echo "同名 Runtime 预检失败；详细 CLI 错误可能包含 Access Key，已隐藏。" >&2
    exit 1
  fi

  existing_runtime_ids=()
  while IFS= read -r runtime_id; do
    if [[ -n "${runtime_id}" ]]; then
      existing_runtime_ids+=("${runtime_id}")
    fi
  done <"${RUNTIME_LIST_FILE}"

  if [[ "${#existing_runtime_ids[@]}" -gt 0 ]]; then
    if [[ "${#existing_runtime_ids[@]}" -gt 1 ]]; then
      echo "发现多个同名 Runtime，无法安全自动选择：" >&2
      printf '  %s\n' "${existing_runtime_ids[@]}" >&2
      echo "请核对后显式设置 AGENTKIT_RUNTIME_ID。" >&2
      exit 1
    fi

    discovered_runtime_id="${existing_runtime_ids[0]}"
    if [[ "${AGENTKIT_EXISTING_RUNTIME_ACTION:-fail}" = "prompt" && -t 0 ]]; then
      echo
      echo "发现同名 Runtime：${PROJECT_RUNTIME_NAME} (${discovered_runtime_id})"
      echo "  1) 更新这个已有 Runtime（推荐）"
      echo "  2) 输入新名称并创建独立 Runtime"
      read -r -p "请选择 [1]: " existing_runtime_choice
      existing_runtime_choice="${existing_runtime_choice:-1}"
      case "${existing_runtime_choice}" in
        1)
          RESOLVED_RUNTIME_ID="${discovered_runtime_id}"
          ;;
        2)
          suggested_runtime_name="${PROJECT_RUNTIME_NAME}-$(date +%m%d%H%M)"
          while true; do
            read -r -p "请输入新 Runtime 名称 [${suggested_runtime_name}]: " candidate_runtime_name
            candidate_runtime_name="${candidate_runtime_name:-${suggested_runtime_name}}"
            if [[ ! "${candidate_runtime_name}" =~ ^[a-z0-9]([a-z0-9-]*[a-z0-9])?$ ]] ||
              [[ "${#candidate_runtime_name}" -gt 63 ]]; then
              echo "Runtime 名称需为 1–63 位小写字母、数字或连字符，且首尾不能是连字符。" >&2
              continue
            fi
            : >"${RUNTIME_LIST_FILE}"
            if ! agentkit runtime list \
              --name "${candidate_runtime_name}" \
              --region "${PROJECT_REGION}" \
              --all \
              --quiet >"${RUNTIME_LIST_FILE}" 2>/dev/null; then
              echo "新名称查重失败；详细 CLI 错误可能包含 Access Key，已隐藏。" >&2
              exit 1
            fi
            if [[ -s "${RUNTIME_LIST_FILE}" ]]; then
              echo "名称 ${candidate_runtime_name} 已存在，请换一个名称。" >&2
              continue
            fi
            RESOLVED_RUNTIME_NAME="${candidate_runtime_name}"
            echo "将创建新 Runtime：${RESOLVED_RUNTIME_NAME}"
            break
          done
          ;;
        *)
          echo "无效选择：${existing_runtime_choice}。未创建或更新 Runtime。" >&2
          exit 2
          ;;
      esac
    elif [[ "${AGENTKIT_REUSE_EXISTING_RUNTIME:-0}" = "1" ]]; then
      RESOLVED_RUNTIME_ID="${discovered_runtime_id}"
    else
      echo "平台已存在同名 Runtime：${PROJECT_RUNTIME_NAME} (${discovered_runtime_id})。" >&2
      echo "交互部署请运行 ./scripts/deploy_interactive.sh 并确认更新；自动化环境请显式设置：" >&2
      echo "  AGENTKIT_RUNTIME_ID='${discovered_runtime_id}' ./scripts/deploy_hybrid.sh" >&2
      exit 1
    fi
  fi
fi

DEPLOY_CONFIG_FILE="$(mktemp "${PROJECT_ROOT}/.agentkit-deploy.XXXXXX")"
chmod 600 "${DEPLOY_CONFIG_FILE}"
cp "${CONFIG_FILE}" "${DEPLOY_CONFIG_FILE}"

python - \
  "${DEPLOY_CONFIG_FILE}" \
  "${DEPLOY_MODE}" \
  "${RESOLVED_RUNTIME_ID}" \
  "${RESOLVED_RUNTIME_NAME}" <<'PY'
import os
import sys
from pathlib import Path

import yaml

path = Path(sys.argv[1])
mode = sys.argv[2]
runtime_id = sys.argv[3]
runtime_name = sys.argv[4]
config = yaml.safe_load(path.read_text()) or {}
hybrid = config.setdefault("launch_types", {}).setdefault("hybrid", {})
hybrid["runtime_name"] = runtime_name
if runtime_id:
    hybrid["runtime_id"] = runtime_id
runtime_envs = config.setdefault("common", {}).setdefault("runtime_envs", {})
for key in ("MODEL_AGENT_NAME", "MODEL_AGENT_API_KEY", "MODEL_AGENT_API_BASE"):
    runtime_envs.pop(key, None)
runtime_envs["DEMO_MODE"] = mode
if mode == "live" and os.environ.get("AGENTKIT_MODEL_REQUIRED", "1") == "1":
    runtime_envs["MODEL_AGENT_NAME"] = os.environ["MODEL_AGENT_NAME"]
    runtime_envs["MODEL_AGENT_API_KEY"] = os.environ["MODEL_AGENT_API_KEY"]
    runtime_envs["MODEL_AGENT_API_BASE"] = os.environ["MODEL_AGENT_API_BASE"]
path.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False))
PY

echo "Validated deployment mode: ${DEPLOY_MODE}. Runtime secret values will not be printed."

echo "Checking Docker daemon ..."
if ! python -c 'import docker; client = docker.from_env(); client.ping()'; then
  echo "AgentKit 需要 Docker SDK 可连接的 daemon/socket；仅有 nerdctl 兼容命令不够。" >&2
  exit 1
fi

echo "Launching hybrid Runtime in ${DEPLOY_MODE} mode ..."
LAUNCH_LOG_FILE="$(mktemp "${TMPDIR:-/tmp}/agentkit-launch.XXXXXX")"
chmod 600 "${LAUNCH_LOG_FILE}"
set +e
run_project_agentkit launch \
  --config-file "${DEPLOY_CONFIG_FILE}" \
  --platform linux/amd64 \
  --preflight-mode skip 2>&1 | tee "${LAUNCH_LOG_FILE}"
launch_status=${PIPESTATUS[0]}
set -e

if [[ "${launch_status}" -ne 0 ]]; then
  if grep -Eqi \
    'unauthorized|authentication required|invalid token claims|token[^[:alnum:]]+is expired|token expired' \
    "${LAUNCH_LOG_FILE}"; then
    cat >&2 <<'EOF'

检测到 Registry 临时凭据已失效或未授权。这种情况下需要人工刷新登录：
1. 打开目标环境“产品与服务 → 镜像仓库 → cr-basic → 获取临时访问指令”。
2. 在当前 Docker 上下文执行页面给出的完整 docker login 命令，确认 Login Succeeded。
3. 不要保存或粘贴临时令牌；重新运行本部署脚本。

正常情况下不需要预先登录；但 launch 已明确返回 token expired/unauthorized 时，
手工刷新临时登录是允许且必要的恢复操作。
EOF
  elif grep -Eq 'InvalidParameter[.]DuplicateName|specified name already exists' \
    "${LAUNCH_LOG_FILE}"; then
    cat >&2 <<'EOF'

平台已存在同名 Runtime，但本地配置没有绑定其 Runtime ID。
请重新运行 ./scripts/deploy_interactive.sh，选择“更新这个已有 Runtime”；
脚本会保存非敏感的 Runtime ID，后续 launch 将执行更新而不是重复创建。
EOF
  fi
  exit "${launch_status}"
fi

# AgentKit writes the newly created Runtime ID into the launch config. Persist
# only that non-secret binding so the next launch updates instead of creating a
# duplicate. Endpoint, API key, and model secrets remain transient.
python - "${DEPLOY_CONFIG_FILE}" "${CONFIG_FILE}" <<'PY'
import sys
from pathlib import Path

import yaml

launch_path = Path(sys.argv[1])
project_path = Path(sys.argv[2])
launch_config = yaml.safe_load(launch_path.read_text()) or {}
runtime_id = (
    ((launch_config.get("launch_types") or {}).get("hybrid") or {}).get("runtime_id")
    or ""
)
runtime_name = (
    ((launch_config.get("launch_types") or {}).get("hybrid") or {}).get("runtime_name")
    or ""
)
if not runtime_id:
    raise SystemExit("launch succeeded but runtime_id was not returned")
if not runtime_name:
    raise SystemExit("launch succeeded but runtime_name was not returned")

project_config = yaml.safe_load(project_path.read_text()) or {}
hybrid = project_config.setdefault("launch_types", {}).setdefault("hybrid", {})
hybrid["runtime_id"] = runtime_id
hybrid["runtime_name"] = runtime_name
project_path.write_text(
    yaml.safe_dump(project_config, allow_unicode=True, sort_keys=False)
)
PY
chmod 600 "${CONFIG_FILE}"
echo "Saved non-secret Runtime binding to ${CONFIG_FILE}; future launches will update it."

run_project_agentkit status --config-file "${DEPLOY_CONFIG_FILE}" --verbose

if [[ "${POST_DEPLOY_INVOKE}" = "1" ]]; then
  echo "Invoking deployed ${DEPLOY_MODE} Runtime ..."
  run_project_agentkit invoke \
    --config-file "${DEPLOY_CONFIG_FILE}" \
    "退款多久到账？"
else
  echo "Runtime is ready; skipping /invoke because this entry point has a non-/invoke public protocol."
fi
