# AI运维 Agent - Mini AIOps

## 概述

> 本项目基于Veadk开发，实现了一个基于AI的运维智能工具

## 核心功能

本项目提供以下核心功能：

- 智能云资源巡检：自动梳理云上资源运行状态，发现潜在风险
- 一键问题诊断：结合日志、监控和主机诊断能力给出故障原因分析
- 运维知识问答：基于内置知识库回答常见运维问题和 SOP 流程
- 多 Agent 协同：通过 CCAPI 等 MCP 工具自动执行部分运维操作
- 长短期记忆：结合会话记忆与长期记忆提供持续性的运维助手体验

## Agent 能力

本项目当前内置一个总控 Agent 和一个子 Agent：

- ve_ai_ops_agent：面向云计算运维场景的总控 Agent，负责理解用户需求并规划巡检、诊断和优化流程。
- ccapi_agent：专注云资源管控的子 Agent，通过 CCAPI MCP 工具集查看和调整云上资源配置。

## 本地运行

### 环境准备

开始前，请确保您的开发环境满足以下要求：

- Python 3.10 或更高版本
- VeADK 0.2.28 或更高版本
- 推荐使用 `uv` 进行依赖管理
- <a target="_blank" href="https://console.volcengine.com/ark/region:ark+cn-beijing/apiKey">获取火山方舟 API KEY</a>
- <a target="_blank" href="https://console.volcengine.com/iam/keymanage/">获取火山引擎 AK/SK</a>

### 快速入门

请按照以下步骤在本地部署和运行本项目。

#### 1. 下载代码并安装依赖

```bash
# 克隆代码仓库
git clone https://github.com/volcengine/agentkit-samples.git
cd python/02-use-cases/06_mini_aiops

# 安装项目依赖
uv sync --index-url https://pypi.tuna.tsinghua.edu.cn/simple
```

#### 2. 配置环境变量

```bash
export MODEL_AGENT_API_KEY="xxxxx"
export VOLCENGINE_ACCESS_KEY="xxxxxx"
export VOLCENGINE_SECRET_KEY="xxxxxx"
```

#### 4. 启动服务

1. 请先保证环境变量配置正确

2. 本地`veadk web`启动测试（注意：请保持在`agentkit-samples/02-use-cases`目录）

```bash
veadk web
```

1. 进入服务url `http://127.0.0.1:8000`
2. 选择`06_mini_aiops`
3. 与Agent进行对话

#### 5. 测试服务

![image1](./img/image1.png)

## 目录结构说明

```plaintext
06_mini_aiops/
├── agent.py        # AIOps Agent 定义
├── README.md       # 使用说明与功能介绍
├── requirements.txt# 依赖列表（基于 veadk-python）
├── pyproject.toml  # 项目配置（uv/构建配置）
├── sop_aiops.md    # 运维 SOP 文档（可导入到知识库）
├── img/            # README 中使用的示意截图
└── uv.lock         # uv 生成的锁定文件
```

## AgentKit 部署

```bash
# 1. 进入`06_mini_aiops`
cd 06_mini_aiops
# 2. 初始化配置
agentkit config
# 3. 根据说明进行配置
# 注意：第7步无需设置环境变量，第8步可以选择cloud模式

# 4. 部署
agentkit launch
```

部署过程完成后，由于运维MCP工具需要ECS相关权限，请前往控制台开通相关权限

进入控制台

![image4](./img/image4.png)

开通相关权限

![image5](./img/image5.png)

## 示例提示词

以下是一些常用的提示词示例：

"创建IAM用户"
"查看现有的ECS实例"
"列出可用的资源类型"
"更新某个资源的配置"

## 效果展示

部署中，控制台界面
![image2](./img/image2.png)
部署完成后，bash界面
![image3](./img/image3.png)

线上测试成功
![image6](./img/image6.png)

## 常见问题

常见问题列表待补充。

## 代码许可

本项目采用开源许可证，详情请参考项目根目录下的 LICENSE 文件。
