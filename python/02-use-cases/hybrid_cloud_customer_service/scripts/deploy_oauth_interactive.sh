#!/usr/bin/env bash
set -euo pipefail

# Deploy a sibling OAuth JWT Runtime.  Its config and Runtime binding are
# deliberately separate from the primary API-Key Runtime.
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OAUTH_CONFIG_FILE="${AGENTKIT_OAUTH_CONFIG_FILE:-${PROJECT_ROOT}/agentkit.oauth.yaml}"
CREATED_OAUTH_CONFIG=0

if [[ ! -t 0 ]]; then
  echo "OAuth 交互部署需要终端输入；自动化环境请使用独立 AGENTKIT_CONFIG_FILE。" >&2
  exit 1
fi

for command_name in uv curl; do
  if ! command -v "${command_name}" >/dev/null 2>&1; then
    echo "缺少命令：${command_name}" >&2
    exit 1
  fi
done

if [[ ! -f "${OAUTH_CONFIG_FILE}" ]]; then
  cp "${PROJECT_ROOT}/agentkit.yaml.example" "${OAUTH_CONFIG_FILE}"
  chmod 600 "${OAUTH_CONFIG_FILE}"
  CREATED_OAUTH_CONFIG=1
fi

auth_scheme=""
while [[ "${auth_scheme}" != "http" && "${auth_scheme}" != "https" ]]; do
  read -r -p "用户池认证域名协议 [http]: " auth_scheme
  auth_scheme="${auth_scheme:-http}"
done

auth_host=""
while [[ -z "${auth_host}" ]]; do
  read -r -p "用户池认证域名（例如 auth.<环境域名>）: " auth_host
  if [[ "${auth_host}" =~ ^https?:// || "${auth_host}" == */* ||
    "${auth_host}" =~ [[:space:]] ]]; then
    echo "只填写域名，不要包含协议、路径或空白字符。" >&2
    auth_host=""
  fi
done

user_pool_id=""
while [[ -z "${user_pool_id}" ]]; do
  read -r -p "可访问用户池 ID: " user_pool_id
done

allowed_client_id=""
while [[ -z "${allowed_client_id}" ]]; do
  read -r -p "允许访问此 Runtime 的用户池 Client ID: " allowed_client_id
done

discovery_url="${auth_scheme}://${auth_host}/userpool/${user_pool_id}/.well-known/openid-configuration"
discovery_file="$(mktemp "${TMPDIR:-/tmp}/agentkit-oidc-discovery.XXXXXX")"
chmod 600 "${discovery_file}"
cleanup() {
  rm -f -- "${discovery_file}"
}
trap cleanup EXIT

echo "正在只读验证用户池 OIDC Discovery（响应内容不打印）..."
curl --fail --silent --show-error \
  --connect-timeout 10 \
  --max-time 20 \
  "${discovery_url}" >"${discovery_file}"

uv run --frozen python - "${discovery_file}" <<'PY'
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text())
missing = [key for key in ("issuer", "token_endpoint", "jwks_uri") if not payload.get(key)]
if missing:
    raise SystemExit(f"OIDC Discovery 缺少字段：{', '.join(missing)}")
PY
echo "OIDC Discovery 验证通过。"

uv run --frozen python - \
  "${OAUTH_CONFIG_FILE}" \
  "${CREATED_OAUTH_CONFIG}" \
  "${discovery_url}" \
  "${allowed_client_id}" \
  "${PROJECT_ROOT}/agentkit.yaml" <<'PY'
import sys
from pathlib import Path

import yaml

path = Path(sys.argv[1])
created = sys.argv[2] == "1"
discovery_url = sys.argv[3]
client_id = sys.argv[4]
primary_path = Path(sys.argv[5])
config = yaml.safe_load(path.read_text()) or {}
hybrid = config.setdefault("launch_types", {}).setdefault("hybrid", {})
primary = yaml.safe_load(primary_path.read_text()) if primary_path.exists() else {}
primary_hybrid = ((primary or {}).get("launch_types") or {}).get("hybrid") or {}
primary_runtime_id = str(primary_hybrid.get("runtime_id") or "")
oauth_runtime_id = str(hybrid.get("runtime_id") or "")
if primary_runtime_id and oauth_runtime_id == primary_runtime_id:
    raise SystemExit(
        "拒绝部署：agentkit.oauth.yaml 意外绑定了主 Runtime ID；"
        "请移走该文件后重新运行。"
    )

# Never let the first OAuth deployment inherit or overwrite the primary
# customer-service Runtime binding from the public template.
if created or (
    not hybrid.get("runtime_id")
    and hybrid.get("runtime_name") == "hybrid-cloud-customer-service"
):
    hybrid["runtime_name"] = "hybrid-cloud-customer-service-oauth"
    hybrid.pop("runtime_id", None)

hybrid["runtime_auth_type"] = "custom_jwt"
hybrid["runtime_jwt_discovery_url"] = discovery_url
hybrid["runtime_jwt_allowed_clients"] = [client_id]
path.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False))
PY
chmod 600 "${OAUTH_CONFIG_FILE}"

echo
echo "将部署独立 OAuth Runtime：hybrid-cloud-customer-service-oauth。"
echo "主 Runtime 的 Name/ID、API Key 和组件关联不会被修改。"
echo "用户池 Client Secret 不属于部署配置；脚本未读取、未写入。"

export AGENTKIT_CONFIG_FILE="${OAUTH_CONFIG_FILE}"
export AGENTKIT_MODEL_REQUIRED=1
export AGENTKIT_DEPLOY_MODE=live
if [[ "${auth_scheme}" = "http" ]]; then
  export AGENTKIT_ALLOW_HTTP_OIDC=1
  echo "注意：当前 POC 用户池使用 HTTP Discovery；已启用仅限本次进程的 CLI 兼容模式。"
  echo "正式环境必须使用 HTTPS，届时不会启用该兼容模式。"
fi
# OAuth Runtime 尚无 API Key；部署后的首个调用由专用验收脚本完成。
export AGENTKIT_POST_DEPLOY_INVOKE=0
exec bash "${PROJECT_ROOT}/scripts/deploy_interactive.sh"
