# Video Breakdown Agent 配置指南

本文档说明 Video Breakdown Agent 所需的全部配置项、优先级规则、可观测性集成方式及常见问题排查。

## 快速开始

```bash
# 1. 复制环境变量模板
cp .env.example .env

# 2. 编辑 .env，至少填写以下必需项
#    MODEL_AGENT_API_KEY     — 方舟模型 API Key
#    VOLCENGINE_ACCESS_KEY   — 火山引擎 AK（上传视频需要）
#    VOLCENGINE_SECRET_KEY   — 火山引擎 SK

# 3. 启动
uv run veadk web
```

## 配置优先级

VeADK 按以下优先级（从高到低）读取配置：

| 优先级 | 来源 | 说明 |
|--------|------|------|
| 1 | 系统环境变量 | 通过 `export` 或 CI/CD 注入 |
| 2 | `.env` 文件 | 项目根目录下，推荐用于本地开发 |
| 3 | `config.yaml` | 项目根目录下，作为备选 |

> 参考：[VeADK 配置项文档](https://volcengine.github.io/veadk-python/configuration/)

## 工具返回数据优化策略

为避免工具返回数据过大导致 LLM context 超限，本项目对视觉分析工具返回数据做了精简处理：

### 优化细节

- **完整数据存储位置**：`tool_context.state["vision_analysis_result"]`（包含完整的 base64 frame_urls）
- **工具返回数据**：移除 base64 图片 URL，替换为占位符 `"（base64图片已省略）"`
- **数据量减少**：从 ~2200KB 精简到 ~3KB（减少 99.8%）
- **后续工具使用**：钩子分析、报告生成等工具从 `tool_context.state` 读取完整数据，不受影响

### 为什么需要精简？

- **Token 限制**：豆包模型的 context window 相对较小，大量 base64 图片数据会导致 `Total tokens exceed max message tokens` 错误
- **性能优化**：减少 LLM 处理的数据量，提升响应速度
- **成本控制**：减少 token 消耗，降低 API 调用成本

### 如何获取完整数据？

如果你的自定义工具需要访问完整的帧图 URL（含 base64），可以这样读取：

```python
from google.adk.tools import ToolContext

async def my_custom_tool(tool_context: ToolContext) -> str:
    # 从 session state 读取完整的视觉分析结果
    vision_result = tool_context.state.get("vision_analysis_result", [])
    
    # vision_result 是一个列表，每个元素包含完整的 frame_urls（含 base64）
    for segment in vision_result:
        frame_urls = segment.get("frame_urls", [])  # 完整的 base64 URLs
        # ... 使用 frame_urls 进行后续处理
```

> 参考实现：[`tools/analyze_hook_segments.py`](video_breakdown_agent/tools/analyze_hook_segments.py) 中从 `tool_context.state` 读取完整数据的示例。

## 环境变量一览

### 必需配置

| 环境变量 | 说明 | 示例值 |
|---------|------|--------|
| `MODEL_AGENT_API_KEY` | 方舟模型 API Key | `your_api_key` |

### 模型配置（MODEL_*）

| 环境变量 | 说明 | 默认值 |
|---------|------|--------|
| `MODEL_AGENT_NAME` | 主 Agent 推理模型名称 | `doubao-seed-1-6-251015` |
| `MODEL_AGENT_PROVIDER` | 模型提供商（火山方舟使用 `openai`） | `openai` |
| `MODEL_AGENT_API_BASE` | 模型 API 地址 | `https://ark.cn-beijing.volces.com/api/v3/` |
| `MODEL_AGENT_API_KEY` | 模型 API 密钥 | — |
| `MODEL_VISION_NAME` | 视觉分析模型（豆包 Responses API） | `doubao-seed-1-6-vision-250815` |
| `MODEL_VISION_API_KEY` | 视觉模型 API Key | 回退到 `MODEL_AGENT_API_KEY` |
| `MODEL_VISION_API_BASE` | 视觉模型 API 地址 | 回退到 `MODEL_AGENT_API_BASE` |
| `MODEL_BGM_NAME` | BGM 分析模型（豆包文本 API） | `doubao-seed-1-6-251015` |
| `MODEL_BGM_API_KEY` | BGM 模型 API Key | 回退到 `MODEL_AGENT_API_KEY` |
| `MODEL_BGM_API_BASE` | BGM 模型 API 地址 | 回退到 `MODEL_AGENT_API_BASE` |
| `MODEL_FORMAT_NAME` | 格式化模型（JSON 校验） | `doubao-seed-1-6-251015` |
| `VISION_CONCURRENCY` | 视觉分析并发数 | `3` |

### 豆包 API 调用架构

本项目使用豆包官方 API 格式，不依赖 LiteLLM 进行工具层的 LLM 调用：

| 组件 | API 类型 | 模型 | Endpoint |
|------|---------|------|----------|
| 主 Agent / 子 Agent | 文本模型（VeADK 框架管理） | `doubao-seed-1-6-251015` | `/chat/completions` |
| `analyze_segments_vision` 工具 | 视觉模型（自定义 httpx 调用） | `doubao-seed-1-6-vision-250815` | `/responses` |
| `analyze_bgm` 工具 | 文本模型（自定义 httpx 调用） | `doubao-seed-1-6-251015` | `/chat/completions` |
| `hook_analysis_agent` | 视觉模型（VeADK 框架管理） | `doubao-seed-1-6-vision-250815` | VeADK 内部路由 |

> **重要**：豆包视觉模型使用 `/responses` endpoint（非标准 OpenAI 格式），封装在 `video_breakdown_agent/utils/doubao_client.py` 中。

### 火山引擎凭证（VOLCENGINE_*）

| 环境变量 | 说明 | 备注 |
|---------|------|------|
| `VOLCENGINE_ACCESS_KEY` | 火山引擎 Access Key | 上传视频到 TOS 时需要 |
| `VOLCENGINE_SECRET_KEY` | 火山引擎 Secret Key | 上传视频到 TOS 时需要 |

### TOS 对象存储（DATABASE_TOS_*）

| 环境变量 | 说明 | 默认值 |
|---------|------|--------|
| `DATABASE_TOS_BUCKET` | TOS 存储桶名称 | `video-breakdown-uploads` |
| `DATABASE_TOS_REGION` | TOS 区域 | `cn-beijing` |
| `DATABASE_TOS_ENDPOINT` | TOS 端点（可选） | 自动生成 |

> 注：为向后兼容，代码同时支持旧变量名 `TOS_BUCKET` / `TOS_REGION`（Deprecated，将在后续版本移除）。

### Thinking 配置

| 环境变量 | 说明 | 默认值 |
|---------|------|--------|
| `THINKING_ROOT_AGENT` | 主 Agent 推理模式 | `disabled` |
| `THINKING_BREAKDOWN_AGENT` | 分镜拆解 Agent | `disabled` |
| `THINKING_HOOK_ANALYZER_AGENT` | 钩子分析 Agent | `disabled` |
| `THINKING_HOOK_FORMAT_AGENT` | 格式化 Agent | `disabled` |
| `THINKING_REPORT_AGENT` | 报告生成 Agent | `disabled` |

### Skills 配置

| 环境变量 | 说明 | 备注 |
|---------|------|------|
| `SKILL_SPACE_ID` | AgentKit Skill Space ID | 配置后从平台加载 Skills |

未配置 `SKILL_SPACE_ID` 时，自动检测本地 `skills/` 目录。

## 可观测性配置

VeADK 支持三种 OpenTelemetry 后端，配置对应环境变量后自动启用：

### APMPlus（火山引擎 APM，推荐）

```bash
OBSERVABILITY_OPENTELEMETRY_APMPLUS_ENDPOINT=http://apmplus-cn-beijing.volces.com:4317
OBSERVABILITY_OPENTELEMETRY_APMPLUS_API_KEY=<your_apm_api_key>
OBSERVABILITY_OPENTELEMETRY_APMPLUS_SERVICE_NAME=video_breakdown_agent
```

### CozeLoop（Coze 平台观测）

```bash
OBSERVABILITY_OPENTELEMETRY_COZELOOP_ENDPOINT=https://api.coze.cn/v1/loop/opentelemetry/v1/traces
OBSERVABILITY_OPENTELEMETRY_COZELOOP_API_KEY=<your_coze_api_key>
OBSERVABILITY_OPENTELEMETRY_COZELOOP_SERVICE_NAME=<your_space_id>
```

### TLS（火山引擎日志服务）

```bash
OBSERVABILITY_OPENTELEMETRY_TLS_ENDPOINT=https://tls-cn-beijing.volces.com:4318/v1/traces
OBSERVABILITY_OPENTELEMETRY_TLS_SERVICE_NAME=<your_topic_id>
OBSERVABILITY_OPENTELEMETRY_TLS_REGION=cn-beijing
```

### 启用开关

配置好上述环境变量后，还需设置对应的开关变量为 `true`：

```bash
VEADK_TRACER_APMPLUS=true      # 启用 APMPlus Exporter
VEADK_TRACER_COZELOOP=true     # 启用 CozeLoop Exporter
VEADK_TRACER_TLS=true          # 启用 TLS Exporter
```

> 三种后端可任选其一或组合使用。详见 [VeADK 可观测文档](https://volcengine.github.io/veadk-python/observability/)。

## config.yaml 与 .env 的对应关系

```
config.yaml 字段                  →  环境变量
──────────────────────────────────────────────────
model.agent.name                  →  MODEL_AGENT_NAME
model.agent.provider              →  MODEL_AGENT_PROVIDER
model.agent.api_base              →  MODEL_AGENT_API_BASE
model.agent.api_key               →  MODEL_AGENT_API_KEY
model.vision.name                 →  MODEL_VISION_NAME
model.vision.api_key              →  MODEL_VISION_API_KEY
model.vision.api_base             →  MODEL_VISION_API_BASE
model.bgm.name                    →  MODEL_BGM_NAME
model.bgm.api_key                 →  MODEL_BGM_API_KEY
model.bgm.api_base                →  MODEL_BGM_API_BASE
model.format.name                 →  MODEL_FORMAT_NAME
volcengine.access_key             →  VOLCENGINE_ACCESS_KEY
volcengine.secret_key             →  VOLCENGINE_SECRET_KEY
database.tos.bucket               →  DATABASE_TOS_BUCKET
database.tos.region               →  DATABASE_TOS_REGION
asr.app_id                        →  VOLC_ASR_APP_ID
asr.access_key                    →  VOLC_ASR_ACCESS_KEY
asr.resource_id                   →  VOLC_ASR_RESOURCE_ID
ffmpeg.bin_path                   →  FFMPEG_BIN
ffmpeg.probe_bin_path             →  FFPROBE_BIN
ffmpeg.media_temp_dir             →  MEDIA_TEMP_DIR
thinking.*                        →  THINKING_*
```

> **模型说明**：视觉分析使用豆包 Responses API（`/responses` endpoint），文本分析使用标准 Chat Completions API。封装代码位于 `video_breakdown_agent/utils/doubao_client.py`。

## 常见问题

### 模型未激活

```
The model or endpoint xxx does not exist or you do not have access to it.
```

请前往 [火山引擎方舟控制台](https://console.volcengine.com/ark) 激活对应模型。当前使用：
- 文本模型：`doubao-seed-1-6-251015`
- 视觉模型：`doubao-seed-1-6-vision-250815`（需单独激活）

### TOS 连接失败

```
TOS 存储桶 xxx 不存在，请先创建
```

1. 确认 `DATABASE_TOS_BUCKET` 对应的存储桶已在火山引擎 TOS 控制台创建
2. 确认 `VOLCENGINE_ACCESS_KEY` 和 `VOLCENGINE_SECRET_KEY` 正确
3. 确认 `DATABASE_TOS_REGION` 与存储桶所在区域一致

### FFmpeg/FFprobe 未找到

```
FileNotFoundError: ffmpeg not found
```

请确认已安装 FFmpeg 和 FFprobe，且可执行文件在系统 PATH 中，或通过 `FFMPEG_BIN` / `FFPROBE_BIN` 环境变量指定路径。

### VeADK 未读取到 config.yaml

确保从项目根目录启动：

```bash
cd 02-use-cases/video_breakdown_agent
uv run veadk web
```

VeADK 从当前工作目录读取 `config.yaml`。
