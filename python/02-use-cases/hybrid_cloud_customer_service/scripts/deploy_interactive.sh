#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ ! -t 0 ]]; then
  echo "交互式部署需要终端输入；自动化环境请设置环境变量后运行 scripts/deploy_hybrid.sh。" >&2
  exit 1
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "未安装 uv。请按 README 的“首次环境准备”安装 uv，重新打开终端后再运行。" >&2
  exit 1
fi

read_global_target() {
  uv run --frozen python - <<'PY' 2>/dev/null || true
from pathlib import Path

import yaml

path = Path.home() / ".agentkit" / "config.yaml"
config = yaml.safe_load(path.read_text()) if path.exists() else {}
config = config or {}
service = ((config.get("services") or {}).get("agentkit") or {})
print(
    service.get("scheme") or "",
    service.get("host") or "",
    config.get("region") or "",
)
PY
}

# 静默读取机密值：不回显明文，读完后仅打印字符位数作为“已收到”反馈，并保证非空。
# 用法：read_secret "提示语: " 目标变量名
read_secret() {
  local __prompt="$1" __outvar="$2" __value=""
  while [[ -z "${__value}" ]]; do
    read -r -s -p "${__prompt}" __value
    echo
  done
  echo "  已收到 ${#__value} 位字符（内容不显示）。"
  printf -v "${__outvar}" '%s' "${__value}"
}

read -r global_scheme global_host global_region < <(read_global_target) || true

terminal_control_complete=0
if [[ -n "${AGENTKIT_OPENAPI_HOST:-}" &&
  -n "${VOLCENGINE_ACCESS_KEY:-}" &&
  -n "${VOLCENGINE_SECRET_KEY:-}" ]]; then
  terminal_control_complete=1
fi

configure_new_target=0
if [[ "${terminal_control_complete}" -eq 1 ]]; then
  echo "检测到当前终端已提供目标环境：${AGENTKIT_OPENAPI_SCHEME:-http}://${AGENTKIT_OPENAPI_HOST}"
  echo "  1) 使用当前终端配置"
  echo "  2) 交互配置另一个目标环境"
  read -r -p "请选择 [1]: " target_choice
  target_choice="${target_choice:-1}"
  [[ "${target_choice}" = "1" ]] || configure_new_target=1
elif [[ -n "${global_host}" ]]; then
  echo "检测到 AgentKit CLI 已配置目标环境：${global_scheme:-http}://${global_host}"
  echo "  1) 复用已有 CLI 配置"
  echo "  2) 交互配置另一个目标环境"
  read -r -p "请选择 [1]: " target_choice
  target_choice="${target_choice:-1}"
  if [[ "${target_choice}" = "1" ]]; then
    unset AGENTKIT_OPENAPI_HOST AGENTKIT_OPENAPI_SCHEME
    unset VOLCENGINE_ACCESS_KEY VOLCENGINE_SECRET_KEY
  else
    configure_new_target=1
  fi
else
  echo "未检测到可复用的 AgentKit CLI 目标环境，开始交互配置。"
  configure_new_target=1
fi

if [[ "${configure_new_target}" -eq 1 ]]; then
  target_scheme=""
  while [[ "${target_scheme}" != "http" && "${target_scheme}" != "https" ]]; do
    read -r -p "OpenAPI 协议 [http]: " target_scheme
    target_scheme="${target_scheme:-http}"
    if [[ "${target_scheme}" != "http" && "${target_scheme}" != "https" ]]; then
      echo "协议只能是 http 或 https。" >&2
    fi
  done

  target_host=""
  while [[ -z "${target_host}" ]]; do
    read -r -p "OpenAPI 域名（不含协议和路径）: " target_host
    if [[ "${target_host}" =~ ^https?:// || "${target_host}" == */* ||
      "${target_host}" =~ [[:space:]] ]]; then
      echo "只填写域名，不要包含协议、路径或空白字符。" >&2
      target_host=""
    fi
  done

  read_secret "目标环境 Access Key（输入不可见）: " target_access_key
  read_secret "目标环境 Secret Key（输入不可见）: " target_secret_key

  export AGENTKIT_OPENAPI_SCHEME="${target_scheme}"
  export AGENTKIT_OPENAPI_HOST="${target_host}"
  export VOLCENGINE_ACCESS_KEY="${target_access_key}"
  export VOLCENGINE_SECRET_KEY="${target_secret_key}"
  echo "目标环境已收集：${AGENTKIT_OPENAPI_SCHEME}://${AGENTKIT_OPENAPI_HOST}，AK/SK=<redacted>。"
fi

detected_region="${VOLCENGINE_REGION:-${global_region}}"
if [[ -n "${detected_region}" ]]; then
  echo "检测到已有 Region：${detected_region}（仅供参考，不会自动采用）。"
fi

confirmed_region=""
while [[ -z "${confirmed_region}" ]]; do
  read -r -p "请输入本次 Runtime 的目标 Region（例如 cn-beijing）: " confirmed_region
done
VOLCENGINE_REGION="${confirmed_region}"
export VOLCENGINE_REGION
echo "本次部署 Region：${VOLCENGINE_REGION}"
export AGENTKIT_EXISTING_RUNTIME_ACTION="prompt"

DEPLOY_MODE="${AGENTKIT_DEPLOY_MODE:-live}"
export AGENTKIT_DEPLOY_MODE="${DEPLOY_MODE}"
MODEL_REQUIRED="${AGENTKIT_MODEL_REQUIRED:-1}"

case "${MODEL_REQUIRED}" in
  0|1) ;;
  *)
    echo "AGENTKIT_MODEL_REQUIRED 只支持 0 或 1；默认是 1。" >&2
    exit 1
    ;;
esac

if [[ "${DEPLOY_MODE}" = "live" && "${MODEL_REQUIRED}" = "1" ]]; then
  echo
  echo "选择模型配置："
  echo "  1) Demo 默认方舟配置（只需 API Key）"
  echo "  2) 自定义 OpenAI-compatible 模型（Name、API Base、API Key）"
  read -r -p "请选择 [1]: " model_profile
  model_profile="${model_profile:-1}"

  case "${model_profile}" in
    1)
      export MODEL_AGENT_NAME="${MODEL_AGENT_NAME:-${ARK_MODEL:-deepseek-v4-pro-260425}}"
      export MODEL_AGENT_API_BASE="${MODEL_AGENT_API_BASE:-${ARK_BASE_URL:-https://ark.cn-beijing.volces.com/api/v3}}"
      ;;
    2)
      current_model_name="${MODEL_AGENT_NAME:-${ARK_MODEL:-}}"
      current_api_base="${MODEL_AGENT_API_BASE:-${ARK_BASE_URL:-}}"
      while [[ -z "${current_model_name}" ]]; do
        read -r -p "Model Name / Endpoint ID: " current_model_name
      done
      while [[ -z "${current_api_base}" ]]; do
        read -r -p "OpenAI-compatible API Base: " current_api_base
      done
      export MODEL_AGENT_NAME="${current_model_name}"
      export MODEL_AGENT_API_BASE="${current_api_base}"
      ;;
    *)
      echo "无效选择：${model_profile}" >&2
      exit 1
      ;;
  esac

  model_api_key="${MODEL_AGENT_API_KEY:-${ARK_API_KEY:-}}"
  if [[ -z "${model_api_key}" ]]; then
    read_secret "Model API Key（输入不可见且不落盘）: " model_api_key
  fi
  export MODEL_AGENT_API_KEY="${model_api_key}"

  echo "模型配置已收集：Name=${MODEL_AGENT_NAME}，API Base=${MODEL_AGENT_API_BASE}，API Key=<redacted>。"
elif [[ "${DEPLOY_MODE}" = "live" ]]; then
  echo "本次 Runtime 不调用模型；跳过模型配置。"
fi

echo
echo "开始部署；模型 Key 仅进入临时部署配置。新输入的控制面配置会由 AgentKit CLI 保存到本机全局配置。"
exec bash "${PROJECT_ROOT}/scripts/deploy_hybrid.sh"
