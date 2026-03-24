---
name: byted-las-video-edit
description: |
  Extract video clips from long videos based on natural-language descriptions.
  Use this skill when user needs to:
  - Extract highlights or specific scenes from videos
  - Find specific people/objects in videos using reference images
  - Split long videos into meaningful clips
  - Generate video summaries with timestamps
  Supports reference images for target identification, outputs TOS clip URLs.
  Requires LAS_API_KEY for authentication.
---

# LAS 视频智能剪辑（`las_video_edit`）

本 Skill 用于把「火山引擎 LAS 视频智能剪辑」文档里的 `submit/poll` 调用流程，封装成可重复使用的脚本化工作流：

- 通过 `POST https://operator.las.cn-beijing.volces.com/api/v1/submit` 提交任务
- 通过 `POST https://operator.las.cn-beijing.volces.com/api/v1/poll` 轮询任务状态并拿到剪辑结果

## 你需要准备什么

- `LAS_API_KEY`：优先从环境变量读取；也支持放在当前目录的 `env.sh`（内容形如 `export LAS_API_KEY="..."`）
- Operator Region（二选一）：
  - 环境变量：`LAS_REGION`（推荐）/ `REGION` / `region`，取值 `cn-beijing`（默认）或 `cn-shanghai`
  - 或在命令里通过 `--region cn-shanghai` 指定
- `video_url`：可下载的视频地址（`http/https` 或 `tos://bucket/key`）
- `output_tos_path`：剪辑片段输出到的 TOS 目录（必须指定）
- 剪辑需求：二选一
  - `task_name`：内置场景名（优先级高）
  - `task_description`：自然语言描述（推荐写清楚“要找谁/什么/在什么场景/是否需要台词”等）

可选能力：

- `reference_images`：参考图像列表（URL 或 TOS），辅助识别角色/物品/场景
- 参考图像结构：推荐用 `target + images[]` 的结构（详见 `references/api.md`），脚本侧用 `--ref-target` + 多个 `--ref-image` 来生成。
- `mode`：处理模式（服务端合法值通常为 `simple`/`detail`；本脚本也兼容 `简单`/`精细` 等常见别名）
- `segment_duration`：子视频切分时长（秒）
- `min_segment_duration`：过滤过短片段（秒）
- `output_format`：输出格式（示例支持 `mp4`/`mkv`）

## 参数与返回字段（详细版）

参数/返回字段在执行时经常需要对照（比如 `mode`、`segment_duration`、`clips[]` 的结构）。完整速查见：

- `references/api.md`

## 推荐使用方式

本 Skill 自带可执行脚本：`scripts/skill.py`。

为方便在不同工程/不同 Agent 之间迁移，下面示例默认你位于该 Skill 目录（与 `SKILL.md` 同级），因此命令使用相对路径 `scripts/skill.py`。

### 1) 提交任务并等待结果

```bash
python3 scripts/skill.py submit \
  --video "https://example.com/video.mp4" \
  --output-tos "tos://bucket/path/to/output" \
  --task-desc "提取戴帽子的小男孩的所有片段，包含台词" \
  --ref-target "戴帽子的小男孩" \
  --ref-image "https://example.com/ref1.jpeg" \
  --region cn-beijing \
  --mode simple \
  --out result.json

如需直接传入 `reference_images` 的 JSON（高级用法，用于完全对齐服务端 schema），可用：

```bash
python3 scripts/skill.py submit \
  --video "https://example.com/video.mp4" \
  --output-tos "tos://bucket/path/to/output" \
  --task-desc "找杜兰特" \
  --ref-json '[{"target":"杜兰特","images":["https://...jpeg"]}]'
```

### 2) 仅提交（不等待）

```bash
python3 scripts/skill.py submit \
  --video "https://example.com/video.mp4" \
  --output-tos "tos://bucket/path/to/output" \
  --task-desc "找出所有高光片段" \
  --no-wait
```

### 3) 轮询任务

```bash
python3 scripts/skill.py poll task-xxx --region cn-shanghai
```

## Region / Endpoint 的选择逻辑

脚本解析顺序：

1) `--region` 命令行参数（`cn-beijing` 或 `cn-shanghai`）
2) 环境变量 `LAS_REGION` / `REGION` / `region`
3) 默认值 `cn-beijing`

Endpoint 由 region 自动映射到 `operator.las.<region>.volces.com`，不支持自定义 API base。

## 输出结果你会得到什么

当任务 `COMPLETED` 时，返回里会包含：

- `total_segments`
- `clips[]`：每个片段的 `clip_id`、`start_time`、`end_time`、`duration`、`description`、`dialogue`、`clip_url(tos://...)` 等

脚本会把核心信息打印为易读摘要，并可选将原始 JSON 落盘。

## 常见问题

### 1) 提示“无法找到 LAS_API_KEY”怎么办？

- 优先推荐设置环境变量：`export LAS_API_KEY="..."`
- 或在运行目录准备 `env.sh`，内容形如：`export LAS_API_KEY="..."`
- 注意脚本是从“当前工作目录”读取 `env.sh`：如果你在别的目录运行，可能读不到。

### 2) 返回 `Parameter.Invalid`（参数非法）可能是什么原因？

- `mode` 不合法：服务端常见合法值为 `simple` / `detail`（脚本兼容 `normal/标准/精细` 等别名，但建议直接用 `simple/detail`）
- `reference_images` 结构不符合服务端 schema：推荐结构为 `[{"target": "杜兰特", "images": ["https://...jpeg"]}]`；可用 `--ref-target` + 多个 `--ref-image` 或直接用 `--ref-json`
- `output_tos_path` 不是 `tos://...` 目录（或无权限写入），导致生成片段失败
- `video_url`/参考图 URL 不可下载、被鉴权拦截、或网络环境不可达

### 3) TOS 路径格式有什么要求？

- `output_tos_path` 必须是 `tos://bucket/prefix` 形式的“目录前缀”，不要写成本地路径或 `s3://`
- 建议不要以文件名结尾（例如 `.../clip_001.mp4`），让服务端按 `clip_001.mp4, clip_002.mp4...` 自动落盘
