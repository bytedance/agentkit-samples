---
name: byted-util-volcengine-detect-retry
description: Orchestrates Volcengine Cloud Detect (云拨测) false-alarm reduction for failing periodic-task dial points. Use for scheduled task scans, retrying failed nodes, control-testing node health, distinguishing real target outages from broken dial points, and suggesting same-type LastMile/IDC/Private replacement nodes. Runs the byted-util-volcengine-cloud-detect volc_detect.py CLI only; requires that skill and ships no API/script implementation.
---

# Volcengine Detect Retry

Reduce Volcengine Cloud Detect (云拨测) operations toil. This skill confirms whether a
failing dial point is a real outage or just noise, and — when a dial point itself is broken
— suggests a similar replacement node.

**This skill ships no script of its own.** It is pure orchestration: every action is one of
the `byted-util-volcengine-cloud-detect` skill's `volc_detect.py` CLI commands
(`get-task`, `get-result`, `list-nodes`, `fuzzy-search-nodes`, `create-task`, `delete-task`).
Follow the workflow below by invoking those commands in sequence and applying the decision
logic to their JSON output.

**Requires**: `byted-util-volcengine-cloud-detect` skill. Do not reimplement any Cloud Detect API call here.

## Locate The Base CLI

Resolve `volc_detect.py` dynamically (never hard-code an absolute path):

```bash
VOLC_DETECT="${VOLC_DETECT:-$(find "${SKILLS_DIR:-$HOME/Code/Skill}" -type f \
  -path '*/byted-util-volcengine-cloud-detect/scripts/volc_detect.py' 2>/dev/null | head -n 1)}"
test -n "$VOLC_DETECT" || { echo "volc_detect.py not found"; exit 1; }
alias vd="python3 \"$VOLC_DETECT\""
```

All commands below are written as `python3 "$VOLC_DETECT" <command>`.

## Prerequisites

Volcengine credentials must be present (the base skill enforces this). If either is missing,
follow the base skill's Prerequisites section to collect and persist them:

```bash
test -n "$VOLC_ACCESSKEY" && test -n "$VOLC_SECRETKEY"
```

## Decision Logic

For each dial point whose **latest** sample in the scan window failed:

1. **Retry 5 times** (configurable) against the **same** monitored target via a temporary
   `create-task`.
   - **All retries succeed** → transient glitch → **ignore** (`transient_issue`).
   - **Any retry fails** → go to control validation.
2. **Control validation**: a temporary `create-task` dials a trusted domain from the **same** node.
   - China nodes → `https://cn.bing.com`
   - Overseas nodes → `https://www.google.com`
   - **Control succeeds** → `real_failure` (target is genuinely down for that node) → **ALERT**.
   - **Control fails** → `node_issue` (the dial point itself is broken) → **find similar
     replacement nodes and suggest replacing it**.
3. Temporary retry/control tasks are **always** deleted (`delete-task`).

By default only **LastMile** dial points (`client_info.type == "1"`, node name suffix `（LM）`)
are auto-validated, because they are the noisy ones. Include IDC/Private only on request.

Replacement-node priority (`node_issue` only):
1. **Mandatory**: same node type (LastMile / IDC / Private).
2. **Preferred**: same province, then same country.

## Success Rule

A result sample is **success** when `basic_detail.usability_info.status` is `"success"`
(or boolean `true`); it is a **failure** when status is `"fail"` (the `usability_info.reason`
array, e.g. `["主机未找到(601)"]`, and `basic_detail.error_msg` explain why). If no
`usability_info` is present, fall back to `http_detail.http_code` in `200–499` = reachable.

## Workflow: Scan One Periodic Task

### Step 1 — Fetch the task and its recent samples

```bash
# Task must be Running (status == 2) to be actively monitoring.
python3 "$VOLC_DETECT" get-task --task-id <TASK_ID>

# Pull the last hour of results (API limits the range to <= 1 hour, PageSize <= 500).
NOW=$(date +%s); START=$((NOW-3600))
python3 "$VOLC_DETECT" get-result --task-id <TASK_ID> \
  --start-time $START --end-time $NOW --page-size 500
```

### Step 2 — Identify failing nodes (latest sample per node)

From the `Data` array, group samples by node and keep the **latest** (max `basic_detail.timestamp`)
per node. A node is identified by its `basic_detail.client_info` (`region` / `city` / `isp` / `type`).
Map that back to a node `id` + full name with `list-nodes` (match `region`, `city`, `isp`
substrings; if `client_info.type` is present, also match node type to disambiguate LM vs IDC).

```bash
python3 "$VOLC_DETECT" list-nodes
```

Keep only nodes whose latest sample is a **failure**. By default, drop non-LastMile nodes
(`client_info.type != "1"`) unless the user asked to include IDC/Private. If a `client_info`
maps to multiple nodes (ambiguous) or none, mark it `inconclusive` and do not auto-page.

### Step 3 — Retry each failing node 5× against the same target

`get-task` gives the monitored `address`. Create a temporary task on the failing node only:

```bash
ADDRESS="<the task's address>"; LINE_ID=<failing node id>
NOW=$(date +%s); FINISH=$((NOW + 5*60 + 120))   # 5 rounds @ 60s + margin
python3 "$VOLC_DETECT" create-task \
  --address "$ADDRESS" --name "retry_${LINE_ID}_${NOW}" \
  --type 1 --node-count 1 --interval-seconds 60 \
  --finish-time $FINISH --line-ids $LINE_ID --http-method 1
```

Wait for ~5 samples (poll `get-task` until `status == 6`, or sleep `rounds × interval`),
fetch the results, then **delete** the temporary task:

```bash
END=$(date +%s); START=$((END-3600))
python3 "$VOLC_DETECT" get-result --task-id <RETRY_TASK_ID> \
  --start-time $START --end-time $END --page-size 500
python3 "$VOLC_DETECT" delete-task --task-id <RETRY_TASK_ID>
```

- **All retry samples succeed** → `transient_issue` → ignore. Done for this node.
- **Any retry fails** → continue to Step 4.

### Step 4 — Control validation from the same node

Pick the control domain by node locality (node name starting with `中国` → CN):

```bash
# China node:   CONTROL="https://cn.bing.com"
# Overseas node: CONTROL="https://www.google.com"
NOW=$(date +%s); FINISH=$((NOW + 90))
python3 "$VOLC_DETECT" create-task \
  --address "$CONTROL" --name "control_${LINE_ID}_${NOW}" \
  --type 1 --node-count 1 --interval-seconds 60 \
  --finish-time $FINISH --line-ids $LINE_ID --http-method 1
```

Wait for a sample, fetch results, then **delete** the control task:

```bash
END=$(date +%s); START=$((END-3600))
python3 "$VOLC_DETECT" get-result --task-id <CONTROL_TASK_ID> \
  --start-time $START --end-time $END --page-size 50
python3 "$VOLC_DETECT" delete-task --task-id <CONTROL_TASK_ID>
```

- **Control succeeds** → `real_failure`: the monitored target is genuinely down for this node
  while the node itself is healthy → **ALERT**.
- **Control fails** → `node_issue`: the dial point itself is broken → go to Step 5.
- **No control samples** → `inconclusive` (do not auto-page).

### Step 5 — Suggest replacement nodes (`node_issue` only)

Find same-type, preferably same-province (then same-country) candidates, excluding the broken
node. `fuzzy-search-nodes` filters by name substrings (`国家-省份-城市-运营商（类型）`):

```bash
# e.g. broken node = 中国-河南-三门峡市-中国电信（LM）
python3 "$VOLC_DETECT" fuzzy-search-nodes "河南 电信 LM"   # same province first
python3 "$VOLC_DETECT" fuzzy-search-nodes "中国 电信 LM"   # fall back to same country
```

Present the top candidates and recommend swapping the node in the source periodic task's
`LineIdList`.

## Classification Reference

| Latest sample | Retry result | Control result | Classification | Action |
|---------------|--------------|----------------|----------------|--------|
| fail | all succeed | — | `transient_issue` | ignore |
| fail | any fail | success | `real_failure` | **alert** |
| fail | any fail | fail | `node_issue` | **suggest replacement node** |
| fail | no samples | — | `inconclusive` | no auto-page |
| fail | any fail | no samples | `inconclusive` | no auto-page |
| fail (non-LastMile) | — | — | `skipped_non_lastmile` | skipped unless user includes all types |

## Reporting

Summarize the scan as a single object the operator can act on:

```json
{
  "alert": true,
  "message": "1 confirmed real failure(s), 1 broken node(s), 2 transient (ignored), 0 inconclusive",
  "real_failures": [
    {
      "task_id": "23275831",
      "line_id": 823,
      "address": "https://example.com",
      "node_name": "中国-河南-三门峡市-中国电信（LM）",
      "classification": "real_failure",
      "control_address": "https://cn.bing.com",
      "details": "Retries failed but the control target succeeded from the same node."
    }
  ],
  "node_issues": [
    {
      "line_id": 229,
      "node_name": "中国-河北-石家庄市-中国电信（LM）",
      "classification": "node_issue",
      "control_address": "https://cn.bing.com",
      "suggested_replacements": [
        {"line_id": 380, "node_name": "中国-河南-南阳市-中国电信（LM）", "match": ["same_type", "same_province", "same_country"]}
      ],
      "details": "Both the monitored target and the control target failed from this node."
    }
  ],
  "suppressed": [{"line_id": 230, "classification": "transient_issue"}],
  "inconclusive": []
}
```

### How To Act On The Output

- `real_failures` → page / alert. The monitored site is genuinely down for those nodes.
- `node_issues` → the dial point is broken. Present `suggested_replacements` and recommend
  swapping the node in the periodic task's `LineIdList`.
- `suppressed` (transient) → no action; log for auditability.
- `inconclusive` → insufficient evidence; surface in the report but **do not** auto-page.

`alert` is `true` only when there is at least one `real_failure`.

### Notification

If the user provides a webhook or notify script, send only the `real_failures` set as the
paging payload, and include `node_issues` (with replacement suggestions) so operators can act.
Include suppressed/inconclusive counts in the text for auditability.

## Scheduling (hourly)

Run the scan workflow on whatever scheduler you use (cron / CI). The 1-hour scan window
matches an hourly cadence; shrink the window if you run more frequently.

## Resources

- **byted-util-volcengine-cloud-detect skill**: provides `volc_detect.py`. This skill calls its
  commands directly and adds only the retry → control → replacement decision logic above.
