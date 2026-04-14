---
name: byted-las-asr-pro
version: "1.0.1"
description: "ASR / STT / speech recognition / voice recognition engine powered by Volcengine LAS. Transcribes and converts speech to text from audio and video files — extracts spoken words and generates text transcription from any recording. Supports dictation, subtitle and caption generation. Handles meeting recordings, meeting notes, meeting minutes, meeting summary, interview transcription, podcast transcription, lecture transcription, customer service call center audio, phone call recording, and recorded audio files. Features speaker diarization and speaker identification (detect who said what), emotion recognition, sentiment detection, gender recognition, and multilingual multi-language auto-detection. Accepts wav, mp3, m4a formats with async submit-poll workflow and batch processing for large-scale transcription jobs. Use this skill when the user wants to transcribe audio or video to text (ASR/speech-to-text), generate subtitles or captions from recordings, do speaker diarization or emotion analysis on meeting/interview/podcast/lecture recordings, or extract spoken content from any audio/video media file."
---

# LAS 语音识别（`las_asr_pro`）

支持将音频/视频转写为文字，可选说话人分离、情绪/性别识别、多语种自动识别。

## 设计模式

本 skill 主要采用：
- **Tool Wrapper**：封装 `lasutil` CLI 调用
- **Pipeline**：包含 Step 0 → Step N 的顺序工作流

## 核心 API 与配置

- **算子 ID**: `las_asr_pro`
- **API**: 异步（`submit` → `poll`）
- **环境变量**: `LAS_API_KEY` (必填)

> 详细参数与接口定义见 [references/api.md](references/api.md)。

## Gotchas

- **格式易错**：`audio.format` 必须是容器格式（wav/mp3/m4a），非编码格式。不确定时用 `ffprobe` 确认。
- **密钥安全**：若聊天框屏蔽密钥，让用户在当前目录创建 `env.sh` 并写入 `export LAS_API_KEY="..."`，SDK 会自动读取。
- **免责声明**：最终回复结果时必须包含："本方式的计费均为预估计费，与实际费用有差距，实际费用以运行后火山产生的账单为准。计费说明请参考 [Volcengine LAS 定价](https://www.volcengine.com/docs/6492/1544808)。"，且禁止使用"实际费用"字眼描述预估价。


## 工作流（严格按步骤执行）

复制此清单并跟踪进度：

```text
执行进度：
- [ ] Step 0: 前置检查
- [ ] Step 1: 初始化与准备
- [ ] Step 2: 预估价格
- [ ] Step 3: 提交任务
- [ ] Step 4: 异步查询
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
source "$(dirname "$0")/scripts/env_init.sh" las_asr_pro
workdir=$LAS_WORKDIR
```

> 如果网络问题导致更新失败，脚本会跳过检查，使用本地已安装的 SDK 继续执行。

- **处理本地文件时**：先本地检查格式和时长，预估价格，用户确认后再上传：
  ```bash
  # 提前检查容器格式（避免参数错误）
  ./scripts/check_format.sh <local_path>
  # 本地使用 ffprobe 获取时长（无需上传即可预估价格）
  ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:noprint_section=1 <local_path>
  ```
  计算预估价格并等待用户确认后，再执行上传：
  ```bash
  # 用户确认后，上传到 TOS
  lasutil file-upload <local_path>
  ```
  上传成功后返回 JSON，取其中的 `presigned_url`（HTTPS 预签名下载链接，24 小时有效）传给算子作为输入 URL。

### Step 2: 预估价格（⚠️ 必须获得用户确认）

1. 读取 [references/prices.md](references/prices.md) 获取最新计费标准。
2. **优先本地获取时长**（避免不必要上传）：
   ```bash
   # 使用 ffprobe 本地获取
   duration_sec=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:noprint_section=1 <local_path>)
   ```
   如果 ffprobe 失败，再使用 lasutil 远程获取：
   ```bash
   lasutil media-duration <presigned_url>
   ```
3. 根据时长和模型单价计算总价，**将计费单价与预估总价一并告知用户并强制暂停执行**，明确等待用户回复确认。在用户明确回复"继续"、"确认"等同意指令前，**绝对禁止**进入下一步（执行/提交任务）。提示：预估仅供参考，实际以火山账单为准。计费说明请参考 [Volcengine LAS 定价](https://www.volcengine.com/docs/6492/1544808)。

### Step 3: 提交任务 (Submit)

构造基础 `data.json`（仅需必填项，其他按需添加）：
```json
{
  "audio": {"url": "<presigned_url>", "format": "wav"},
  "request": {"model_name": "bigmodel"}
}
```

```bash
data=$(cat "$workdir/data.json")
lasutil submit las_asr_pro "$data" > "$workdir/submit.json"
```
*记录返回的 `metadata.task_id`。*

### Step 4: 异步查询 (Poll)

⚠️ **异步任务与后台轮询约束**：
- 如果你当前的环境**支持后台任务/异步长效运行**：你可以利用环境提供的后台能力（例如发起后台轮询任务），并在任务完成后主动将结果返回给用户。
- 如果你当前的环境**不支持**长效后台任务（如普通的单轮对话沙箱），且直接 `sleep` 循环会导致超时崩溃：**绝对禁止在代码中执行死循环等待！** 此时必须立即向用户输出 Task ID 并结束当前轮次，告知用户："任务已提交，请稍后向我询问进度"。

**使用优化的后台轮询脚本（动态间隔 + 自动提取结果）**：
```bash
mkdir -p "./output/{task_id}"
./scripts/poll_background.sh {task_id} "./output/{task_id}" & disown
```
脚本特性：
- **动态间隔**：前 5 次 30s，5-10 次 60s，10 次后 120s，减少不必要轮询
- **自动提取**：完成后自动生成 `transcript.txt` / `utterances.json` / `utterances.csv`
- **日志记录**：完整轮询历史保存在 `poll.log`

手动查询示例：
```bash
lasutil poll las_asr_pro {task_id} > "./output/{task_id}/result.json"
```
- `COMPLETED` → 结果已自动提取保存到 `./output/{task_id}/`
- `RUNNING`/`PENDING` → 继续等待后台轮询
- `FAILED` → 返回错误。

### Step 5: 结果呈现

**处理结果**（后台轮询已自动完成提取）：

```bash
# 自动生成结果展示 markdown（包含必填计费声明）
./scripts/generate_result.md.sh {task_id} "./output/{task_id}" <estimated_price>
```

生成内容包括：
- 任务信息卡片
- 识别统计（时长/语种/字数）
- 文本预览（前 500 字）
- **自动包含计费声明** ✅

输出文件结构（已由 `poll_background.sh` 自动生成）：
```
./output/{task_id}/
├── result.json       # 完整 API 响应
├── transcript.txt    # 完整识别文本
├── utterances.json   # 分句原始数据（若开启）
└── utterances.csv    # 分句说话人 CSV（若开启）
```

**上传结果文件**（可选）：

```bash
# 上传文本文件供用户下载
lasutil file-upload "./output/{task_id}/transcript.txt"
lasutil file-upload "./output/{task_id}/utterances.csv"
```

**向用户展示**：
1. 使用生成的 markdown 模板
2. 展示前 500 字转写文本
3. 提供本地文件路径
4. 提供签名下载链接（如上传成功）
5. 计费声明已自动包含在模板中


## 审查标准

执行完成后，Agent 应自检：
1. 环境变量是否正确配置
2. 输入文件是否成功上传
3. 输出结果是否正确呈现给用户
4. 计费声明是否包含
