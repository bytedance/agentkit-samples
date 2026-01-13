# Travel Concierge - 旅游行程规划 Agent

基于火山引擎 VeADK 和 AgentKit 构建的智能旅游规划助手，展示如何结合 Web 搜索工具和专业领域知识，自动规划完整的旅行行程。

## 概述

本示例构建了一个专业的旅游行程规划师 Agent。

## 核心功能

- **智能规划**：根据用户需求自动规划旅行行程
- **全面覆盖**：包含自然景点、人文景点、当地美食三个维度
- **工具增强**：使用 Web 搜索获取最新的旅游信息
- **专业指导**：遵循专业的旅游规划流程和约束

## Agent 能力

```text
用户旅行需求
    ↓
AgentKit 运行时
    ↓
Travel Agent（旅游规划师）
    ├── VeADK Agent (对话引擎)
    ├── web_search（网络搜索工具）
    │   └── 搜索景点、美食、交通等信息
    ├── 专业指令系统
    │   ├── 需求分析
    │   ├── 信息收集
    │   ├── 行程规划
    │   ├── 评估调整
    │   └── 呈现反馈
    └── ShortTermMemory（会话记忆）
```

### 核心组件

| 组件 | 描述 |
| - | - |
| **Agent 服务** | [agent.py](https://github.com/volcengine/agentkit-samples/blob/main/02-use-cases/beginner/travel_concierge/agent.py) - 旅游规划 Agent 应用 |
| **专业指令** | [agent.py](https://github.com/volcengine/agentkit-samples/blob/main/02-use-cases/beginner/travel_concierge/agent.py#L21-L94) - 详细的角色定义和工作流程 |
| **测试客户端** | [client.py](https://github.com/volcengine/agentkit-samples/blob/main/02-use-cases/beginner/travel_concierge/client.py) - SSE 流式调用客户端 |
| **项目配置** | [pyproject.toml](https://github.com/volcengine/agentkit-samples/blob/main/02-use-cases/beginner/travel_concierge/pyproject.toml) - 依赖管理（uv 工具） |
| **Web 搜索** | `web_search` - 内置的网络搜索工具 |
| **短期记忆** | 本地后端存储会话上下文 |

### 代码特点

**Agent 定义**（[agent.py](https://github.com/volcengine/agentkit-samples/blob/main/02-use-cases/beginner/travel_concierge/agent.py#L100-L105)）：

```python
root_agent = Agent(
    name="travel_agent",
    description="Simple travel Agent",
    instruction=instruction,  # 详细的专业指令
    tools=[web_search],       # 网络搜索工具
)
```

**专业指令系统**（[agent.py](https://github.com/volcengine/agentkit-samples/blob/main/02-use-cases/beginner/travel_concierge/agent.py#L21-L44)）：

包含完整的角色定义：

- **角色**：专业旅游行程规划师
- **目标**：规划完整行程，结合景点与美食
- **技能**：丰富旅游知识，熟练使用工具
- **工作流程**：沟通→收集→规划→评估→呈现
- **约束**：必须包含三个方面，符合实际，使用工具
- **输出格式**：清晰有条理的行程安排

## 目录结构说明

```bash
travel_concierge/
├── agent.py           # Agent 应用入口（含专业指令系统）
├── client.py          # 测试客户端（SSE 流式调用）
├── requirements.txt   # Python 依赖列表 （agentkit部署时需要指定依赖文件)
├── pyproject.toml     # 项目配置（uv 依赖管理）
└── README.md          # 项目说明文档
```

## 本地运行

### 前置准备

**1. 开通火山方舟模型服务：**

- 访问 [火山方舟控制台](https://exp.volcengine.com/ark?mode=chat)
- 开通模型服务

**2. 获取火山引擎访问凭证：**

- 参考 [用户指南](https://www.volcengine.com/docs/6291/65568?lang=zh) 获取 AK/SK

### 依赖安装

#### 1. 安装 uv 包管理器

```bash
# macOS / Linux（官方安装脚本）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 或使用 Homebrew（macOS）
brew install uv
```

#### 2. 初始化项目依赖

```bash
# 进入项目目录
cd 02-use-cases/beginner/travel_concierge
```

使用 `uv` 工具来安装本项目依赖：

```bash
# 如果没有 `uv` 虚拟环境，可以使用命令先创建一个虚拟环境
uv venv --python 3.12

# 使用 `pyproject.toml` 管理依赖
uv sync --index-url https://pypi.tuna.tsinghua.edu.cn/simple

# 激活虚拟环境
source .venv/bin/activate
```

### 环境准备

```bash
# 火山方舟模型名称
export MODEL_AGENT_NAME=doubao-seed-1-6-251015

# 火山引擎访问凭证（必需）
export VOLCENGINE_ACCESS_KEY=<Your Access Key>
export VOLCENGINE_SECRET_KEY=<Your Secret Key>
```

### 调试方法

#### 方式一：命令行测试（推荐入门）

```bash
# 启动 Agent 服务
uv run agent.py
# 服务将监听 http://0.0.0.0:8000

# 新开终端，运行测试客户端
uv run client.py
```

**运行效果**：

```bash
[create session] Response from server: {"session_id": "agentkit_session"}
[run agent] Event from server:
data: {"event":"on_agent_start",...}
data: {"event":"on_tool_start","tool":"web_search","input":"杭州三日游景点推荐"}
data: {"event":"on_tool_end","tool":"web_search","output":"..."}
data: {"event":"on_llm_chunk","data":{"content":"为您规划杭州三日游行程..."}}
```

#### 方式二：使用 VeADK Web 调试界面

```bash
# 进入上级目录
cd ..

# 启动 VeADK Web 界面
veadk web

# 在浏览器访问：http://127.0.0.1:8000
```

Web 界面可以实时查看 Web 搜索的调用和返回结果。

## AgentKit 部署

### 前置准备

**重要提示**：在运行本示例之前，请先访问 [AgentKit 控制台授权页面](https://console.volcengine.com/agentkit/region:agentkit+cn-beijing/auth?projectName=default) 对所有依赖服务进行授权，确保案例能够正常执行。

**1. 开通火山方舟模型服务：**

- 访问 [火山方舟控制台](https://exp.volcengine.com/ark?mode=chat)
- 开通模型服务

**2. 获取火山引擎访问凭证：**

- 参考 [用户指南](https://www.volcengine.com/docs/6291/65568?lang=zh) 获取 AK/SK

### AgentKit 云上部署

```bash
cd travel_concierge

# 配置部署参数
agentkit config

# 启动云端服务
agentkit launch

# 测试部署的 Agent
agentkit invoke '我想在杭州进行一次为期3天的旅行，喜欢自然风光和历史文化，预算中等?'

# 或使用 client.py 连接云端服务
uv run client.py
```

## 示例提示词

### 示例一：杭州三日游

```text
用户：我想在杭州进行一次为期3天的旅行，喜欢自然风光和历史文化，预算中等。

Agent 执行流程：
1. [需求分析] 提取关键信息：
   - 目的地：杭州
   - 时长：3天
   - 偏好：自然风光、历史文化
   - 预算：中等

2. [信息收集] 使用 web_search 搜索：
   - "杭州自然景点推荐"
   - "杭州历史文化景点"
   - "杭州特色美食"
   - "杭州交通住宿"

3. [行程规划] 结合搜索结果规划行程

4. [评估调整] 检查合理性和可行性

Agent 回复：

为您规划杭州三日游行程：

**第一天：西湖及周边**

上午：
- 抵达杭州，前往西湖
- 游览苏堤、白堤等自然美景
- 漫步湖边，欣赏"西湖十景"

中午：
- 在湖边餐厅品尝西湖醋鱼、龙井虾仁等当地美食
- 人均：80-120元

下午：
- 参观岳王庙，了解岳飞事迹和南宋历史
- 门票：25元

晚上：
- 西湖音乐喷泉表演（免费）
- 在湖滨路品尝夜宵小吃

**第二天：灵隐寺与九溪**

上午：
- 前往灵隐寺（飞来峰景区）
- 感受千年古刹的佛教文化
- 门票：75元（含飞来峰）

中午：
- 在灵隐寺附近品尝素斋
- 人均：60-80元

下午：
- 游览九溪烟树，享受自然风光
- 沿溪而行，空气清新
- 免费景点

晚上：
- 返回市区，品尝杭帮菜
- 推荐：楼外楼、知味观
- 人均：100-150元

**第三天：博物馆与特色街区**

上午：
- 参观浙江省博物馆或杭州博物馆
- 了解杭州历史和文化
- 免费开放

中午：
- 在河坊街品尝特色小吃
- 推荐：定胜糕、葱包烩、酥油饼
- 人均：40-60元

下午：
- 逛河坊街、南宋御街
- 购买特产：龙井茶、丝绸等
- 准备返程

**费用预算（每人）**：
- 住宿：300元/晚 × 2晚 = 600元
- 餐饮：约500元
- 门票：约100元
- 交通（市内）：约100元
- 总计：约1300-1500元

**交通提示**：
- 杭州地铁发达，建议购买杭州通
- 西湖周边可骑共享单车游览
- 部分景点有公交直达

**住宿推荐**：
- 西湖周边快捷酒店：300-400元/晚
- 或选择河坊街附近，交通便利

祝您旅途愉快！如有其他需求请随时告诉我。
```

### 示例二：成都四日游

```text
用户：我打算去成都玩4天，喜欢美食和休闲的氛围，预算充足。

Agent 执行流程：
1. [需求分析] 目的地：成都，时长：4天，偏好：美食、休闲，预算：充足

2. [信息收集] 搜索：
   - "成都美食攻略"
   - "成都休闲景点"
   - "成都周边一日游"

3. [行程规划] 规划4天行程

Agent 回复：

为您规划成都四日游行程：

**第一天：市区休闲游**

上午：
- 抵达成都，前往锦里古街
- 感受成都的休闲氛围
- 免费开放

中午：
- 在锦里品尝成都小吃
- 推荐：三大炮、糖油果子、钟水饺
- 人均：60-80元

下午：
- 参观武侯祠，了解三国文化
- 门票：50元

晚上：
- 品尝正宗四川火锅
- 推荐：蜀大侠、小龙坎
- 人均：120-180元

**第二天：青城山一日游**

上午：
- 前往青城山（约1小时车程）
- 欣赏"青城天下幽"的自然风光
- 门票：80元，索道往返60元

中午：
- 在山上品尝农家菜
- 人均：60-80元

下午：
- 在青城山休息，享受宁静时光
- 可选：泡温泉（额外费用）

晚上：
- 返回成都市区
- 九眼桥酒吧街体验夜生活

**第三天：文化与美食**

上午：
- 参观杜甫草堂，感受诗歌文化
- 门票：50元

中午：
- 附近餐厅品尝川菜
- 推荐：陈麻婆豆腐
- 人均：80-120元

下午：
- 宽窄巷子逛街购物
- 品尝特色小吃和茶饮
- 免费开放

晚上：
- 观看川剧变脸表演
- 推荐：蜀风雅韵
- 票价：180-280元

**第四天：熊猫基地**

上午：
- 前往成都大熊猫繁育研究基地
- 观看可爱的大熊猫
- 门票：55元
- 建议早上9点前到达（熊猫活跃期）

中午：
- 在基地附近餐厅用餐
- 人均：80-100元

下午：
- 返回市区，春熙路购物
- 或在茶馆喝茶、打麻将（体验成都慢生活）

晚上：
- 准备返程

**费用预算（每人）**：
- 住宿：500元/晚 × 3晚 = 1500元
- 餐饮：约800元
- 门票及交通：约500元
- 娱乐（变脸等）：约300元
- 总计：约3000-3500元

**美食清单**：
- 必吃：火锅、串串、麻辣烫、担担面、龙抄手
- 甜品：三大炮、红糖糍粑
- 小吃：夫妻肺片、钟水饺、韩包子

**住宿推荐**：
- 春熙路/太古里周边：交通便利，购物方便
- 宽窄巷子附近：氛围好，体验成都生活

享受您的成都之旅！如需调整行程请告诉我。
```

### 示例三：周末短途游

```text
用户：周末想去北京周边玩一天，喜欢历史古迹，有什么推荐吗？

Agent：根据您的需求，为您推荐北京周边一日游：

**推荐一：八达岭长城**

行程安排：
- 早上7:30 出发（避开人流高峰）
- 9:00 到达八达岭长城
- 9:00-12:00 登长城，体验"不到长城非好汉"
- 12:00-13:00 附近用午餐
- 13:30-15:00 参观长城博物馆
- 15:30 返程

费用：门票40元，往返交通约50元

**推荐二：慕田峪长城（人少景美）**

适合想避开人群的游客，风景更原始，体验更好。

**推荐三：古北水镇**

既有历史古迹，又有特色小镇，可以泡温泉、品美食。

您更偏好哪一个？我可以为您详细规划行程！
```

## 效果展示

## 技术要点

### 专业指令系统

本示例的核心是详细的专业指令系统（[agent.py](agent.py:21-94)），包含：

**1. 角色定义**：

```text
你是一名专业的旅游行程规划师，擅长根据用户需求，结合当地实际情况，
规划出包含自然景点、人文景点和当地美食的旅游行程
```

**2. 目标设定**：

- 按照用户需求规划完整行程
- 结合自然景点、人文景点、当地美食
- 调用合适的工具满足需求

**3. 工作流程**：

1. 与用户沟通，明确需求（时间、预算、偏好等）
2. 运用工具收集信息
3. 根据信息规划初步行程
4. 评估调整，确保合理性
5. 呈现行程，根据反馈修改

**4. 约束条件**：

- 必须结合自然景点、人文景点、美食三个方面
- 内容必须符合当地实际情况
- 必须使用工具进行信息收集
- 禁止规划不合理或不可行的行程

**5. 输出格式**：

- 清晰有条理的文本
- 包含每天的行程安排
- 景点介绍、美食推荐
- 专业实用的文字风格

### Web 搜索工具使用

**工具集成**（[agent.py](https://github.com/volcengine/agentkit-samples/blob/main/02-use-cases/beginner/travel_concierge/agent.py#L104)）：

```python
from veadk.tools.builtin_tools.web_search import web_search

root_agent = Agent(
    tools=[web_search],
)
```

**搜索策略**：

Agent 会根据用户需求自动组织搜索关键词：

- 目的地 + "旅游景点推荐"
- 目的地 + "特色美食"
- 目的地 + "住宿交通"
- 目的地 + "旅游攻略"

**结果处理**：

Agent 会：

1. 从多个搜索结果中提取关键信息
2. 验证信息的真实性和时效性
3. 结合多个来源综合规划
4. 过滤广告和不相关内容

### 🎯 扩展方向

### 1. 增强信息源

- **集成地图 API**：获取实时距离和路线
- **天气 API**：考虑天气因素调整行程
- **点评数据**：引入大众点评、携程等评分

### 2. 个性化推荐

- **用户画像**：记录用户历史偏好
- **智能推荐**：基于历史数据推荐景点
- **动态调整**：根据实时反馈调整行程

### 3. 自动化服务

- **预订集成**：自动预订酒店、门票
- **行程提醒**：发送行程提醒和注意事项
- **导游服务**：提供实时导览和讲解

## 相关示例

完成 Travel Concierge 后，可以探索：

1. **[Hello World](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/beginner/hello_world/README.md)** - 了解基础 Agent
2. **[MCP Simple](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/beginner/mcp_simple/README.md)** - 集成更多专业工具
3. **[Multi Agents](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/beginner/multi_agents/README.md)** - 构建多Agent协作
4. **[Video Generator](../../video_gen/README.md)** - 复杂工具链编排

## 常见问题

无。

## 参考资料

- [VeADK 官方文档](https://volcengine.github.io/veadk-python/)
- [AgentKit 开发指南](https://volcengine.github.io/agentkit-sdk-python/)
- [火山方舟模型服务](https://console.volcengine.com/ark/region:ark+cn-beijing/overview?briefPage=0&briefType=introduce&type=new&projectName=default)

## 代码许可

本工程遵循 Apache 2.0 License
