#!/usr/bin/env bash
# Run the Knowledge/Memory proof without persisting Runtime credentials.
set -euo pipefail
set +x

endpoint="${RUNTIME_ENDPOINT:-}"
api_key="${RUNTIME_API_KEY:-}"

if [[ -n "$endpoint" ]]; then
  read -r -p "Reuse Runtime Endpoint from this terminal? [Y/n] " reuse_endpoint
  if [[ "${reuse_endpoint:-Y}" =~ ^[Nn]$ ]]; then
    endpoint=""
  fi
fi
while [[ -z "$endpoint" ]]; do
  read -r -p "Runtime Endpoint (http:// or https://): " endpoint
done
if [[ ! "$endpoint" =~ ^https?:// ]]; then
  echo "Runtime Endpoint must start with http:// or https://." >&2
  exit 2
fi
# The console "调用信息" page shows the URL already ending in /invoke, while
# verify_knowledge_memory.py appends /invoke itself. Strip a pasted trailing
# /invoke (with optional slash) so the request is not sent to /invoke/invoke.
endpoint="${endpoint%/}"
endpoint="${endpoint%/invoke}"

if [[ -n "$api_key" ]]; then
  read -r -p "Reuse Runtime API Key from this terminal? [Y/n] " reuse_key
  if [[ "${reuse_key:-Y}" =~ ^[Nn]$ ]]; then
    api_key=""
  fi
fi
while [[ -z "$api_key" ]]; do
  read -r -s -p "Runtime API Key (hidden input): " api_key
  printf '\n'
done

# Values are passed only to this child process; they are neither exported in
# the parent shell nor written to a file or echoed.
RUNTIME_ENDPOINT="$endpoint" RUNTIME_API_KEY="$api_key" \
  uv run --frozen scripts/verify_knowledge_memory.py "$@"
