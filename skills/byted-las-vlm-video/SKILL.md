---
name: byted-las-vlm-video
version: "1.0.1"
description: "Analyzes and understands video content using Volcengine LAS Doubao vision-language models (VLM). Multimodal AI video analysis, video comprehension, and visual understanding of video clips and footage. Performs video question answering (video Q&A) — ask questions about what happens in a video and get AI answers. Scene recognition and scene description, object recognition and object detection, action recognition and action detection from video frames. Generates video descriptions, video captions, video summaries, video annotations, and content summarization. Visual frame analysis for identifying people, objects, actions, and events in video. Auto-compresses video to 50MB before inference. Synchronous single-call processing. Use this skill when the user wants to analyze or understand video content using VLM/AI, do video Q&A (ask questions about a video), describe what happens in a video, recognize objects/actions/scenes in video frames, generate video captions/descriptions/summaries, annotate or label video content, get AI-powered visual understanding of video clips, or perform multimodal video analysis with vision-language models."
---

# LAS 视频内容理解（`las_vlm_video`）

基于豆包视觉大模型对视频进行理解和分析（物体识别、动作分析、场景描述、摘要、字幕生成）。视频自动压缩到 50MB 以内再推理。

## 设计模式

本 skill 主要采用：
- **Tool Wrapper**：封装 `lasutil` CLI 调用
- **Pipeline**：包含 Step 0 → Step N 的顺序工作流

## 核心 API 与配置

- **算子 ID**: `las_vlm_video`
- **API**: 同步（`process`）
- **环境变量**: `LAS_API_KEY` (必填)
- **视频限制**: 需公网/火山内网可访问，≤ 1GiB，暂不支持理解音频信息。

> 详细参数与接口定义见 [references/api.md](references/api.md)。

## Gotchas

- **不可精确预估**：按 Token 计费，且视频压缩后 token 量动态变化，需明确告知用户计费模式。
- **密钥安全**：若聊天框屏蔽密钥，让用户在当前目录创建 `env.sh` 并写入 `export LAS_API_KEY="..."`，SDK 会自动读取。
- **免责声明**：最终回复结果时必须包含："本方式的计费均为预估计费，与实际费用有差距，实际费用以运行后火山产生的账单为准。计费说明请参考 [Volcengine LAS 定价](https://www.volcengine.com/docs/6492/1544808)。"，且禁止使用"实际费用"字眼描述预估价。


## 工作流（严格按步骤执行）

复制此清单并跟踪进度：

```text
执行进度：
- [ ] Step 0: 前置检查
- [ ] Step 1: 初始化与准备
- [ ] Step 2: 预估价格
- [ ] Step 3: 执行/提交任务
- [ ] Step 4: 结果呈现
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
source "$(dirname "$0")/scripts/env_init.sh" las_vlm_video
workdir=$LAS_WORKDIR
```

> 如果网络问题导致更新失败，脚本会跳过检查，使用本地已安装的 SDK 继续执行。

- **处理本地文件时**：先本地检查格式和时长，告知预估后，用户确认再上传：
  ```bash
  # 提前检查视频格式（避免参数错误）
  ./scripts/check_format.sh <local_path>
  # 本地使用 ffprobe 获取时长（无需上传即可预估token）
  duration_sec=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:noprint_section=1 <local_path>)
  ```
  根据时长估算 token 量并等待用户确认后，再执行上传：
  ```bash
  # 用户确认后，上传到 TOS
  lasutil file-upload <local_path>
  ```
  上传成功后返回 JSON，取其中的 `tos_uri`（格式 `tos://bucket/key`）传给算子作为输入路径。

### Step 2: 预估价格（⚠️ 必须获得用户确认）

本 skill 按 token 计费，提交前无法精确预估费用。需将以下单价表告知用户，由用户决定是否继续。

1. 读取 [references/prices.md](references/prices.md) 获取最新计费标准（或使用下方基本参考）。
2. **优先本地获取视频时长**帮助预估（避免不必要上传）：
   ```bash
   # 使用 ffprobe 本地获取
   duration_sec=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:noprint_section=1 <local_path>)
   ```
   根据时长估算 token 量后，告知用户 `tos://` 内网访问更便宜。**等待用户确认后才可继续**。提示：预估仅供参考，实际以火山账单为准。计费说明请参考 [Volcengine LAS 定价](https://www.volcengine.com/docs/6492/1544808)。

### Step 3: 执行视频理解 (Process)

构造基础 `data.json`（详细参数与接口定义见 [references/api.md](references/api.md)）：
```json
{
  "messages": [
    {"role": "user", "content": [
      {"type": "video_url", "video_url": {"url": "<presigned_url>"}},
      {"type": "text", "text": "分析视频内容，输出要点列表"}
    ]}
  ],
  "model_name": "doubao-seed-1.6-vision"
}
```

执行命令：
```bash
data=$(cat "$workdir/data.json")
lasutil process las_vlm_video "$data" > "$workdir/result.json"
```

输出解析：模型返回文本在 `result.data.vlm_result.choices[0].message.content` 中。

### Step 5: 结果呈现

**处理结果**：

```bash
# 保存结果到本地
mkdir -p "./output/{task_id}"
cat "./output/{task_id}/result.json" | jq -r '.data.summary' > "./output/{task_id}/summary.txt"
cat "./output/{task_id}/result.json" | jq '.data.events' > "./output/{task_id}/events.json"
```

**上传结果文件**（可选）：

```bash
# 上传摘要和事件列表
lasutil file-upload "./output/{task_id}/summary.txt"
lasutil file-upload "./output/{task_id}/events.json"
```

**向用户展示**：
1. 视频摘要
2. 关键事件列表（时间、描述）
3. 本地文件路径：`./output/{task_id}/`
4. 签名下载链接（如上传成功）
5. 计费声明


## 审查标准

执行完成后，Agent 应自检：
1. 环境变量是否正确配置
2. 输入文件是否成功上传
3. 输出结果是否正确呈现给用户
4. 计费声明是否包含
