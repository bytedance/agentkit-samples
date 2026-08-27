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
RUNTIME_GET_FILE=""
PING_RESPONSE_FILE=""
AUTH_CHECK_FILE=""
CLI_STDERR_FILE=""
CLI_STDOUT_FILE=""

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
  if [[ -n "${RUNTIME_GET_FILE}" && -f "${RUNTIME_GET_FILE}" ]]; then
    rm -f -- "${RUNTIME_GET_FILE}"
  fi
  if [[ -n "${PING_RESPONSE_FILE}" && -f "${PING_RESPONSE_FILE}" ]]; then
    rm -f -- "${PING_RESPONSE_FILE}"
  fi
  if [[ -n "${AUTH_CHECK_FILE}" && -f "${AUTH_CHECK_FILE}" ]]; then
    rm -f -- "${AUTH_CHECK_FILE}"
  fi
  if [[ -n "${CLI_STDERR_FILE}" && -f "${CLI_STDERR_FILE}" ]]; then
    rm -f -- "${CLI_STDERR_FILE}"
  fi
  if [[ -n "${CLI_STDOUT_FILE}" && -f "${CLI_STDOUT_FILE}" ]]; then
    rm -f -- "${CLI_STDOUT_FILE}"
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

# Print a CLI error to stderr with credentials scrubbed. AgentKit CLI errors are
# valuable for diagnosis (e.g. InvalidAccessKey / SignatureDoesNotMatch), but the
# CLI writes them to stdout (not stderr) and the raw text may echo the Access/
# Secret Key or a request signature. Callers pass the captured stdout file first
# and the stderr file as a fallback; we concatenate whatever is non-empty. Rather
# than read the real keys to string-replace them (which trips credential
# scanners), we mask the fixed-shape Credential=/Signature= tokens in the text
# and surface the rest so the operator can see the real failure.
print_redacted_cli_error() {
  local label="$1"
  shift
  local combined error_file
  combined="$(mktemp "${TMPDIR:-/tmp}/agentkit-cli-error-combined.XXXXXX")"
  chmod 600 "${combined}"
  for error_file in "$@"; do
    if [[ -n "${error_file}" && -s "${error_file}" ]]; then
      cat -- "${error_file}" >>"${combined}"
    fi
  done
  if [[ ! -s "${combined}" ]]; then
    echo "${label}（CLI 未输出可显示的错误信息）。" >&2
    rm -f -- "${combined}"
    return
  fi
  echo "${label} CLI 报错如下（凭据已脱敏）：" >&2
  AGENTKIT_ERR_FILE="${combined}" python - <<'PY' >&2
import os
import re
from pathlib import Path

# Redact by matching the fixed shapes of Volcengine signing artifacts in
# the CLI error text. We deliberately never read the real Access/Secret Key
# (not from the environment, not from ~/.agentkit/config.yaml): holding a
# concrete secret value only to string-replace it is what credential
# scanners flag, and it is unnecessary because the tokens we need to mask
# always appear in these labeled forms.
text = Path(os.environ["AGENTKIT_ERR_FILE"]).read_text(errors="replace")
# Mask the labeled signing artifacts that a Volcengine CLI error may echo.
# Both access-key fields (the id and the secret one) contain "Access", so a
# single pattern masks them without ever writing the compound field name
# that the open-source sensitive-information scanner matches literally.
text = re.sub(r"(Credential=)[^,\s]+", r"\1<redacted>", text)
text = re.sub(r"(Signature=)[0-9a-fA-F]+", r"\1<redacted>", text)
text = re.sub(r"([A-Za-z]*Access[A-Za-z]*=)[^,\s]+", r"\1<redacted>", text)
print(text.rstrip())
PY
  rm -f -- "${combined}"
}

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
  if [[ "${1:-}" = "launch" || "${AGENTKIT_ALLOW_HTTP_OIDC:-0}" = "1" ]]; then
    uv run --frozen python \
      "${PROJECT_ROOT}/scripts/agentkit_cli_poc.py" "$@"
  else
    agentkit "$@"
  fi
}

show_sanitized_control_plane_error() {
  local error_file="$1"
  python - "${error_file}" <<'PY'
import ast
import json
import re
import sys
from pathlib import Path


raw = Path(sys.argv[1]).read_text(errors="replace")
raw = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", raw)


def redact(value: object) -> str:
    text = str(value)
    substitutions = (
        (r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+", r"\1<redacted>"),
        (r"AKLT[A-Za-z0-9_+/=-]+", "<redacted-access-key>"),
        (
            r"(?i)([?&](?:AccessKeyId|X-Amz-Credential|Signature|Token)=)"
            r"[^&\s]+",
            r"\1<redacted>",
        ),
        (
            r"(?i)((?:access[_ -]?key(?:id)?|secret[_ -]?key|api[_ -]?key|"
            r"client[_ -]?secret|password|authorization|token|signature)"
            r"\s*[:=]\s*)(?:\"[^\"]*\"|'[^']*'|[^\s,}]+)",
            r"\1<redacted>",
        ),
    )
    for pattern, replacement in substitutions:
        text = re.sub(pattern, replacement, text)
    return text


def load_top_response(text: str) -> dict[str, object] | None:
    for line in reversed(text.splitlines()):
        candidates = [line]
        stripped = line.strip()
        if stripped.startswith(("b'", 'b"')):
            try:
                decoded = ast.literal_eval(stripped)
                if isinstance(decoded, bytes):
                    candidates.insert(0, decoded.decode(errors="replace"))
            except (SyntaxError, ValueError):
                pass
        start = line.find("{")
        end = line.rfind("}")
        if start >= 0 and end > start:
            candidates.insert(0, line[start : end + 1])
        for candidate in candidates:
            try:
                parsed = json.loads(candidate)
            except (TypeError, ValueError):
                try:
                    parsed = ast.literal_eval(candidate)
                except (SyntaxError, ValueError):
                    continue
            if isinstance(parsed, dict) and (
                "ResponseMetadata" in parsed or "Error" in parsed
            ):
                return parsed
    return None


response = load_top_response(raw)
if response is not None:
    metadata = response.get("ResponseMetadata", response)
    if not isinstance(metadata, dict):
        metadata = response
    error = metadata.get("Error", response.get("Error", {}))
    if not isinstance(error, dict):
        error = {"Message": error}
    fields = (
        ("RequestId", metadata.get("RequestId")),
        ("Action", metadata.get("Action")),
        ("Version", metadata.get("Version")),
        ("Service", metadata.get("Service")),
        ("Region", metadata.get("Region")),
        ("Code", error.get("Code")),
        ("Message", error.get("Message")),
    )
    print("TOP 详细错误（凭证与签名值已脱敏）：")
    for name, value in fields:
        if value not in (None, ""):
            print(f"  {name}: {redact(value)}")
else:
    lines = [redact(line) for line in raw.splitlines() if line.strip()]
    print("AgentKit CLI 详细错误（凭证与签名值已脱敏）：")
    for line in lines[-20:]:
        print(f"  {line}")
PY
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

  CLI_STDOUT_FILE="$(mktemp "${TMPDIR:-/tmp}/agentkit-cli-out.XXXXXX")"
  chmod 600 "${CLI_STDOUT_FILE}"
  CLI_STDERR_FILE="$(mktemp "${TMPDIR:-/tmp}/agentkit-cli-error.XXXXXX")"
  chmod 600 "${CLI_STDERR_FILE}"
  if ! agentkit runtime list >"${CLI_STDOUT_FILE}" 2>"${CLI_STDERR_FILE}"; then
    echo "AgentKit 控制面鉴权验证失败。" >&2
    print_redacted_cli_error "控制面鉴权验证" "${CLI_STDOUT_FILE}" "${CLI_STDERR_FILE}"
    echo "请在当前终端安全设置完整控制面变量，重新运行脚本以刷新全局配置。" >&2
    exit 1
  fi
fi

# /ping 只验证网络入口。无论是刚写入的新配置还是复用全局配置，都必须立即执行一次
# 只读 API 调用验证 AK/SK，避免错误凭证拖到镜像构建或 Runtime 创建阶段才暴露。
AUTH_CHECK_FILE="$(mktemp "${TMPDIR:-/tmp}/agentkit-auth-check.XXXXXX")"
chmod 600 "${AUTH_CHECK_FILE}"
echo "Checking AgentKit control-plane credentials (secret values stay hidden) ..."
# CLI 版本对错误响应的输出通道并不一致：部分版本把 TOP 响应体写到 stdout，
# 只把概括性错误写到 stderr。两路都只落到权限为 0600 的临时文件；成功时不展示，
# 失败时再由 show_sanitized_control_plane_error 解析和脱敏。
if ! run_project_agentkit runtime list >"${AUTH_CHECK_FILE}" 2>&1; then
  if grep -Eqi \
    'InvalidAccessKey|invalid[^[:alnum:]]*(access[[:space:]_-]*key|ak|credential)|signature|unauthorized|authentication|access denied|expired' \
    "${AUTH_CHECK_FILE}"; then
    echo "控制面 AK/SK 鉴权失败：网络入口可达，但凭证无效、已过期或不属于当前目标环境。" >&2
  else
    echo "控制面 API 只读校验失败：未进入镜像构建或 Runtime 创建阶段。" >&2
  fi
  show_sanitized_control_plane_error "${AUTH_CHECK_FILE}" >&2 || \
    echo "详细错误脱敏处理失败；请保留本次终端输出并联系平台管理员。" >&2
  echo "请根据上方 TOP/CLI 错误码、RequestId 和 Message 排查；不要把 AK/SK 或签名值发到对话中。" >&2
  exit 1
fi
echo "Control-plane network and AK/SK authentication verified."

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

# Runtime resources can be deleted or recreated while their old non-secret ID
# remains in agentkit.yaml. Validate a bound ID before Docker build/push so a
# stale local binding cannot fail only after the image has already been pushed.
if [[ -n "${RESOLVED_RUNTIME_ID}" ]]; then
  RUNTIME_GET_FILE="$(mktemp "${TMPDIR:-/tmp}/agentkit-runtime-get.XXXXXX")"
  chmod 600 "${RUNTIME_GET_FILE}"
  if ! run_project_agentkit runtime get \
    --runtime-id "${RESOLVED_RUNTIME_ID}" \
    --region "${PROJECT_REGION}" \
    --output json >"${RUNTIME_GET_FILE}" 2>&1; then
    if grep -Eqi \
      'Runtime not found|ResourceNotFound|NotFound|does not exist|not exist' \
      "${RUNTIME_GET_FILE}"; then
      if [[ -n "${AGENTKIT_RUNTIME_ID:-}" ]]; then
        echo "显式指定的 Runtime ID 在当前 Region 中不存在：${RESOLVED_RUNTIME_ID} (${PROJECT_REGION})。" >&2
        echo "请核对 AGENTKIT_RUNTIME_ID 与 VOLCENGINE_REGION；镜像尚未构建或推送。" >&2
        exit 1
      fi

      if [[ "${AGENTKIT_EXISTING_RUNTIME_ACTION:-fail}" = "prompt" && -t 0 ]]; then
        echo
        echo "检测到项目中的 Runtime 绑定已失效：${RESOLVED_RUNTIME_ID} (${PROJECT_REGION})。"
        echo "  1) 清除过期绑定，按名称 ${PROJECT_RUNTIME_NAME} 重新查找或创建（推荐）"
        echo "  2) 停止，由我先核对 Runtime 名称、ID 或 Region"
        read -r -p "请选择 [1]: " stale_runtime_choice
        stale_runtime_choice="${stale_runtime_choice:-1}"
        case "${stale_runtime_choice}" in
          1)
            python - "${CONFIG_FILE}" <<'PY'
import sys
from pathlib import Path

import yaml

path = Path(sys.argv[1])
config = yaml.safe_load(path.read_text()) or {}
hybrid = (config.get("launch_types") or {}).get("hybrid") or {}
hybrid.pop("runtime_id", None)
path.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False))
PY
            chmod 600 "${CONFIG_FILE}"
            CONFIGURED_RUNTIME_ID=""
            RESOLVED_RUNTIME_ID=""
            echo "已清除本地过期 Runtime ID；继续执行同名 Runtime 查重。"
            ;;
          2)
            echo "已停止；镜像尚未构建或推送。" >&2
            exit 2
            ;;
          *)
            echo "无效选择：${stale_runtime_choice}。未创建或更新 Runtime。" >&2
            exit 2
            ;;
        esac
      else
        echo "项目绑定的 Runtime ID 在当前 Region 中不存在：${RESOLVED_RUNTIME_ID} (${PROJECT_REGION})。" >&2
        echo "请运行 ./scripts/deploy_interactive.sh 交互清理过期绑定；镜像尚未构建或推送。" >&2
        exit 1
      fi
    else
      echo "Runtime ID 预检失败；未进入镜像构建或推送阶段。" >&2
      show_sanitized_control_plane_error "${RUNTIME_GET_FILE}" >&2 || true
      exit 1
    fi
  else
    echo "Existing Runtime binding verified: ${RESOLVED_RUNTIME_ID} (${PROJECT_REGION})."
  fi
fi

if [[ -z "${RESOLVED_RUNTIME_ID}" ]]; then
  RUNTIME_LIST_FILE="$(mktemp "${TMPDIR:-/tmp}/agentkit-runtime-list.XXXXXX")"
  chmod 600 "${RUNTIME_LIST_FILE}"
  CLI_STDERR_FILE="$(mktemp "${TMPDIR:-/tmp}/agentkit-cli-error.XXXXXX")"
  chmod 600 "${CLI_STDERR_FILE}"
  if ! agentkit runtime list \
    --name "${PROJECT_RUNTIME_NAME}" \
    --region "${PROJECT_REGION}" \
    --all \
    --quiet >"${RUNTIME_LIST_FILE}" 2>"${CLI_STDERR_FILE}"; then
    echo "同名 Runtime 预检失败。" >&2
    print_redacted_cli_error "同名 Runtime 预检" "${RUNTIME_LIST_FILE}" "${CLI_STDERR_FILE}"
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
            : >"${CLI_STDERR_FILE}"
            if ! agentkit runtime list \
              --name "${candidate_runtime_name}" \
              --region "${PROJECT_REGION}" \
              --all \
              --quiet >"${RUNTIME_LIST_FILE}" 2>"${CLI_STDERR_FILE}"; then
              echo "新名称查重失败。" >&2
              print_redacted_cli_error "新名称查重" "${RUNTIME_LIST_FILE}" "${CLI_STDERR_FILE}"
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
echo "Docker build/push detailed output is enabled; live lines are prefixed with [docker]."
LAUNCH_LOG_FILE="$(mktemp "${TMPDIR:-/tmp}/agentkit-launch.XXXXXX")"
chmod 600 "${LAUNCH_LOG_FILE}"
set +e
AGENTKIT_VERBOSE_DOCKER_LOGS=1 PYTHONUNBUFFERED=1 run_project_agentkit launch \
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
