# Callback - Agent 回调与护栏演示

基于火山引擎 VeADK 和 AgentKit 构建的回调机制示例，全面展示 Agent 生命周期各阶段的回调函数和护栏功能。

## 📋 概述

本示例演示了 VeADK 中完整的 Agent 回调体系：

- **六大回调函数**：覆盖 Agent 执行的完整生命周期
- **护栏机制**：输入输出内容审核、PII 信息过滤
- **工具参数校验**：执行前参数验证和准备
- **结果后处理**：统一格式化和规范化输出
- **全链路日志**：完整记录 Agent 执行轨迹

## 🏗️ 架构

```
用户请求
    ↓
before_agent_callback（输入护栏、日志记录）
    ↓
AgentKit 运行时
    ↓
before_model_callback（请求预处理）
    ↓
LLM 模型调用
    ↓
after_model_callback（响应后处理、PII过滤）
    ↓
before_tool_callback（参数校验）
    ↓
Tool 执行（write_article）
    ↓
after_tool_callback（结果规范化）
    ↓
after_agent_callback（收尾、日志汇总）
    ↓
返回给用户
```

### 核心组件

| 组件                 | 描述                                                         |
| -------------------- | ------------------------------------------------------------ |
| **Agent 服务** | [agent.py](agent.py) - 配置回调和护栏的主 Agent                 |
| **回调函数**   | [callbacks/](callbacks/) - 六个回调函数实现                     |
| **工具定义**   | [tools/write_article.py](tools/write_article.py) - 文章撰写工具 |
| **项目配置**   | [pyproject.toml](pyproject.toml) - 依赖管理                     |
| **短期记忆**   | 本地后端存储会话上下文                                       |

### 代码特点

**Agent 配置**（[agent.py](agent.py:11-22)）：

```python
root_agent = Agent(
    name="ChineseContentModerator",
    description="一个演示全链路回调和护栏功能的中文内容审查助手。",
    instruction="你是一个内容助手，可以根据用户要求撰写文章。利用好工具",
    tools=[write_article],
    before_agent_callback=before_agent_callback,
    before_model_callback=before_model_callback,
    after_model_callback=after_model_callback,
    before_tool_callback=before_tool_callback,
    after_tool_callback=after_tool_callback,
    after_agent_callback=after_agent_callback,
)
```

**测试场景**（[agent.py](agent.py:37-44)）：

```python
# 场景1: 正常调用，触发工具和PII过滤
await runner.run(messages="请帮我写一篇关于'人工智能未来'的500字文章。")

# 场景2: 输入包含敏感词，被护栏拦截
await runner.run(messages="你好，我想了解一些关于 zanghua 的信息。")

# 场景3: 工具参数校验失败
await runner.run(messages="写一篇关于'太空探索'的文章，字数-100。")
```

## 🚀 快速开始

### 前置条件

**重要提示**：在运行本示例之前，请先访问 [AgentKit 控制台授权页面](https://console.volcengine.com/agentkit/region:agentkit+cn-beijing/auth?projectName=default) 对所有依赖服务进行授权，确保案例能够正常执行。

**1. 开通火山方舟模型服务**

- 访问 [火山方舟控制台](https://exp.volcengine.com/ark?mode=chat)
- 开通模型服务

**2. 获取火山引擎访问凭证**

- 参考 [用户指南](https://www.volcengine.com/docs/6291/65568?lang=zh) 获取 AK/SK

### 安装步骤

#### 1. 安装 uv 包管理器

```bash
# macOS / Linux（官方安装脚本）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 或使用 Homebrew（macOS）
brew install uv
```

#### 2. 初始化项目依赖

```bash
cd 02-use-cases/beginner/callback

# 初始化虚拟环境和安装依赖
uv sync

# 激活虚拟环境
source .venv/bin/activate
```

#### 3. 配置环境变量

```bash
# 火山方舟模型名称
export MODEL_AGENT_NAME=doubao-seed-1-6-251015

# 火山引擎访问凭证（必需）
export VOLCENGINE_ACCESS_KEY=<Your Access Key>
export VOLCENGINE_SECRET_KEY=<Your Secret Key>
```

### 运行方式

#### 方式一：部署到 AgentKit 平台（推荐）

```bash
cd callback

# 配置部署参数
agentkit config

# 启动云端服务
agentkit launch

# 测试回调功能
agentkit invoke '请帮我写一篇关于人工智能未来的500字文章'

# 测试护栏功能
agentkit invoke '你好，我想了解一些关于 zanghua 的信息'

# 或使用 client.py 连接云端服务
# 需要编辑 client.py，将其中的第 14 行和第 15 行的 base_url 和 api_key 修改为 agentkit.yaml 中生成的 runtime_endpoint 和 runtime_apikey 字段
# 按需修改 client.py，第 56 行，请求的内容
uv run client.py
```

#### 方式二：使用 VeADK Web 调试界面

```bash
# 进入上级目录
cd ..

# 启动 VeADK Web 界面
veadk web --port 8080

# 在浏览器访问：http://127.0.0.1:8080
```

Web 界面可以实时查看回调执行顺序和日志输出。

#### 方式三：命令行测试

```bash
# 启动 Agent 服务并运行测试场景
uv run agent.py
```

**运行效果**：

```
==================== 场景1: 正常调用，触发工具和PII过滤 ====================
[before_agent] 开始处理请求...
[before_model] 准备调用模型...
[before_tool] 校验工具参数...
[after_tool] 工具执行完成，规范化结果...
[after_model] PII信息已过滤...
[after_agent] 请求处理完成

==================== 场景2: 输入包含敏感词，被护栏拦截 ====================
[before_agent] 检测到敏感词，请求被拦截

==================== 场景3: 工具参数校验失败 ====================
[before_tool] 参数校验失败：字数必须为正数
```

#### 方式四：部署到火山引擎 veFaaS

**安全提示**：

> 以下命令仅用于开发测试。生产环境必须启用 `VEFAAS_ENABLE_KEY_AUTH=true`（默认值）并配置 IAM 角色。

```bash
cd callback

# 配置环境变量（仅测试用）
export VEFAAS_ENABLE_KEY_AUTH=false
export VOLCENGINE_ACCESS_KEY=<Your Access Key>
export VOLCENGINE_SECRET_KEY=<Your Secret Key>

# 基础部署（快速开始）
veadk deploy --vefaas-app-name=callback_example --use-adk-web

# 生产级部署（推荐）
veadk deploy \
  --vefaas-app-name=callback_example \
  --use-adk-web \
  --veapig-instance-name=<Your veaPIG Instance> \
  --iam-role "trn:iam::<Your Account ID>:role/<Your IAM Role>"
```

## 💡 回调函数详解

### 1. before_agent_callback

**作用**：Agent 开始运行前的预处理

**典型用途**：

- 输入护栏检查（敏感词过滤）
- 初始化上下文变量
- 记录请求开始日志
- 请求限流和鉴权

**示例**（[callbacks/before_agent_callback.py](callbacks/before_agent_callback.py)）：

```python
def before_agent_callback(agent, callback_context):
    # 敏感词检查
    if contains_sensitive_words(callback_context.input):
        callback_context.reject("检测到敏感内容")
        return

    # 记录日志
    logger.info(f"开始处理请求: {callback_context.session_id}")
```

### 2. before_model_callback

**作用**：LLM 调用前的请求预处理

**典型用途**：

- 修改系统指令（System Prompt）
- 补充元数据和上下文
- 参数调整（温度、max_tokens等）
- 请求内容预处理

**示例**（[callbacks/before_model_callback.py](callbacks/before_model_callback.py)）：

```python
def before_model_callback(callback_context, llm_request):
    # 动态调整系统指令
    llm_request.system_instruction += "\n请确保回复专业且友好。"

    # 调整生成参数
    llm_request.temperature = 0.7
    llm_request.max_tokens = 2000
```

### 3. after_model_callback

**作用**：LLM 响应后的内容后处理

**典型用途**：

- 格式化输出内容
- PII（个人身份信息）过滤
- 提取结构化信息
- 内容审核和改写

**示例**（[callbacks/after_model_callback.py](callbacks/after_model_callback.py)）：

```python
def after_model_callback(callback_context, llm_response):
    # PII信息过滤
    llm_response.content = filter_pii(llm_response.content)

    # 格式化输出
    llm_response.content = format_markdown(llm_response.content)
```

### 4. before_tool_callback

**作用**：工具执行前的参数校验和准备

**典型用途**：

- 参数类型转换和验证
- 默认值填充
- 权限检查
- 轻量级参数预处理

**示例**（[callbacks/before_tool_callback.py](callbacks/before_tool_callback.py)）：

```python
def before_tool_callback(tool_context):
    # 参数校验
    if tool_context.tool_name == "write_article":
        word_count = tool_context.parameters.get("word_count")
        if word_count and word_count < 0:
            raise ValueError("字数必须为正数")

    # 默认值填充
    tool_context.parameters.setdefault("language", "zh-CN")
```

### 5. after_tool_callback

**作用**：工具执行后的结果处理

**典型用途**：

- 结果格式规范化
- 追加辅助信息
- 结果持久化存储
- 错误处理和重试

**示例**（[callbacks/after_tool_callback.py](callbacks/after_tool_callback.py)）：

```python
def after_tool_callback(tool_context, tool_result):
    # 规范化输出格式
    if tool_context.tool_name == "write_article":
        tool_result = {
            "content": tool_result,
            "word_count": len(tool_result),
            "timestamp": datetime.now().isoformat()
        }

    # 保存到数据库
    save_to_database(tool_result)

    return tool_result
```

### 6. after_agent_callback

**作用**：Agent 执行完成后的收尾工作

**典型用途**：

- 汇总执行日志
- 清理临时资源
- 生成执行报告
- 性能指标统计

**示例**（[callbacks/after_agent_callback.py](callbacks/after_agent_callback.py)）：

```python
def after_agent_callback(agent, callback_context, result):
    # 汇总日志
    logger.info(f"请求完成: session_id={callback_context.session_id}")
    logger.info(f"执行时长: {callback_context.duration}ms")
    logger.info(f"调用工具数: {callback_context.tool_count}")

    # 清理资源
    cleanup_temp_files(callback_context.session_id)
```

## 📂 目录结构

```
callback/
├── agent.py                    # Agent 应用入口
├── callbacks/                  # 回调函数实现
│   ├── __init__.py
│   ├── before_agent_callback.py    # Agent前回调
│   ├── after_agent_callback.py     # Agent后回调
│   ├── before_model_callback.py    # 模型前回调
│   ├── after_model_callback.py     # 模型后回调
│   ├── before_tool_callback.py     # 工具前回调
│   └── after_tool_callback.py      # 工具后回调
├── tools/                      # 工具定义
│   ├── __init__.py
│   └── write_article.py        # 文章撰写工具
├── requirements.txt            # Python 依赖列表
├── pyproject.toml              # 项目配置（uv 依赖管理）
└── README.md                   # 项目说明文档
```

## 🔍 技术要点

### 回调执行顺序

```
1. before_agent_callback      → 检查输入，初始化
2. before_model_callback       → 准备模型请求
3. [LLM 调用]                 → 模型生成响应
4. after_model_callback        → 处理模型输出
5. before_tool_callback        → 校验工具参数
6. [Tool 执行]                → 执行具体工具
7. after_tool_callback         → 规范化工具结果
8. [循环 2-7 直到完成]
9. after_agent_callback        → 最终收尾
```

### 护栏机制

**输入护栏**：

- 敏感词检测和拦截
- 恶意请求识别
- 内容安全审核

**输出护栏**：

- PII 信息过滤（身份证、电话、邮箱等）
- 有害内容过滤
- 格式规范化

### 使用场景

| 场景                 | 使用的回调                | 目的               |
| -------------------- | ------------------------- | ------------------ |
| **内容审核**   | before_agent, after_model | 过滤敏感和有害内容 |
| **参数校验**   | before_tool               | 确保工具参数合法   |
| **日志记录**   | 所有回调                  | 追踪完整执行轨迹   |
| **性能监控**   | before_agent, after_agent | 统计响应时间       |
| **结果规范化** | after_tool, after_model   | 统一输出格式       |

## 🎯 扩展方向

### 1. 增强护栏功能

- **多级审核**：接入第三方内容审核 API
- **自定义规则**：配置化敏感词库
- **风险评分**：对请求进行风险评估

### 2. 高级日志

- **分布式追踪**：集成 OpenTelemetry
- **可视化监控**：接入 Grafana/Prometheus
- **审计日志**：合规性审计记录

### 3. 智能优化

- **自适应参数**：根据历史表现调整模型参数
- **A/B 测试**：对比不同策略效果
- **异常检测**：自动识别异常请求

## 📖 相关示例

完成 Callback 学习后，可以探索：

1. **[Hello World](../hello_world/README.md)** - 了解基础 Agent
2. **[Multi Agents](../multi_agents/README.md)** - 多 Agent 中的回调
3. **[Travel Concierge](../travel_concierge/README.md)** - 工具集成
4. **[Video Generator](../../video_gen/README.md)** - 复杂工作流

## 📖 参考资料

- [VeADK 官方文档](https://volcengine.github.io/veadk-python/)
- [AgentKit 开发指南](https://volcengine.github.io/agentkit-sdk-python/)
- [火山方舟模型服务](https://console.volcengine.com/ark/region:ark+cn-beijing/overview?briefPage=0&briefType=introduce&type=new&projectName=default)
