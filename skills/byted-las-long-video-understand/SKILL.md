---
name: byted-las-long-video-understand
version: "1.0.1"
description: "Performs deep AI-powered analysis and understanding of long-form videos (up to 3 hours, 10GB) using Volcengine LAS large language models. Video analysis, video comprehension, and video summarization — generates comprehensive video summaries, video recaps, chapter breakdowns, event timelines, key moments, and structured content indexing. Supports behavior detection, action detection, video annotation, video tagging, and video content recognition. Enables intelligent video question answering — ask questions about video content and get AI answers. Handles long meeting recordings, lecture videos, webinars, surveillance and security footage, movies, tutorials, and any long video that needs detailed understanding. Async processing with submit-poll workflow. Use this skill when the user wants to analyze or understand long videos (up to 3h/10GB) with LLM-based deep comprehension, summarize video content or generate recaps, extract chapters/key moments/timelines from videos, do video Q&A (ask questions about video content), detect actions/behaviors in videos, review meeting recordings/lectures/webinars, or get structured video descriptions."
---

# LAS 视频精细理解（`las_long_video_understand`）

基于大模型提供多维度、精细化的视频结构化理解。支持小时级（最大 3h）视频的全局理解、事件与行为识别、视频问答、高效摘要及结构化输出。

## 设计模式

本 skill 主要采用：
- **Tool Wrapper**：封装 `lasutil` CLI 调用
- **Pipeline**：包含 Step 0 → Step N 的顺序工作流

## 核心 API 与配置

- **算子 ID**: `las_long_video_understand`
- **API**: 异步（`submit` → `poll`）
- **环境变量**: `LAS_API_KEY` (必填)
- **支持时长**: 最大支持 3h (10G) 视频。

> 详细参数与接口定义见 [references/api.md](references/api.md)。

## Gotchas

- **不可精确预估**：按 Token 计费，受视频时长和复杂度影响极大。
- **密钥安全**：若聊天框屏蔽密钥，让用户在当前目录创建 `env.sh` 并写入 `export LAS_API_KEY="..."`，SDK 会自动读取。
- **免责声明**：最终回复结果时必须包含："本方式的计费均为预估计费，与实际费用有差距，实际费用以运行后火山产生的账单为准。计费说明请参考 [Volcengine LAS 定价](https://www.volcengine.com/docs/6492/1544808)。"，且禁止使用"实际费用"字眼描述预估价。

## 工作流（严格按步骤执行）

复制此清单并跟踪进度：

```text
执行进度：
- [ ] Step 0: 前置检查
- [ ] Step 1: 初始化与准备
- [ ] Step 2: 预估价格
- [ ] Step 3: 提交异步任务
- [ ] Step 4: 轮询任务状态
- [ ] Step 5: 结果呈现
```

### Step 0: 前置检查（⚠️ 必须在第一轮对话中完成）

在接受用户的任务后，**不要立即开始执行**，必须首先进行以下环境检查：
1. **检查 `LAS_API_KEY` 与 `LAS_REGION`**：确认环境变量或 `.env` 中是否已配置。
   - 若无，必须立即向用户索要（提示：`LAS_REGION` 常见为 `cn-beijing`）。
   - **注意**：`LAS_REGION` 必须与您的 API Key 及 TOS Bucket 所在的地域完全一致。如果用户中途切换了 Region，必须提醒用户其 TOS Bucket 也需对应更换，否则会导致权限异常或上传失败。
2. **检查输入路径**：
   - 如果用户要求处理的是**本地文件**，则需要先通过 File API 上传至 TOS（只需 `LAS_API_KEY`，无需额外 TOS 凭证）。
   - 如果算子的**输出结果**存放在 TOS 上，且用户需要下载回本地，则需要 `VOLCENGINE_ACCESS_KEY` 和 `VOLCENGINE_SECRET_KEY`。对于**仅需要上传输入文件**的场景，TOS 凭证**不再必须**。
3. **确认无误后**：才能进入下一步。

### Step 1: 初始化与准备

**环境初始化（Agent 必做）**：

```bash
# 执行统一的环境初始化与更新脚本（会自动创建/激活虚拟环境，并检查更新）
source "$(dirname "$0")/scripts/env_init.sh" las_long_video_understand
workdir=$LAS_WORKDIR
```

> 如果网络问题导致更新失败，脚本会跳过检查，使用本地已安装的 SDK 继续执行。

- **处理本地文件时**：先本地检查格式和时长，预估价格，用户确认后再上传：
  ```bash
  # 提前检查视频格式（避免参数错误）
  ./scripts/check_format.sh <local_path>
  # 本地使用 ffprobe 获取时长（无需上传即可预估价格）
  duration_sec=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:noprint_section=1 <local_path>)
  ```
  计算预估价格并等待用户确认后，再执行上传：
  ```bash
  # 用户确认后，上传到 TOS
  lasutil file-upload <local_path>
  ```
  上传成功后返回 JSON，取其中的 `tos_uri`（格式 `tos://bucket/key`）传给算子作为输入路径。

### Step 2: 预估价格（⚠️ 必须获得用户确认）

本 skill 按 token 计费，由于视频长且分析复杂，提交前无法精确预估费用。

1. 查阅 [references/prices.md](references/prices.md) 的说明。
2. 说明此任务产生的 token 量可能会非常大（特别是对于长视频）。
3. **将计费单价告知用户并强制暂停执行**，明确等待用户回复确认。在用户明确回复"继续"、"确认"等同意指令前，**绝对禁止**进入下一步（执行/提交任务）。提示：预估仅供参考，实际以火山账单为准。计费说明请参考 [Volcengine LAS 定价](https://www.volcengine.com/docs/6492/1544808)。

### Step 3: 提交异步任务 (Submit)

构造 `data.json`：
```json
{
  "video_url": "<url>",
  "query": "请总结这个视频的主要内容",
  "fps": 1.0,
  "model_name": "doubao-seed-2-0-lite-260215"
}
```

执行命令：
```bash
data=$(cat "$workdir/data.json")
lasutil submit las_long_video_understand "$data" > "$workdir/submit.json"
task_id=$(cat "$workdir/submit.json" | jq -r '.metadata.task_id')
echo "Task ID: $task_id"
```

### Step 4: 轮询任务状态 (Poll)

```bash
# 获取任务状态
lasutil poll las_long_video_understand "$task_id" > "$workdir/poll.json"
cat "$workdir/poll.json" | jq -r '.metadata.task_status'
```

- 如果状态是 `PENDING` 或 `RUNNING`，等待一段时间后再次执行上述命令。由于是长视频理解，耗时可能较长。
- 如果状态是 `COMPLETED`，继续 Step 5。
- 如果状态是 `FAILED`，向用户报告错误 `error_msg`。

### Step 4: 异步查询 (Poll)

⚠️ **异步任务与后台轮询约束**：
- 如果环境支持后台任务，可以使用优化后的后台轮询脚本自动轮询直到完成：
  ```bash
  mkdir -p "./output/${task_id}"
  ./scripts/poll_background.sh ${task_id} "./output/${task_id}" & disown
  ```
  脚本特性：
  - **动态间隔**：前 5 次 30s，5-10 次 60s，10 次后 120s
  - **完成标记**：生成 `COMPLETED` 标记文件
  - 适合长视频理解这类耗时较长的任务

- 如果环境不支持后台任务，手动轮询：
  ```bash
  # 获取任务状态
  lasutil poll las_long_video_understand "$task_id" > "$workdir/poll.json"
  cat "$workdir/poll.json" | jq -r '.metadata.task_status'
  ```
  - 如果状态是 `PENDING` 或 `RUNNING`，等待一段时间后再次执行上述命令。由于是长视频理解，耗时可能较长。
  - 如果状态是 `COMPLETED`，继续 Step 5。
  - 如果状态是 `FAILED`，向用户报告错误 `error_msg`。

### Step 5: 结果呈现

**处理结果**：

使用脚本自动生成结果展示（自动包含计费声明）：
```bash
./scripts/generate_result.md.sh ${task_id} "./output/${task_id}" <estimated_price>
```

**手动处理**：
```bash
# 解析最终摘要
cat "$workdir/poll.json" | jq -r '.data.final_summary'

# 可选：保存 clips 详情到本地
cat "$workdir/poll.json" | jq '.data.clips' > "./output/${task_id}/clips_detail.json"
```

**向用户展示**：
1. 使用生成的 markdown 展示
2. 呈现视频的 `final_summary`（最终摘要）
3. 如果有精彩片段问答或特定 query 回答，结合 `clips` 提取并展示
4. 自动包含计费声明 ✅
