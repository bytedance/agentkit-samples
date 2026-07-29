---
name: byted-util-volcengine-cloud-detect
description: Volcengine Cloud Detect (云拨测) API integration for creating detection tasks, retrieving results, generating reports, and managing detection nodes. Use when the user wants to (1) create network detection/dialing tasks (拨测任务), (2) check task results or generate detection reports, (3) list or search detection nodes (拨测节点), (4) manage existing tasks (list/stop/restart/delete). Triggers include natural language requests about website monitoring, network latency testing, HTTP detection, ping tests, DNS tests, node queries, or report generation for Volcengine cloud detect service.
---

# Volcengine Cloud Detect

Interact with Volcengine Cloud Detect API (云拨测) through natural language. All API calls are handled via `scripts/volc_detect.py`. For detailed API parameters, read `references/api_docs.md`.

## Prerequisites

Volcengine credentials are required:
- `VOLC_ACCESSKEY`: Access Key
- `VOLC_SECRETKEY`: Secret Key

Before executing any command, check whether both credentials exist in environment variables:

```bash
test -n "$VOLC_ACCESSKEY" && test -n "$VOLC_SECRETKEY"
```

If either value is missing, ask the user to provide the missing AK/SK, then write them to the current shell environment and persist them to the user's shell profile:

```bash
export VOLC_ACCESSKEY="USER_PROVIDED_ACCESS_KEY"
export VOLC_SECRETKEY="USER_PROVIDED_SECRET_KEY"

SHELL_PROFILE="${ZDOTDIR:-$HOME}/.zshrc"
grep -q '^export VOLC_ACCESSKEY=' "$SHELL_PROFILE" 2>/dev/null \
  && sed -i '' 's|^export VOLC_ACCESSKEY=.*|export VOLC_ACCESSKEY="USER_PROVIDED_ACCESS_KEY"|' "$SHELL_PROFILE" \
  || printf '\nexport VOLC_ACCESSKEY="USER_PROVIDED_ACCESS_KEY"\n' >> "$SHELL_PROFILE"
grep -q '^export VOLC_SECRETKEY=' "$SHELL_PROFILE" 2>/dev/null \
  && sed -i '' 's|^export VOLC_SECRETKEY=.*|export VOLC_SECRETKEY="USER_PROVIDED_SECRET_KEY"|' "$SHELL_PROFILE" \
  || printf 'export VOLC_SECRETKEY="USER_PROVIDED_SECRET_KEY"\n' >> "$SHELL_PROFILE"
```

Never run `scripts/volc_detect.py` until both `VOLC_ACCESSKEY` and `VOLC_SECRETKEY` are available.

## Default Parameters for CreateTask

When user creates a task without specifying all parameters, use these defaults:

| Parameter | Default Value | Notes |
|-----------|--------------|-------|
| ProjectName | `default` | Always use unless user specifies |
| Type | `1` (HTTP(S)) | Task type |
| Name | `{current_time}_claw_detect` | Format: YYYYMMDD_HHMMSS_claw_detect |
| Address | **(required)** | Must ask user if not provided |
| NodeCount | `5` | Samples per line |
| IntervalSeconds | `60` | Detection frequency |
| FinishTime | `current_time + 90 seconds` | 1.5 minutes after creation |
| LineIdList | **(required)** | Must obtain from ListNodes |

**Task Type Mapping**: 1=HTTP(S), 2=DNS, 3=PING, 5=UDP, 6=TCP, 8=Upload, 9=Download, 11=PageElement

**Interval Options** (seconds): 60, 120, 180, 300, 600, 900, 1200, 1800, 3600, 7200, 10800, 21600, 43200, 86400

## Workflow: Creating a Detection Task

1. **Collect required info**: Ask user for `Address` (target URL). If not provided, prompt for it.
2. **Determine node selection**: Before creating task, ask user about detection requirements to filter nodes:
   - Target region? (e.g., mainland China, specific provinces/cities)
   - ISP preference? (e.g., China Telecom, China Mobile, China Unicom)
   - Node type? (IDC = data center, LastMile = end user)
3. **Fetch and filter nodes**: Run `list-nodes`, then fuzzy-search based on user requirements.
4. **Confirm LineIdList**: Show matched nodes to user and confirm selection.
5. **Create task**: Run `create-task` with all parameters including confirmed LineIdList.
6. **Return TaskId**: Present the created task ID to user.

### Node Selection Conversation Guide

When user says "create a detection task for baidu.com", respond by:
1. Confirming the target address
2. Asking about geographic/ISP requirements
3. Running `list-nodes` to show available options
4. Using `fuzzy-search-nodes` to filter based on user's description

Example user requirements to node filters:
- "mainland China + Telecom" → `--is-mainland true` + search "电信"
- "Beijing IDC nodes" → search "北京 IDC"
- "Shanghai and Guangzhou Mobile" → search "上海 移动" and "广州 移动"
- "all over the country" → `--is-mainland true`, select diverse nodes

## Workflow: Getting Results & Reports

1. **Get task results**: Run `get-result` with TaskId and time range (must be <= 1 hour).
2. **Generate report**: Run `generate-report` to produce summary statistics.
3. **Present findings**: Show key metrics in a concise format.

### Report Format

Present reports using this structure:

```
## Detection Report for {TaskName} (ID: {TaskId})

**Time Range**: {start} ~ {end}
**Total Samples**: {N}
**Success Rate**: {X}%

### Latency Statistics (ms)
| Metric | Value |
|--------|-------|
| Avg | {avg} |
| Min | {min} |
| Max | {max} |
| P90 | {p90} |

### Status Code Distribution
| Code | Count |
|------|-------|
| ... | ... |

### Issues
- {N} failures from {region-isp} nodes
- Top error: {error_code} ({count} occurrences)
```

## Workflow: Managing Tasks

- **List tasks**: `list-tasks` with optional filters (--name, --address)
- **Stop task**: `stop-task --task-id ID`
- **Restart task**: `restart-task --task-id ID`
- **Delete task**: `delete-task --task-id ID` (confirm with user first)
- **Get task details**: `get-task --task-id ID`

## Workflow: Node Discovery

- **List all nodes**: `list-nodes [--is-mainland true|false]`
- **Filter by type**: `list-nodes --line-types 1,2` (1=LastMile, 2=IDC)
- **Fuzzy search**: `fuzzy-search-nodes "search query"`

## Script Commands Reference

All commands use `python scripts/volc_detect.py`:

```bash
# Create task
python scripts/volc_detect.py create-task \
  --address "https://example.com" \
  --name "task_name" \
  --type 1 \
  --node-count 5 \
  --interval-seconds 60 \
  --finish-time TIMESTAMP \
  --line-ids 228,229,230 \
  --http-method 1

# Get results
python scripts/volc_detect.py get-result \
  --task-id 12345 \
  --start-time 1672531200 \
  --end-time 1672534800 \
  --page-size 500

# List nodes
python scripts/volc_detect.py list-nodes --is-mainland true

# Fuzzy search nodes
python scripts/volc_detect.py fuzzy-search-nodes "北京 电信 IDC"

# Generate report
python scripts/volc_detect.py generate-report \
  --task-id 12345 \
  --start-time 1672531200 \
  --end-time 1672534800

# Task management
python scripts/volc_detect.py list-tasks --page-size 20
python scripts/volc_detect.py stop-task --task-id 12345
python scripts/volc_detect.py restart-task --task-id 12345
python scripts/volc_detect.py delete-task --task-id 12345
python scripts/volc_detect.py get-task --task-id 12345
```

## Key API Notes

- **Time constraints**: GetTaskResult time range must be <= 1 hour
- **Page size limit**: GetTaskResult max PageSize is 500
- **Node naming format**: `国家-省份-城市-运营商（类型）`, e.g., `中国-北京-北京市-中国电信（IDC）`
- **Task status**: 2=Running, 4=Paused, 6=Ended
- **Project scoping**: All task-scoped commands (`create-task`, `get-result`, `get-task`, `list-tasks`, `stop-task`, `restart-task`, `delete-task`, `generate-report`, `list-nodes`) accept an optional `--project-name`. `create-task` defaults to `default`; the others default to the account's default project when omitted.

## Resources

- **scripts/volc_detect.py**: Complete API client with auth, all API operations, fuzzy search, and report generation
- **references/api_docs.md**: Detailed API parameter reference for all 8 endpoints
