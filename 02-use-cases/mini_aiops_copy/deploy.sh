#!/bin/bash
set -euo pipefail

agentkit config \
  --agent_name mini_aiops \
  --entry_point agent.py \
  --description "a mini agent for aiops" \
  --launch_type cloud \
  --image_tag v1.0.0 \
  --region cn-beijing

agentkit launch

