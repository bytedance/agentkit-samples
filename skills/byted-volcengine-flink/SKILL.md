---
name: byted-volcengine-flink
description: Entrypoint for managing Volcengine Flink (based on Apache Flink) workloads. Use it for developing and deploying streaming and batch jobs, diagnosing real-time issues (e.g., backpressure, checkpoint failures, OOM), troubleshooting resources, and performing SRE actions (stop/start/restart/scale/config changes). It intelligently routes requests to four specialized sub-skills and leverages flink-mcp for tool execution.
license: Complete terms in LICENSE
---

# Byted Volcengine Flink

火山引擎 Flink 聚合技能入口，用于统一处理 Flink 相关需求，并按意图转发到对应子技能文档。

## 前置环境

在安装并使用本技能前，需要先完成 `flink-mcp` 前置准备。

### 1) 安装并验证 mcporter

`flink-dev.md`、`flink-resource.md`、`flink-sre.md` 中的运维/诊断指令依赖 `mcporter`。

可按你的 Python 环境选择任一方式安装：

```bash
npm install -g mcporter
```

安装后验证：

```bash
mcporter --help
```

### 2) 配置必需环境变量

`flink-mcp` 启动依赖以下环境变量（缺一不可）：

- `VOLCENGINE_ACCESS_KEY`
- `VOLCENGINE_SECRET_KEY`
- `VOLCENGINE_REGION`
- `VOLCENGINE_PROJECT_NAME`

示例：

```bash
export VOLCENGINE_ACCESS_KEY="your-access-key"
export VOLCENGINE_SECRET_KEY="your-secret-key"
export VOLCENGINE_REGION="cn-beijing"
export VOLCENGINE_PROJECT_NAME="your-flink-project"
```

### 3) 在本地 MCP 配置文件中注册 flink-mcp（推荐）

将 `flink-mcp` 加入本地 MCP Client 使用的配置文件（通常为 `mcp.json` 或等效配置文件）。

说明：MCP Client 会根据这段配置拉起 `flink-mcp`，因此这是默认主路径。

先确保本地已安装 `uv` / `uvx`，然后写入如下配置：

```json
{
  "mcpServers": {
    "mcp-server-flink": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/volcengine/mcp-server#subdirectory=server/mcp_server_flink",
        "mcp-server-flink",
        "-t",
        "streamable-http"
      ],
      "env": {
        "VOLCENGINE_ACCESS_KEY": "${VOLCENGINE_ACCESS_KEY}",
        "VOLCENGINE_SECRET_KEY": "${VOLCENGINE_SECRET_KEY}",
        "VOLCENGINE_REGION": "${VOLCENGINE_REGION}",
        "VOLCENGINE_PROJECT_NAME": "${VOLCENGINE_PROJECT_NAME}",
        "UV_INDEX_URL": "https://mirrors.ivolces.com/pypi/simple/"
      }
    }
  }
}
```

### 4) 可选：手动启动 flink-mcp（仅用于联调/排障）

当需要独立验证服务是否可启动时，可在终端手动执行：

```bash
uvx --from git+https://github.com/volcengine/mcp-server#subdirectory=server/mcp_server_flink mcp-server-flink -t streamable-http
```

## 子技能引用与路由

根据用户需求，将任务路由到以下子技能：

- 开发/部署 Flink SQL：`flink-dev.md`
- 只读诊断（禁止变更操作）：`flink-diagnosis.md`
- 资源与故障分析：`flink-resource.md`
- SRE 运维变更（启停/重启/扩缩容/参数修改）：`flink-sre.md`

### 路由规则

1. 用户表达“创建 SQL / 开发 SQL / 部署 SQL / 调试 SQL”时，优先使用 `flink-dev.md`。
2. 用户明确要求“只读排查、不做任何变更”时，必须使用 `flink-diagnosis.md`。
3. 用户询问故障根因、OOM、Checkpoint、性能问题、连接问题时，优先使用 `flink-resource.md`。
4. 用户要求执行运维动作（启动、停止、重启、扩容、缩容、改配置）时，必须使用 `flink-sre.md`，且先做风险确认。

## 执行原则

- 在信息不足时，先补齐关键参数：项目名、任务名、时间范围、目标动作。
- 任何变更类操作（尤其在 `flink-sre.md` 中）都必须先让用户确认风险。
- 当用户只需要排查时，坚持只读工具链，不触发启动/停止/部署等动作。
