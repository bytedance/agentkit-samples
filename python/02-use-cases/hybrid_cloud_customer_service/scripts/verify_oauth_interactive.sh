#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ ! -t 0 ]]; then
  echo "OAuth 验收需要交互输入 Endpoint 与用户池 Client 凭据。" >&2
  exit 1
fi
if ! command -v uv >/dev/null 2>&1; then
  echo "缺少 uv；请先按 README 完成环境准备。" >&2
  exit 1
fi

oauth_runtime_endpoint="${OAUTH_RUNTIME_ENDPOINT:-}"
while [[ -z "${oauth_runtime_endpoint}" ]]; do
  read -r -p "独立 OAuth Runtime Endpoint（http:// 或 https://）: " oauth_runtime_endpoint
done
if [[ ! "${oauth_runtime_endpoint}" =~ ^https?:// ]]; then
  echo "Runtime Endpoint 必须以 http:// 或 https:// 开头。" >&2
  exit 2
fi

auth_scheme=""
while [[ "${auth_scheme}" != "http" && "${auth_scheme}" != "https" ]]; do
  read -r -p "用户池认证域名协议 [http]: " auth_scheme
  auth_scheme="${auth_scheme:-http}"
done
auth_host=""
while [[ -z "${auth_host}" ]]; do
  read -r -p "用户池认证域名（不含协议和路径）: " auth_host
done
user_pool_id=""
while [[ -z "${user_pool_id}" ]]; do
  read -r -p "可访问用户池 ID: " user_pool_id
done
oauth_client_id="${OAUTH_CLIENT_ID:-}"
while [[ -z "${oauth_client_id}" ]]; do
  read -r -p "用户池 Client ID: " oauth_client_id
done
oauth_client_secret="${OAUTH_CLIENT_SECRET:-}"
while [[ -z "${oauth_client_secret}" ]]; do
  read -r -s -p "用户池 Client Secret（输入不可见且不落盘）: " oauth_client_secret
  echo
done

export OAUTH_RUNTIME_ENDPOINT="${oauth_runtime_endpoint}"
export OAUTH_DISCOVERY_URL="${auth_scheme}://${auth_host}/userpool/${user_pool_id}/.well-known/openid-configuration"
export OAUTH_CLIENT_ID="${oauth_client_id}"
export OAUTH_CLIENT_SECRET="${oauth_client_secret}"

echo "将从用户池获取短期 Token，并用 Bearer Token 调用独立 OAuth Runtime。"
echo "Token 与 Client Secret 均不会显示或落盘。"
uv run --frozen python "${PROJECT_ROOT}/scripts/verify_oauth.py" "$@"
