---
name: byted-airesearch-videoeval
description: Create and check long-running video material evaluation tasks. Use this skill when the user wants to submit videos for evaluation, check an existing video evaluation task list, or fetch the result of a previously created video evaluation task. This skill is not a general-purpose video upload skill because upload is allowed only as an internal step of task creation. Authentication uses an API key passed as an Authorization bearer token.
license: Complete terms in LICENSE
---

# Byted Airesearch Videoeval

Use this skill to submit and query long-running material evaluation tasks.

## When to use

Use this skill when the user wants to:

- evaluate a video material or creative asset
- submit a material evaluation task and get back a task identifier
- check the status of an existing evaluation task later
- fetch the final detail/result of a previously created evaluation task

Do not use this skill for generic video upload requests.

## Current workflow

1. Validate the full input batch before any upload starts.
2. Upload the local video files and capture the returned `attachment_id` values.
3. Create a task with the uploaded attachment IDs.
4. Return success immediately after the task is created.
5. Ask the user to query task list or task detail later if they want progress or results.

This workflow is intentionally non-blocking. Do not poll automatically after task creation.

## Mandatory behavior

- Do not expose the upload API as a standalone user-facing capability.
- Do not trigger this skill for generic requests such as “upload this video”, “store this file”, or “send this video”.
- Only call the upload API when the user explicitly intends to create a new material evaluation task.
- For new task creation, prefer `scripts/submit_evaluation_task.py` so validation, upload, and task creation stay in one controlled flow.
- Treat `scripts/upload_video.py` as an internal helper used by the orchestration flow, not as the primary user entrypoint. The script itself rejects direct use unless it is called with the internal orchestration marker.

For multi-file submissions, use the orchestration entrypoint so the whole batch is validated before the first upload starts.

## Authentication

The current APIs use API key authentication.

All API requests sent by this skill must include the header:

- `x-product-version: 20`
- `Authorization: bearer {API_KEY}`

Preferred input methods:

- `--api-key "<api-key>"`
- `BYTED_AIRESEARCH_VIDEOEVAL_API_KEY`

If no API key is available, ask the user to create or view one at:

- `https://console.volcengine.com/datatester/ai-research/audience/list?tab=apikey`

Then ask the user to provide the API key before calling the API.

If the API key is missing, the scripts must fail immediately with a clear error that points the user to the API key page above.

## Known API coverage

### Upload attachment

- Endpoint: `POST https://console.volcengine.com/datatester/compass/api/v3/survey/attachment`
- Request: `multipart/form-data`
- File field: `file`
- Upload constraints:
  - each upload request contains exactly one video file
  - each video must be 50MB or smaller
  - file format must be `mp4`
  - MIME type must be `video/mp4`
- Output mapping:
  - preserve the raw attachment payload
  - map the attachment object's `id` field to `attachment_id`

The `upload_video.py` script is an internal helper for the create-task workflow. It is not the primary user-facing entrypoint.

### Create task

- Endpoint: `POST https://console.volcengine.com/datatester/compass/api/v3/survey/task`
- Fixed request fields:
  - `form_id: 0`
  - `agent_id: 125`
  - `audience_id: 3664529`
- Optional request fields currently exposed:
  - `prompt`
  - `language`
  - `is_typical_user_enabled`
  - `typical_user_count`
  - `typical_user_selection_mode`
  - `is_report_enabled`
  - `attachment_ids`
- Create constraints:
  - one task submission can include at most 50 videos
  - `attachment_ids` must contain at most 50 items per request

The create step should send the uploaded `attachment_id` as a one-element `attachment_ids` array unless multiple attachment IDs are explicitly provided.

### List and detail

Task detail is wired and can query an existing task directly:

- Endpoint: `GET https://console.volcengine.com/datatester/compass/api/v3/survey/task/{id}`
- Current auth: API key bearer token
- Output mapping:
  - map the task object's `id` field to `task_id`
  - map the task object's `status` field to `task_status`
  - parse `task.detail`
  - keep only items where `key == video_structured_result` and `sub_tab != null`
  - expose a compact `summary` block for downstream agent use

Task list is wired and can query existing tasks directly:

- Endpoint: `GET https://console.volcengine.com/datatester/compass/api/v3/survey/task`
- Current auth: API key bearer token
- Current fixed query params:
  - `page=1`
  - `page_size=100`
  - `agent_id=125`
- Output mapping:
  - map each task item to `task_id`, `name`, `status`, `created_at`, `updated_at`
  - preserve pagination info in `data.page`

## Commands

```bash
# Validate a whole batch before upload, then upload all files and create the task
python scripts/submit_evaluation_task.py \
  --file /path/to/video-1.mp4 \
  --file /path/to/video-2.mp4 \
  --api-key "<api-key>"

# Single-video create flow
python scripts/submit_evaluation_task.py \
  --file /path/to/video.mp4 \
  --prompt "Evaluate this material for audience fit and content quality." \
  --api-key "<api-key>"

# Query task list later
python scripts/list_evaluation_tasks.py

# Query task detail later
python scripts/get_evaluation_task_detail.py --task-id 12345
```

## Response handling

All scripts emit JSON to stdout with the same top-level envelope:

- `status`
- `message`
- `request_id`
- `data`
- `error`

Important normalized fields:

- submit task: `data.task_id`, `data.task_status`, `data.submitted_video_count`
- list: `data.items`
- detail: `data.detail`, `data.summary`

## Final answer rules

- Use the structured JSON returned by the detail endpoint as the internal source of truth.
- Present the final answer in human-readable natural language.
- When the task is finished, prefer a concise report-style answer rather than a raw data dump.
- Do not dump raw JSON to the user.
- Do not expose internal field names such as `video_eval`, `video_user_report`, `distribution`, `field_desc`, or similar implementation-oriented keys.
- Apply the same rule to task list responses: use the list result as internal source data, but present the outcome as a natural-language summary rather than raw fields.
- For task list answers, it is acceptable to include the task ID, task name, status, created time, and updated time in human-readable prose, because those fields help the user choose a task for follow-up detail queries.
- When multiple videos are present, summarize them separately.
- For finished task detail results, prefer a readable report flow such as: task conclusion first, then one short section per video, then overall recommendations if the source data supports them.
- If the task is not finished yet, do not fabricate a report. Clearly state the current status and ask the user to check again later.
- Only provide raw structured data if the user explicitly asks for the raw result.

## Practical guidance

- For new submissions, use the orchestration flow rather than exposing upload as a standalone step to the user.
- Validate the local file before upload. Reject non-MP4 files, files with non-`video/mp4` MIME types, or files larger than 50MB with a direct and actionable error message.
- Validate the task creation input before calling the API. Reject any request that contains more than 50 attachment IDs with a direct and actionable error message.
- For a multi-video submit flow, validate the full batch size before any upload starts. If the batch contains more than 50 files, fail immediately and do not upload anything.
- After create succeeds, tell the user the task has been submitted successfully and can be checked later.
- Use task list when the user wants to browse or find historical tasks.
- Use task detail when the user already knows the task ID and wants the final result.
