# 电商营销视频生成 E-commerce Marketing Video Generation

## 概述

> 本项目基于 VeADK 与 AgentKit 实现电商营销视频生成。用户提供商品名称、卖点、目标人群、使用场景和可选商品图 URL 后，单个 Agent 会先生成一张四宫格营销故事参考图，再基于该参考图生成一条完整的商品营销短视频。
>
> 该示例采用单 Agent 架构，直接调用内置 `image_generate` 与 `video_generate` 工具完成“营销故事构思 / 参考图生成 / 图生视频 / 结果预览”的完整链路，适合作为电商营销视频生成场景的轻量化端到端示例。

- 本项目面向 AgentKit 平台部署，适合快速搭建商品展示、活动促销、品牌种草等短视频生成能力。
- 本项目使用单个 Root Agent 对外提供服务，便于本地调试、云端部署和二次开发。
- 本项目不包含候选生成、质量评估、视频拼接和 TOS 上传等复杂后处理，重点展示更轻量的端到端生成流程。

## 核心功能

本项目提供以下核心功能：

- **商品信息理解**：根据商品名称、卖点、目标人群、使用场景、风格偏好等信息理解营销需求
- **营销故事规划**：自动构思 4 段式营销故事，覆盖吸睛开场、场景代入、卖点放大和行动收束
- **四宫格参考图生成**：调用内置生图工具生成一张 2x2 四宫格营销故事参考图，用于统一商品外观、画面风格和叙事结构
- **商品图参考输入**：支持传入可公开访问的商品图 URL，并在生图阶段尽量保持商品外观、包装结构和主色调一致
- **图生视频生成**：调用内置生视频工具，基于四宫格参考图生成默认 9:16、1080P、15 秒营销短视频
- **可直接预览输出**：以 Markdown 图片和 HTML video 标签返回结果，便于在 AgentKit 调试页或 Web 页面中直接查看

## Agent 能力

系统由一个 Root Agent 对外提供服务，内部通过 Prompt 约束和工具调用完成完整视频生成流程：

- **营销策划能力**：解析用户输入，提取商品名称、核心卖点、受众、场景、风格和比例等关键信息
- **分镜构思能力**：将商品营销需求组织成 4 段式故事结构，并映射到四宫格参考图
- **生图调用能力**：调用 `image_generate` 生成单张四宫格参考图；如用户提供商品图 URL，则作为图生图参考图传入
- **生视频调用能力**：调用 `video_generate`，将四宫格参考图作为 `reference_images`，生成连续营销短视频
- **结果组织能力**：先返回中间态参考图，再返回最终视频，保证生成过程可观察、结果可预览

### 费用说明

| 相关服务 | 描述 | 计费说明 |
| --- | --- | --- |
| DeepSeek V4 Pro (`deepseek-v4-pro-260425`) | 负责理解用户信息、规划营销故事并转化为工具调用。 | [多种计费方式](https://www.volcengine.com/docs/82379/1099320) |
| Doubao Seedream 5.0 pro (`doubao-seedream-5-0-pro-260628`) | 负责根据文本或参考商品图生成四宫格营销故事参考图。 | [多种计费方式](https://www.volcengine.com/docs/82379/1099320) |
| Doubao Seedance 2.0 (`doubao-seedance-2-0-260128`) | 负责根据四宫格参考图和视频描述生成营销短视频。 | [多种计费方式](https://www.volcengine.com/docs/82379/1099320) |

## 本地运行

### 环境准备

开始前，请确保您的开发环境满足以下要求：

- Python 3.12 或更高版本
- veadk-python 0.5.37（见 `pyproject.toml`）
- agentkit-sdk-python 0.5.10（见 `pyproject.toml`）
- 推荐使用 `uv` 进行依赖管理
- <a target="_blank" href="https://console.volcengine.com/ark/region:ark+cn-beijing/apiKey">获取火山方舟 API KEY</a>

### 快速入门

请按照以下步骤在本地部署和运行本项目。

#### 1. 下载代码并安装依赖

```bash
# 克隆代码仓库
git clone https://github.com/bytedance/agentkit-samples.git
cd agentkit-samples/python/02-use-cases/ad_video_gen

# 安装项目依赖
uv sync --index-url https://mirrors.aliyun.com/pypi/simple

# macOS 或 Linux
source .venv/bin/activate

# Windows PowerShell
.venv\Scripts\activate
```

#### 2. 配置环境变量

本地调试时可直接通过环境变量配置模型与 API Key。

```bash
# 主模型
export MODEL_AGENT_NAME=deepseek-v4-pro-260425
export MODEL_AGENT_API_BASE=https://ark.cn-beijing.volces.com/api/v3/
export MODEL_AGENT_API_KEY=<Your Ark API Key>

# 生图模型
export MODEL_IMAGE_NAME=doubao-seedream-5-0-pro-260628
export MODEL_IMAGE_API_BASE=https://ark.cn-beijing.volces.com/api/v3/
export MODEL_IMAGE_API_KEY=<Your Ark API Key>

# 生视频模型
export MODEL_VIDEO_NAME=doubao-seedance-2-0-260128
export MODEL_VIDEO_API_BASE=https://ark.cn-beijing.volces.com/api/v3/
export MODEL_VIDEO_API_KEY=<Your Ark API Key>
```

#### 3. 本地调试

使用 `veadk web` 进行本地调试。按照 VeADK Web 的应用发现规范，请在上一级 `python/02-use-cases` 目录启动服务：

```bash
cd ..
veadk web
```

默认监听 `http://0.0.0.0:8000`。

## AgentKit 部署


如需生成部署配置，可在当前目录执行：

```bash
agentkit config \
    --agent_name ad_video_gen \
    --entry_point agent.py \
    --launch_type cloud \
    --image_tag v1.0.0
```

命令执行完成后，会在当前目录生成 `agentkit.yaml`。

部署到运行时：

```bash
agentkit launch
```

`agentkit launch` 会根据部署配置构建运行产物，并在当前目录生成 `Dockerfile`。

如需本地容器化运行，可将 `--launch_type` 设置为 `local`，或根据 AgentKit CLI 交互提示选择本地部署。

## 技术实现

本项目核心是一套基于 VeADK 的单 Agent 工作流，由 Root Agent 统一完成需求理解、提示词规划和工具调度：

用户输入 → 营销故事规划 → 四宫格参考图生成 → 参考图中间态展示 → 图生视频生成 → 图片与视频预览输出

生成流程中只调用一次 `image_generate` 和一次 `video_generate`：

- `image_generate` 生成一张包含 4 个分镜画面的 2x2 四宫格参考图
- `video_generate` 将四宫格参考图作为 `reference_images`，生成一条连续营销短视频

## 目录结构说明

```plaintext
/
├── README.md                 # 中文文档
├── README_en.md              # 英文文档
├── agent.py                  # AgentKit 服务入口和 root_agent 定义
├── prompt.py                 # 单 Agent 主 Prompt
├── pyproject.toml            # 依赖管理（uv）
├── requirements.txt          # 依赖管理（pip/uv pip）
├── agentkit.yaml             # AgentKit 部署配置（运行 agentkit config 后生成）
└── Dockerfile                # 镜像构建文件（运行 agentkit launch 后生成）
```

## 示例提示词

以下是一些常用的提示词示例：

- `请生成一条杨梅饮料的商品展示视频，竖屏 9:16，清爽夏日风。商品卖点：天然杨梅、酸甜解腻、冰镇更好喝、适合火锅烧烤聚餐。商品图：https://ark-tutorial.tos-cn-beijing.volces.com/multimedia/%E6%9D%A8%E6%A2%85%E9%A5%AE%E6%96%99.jpg`
- `请生成一条奶香松软拉丝吐司的电商营销视频。适用场景：早餐、下午茶、露营野餐。核心卖点：奶香浓郁、组织松软、烤后外脆内软，适合家庭分享。风格：温暖、明亮、有食欲。`
- `为一款侘寂风香薰蜡烛生成 15 秒商品种草视频。目标人群：喜欢极简家居和睡前放松的都市白领。卖点：天然大豆蜡、木质香调、水泥罐身可复用。画面风格：克制、安静、高级。`

## 效果展示

系统能够：

- 自动解析商品信息并生成营销故事结构
- 创建四宫格营销故事参考图
- 基于参考图生成连续商品营销短视频
- 支持商品图 URL 作为图生图参考
- 在 AgentKit 调试页面中直接预览图片和视频结果

## 常见问题

### 是否支持直接上传图片或 base64 图片？

当前示例只支持可公开访问的图片 URL 作为商品参考图。不支持直接上传图片或 base64 图片。

### 是否会生成多条候选视频并自动评估？

当前单 Agent 版本默认只生成一张参考图和一条视频，不包含候选生成、质量评估、拼接和上传流程。

### 是否可以调整视频比例和时长？

可以。默认生成 9:16、1080P、15 秒视频。如果用户在输入中明确指定横版、方版或其他时长，Agent 会优先按照用户指定的规格生成。

## 代码许可

本项目采用开源许可证，详情请参考项目根目录下的 LICENSE 文件。
