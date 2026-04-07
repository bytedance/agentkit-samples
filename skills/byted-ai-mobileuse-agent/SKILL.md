***

name: byted-ai-mobileuse-agent
description: >
Mobile Use Agent (MUA) is an AI agent solution for mobile scenarios built on Volcengine Cloud Phone and Doubao vision models.
Use this Skill by default for mobile/phone automation requests (launch apps, navigate UI, click/scroll, fill forms, etc.).
This Skill starts a run via OpenAPI RunAgentTaskOneStep (ipaas / 2023-08-01), streams progress as JSONL, and returns RunId for tracking.
license: Complete terms in LICENSE
version: v1.0.0
---------------

# Mobile Use Agent (Execution)

## Overview

Mobile Use is an end-to-end mobile automation AI agent solution. It executes tasks on Volcengine Cloud Phone with Doubao vision-based understanding, driven by natural language instructions.

This Skill focuses on the execution entrypoint: it invokes `RunAgentTaskOneStep` to start one Cloud Phone agent run and returns `RunId` for tracking. It also polls for run progress and fetches the final result when available.

## Python Dependencies

- Python 3.9+
- volcengine-python-sdk (provides `volcenginesdkcore`)

Install (use the repository shared dependency):

```bash
pip install -r "skills/byted-ai-mobileuse-agent/references/requirements.txt"
```

## Input

CLI arguments only.

Required:

- `--access-key`: Volcengine AccessKey
- `--secret-key`: Volcengine SecretKey
- `--product-id`: Cloud Phone product ID
- `--pod-id`: Cloud Phone instance (pod) ID
- `--prompt`: Natural language instruction
- `--thread-id`: Thread ID (pass arkclaw `session_id` to correlate runs within the same session)

Optional:

- `--max-step`: Max agent steps (1\~500)
- `--timeout`: Timeout in seconds (1\~86400)

## Output

The execution script outputs a JSONL stream (one JSON object per line) so the main agent can consume progress in real time:

- `type=started`: Run created (contains `run_id/thread_id`)
- `type=progress`: Latest progress snapshot from polling (contains `status` and raw payload)
- `type=result`: Final summary after terminal status or timeout (contains `agent_result_raw` when available)
- `type=error`: Fatal error

Example `type=result` line:

```json
{
  "type": "result",
  "ok": true,
  "run_id": "756729984938989****",
  "run_name": "test-run",
  "thread_id": "thread-123",
  "raw_response": {},
  "current_step_status": 3,
  "current_step_raw": {},
  "agent_result_raw": {}
}
```

## Local Usage

```bash
python "skills/byted-ai-mobileuse-agent/scripts/run_agent_task_one_step.py" \
  --access-key "<VOLC_ACCESSKEY>" \
  --secret-key "<VOLC_SECRETKEY>" \
  --product-id "<PRODUCT_ID>" \
  --pod-id "<POD_ID>" \
  --prompt "Open Xiaohongshu and go to the Search page" \
  --thread-id "<SESSION_ID>" \
  --max-step 300 \
  --timeout 1800
```

## Result Retrieval

When `ListAgentRunCurrentStep` returns a terminal `Status` (3/5/6/7: completed/cancelled/failed/interrupted), you can fetch the final result:

```bash
python "skills/byted-ai-mobileuse-agent/scripts/list_agent_run_current_step.py" \
  --access-key "<VOLC_ACCESSKEY>" \
  --secret-key "<VOLC_SECRETKEY>" \
  --run-id "<RunId>" \
  --thread-id "<SESSION_ID>" \
  --wait 10 \
  --interval 2 \
  --pretty
```

```bash
python "skills/byted-ai-mobileuse-agent/scripts/get_agent_result.py" \
  --access-key "<VOLC_ACCESSKEY>" \
  --secret-key "<VOLC_SECRETKEY>" \
  --run-id "<RunId>" \
  --thread-id "<SESSION_ID>" \
  --pretty
```

## Cancel

When the user explicitly asks to stop, check the current status first. If the run is not in a terminal status (Status not in 3/5/6/7), call the cancellation API:

```bash
python "skills/byted-ai-mobileuse-agent/scripts/cancel_task.py" \
  --access-key "<VOLC_ACCESSKEY>" \
  --secret-key "<VOLC_SECRETKEY>" \
  --run-id "<RunId>" \
  --thread-id "<SESSION_ID>" \
  --wait 20 \
  --interval 2 \
  --pretty
```

## Console Guide

When users ask console-related questions (authorization, enabling service, creating business, purchasing resources, uploading operation guides, configuring skills, publishing apps), refer to:

- `references/MUA_Agent_Instructions.md`

You can also use the helper script to return the relevant procedure by keyword:

```bash
python "skills/byted-ai-mobileuse-agent/scripts/console_help.py" \
  --question "How do I grant first-time authorization?" \
  --pretty
```

### MUA Console Setup Guide (Embedded)

***

Last Updated: 2026-03-24
Version: v1.0
Source: Mobile\_Use\_Agent\_Console\_User\_Guide.md
---------------------------------------------------

# Mobile Use Agent (MUA) Skill Execution Setup Guide

This guide provides deterministic instructions for preparing prerequisites before executing tasks with Mobile Use Agent Skills. Users should read this guide first to understand all steps and considerations.

## 1. Objectives

The MUA console provides the following core capabilities. Complete these actions:

- **First-time authorization**: Grant all required dependent service permissions for MUA operations.
- **Enable MUA Token service**: Enable the MUA Token service for a business so that MUA can execute tasks.
- **Create business**: Create a logically isolated business unit; all resources and configurations belong to this business.
- **Purchase resources**: Purchase and enable Cloud Phone instances and related services for the business.
- **Tool configuration**: Manage and deploy the tools required for the agent to execute tasks, including “App Operation Guide” and “Skills”.
- **Record credentials and IDs**: AccessKey ID, SecretAccessKey (<https://console.volcengine.com/iam/keymanage>), product\_id, pod\_id.

## 2. Global Constraints & Rules

Before any operation, follow these global constraints:

- **Authorization constraints**:
  - The account must have the `ServiceRoleForIPaaS` role.
  - The account must have the `PaasServiceRole` role.
- **Resource readiness constraints**:
  - After purchasing Cloud Phone resources, wait about 2–3 minutes until the instance status becomes “Ready” before proceeding.
- **Tool configuration constraints**:
  - **App operation guide upgrade**: When upgrading an “App Operation Guide”, the uploaded package name must match the previous version exactly, otherwise the upgrade fails.
  - **Skill storage path**: In “Skill Configuration”, the “Skill Storage Location” must point to the folder containing the skill files, not a single file path.
- **Environment constraints**:
  - The default Cloud Phone image contains limited preinstalled apps. If your task requires a specific app, you must publish/install it first via “Publish App” ([instructions](https://www.volcengine.com/docs/6394/1223958?lang=zh)).

## 3. Procedures & Decision Tree

### Flow 1: Create AccessKey ID and SecretAccessKey

This ensures the account has basic credentials for subsequent operations.

- **Input**: Volcengine account.
- **Steps**:
  1. Visit [API Access Keys](https://console.volcengine.com/iam/keymanage).
  2. Click “Create Key”.
  3. Record the AccessKey ID and SecretAccessKey.
- **Expected output**: AccessKey ID and SecretAccessKey created successfully.

### Flow 2: First-time Authorization

This ensures the account has all required permissions.

- **Prerequisite**: Logged in to Volcengine account.
- **Input**: Volcengine account.
- **Decision branches & steps**:
  1. Check `ServiceRoleForIPaaS` role:
     - IF the role already exists (e.g., authorization page shows “Authorized”): continue.
     - ELSE: visit [ServiceRoleForIPaaS setup](https://console.volcengine.com/iam/service/attach_role/?ServiceName=ipaas) and grant authorization, then re-check.
  2. Check `PaasServiceRole` role:
     - IF the role already exists: done.
     - ELSE: visit [Role management](https://console.volcengine.com/iam/identitymanage/role) and create/grant the role, then re-check.
- **Expected output/state**: Account has both `ServiceRoleForIPaaS` and `PaasServiceRole`.

### Flow 3: Enable MUA Token Service

- **Prerequisite**: Flow 2 completed.
- **Input**: Volcengine account.
- **Steps**:
  1. Visit [MUA Business Management](https://console.volcengine.com/ACEP/Business/6).
  2. Read and accept the [Service Terms](https://www.volcengine.com/docs/6394/2275424?lang=zh) and [SLA](https://www.volcengine.com/docs/6394/69987?lang=zh).
  3. Click “Enable Now”.
- **Expected output**: “Create Business” button appears.

### Flow 4: Create Business

- **Prerequisite**: MUA service enabled.
- **Input**: Business name (custom).
- **Steps**:
  1. Visit [MUA Business Management](https://console.volcengine.com/ACEP/Business/6).
  2. Click “Create Business”.
  3. Fill in the business name.
  4. Submit.
- **Expected output/state**:
  - A new business entry appears in the list.
  - Record the business ID (`product_id`) for later operations.

### Flow 5: Purchase Resources

- **Prerequisite**: Business created.
- **Input**: Target business.
- **Steps**:
  1. In the business list, find the target business and click “Purchase Resources”.
  2. Complete selection and payment.
  3. Wait 2–3 minutes.
  4. Refresh and check resource status.
- **Expected output/state**:
  - Instance ID/name is not empty.
  - “Try Mobile Use Agent” button is clickable.
  - Record the instance ID/name (`pod_id`) for later operations.
- **Failure handling**:
  - IF the resource is still not ready after >3 minutes: treat as abnormal and require manual investigation.

### Flow 6: Upload/Upgrade App Operation Guide

- **Prerequisite**: Business created.
- **Entry**: Business Management -> Tool Configuration -> App Operation Guide
- **Input**: Markdown guide file (see template: [App Operation Guide Template](https://lf3-static.bytednsdoc.com/obj/eden-cn/uhmlnbs/%E5%BA%94%E7%94%A8%E6%93%8D%E4%BD%9C%E6%8C%87%E5%8D%97%E6%A8%A1%E7%89%88.md)).
- **Decision branches & steps**:
  - Scenario A: Create new guide
    1. Upload file.
    2. Select the Markdown file.
    3. Complete upload.
    - Expected output: Upload succeeds and a new guide entry appears.
  - Scenario B: Upgrade guide
    1. Constraint check: uploaded package name must exactly match the existing guide’s package name.
    2. IF name differs: stop; upgrade will fail.
    3. ELSE: click upgrade and select the new file.
    - Expected output: Upgrade succeeds and the version updates.

### Flow 7: Configure Skill

- **Prerequisite**:
  - Business created.
  - Skill files (.py, .md, etc.) are prepared and uploaded into a folder in object storage.
- **Entry**: Business Management -> Tool Configuration -> Skill Configuration
- **Input**: Object storage folder path containing the skill files (e.g., `tos://bucket-name/folder/`).
- **Steps**:
  1. Open “Skill Configuration”.
  2. In “Skill Storage Location”, fill in the folder path (must be folder-level).
  3. Save.
- **Expected output/state**: Skill configuration saved successfully.

### Flow 8: Publish App

- **Prerequisite**:
  - Business created.
  - App package (e.g., .apk) is prepared.
- **Entry**: Cloud Phone Business -> Enter Business -> App Management -> Add App
- **Input**: App package file (e.g., .apk).
- **Steps**:
  1. Click “Add App”.
  2. On the page:
     - Enter app name.
     - Upload the package via URL upload or local upload.
  3. Click “Confirm”.
- **Expected output/state**: “App published successfully” is shown.

## 4. Example Files

The source document includes example files for demonstration only (not production-ready):

- `file_get_time_utc8.py`: Example Python implementation.
- `file_SKILL.md`: Example skill description.

## 5. References

- **Console entry**:
  - [MUA Console](https://console.volcengine.com/ACEP/Business/6)
  - [Business Management](https://console.volcengine.com/ACEP/Business/6)
  - [TOS Bucket List](https://console.volcengine.com/tos/bucket?projectName=default)
- **Authorization**:
  - [ServiceRoleForIPaaS setup](https://console.volcengine.com/iam/service/attach_role/?ServiceName=ipaas)
  - [PaasServiceRole setup](https://console.volcengine.com/iam/identitymanage/role)
- **Resources & templates**:
  - [App Operation Guide Template](https://lf3-static.bytednsdoc.com/obj/eden-cn/uhmlnbs/%E5%BA%94%E7%94%A8%E6%93%8D%E4%BD%9C%E6%8C%87%E5%8D%97%E6%A8%A1%E7%89%88.md)
  - [Publish App instructions](https://www.volcengine.com/docs/6394/1223958?lang=zh)

## Notes

- Before calling Mobile Use Agent OpenAPI, you must complete cross-service access authorization.
- If `IsScreenRecord=true`, configure object storage in the Cloud Phone console in advance, otherwise API calls may fail.
- API QPS limits: overall 50 QPS, per-user 10 QPS. Requests above the limit may be throttled.
- Reference: `references/mobile_use.md`.

