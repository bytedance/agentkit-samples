# 电商营销视频生成 E-commerce Marketing Video Generation

## 概述

> 本项目基于 VeADK 的 SequentialAgent（串行多 Agent 编排）实现电商营销视频生成：从“营销策划/分镜脚本/图片生成/质量评估/视频生成/合成发布”串联成一条稳定的工作流，适合快速生成商品展示类短视频（如单品宣传、活动促销物料）。
>
> 该示例以单个 Root Agent 对外提供服务，内部由多个子 Agent 按固定顺序执行，便于本地调试与云端部署。

- 本项目是`ad_video_gen_a2a`的衍生，对其进行了agentkit平台部署的适配。
- 本项目是sequential-agent，而multimedia是使用的是a2a 方式进行agent交互
- 本项目能够在agentkit 平台进行部署

## 核心功能

本项目提供以下核心功能：

- **营销策划与生成配置**：根据用户输入（商品名/卖点/素材链接）生成视频结构与生成参数
- **分镜脚本生成**：自动输出分镜（shot）脚本，包含画面描述、动作与生成要点
- **文生图/图生图批量生成**：按分镜批量生成多张候选首帧图，支持参考图输入
- **图片/视频质量评估与筛选**：对候选图/视频打分并选优，减少“抽卡”成本
- **文生视频/首帧引导视频生成**：基于选中的首帧为每个分镜生成多条视频候选
- **本地合成与TOS上传**：本地拼接分镜视频为成片，并上传到 TOS 生成可访问 URL

## Agent 能力

系统由一个 Root Agent 对外提供服务，内部按顺序编排以下子 Agent：

- **营销策划 Agent (`market_agent`)**：解析用户输入、补全关键信息，生成视频生成配置与分镜数量要求
- **分镜 Agent (`storyboard_agent`)**：根据配置输出分镜脚本（shots）
- **生图 Agent (`image_agent`)**：为每个分镜批量生成候选首帧图
- **图片评估 Agent (`image_evaluate_agent`)**：对每个分镜候选图片进行打分并选优
- **生视频 Agent (`video_agent`)**：基于选优图片生成分镜视频（支持批量、多条候选）
- **视频评估 Agent (`video_evaluate_agent`)**：对分镜视频进行质量评估并选优
- **合成发布 Agent (`release_agent`)**：将选优分镜视频拼接成成片并上传到 TOS 输出链接

### 费用说明

| 相关服务 | 描述 | 计费说明 |
| --- | --- | --- |
| [Doubao-Seed-1.6](https://console.volcengine.com/ark/region:ark+cn-beijing/model/detail?Id=doubao-seed-1-6) | 负责理解用户信息并转化为工具调用。 | [多种计费方式](https://www.volcengine.com/docs/82379/1099320) |
| [Doubao-Seedance 1.5 pro](https://console.volcengine.com/ark/region:ark+cn-beijing/model/detail?Id=doubao-seedance-1-5-pro) | 负责将图片和文字描述转为视频。 | [多种计费方式](https://www.volcengine.com/docs/82379/1099320) |
| [Doubao-Seedream 4.5 pro](https://console.volcengine.com/ark/region:ark+cn-beijing/model/detail?Id=doubao-seedream-4-5) | 负责根据文字或参考图生成图片 | [多种计费方式](https://www.volcengine.com/docs/82379/1099320) |

## 本地运行

### 环境准备

开始前，请确保您的开发环境满足以下要求：

- Python 3.12 或更高版本
- veadk-python 0.5.5（见 `pyproject.toml`）
- 推荐使用 `uv` 进行依赖管理
- 本地需要可用的 `ffmpeg`（用于 `moviepy` 合成视频）
- <a target="_blank" href="https://console.volcengine.com/ark/region:ark+cn-beijing/apiKey">获取火山方舟 API KEY</a>
- <a target="_blank" href="https://console.volcengine.com/iam/keymanage/">获取火山引擎 AK/SK</a>

### 快速入门

请按照以下步骤在本地部署和运行本项目。

#### 1. 下载代码并安装依赖

```bash
# 克隆代码仓库
git clone https://github.com/volcengine/agentkit-samples.git
cd agentkit-samples/python/02-use-cases/ad_video_gen_seq

# 安装项目依赖
uv sync --index-url https://mirrors.aliyun.com/pypi/simple

# mac or linux
source .venv/bin/activate
# windows powershell
.venv\Scripts\activate
```

#### 2. 配置环境变量

请参考 `config.yaml.example` 创建 `config.yaml`，并填入必要的密钥信息（模型、AK/SK、TOS bucket 等）。

```bash
# 复制配置文件
cp config.yaml.example config.yaml
```

`config.yaml` 的关键字段包括：

- `model.agent.*`：用于文本理解/规划/评估的模型配置
- `model.agent.image.*`：用于生图的模型配置
- `model.agent.video.*`：用于生视频的模型配置
- `volcengine.access_key` / `volcengine.secret_key`：用于 TOS 上传鉴权
- `database.tos.bucket`：用于存储生成视频、图片等产物的 bucket 名称
  - 你可以将bucket设置为agentkit-platform-{{your_account_id}}
  - 其中 `{{your_account_id}}`需要替换为您的火山引擎账号 ID
  - 示例: `DATABASE_TOS_BUCKET=agentkit-platform-12345678901234567890`

#### 3.本地调试

- 本地调试时，可直接运行 `debug.py` 启动服务。

  ```bash
  python debug.py
  ```

- 或者通过 `veadk web` 进行调试
  
  通过 `veadk web` 进行本地测试

  ```bash
  veadk web
  ```

默认监听 `http://0.0.0.0:8000`。

#### 4. 调试方法

推荐使用以下方式在本地快速调试完整链路：

```bash
python debug.py
```

## AgentKit 部署

部署前请设置相关环境变量

```bash
export VOLCENGINE_ACCESS_KEY={your_ak}
export VOLCENGINE_SECRET_KEY={your_sk}
```

部署到运行时

```bash
agentkit config \
    --agent_name multimedia_seq \
    --entry_point main.py \
    --launch_type cloud \
    --runtime_envs DATABASE_TOS_BUCKET=agentkit-platform-{{your_account_id}} \
    --image_tag v1.0.0

agentkit launch
```

### 技术实现

本项目核心为一套基于 VeADK 构建的串行多 Agent 工作流，由 Root Agent 统一编排各子 Agent 顺序执行，形成稳定、可复现的视频生产链路：

用户输入 → 营销策划 → 分镜生成 → 生图 → 图片评估 → 生视频 → 视频评估 → 合成与上传

## 目录结构说明

```plaintext
/
├── README.md                 # 本文档
├── app/                      # Agent 与工具实现
│   ├── root/                 # Root 顺序编排入口（SequentialAgent）
│   ├── market/               # 营销策划（生成视频配置/分镜数量等）
│   ├── storyboard/           # 分镜脚本生成
│   ├── image/                # 生图与图片结果结构化
│   ├── eval/                 # 图片/视频评估与选优
│   ├── video/                # 生视频（支持批量生成）
│   ├── release/              # 视频拼接与上传
│   └── utils.py              # URL code 映射、TOS 上传等公共方法
├── config.yaml.example       # 配置文件示例
├── debug.py                  # 本地调试脚本（不启动服务）
├── model.py                  # Agent Model
├── main.py                   # 本地启动服务入口（AgentkitAgentServerApp）
├── pyproject.toml            # 依赖管理（uv）
└── requirements.txt          # 依赖管理（pip/uv pip）
```

## 示例提示词

以下是一些常用的提示词示例：
- `请生成一条巧克力的圣诞节营销视频。商品名：圣诞限定黑巧克力礼盒装。适用场景和人群：适合所有巧克力爱好者，特别是追求圣诞节极致口感、甜蜜分享与能量补充的消费者；适用于圣诞下午茶时光、节日亲友聚会、温馨赠礼或任何需要增添节日氛围的愉悦时刻。主要成分：精选可可豆、纯可可脂、优质牛奶、天然香草，无添加人工色素和防腐剂，富含抗氧化剂。口味/特点：入口即化，丝滑醇厚，浓郁可可香，微苦回甘中带有节日限定的暖心回味 http://lf3-static.bytednsdoc.com/obj/eden-cn/lm_sth/ljhwZthlaukjlkulzlp/ark/assistant/images/ad_chocolate.png`
- `请生成一条面包营销视频。商品名：奶香松软拉丝吐司；适用场景和人群：场景：早餐配餐、下午茶点、日常代餐，人群：上班族、学生党、家庭群体（偏好松软口感的面包爱好者）；主要成分：高筋面粉、牛奶、鸡蛋、黄油、酵母、白砂糖；口味 / 特点：口味：浓郁奶香，搭配黄油 + 蜂蜜后口感香甜柔润，特点：面包质地松软、切面蜂窝气孔均匀，烤后表皮带焦脆斑点，兼具松软内里与香脆外皮的双重口感 http://lf3-static.bytednsdoc.com/obj/eden-cn/lm_sth/ljhwZthlaukjlkulzlp/ark/assistant/images/ad_bread.jpeg`
- `生成一条侘寂风香薰蜡烛的商品图电商营销视频。商品名：侘寂风香薰蜡烛；适用场景和人群：场景：居家客厅装饰、卧室助眠、书房放松、极简风空间氛围营造，人群：喜欢极简 / 侘寂美学的家居爱好者、追求松弛感的都市白领、香薰收藏者；主要成分：天然大豆蜡、植物精油、水泥罐身、纸质标识贴；气味 / 特点：气味：可选木质调（雪松 / 檀香）、草本调（鼠尾草 / 尤加利）等中性舒缓香型，特点：水泥罐身带原生肌理质感，搭配黑白极简花纹标识，烛火柔和不刺眼；罐身可重复利用，整体风格低调质朴，契合侘寂美学的调性 http://lf3-static.bytednsdoc.com/obj/eden-cn/lm_sth/ljhwZthlaukjlkulzlp/ark/assistant/images/ad_candle.jpeg`

## 效果展示

系统能够：

- ✅ 自动解析商品信息并生成营销策略
- ✅ 创建高质量的视频脚本和分镜
- ✅ 生成吸引人的营销文案
- ✅ 制作专业的电商营销视频
- ✅ 提供视频质量评估和优化
- ✅ 支持一键发布到多个平台

## 常见问题

常见问题列表待补充。

## 代码许可

本项目采用开源许可证，详情请参考项目根目录下的 LICENSE 文件。
