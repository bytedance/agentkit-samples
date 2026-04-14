---
name: byted-las-video-edit
version: "1.0.1"
description: "Extracts and clips video segments from long videos using natural language descriptions. AI-powered smart video editing, video trimming, and video cutting powered by Volcengine LAS. Describe what you want — scenes, people, objects, actions, events — and get trimmed clips automatically. Video search and video content retrieval: find and locate specific people, objects, or scenes in footage. Supports reference images for person matching and object matching (search video by image). Two modes: simple (fast) and detail (thorough, optional ASR). Use this skill when the user wants to edit/clip/cut videos using natural language descriptions, extract highlights or key moments from videos, find specific people/objects/scenes in video footage (by text or reference image), compile highlight reels from long videos, trim video segments, or do AI-powered smart video editing."
---

# LAS 视频智能剪辑（`las_video_edit`）

根据自然语言描述从长视频中提取精彩片段，支持参考图像辅助识别特定人物/物体。两种模式：`simple`（快速）和 `detail`（精细分析）。

## 设计模式

本 skill 主要采用：
- **Tool Wrapper**：封装 `lasutil` CLI 调用
- **Pipeline**：包含 Step 0 → Step N 的顺序工作流

## 核心 API 与配置

- **算子 ID**: `las_video_edit`
- **API**: 异步（`submit` → `poll`）
- **环境变量**: `LAS_API_KEY` (必填)

> 详细参数与接口定义见 [references/api.md](references/api.md)。

## Gotchas

- **输出路径格式**：`output_tos_path` 必须是 `tos://` 前缀的目录（不要以文件名结尾），服务端自动创建片段文件。
- **模式选择**：`simple` 快速适用多数场景；`detail` 精细分析时间更长但效果更好。
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
3. **检查输出路径**：
   - `output_tos_path` 为必填参数，必须由用户提供**自己可写的 TOS 目录路径**（格式：`tos://bucket/output_dir/`）。
   - 服务端需要将剪辑输出的视频片段写入此目录。
4. **确认无误后**：才能进入下一步。

### Step 1: 初始化与准备

**环境初始化（Agent 必做）**：

```bash
# 执行统一的环境初始化与更新脚本（会自动创建/激活虚拟环境，并检查更新）
source "$(dirname "$0")/scripts/env_init.sh" las_video_edit
workdir=$LAS_WORKDIR
```

> 如果网络问题导致更新失败，脚本会跳过检查，使用本地已安装的 SDK 继续执行。

- **处理本地文件时**：使用 File API 上传（只需 `LAS_API_KEY`，无需 TOS 凭证和 Bucket）：
  ```bash
  lasutil file-upload <local_path>
  ```
  上传成功后返回 JSON，取其中的 `presigned_url`（HTTPS 预签名下载链接，24 小时有效）传给算子作为输入 URL。

### Step 2: 预估价格（⚠️ 必须获得用户确认）

1. 读取 [references/prices.md](references/prices.md) 获取最新计费标准。
2. 获取视频时长：
   ```bash
   lasutil media-duration <video_url>
   ```
3. 根据时长和模式单价计算总价，**将计费单价与预估总价一并告知用户并强制暂停执行**，明确等待用户回复确认。在用户明确回复"继续"、"确认"等同意指令前，**绝对禁止**进入下一步（执行/提交任务）。提示：预估仅供参考，实际以火山账单为准。计费说明请参考 [Volcengine LAS 定价](https://www.volcengine.com/docs/6492/1544808)。

### Step 3: 提交任务 (Submit)

构造基础 `data.json`：
```json
{
  "video_url": "<presigned_url>",
  "output_tos_path": "tos://<your-bucket>/output_dir/",
  "task_description": "提取戴帽子的小男孩的所有片段，包含台词",
  "reference_images": [
    {"target": "戴帽子的小男孩", "images": ["https://example.com/ref1.jpeg"]}
  ],
  "mode": "simple"
}
```

> **重要提示**: `output_tos_path` **必须由用户提供**，需要填写用户自己账号下可写的 TOS 目录（服务端会将剪辑后的视频片段写入此目录）。

**单文件提交**：
```bash
data=$(cat "$workdir/data.json")
lasutil submit las_video_edit "$data" > "$workdir/submit.json"
```

⚠️ **强制反馈**：任务提交成功后，**必须立即向用户返回生成的 `task_id`**，以便用户跟踪进度或在必要时手动查询。

### Step 4: 异步查询 (Poll)

⚠️ **异步任务与后台轮询约束**：
- 如果你当前的环境**支持后台任务/异步长效运行**：你可以利用环境提供的后台能力（例如发起后台轮询任务），并在任务完成后主动将结果返回给用户。
- 如果你当前的环境**不支持**长效后台任务（如普通的单轮对话沙箱），且直接 `sleep` 循环会导致超时崩溃：**绝对禁止在代码中执行死循环等待！** 此时必须立即向用户输出 Task ID 并结束当前轮次，告知用户："任务已提交，请稍后向我询问进度"。


**单任务查询**：
```bash
lasutil poll las_video_edit {task_id}
```
- `COMPLETED` → 返回剪辑片段列表 `result.data.clips[]`。
- `RUNNING`/`PENDING` → 稍后重试。

### Step 5: 结果呈现

**处理结果**：

```bash
# 保存片段列表到本地
mkdir -p "./output/{task_id}"
cat "./output/{task_id}/result.json" | jq '.data.clips' > "./output/{task_id}/clips.json"

# 生成 CSV 摘要
cat "./output/{task_id}/result.json" | jq -r '.data.clips[] | 
  "\(.clip_id),\(.start_time),\(.end_time),\(.duration)s,\(.description),\(.clip_url)"' > "./output/{task_id}/clips.csv"
```

**视频片段**：
- 视频片段已保存在 TOS，直接返回预签名 URL
- 无需再次上传，直接提供下载链接即可

**向用户展示**：
1. 片段数量、总时长
2. 片段列表（CSV 格式）
3. 每个片段的下载链接（`clip_url`）
4. 本地文件路径：`./output/{task_id}/`
5. 计费声明


## 审查标准

执行完成后，Agent 应自检：
1. 环境变量是否正确配置
2. 输入文件是否成功上传
3. 输出结果是否正确呈现给用户
4. 计费声明是否包含
