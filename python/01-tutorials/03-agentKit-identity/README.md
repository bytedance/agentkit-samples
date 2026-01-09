# Agent Identity 入门教程

> 为智能体提供企业级身份与权限管理能力

## 概述

随着 LLM 应用的爆发，我们注意到一个明显的趋势：开发者使用 veADK/LangChain 等框架在本地（VS Code/Cursor）构建一个 Demo 非常容易。但在将智能体推向**企业级生产环境**时，往往会撞上一堵“安全墙”。

与传统的微服务不同，真正的企业级 Agent 必须具备 **自主行动能力（Agency）**。而受制于模型能力，Agent 的行为又是不可预测的。这带来了三个核心挑战：

1.  **入站安全 (Inbound Security) —— 谁能调用 Agent？**
    * 常见的基于 API Key 的访问方式由于缺乏防重放机制，安全性低。
    * 企业往往希望复用既有 IdP ，Agent 需要支持通过 SSO (如飞书) 方式验证用户身份，确保只有授权用户才能发起对话。
    
2.  **出站安全 (Outbound Security) —— Agent 代表谁在操作？**
    * **凭证泄露风险**：开发者习惯将 API Key 硬编码在 Agent 代码中，这是巨大的安全隐患。
    * **权限越界**：当 Agent 访问飞书文档或数据库时，它应该拥有“上帝视角”，还是仅拥有“当前用户”的权限？
    * **身份传递**：如何让后端资源知道，这次调用是由“User A”授权“Agent B”发起的？

3.  **细粒度权限管控 (Governance) —— 如何管控“黑盒”？**
    * Agent 需要细粒度的策略控制，而不是一把梭的 `Admin` 权限。
    * 企业 CISO 和安全团队需要知道 Agent 到底访问了什么资源。

## Agent Identity 解决方案

Agent Identity 专为解决上述问题设计，它不是简单的 OAuth 包装，而是为智能体构建的一套完整的**身份治理基础设施**。
![alt text](image.png)
Agent Identity 把“用户 → 应用 → Agent → 资源”的链路拆开治理，并提供一套可复用的安全构件：

- **Inbound 认证**：对接企业现有 IdP（用户池 / OAuth / SSO 等），让“谁能调用 Agent”可配置、可审计。
- **Agent 权威身份**：为 Agent 提供唯一、可验证的身份主体，便于策略绑定与审计归因。
- **Outbound 凭证托管（Token Vault）**：把 OAuth / API Key 的存储、刷新、最小化授权从业务代码中剥离出来；默认做到“凭据不落地”。
- **细粒度权限控制**：基于委托链（Delegation Chain）把“用户权限”和“Agent 权限”组合校验，默认拒绝、按需放开。
- **可观测与审计**：把“谁在什么时候代表谁调用了哪个工具/资源”沉淀为审计事件，方便排障、合规与内控。

## 实验列表
| 实验 | 说明 | 目录 |
|------|------|------|
| **实验1: 用户池认证** | 使用用户池管控智能体访问 (Inbound 认证) | [tutorial-1-userpool-inbound](./tutorial-1-userpool-inbound/) |
| **实验2: 飞书联合登录** | 使用飞书账号作为企业身份源 (IdP 集成) | [tutorial-2-feishu-idp](./tutorial-2-feishu-idp/) |

## 核心功能

- **身份认证 (Inbound)**: 验证用户身份，只有授权用户才能访问 Agent
- **凭证托管 (Outbound)**: Agent 安全访问飞书等外部服务，凭证由平台管理
- **权限控制**: 基于委托链的细粒度权限，控制 Agent 能访问的资源


## 目录结构说明

```
identity/
├── README.md                           # 本文件
├── tutorial-1-userpool-inbound/        # 实验1: Inbound 认证
│   ├── README.md                       # 教程文档
│   ├── main.py                         # 示例代码
│   ├── pyproject.toml                  # 依赖配置
│   ├── .env.template                   # 环境变量模板
│   └── assets/                         # 截图和流程图
└── tutorial-2-feishu-idp/              # 实验2: 飞书 IdP 联合登录
    ├── README.md
    ├── main.py
    ├── pyproject.toml
    ├── .env.template
    └── assets/
```

## 本地运行

### 前置准备

| 项目 | 说明 |
|------|------|
| **火山控制台账号** | 需要 IDFullAccess、STSAssumeRoleAccess 权限的子账号 |
| **Python 环境** | Python 3.12+ 及 [uv](https://docs.astral.sh/uv/) |
| **飞书账号**（实验2/3） | 用于测试飞书登录和文档访问 |

### 快速开始

```bash
# 1. 克隆仓库
git clone https://github.com/volcengine/agentkit-samples.git
cd agentkit-samples/01-tutorials/identity

# 2. 选择实验目录
cd tutorial-1-userpool-inbound  # 或其他实验

# 3. 配置环境变量
cp .env.template .env
# 编辑 .env 填写配置

# 4. 安装依赖
uv sync

# 5. 启动服务
uv run veadk web
```

## AgentKit 部署

本教程所有示例均可通过 `uv run veadk web` 在本地运行。

如需部署到 AgentKit Runtime，请参考 [AgentKit Runtime 文档](https://volcengine.github.io/agentkit-sdk-python/content/4.runtime/1.runtime_quickstart.html)。