---
name: byted-airesearch-survey
description: Launch and continue the Volcengine AI Research survey workflow for concept testing, audience design, questionnaire drafting, interview guide generation, execution confirmation, progress checks, and result queries. Use this skill when the user wants to create, revise, confirm, execute, or follow up on a real AI research survey task in ABCompass instead of doing generic brainstorming, copywriting, translation, summarization, or broad market discussion.
license: Apache-2.0
metadata: {"clawdbot":{"emoji":"🧪","homepage":"https://www.volcengine.com/","requires":{"bins":["python3"]},"os":["darwin","linux"]},"openclaw":{"emoji":"🧪","homepage":"https://www.volcengine.com/","requires":{"bins":["python3"]},"os":["darwin","linux"]},"moltbot":{"emoji":"🧪","homepage":"https://www.volcengine.com/","requires":{"bins":["python3"]},"os":["darwin","linux"]}}
---

# Volcengine AI Research Survey

Use this skill to run a real conversational AI Research survey workflow backed by ABCompass.

## When to use

Use this skill when the user wants to:

- start a new AI research survey task
- revise an existing research plan
- confirm execution of a generated plan
- check the current plan, progress, or final result
- run concept testing, audience design, questionnaire drafting, or interview-guide generation as a real workflow

Do not use this skill when the user only wants:

- generic brainstorming or ideation with no intention to run a task
- copywriting, translation, polishing, or summarization
- broad market discussion without asking to launch or query the AI Research workflow
- generic platform troubleshooting unrelated to this workflow

## Primary command

For every valid workflow turn, run:

```bash
python3 scripts/send_survey_message.py --message "<user message>"
```

This wrapper is the only user-facing entrypoint in this repository. It manages session continuity, API key binding, and production-safe sync transport on top of the canonical `ai_research_message` tool logic.

## Core workflow

1. Decide whether the request belongs to the AI Research survey workflow.
2. If the request is valid, call `scripts/send_survey_message.py` before replying.
3. Prefer backend `reply_markdown` as the user-facing answer.
4. Treat backend `presentation`, `next_actions`, `session_event`, and `capability_hints` as the rendering contract.
5. If the task is still running, report real progress only. Do not fabricate a finished report.

Read references only when needed:

- `references/industries.md` for industry normalization guidance
- `references/status-response-rules.md` for status-specific handling
- `references/user-facing-messages.md` for wording consistency

## Authentication

First-time use requires an API key.

Preferred input methods:

- `--api-key "<api-key>"`
- `BYTED_AI_RESEARCH_SURVEY_API_KEY`

If no API key is available, ask the user to create or view one at:

- `https://console.volcengine.com/datatester/ai-research/audience/list?tab=apikey`

Then ask the user to provide the API key before calling the API. If the wrapper returns `AUTH_REQUIRED`, do not ask the user to repeat the research request. The pending request can continue directly after key binding.

## Parameter guidance

| Category | Parameters | When to set |
|----------|-----------|-------------|
| Always pass | `--message` | Every call |
| Pass when user provides | `--api-key`, `--session-id`, `--force-new-session`, `--research-method`, `--language` | User explicitly specifies these values. Note: `--api-key` is not persisted by the wrapper — the host must retain it in conversation context and pass it on every subsequent call, or guide the user to set the `BYTED_AI_RESEARCH_SURVEY_API_KEY` environment variable. |
| Pass when host can confidently resolve | `--request-kind`, `--industry-hint`, `--normalized-message` | Host has enough context to classify intent or normalize industry. Read `references/industries.md` for mapping rules. |
| Use from `next_actions` | All parameters in `tool_input` | When the previous response included `next_actions`, use the pre-built parameters directly. Do not modify or guess. |
| Leave to defaults | `--source-channel`, `--response-mode`, `--app-id`, `--status-only` | Only set when you have a specific reason |

## Critical rules

1. Never bypass `scripts/send_survey_message.py` by manually constructing HTTP requests, curl commands, or calling any API endpoint directly. This wrapper is the only interface to the backend — there are no alternative call paths, sub-agents, or other scripts to try.
2. Never expose API keys, request headers, environment-specific headers, environment variable names, curl commands, or internal request traces in user-facing replies. All debugging output is gated behind the wrapper's built-in redaction mechanism.
3. Never mention or distinguish between internal environments (such as "testing environment", "production environment", "pre-production", or any environment-specific terminology) in user-facing replies. Runtime profile differences are opaque implementation details.
4. Use backend `reply_markdown` verbatim as the user-facing answer. Do not compress, rephrase, summarize, or replace it. If `reply_markdown` is empty, use the fallback message from the response — do not invent content.
5. When the response contains `next_actions`, use them as the exclusive set of suggested next steps. Each action includes a pre-built `tool_input` with all necessary parameters. Do not invent actions outside this set.
6. Do not invent tool methods, parameters, or session lifecycle events beyond what the wrapper supports.
7. Do not force unsupported industries into backend execution. If the industry cannot be confidently mapped, return the unsupported-industry response.
8. For confirm, execute, progress, plan, and result queries, always call the wrapper to get the latest backend state. Never answer from memory or cached context.
9. Do not narrate internal tool steps (reading files, checking state, retrying requests, switching endpoints) in user-facing replies.
10. Treat backend `presentation`, `session_event`, and `capability_hints` as the rendering contract. Do not invent a parallel workflow.
11. Do not claim scheduled follow-up, automatic notifications, or similar host abilities unless the host has actually completed that action and `capability_hints.followup_supported` is true.

## Forbidden behaviors

These are real failure patterns observed in host integrations. Each one violates a critical rule above.

### Do not bypass the wrapper

Bad — the host manually constructed an HTTP request instead of calling the wrapper:

> 我直接手动拼了请求参数调用接口：curl -X POST "https://..." -H "x-api-key: ..." -d '{"message": "..."}'

Why forbidden: Bypassing the wrapper leaks headers, credentials, and internal URLs. The wrapper handles credential redaction, error recovery, and session management.

### Do not expose environment concepts

Bad — the host told the user about internal environments:

> 先后尝试了测试环境和正式环境的接口都访问失败（测试环境域名解析失败，正式环境接口返回404）

Why forbidden: Internal infrastructure topology is not a user concept. If the wrapper fails, return its error response directly.

### Do not leak credentials or request details

Bad — the host showed unredacted API key and internal headers:

> -H "x-api-key: 3089e65f8d577071a7c9f7a1ae041716b351ac2a"
> -H "x-tt-env: ppe_datarangers"

Why forbidden: API keys must never appear unredacted. Internal request headers are implementation details. Only the wrapper's built-in redaction mechanism may expose request details.

### Do not invent alternative calling methods

Bad — the host fabricated a non-existent calling method:

> 工具：sessions_spawn / 参数：agentId: "byted-airesearch-survey" / 返回错误：{"status": "forbidden"}

Why forbidden: `sessions_spawn` and `agentId` do not exist. The only interface is `scripts/send_survey_message.py`.

### Do not improvise on failure

Bad — the host tried alternative paths after the standard call failed:

> 由于子agent方式被禁止，我就换了手动构造curl的方式直接调用接口

Why forbidden: When the wrapper fails, return its error response. Do not diagnose, retry via alternative paths, or construct manual HTTP requests.

### Do not invent next steps beyond next_actions

Bad — the host suggested capabilities that do not exist:

> 你还可以导出结果为PDF、分享给团队成员、或者设置每周自动调研

Why forbidden: The backend returns `next_actions` with pre-built parameters for each valid next step. Do not invent capabilities not listed in `next_actions`.

### Do not summarize or compress long reply_markdown

Bad — the host compressed a full plan card into a summary:

> **方案概览** 主题：喜茶芝芝莓莓 / 方式：定性 / 题目数：21 / 预计耗时：1小时

Why forbidden: `reply_markdown` must be presented verbatim regardless of length. The backend deliberately generates detailed plan cards — compressing them loses critical information like individual questions, audience strategy, and evaluation notes. If the content is long, show it in full.

## When the wrapper fails

1. Return the wrapper's `reply_markdown` directly — it already contains a user-safe error message.
2. Do not attempt to diagnose the failure, retry via alternative paths, or construct manual HTTP calls.
3. Do not expose HTTP status codes, error payloads, or transport details unless the user has explicitly requested debugging (in which case, let the wrapper handle redaction).
4. It is acceptable to say "the request did not succeed" and suggest the user retry later. It is not acceptable to explain internal infrastructure details.

## Command examples

```bash
# Start a new research conversation
python3 scripts/send_survey_message.py \
  --message "Help me run a concept test for a new ready-to-drink tea product" \
  --force-new-session

# Start with a normalized industry hint
python3 scripts/send_survey_message.py \
  --message "Help me research a new Chagee product launch" \
  --industry-hint "现制茶饮" \
  --normalized-message "Help me run a concept test for a new freshly made tea product"

# Revise the current plan
python3 scripts/send_survey_message.py \
  --message "Change this to a quantitative survey with 400 samples"

# Query current session status directly
python3 scripts/send_survey_message.py \
  --message "Check progress" \
  --status-only
```

## Final answer rules

- Present user-facing results in natural language, not as a raw JSON dump.
- When backend `reply_markdown` is available, prefer it over a rewritten summary.
- When status is `WAITING_CONFIRM`, preserve the plan-card structure and invite the user to revise or confirm execution.
- When status is `FINISHED`, prefer a report-style answer and include the result link when available.
- When status is `UNSUPPORTED_INDUSTRY`, explain the limit clearly and invite the user to revise.
- When status is `FAILED`, explain that execution failed and offer retry, revise, or restart options.
- Keep transport sync-only. Prefer `sync_deferred`, and use `sync_blocking` only when the host explicitly needs a blocking response.
