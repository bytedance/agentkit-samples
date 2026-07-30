#!/usr/bin/env bash
set -euo pipefail

# Deploy a standalone A2A data agent without touching the primary
# customer-service Runtime binding. The generated config is ignored by Git.
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
A2A_CONFIG_FILE="${AGENTKIT_A2A_CONFIG_FILE:-${PROJECT_ROOT}/agentkit.a2a.yaml}"
CREATED_A2A_CONFIG=0

if [[ ! -t 0 ]]; then
  echo "A2A 交互部署需要终端输入；自动化环境请使用 AGENTKIT_CONFIG_FILE 和 scripts/deploy_hybrid.sh。" >&2
  exit 1
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "未安装 uv。请按 README 的“首次环境准备”安装 uv，重新打开终端后再运行。" >&2
  exit 1
fi

if [[ ! -f "${A2A_CONFIG_FILE}" ]]; then
  cp "${PROJECT_ROOT}/agentkit.yaml.example" "${A2A_CONFIG_FILE}"
  chmod 600 "${A2A_CONFIG_FILE}"
  CREATED_A2A_CONFIG=1
fi

read -r -p "数据 Agent 展示名称 [hybrid-cloud-complaint-data-agent]: " a2a_agent_name
a2a_agent_name="${a2a_agent_name:-hybrid-cloud-complaint-data-agent}"
read -r -p "AgentCard 能力 ID（skills[].id）[complaint-trend-analysis]: " a2a_skill_id
a2a_skill_id="${a2a_skill_id:-complaint-trend-analysis}"
if [[ ! "${a2a_skill_id}" =~ ^[a-z0-9][a-z0-9._-]{1,62}$ ]]; then
  echo "AgentCard 能力 ID 只能包含小写字母、数字、点、下划线或连字符。" >&2
  exit 2
fi

uv run --frozen python - \
  "${A2A_CONFIG_FILE}" "${CREATED_A2A_CONFIG}" "${a2a_agent_name}" "${a2a_skill_id}" <<'PY'
import sys
from pathlib import Path

import yaml

path = Path(sys.argv[1])
created = sys.argv[2] == "1"
agent_name = sys.argv[3]
skill_id = sys.argv[4]
config = yaml.safe_load(path.read_text()) or {}
runtime_envs = config.setdefault("common", {}).setdefault("runtime_envs", {})
runtime_envs["AGENT_APP_MODE"] = "a2a_data_analyst"
runtime_envs["PORT"] = "8000"
runtime_envs["A2A_AGENT_NAME"] = agent_name
runtime_envs["A2A_AGENT_SKILL_ID"] = skill_id
hybrid = config.setdefault("launch_types", {}).setdefault("hybrid", {})
# The public template belongs to the main customer-service Runtime.  On first
# A2A use, always derive a distinct name rather than letting the generic
# template name select or overwrite the primary Runtime.  The exact legacy
# template name is also repaired before any A2A Runtime ID is bound.
if created or (
    not hybrid.get("runtime_id")
    and hybrid.get("runtime_name") == "hybrid-cloud-customer-service"
):
    hybrid["runtime_name"] = "hybrid-cloud-customer-service-a2a"
path.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False))
PY
chmod 600 "${A2A_CONFIG_FILE}"

echo "将部署独立的 A2A 数据分析 Runtime：hybrid-cloud-customer-service-a2a。"
echo "首次部署默认使用 -a2a 后缀，不会修改主客服 Runtime 的本地绑定。"
echo "AgentCard：${a2a_agent_name}；业务能力：${a2a_skill_id}。"
echo "说明：该能力 ID 来自 A2A AgentCard 的 skills[].id，与 Skills 中心、Skills Space 无关。"
echo "接下来会像主 Runtime 一样交互收集模型配置；模型 Key 只进入临时部署配置。"
echo "A2A 中心的首次空间/AgentCard 授权仍需在控制台确认。"

export AGENTKIT_CONFIG_FILE="${A2A_CONFIG_FILE}"
export AGENTKIT_MODEL_REQUIRED=1
export AGENTKIT_DEPLOY_MODE=live
export AGENTKIT_POST_DEPLOY_INVOKE=0
exec bash "${PROJECT_ROOT}/scripts/deploy_interactive.sh"
