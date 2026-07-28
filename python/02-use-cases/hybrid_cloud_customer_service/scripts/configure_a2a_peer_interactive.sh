#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MAIN_CONFIG_FILE="${AGENTKIT_MAIN_CONFIG_FILE:-${PROJECT_ROOT}/agentkit.yaml}"

if [[ ! -t 0 ]]; then
  echo "A2A 主 Runtime 配置需要终端输入。" >&2
  exit 1
fi
if ! command -v uv >/dev/null 2>&1; then
  echo "未安装 uv。请按 README 的“首次环境准备”安装 uv 后重试。" >&2
  exit 1
fi
if [[ ! -f "${MAIN_CONFIG_FILE}" ]]; then
  echo "未找到主 Runtime 本地绑定：${MAIN_CONFIG_FILE}。请先完成主客服 Runtime 部署。" >&2
  exit 1
fi

main_runtime_id="$(uv run --frozen python - "${MAIN_CONFIG_FILE}" <<'PY'
import sys
from pathlib import Path

import yaml

config = yaml.safe_load(Path(sys.argv[1]).read_text()) or {}
hybrid = (config.get("launch_types") or {}).get("hybrid") or {}
print(hybrid.get("runtime_id") or "")
PY
)"
if [[ -z "${main_runtime_id}" ]]; then
  read -r -p "主客服 Runtime ID: " main_runtime_id
fi
if [[ -z "${main_runtime_id}" ]]; then
  echo "必须提供主客服 Runtime ID。" >&2
  exit 1
fi

echo "将只更新主客服 Runtime：${main_runtime_id}"
read -r -p "确认继续 [y/N]: " confirmed
if [[ "${confirmed}" != "y" && "${confirmed}" != "Y" ]]; then
  echo "已取消；未修改 Runtime。"
  exit 0
fi

region=""
while [[ -z "${region}" ]]; do
  read -r -p "主客服 Runtime 的 Region（例如 cn-beijing）: " region
done

peer_base=""
while [[ -z "${peer_base}" ]]; do
  read -r -p "A2A 中心登记的服务地址（或以 /a2a 结尾的地址）: " peer_base
  if [[ ! "${peer_base}" =~ ^https?:// ]] || [[ "${peer_base}" =~ [[:space:]@] ]]; then
    echo "请输入不含凭据和空格的 http(s) 服务地址。" >&2
    peer_base=""
  fi
done
peer_base="${peer_base%/}"
if [[ "${peer_base}" == */a2a ]]; then
  peer_rpc_url="${peer_base}"
else
  peer_rpc_url="${peer_base}/a2a"
fi

peer_key=""
while [[ -z "${peer_key}" ]]; do
  read -r -s -p "数据 Agent Runtime API Key（输入不可见）: " peer_key
  printf '\n' >&2
done

export A2A_DATA_AGENT_API_KEY="${peer_key}"
trap 'unset A2A_DATA_AGENT_API_KEY peer_key' EXIT

echo "正在从服务地址读取 AgentCard（不会显示 API Key）..."
card_summary="$(
  uv run --frozen python "${PROJECT_ROOT}/scripts/discover_a2a_card.py" \
    --service-url "${peer_base}"
)"
peer_agent_name="$(
  uv run --frozen python - "${card_summary}" <<'PY'
import json
import sys

print(json.loads(sys.argv[1])["name"])
PY
)"
capability_ids="$(
  uv run --frozen python - "${card_summary}" <<'PY'
import json
import sys

print("\n".join(json.loads(sys.argv[1])["capability_ids"]))
PY
)"
capability_count="$(printf '%s\n' "${capability_ids}" | awk 'NF {count++} END {print count+0}')"

echo "已发现 AgentCard：${peer_agent_name}"
if [[ "${capability_count}" -eq 1 ]]; then
  peer_capability_id="${capability_ids}"
  echo "已自动选择 AgentCard 能力 ID：${peer_capability_id}"
else
  echo "AgentCard 声明了多个能力："
  while IFS= read -r capability_id; do
    [[ -n "${capability_id}" ]] && printf '  - %s\n' "${capability_id}"
  done <<< "${capability_ids}"
  peer_capability_id=""
  while [[ -z "${peer_capability_id}" ]]; do
    read -r -p "请选择其中一个 AgentCard 能力 ID: " peer_capability_id
    if ! printf '%s\n' "${capability_ids}" | grep -Fqx "${peer_capability_id}"; then
      echo "输入值不在 AgentCard 的 skills[].id 列表中。" >&2
      peer_capability_id=""
    fi
  done
fi

uv run --frozen python "${PROJECT_ROOT}/scripts/configure_a2a_peer.py" \
  --runtime-id "${main_runtime_id}" \
  --region "${region}" \
  --rpc-url "${peer_rpc_url}" \
  --agent-name "${peer_agent_name}" \
  --capability-id "${peer_capability_id}"

echo "A2A 对端已写入主客服 Runtime 并完成 release。"
echo "下一步：从主 Runtime 的快速调用页获取其 Endpoint/API Key，按 A2A 步骤文档发起委派验收。"
