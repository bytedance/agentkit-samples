# EFS 代码工作区智能体

> [!IMPORTANT]
> 本示例展示“代码智能体 → 创建 A Sandbox 并挂载 EFS filespace → 写入代码产物和可执行脚本 → 创建 B Sandbox 并挂载同一个 filespace → 执行 A 写入的脚本验证跨实例共享”的完整链路。VeADK 负责智能体入口和工具编排，EFS Session 操作由确定性的自定义工具完成。

## 概述

很多代码智能体需要一个跨沙箱实例共享的工作区：模型可能分多轮生成脚本、报告、测试结果或中间数据；后续任务如果调度到新的沙箱实例，仍然应该可以访问同一个 filespace 下的产物。这个示例把 EFS 挂载进两个独立的 Sandbox Session，让 writer Session 在 EFS 路径下写入任务说明、报告、元数据和校验脚本，再让 reader Session 挂载同一个 `FilespaceName` 并执行 writer 留下的脚本。

本示例适合验证三类能力：

- **跨实例共享**：A Session 写入 EFS，B Session 挂载同一 filespace 后读取并执行同一目录下的文件。
- **filespace 隔离**：可选创建 C Session 挂载另一个 filespace，验证同一路径下看不到 A Session 的产物。
- **接口接入方式**：通过 AgentKit Tools OpenAPI 的 CreateSession 传入 EFS 挂载配置。

## 核心功能

1. **创建 writer 沙箱会话**：调用 CreateSession，并传入 `EfsMountConfigs` 挂载目标 filespace。
2. **生成代码工作区产物**：在 EFS 挂载路径下写入任务说明、报告、元数据、活动日志和 `read_workspace.py`。
3. **创建 reader 沙箱会话**：再次调用 CreateSession，挂载同一个 `FilespaceName`。
4. **执行共享文件验证**：reader Session 执行 writer 写入的 `read_workspace.py`，证明目录来自同一个 EFS filespace。
5. **可选隔离校验**：如果配置了第二个 filespace，创建 C Session 验证同一路径下不可见。
6. **结构化返回结果**：把 writer/reader Session ID、工作区路径、报告路径和验证结果返回给 VeADK Agent。

## Agent 能力

| 组件 | 描述 |
| --- | --- |
| 智能体入口 | `agent.py` 定义 VeADK Agent，并挂载 EFS 工作区工具 |
| OpenAPI Client | `agentkit_client.py` 完成 AgentKit Tools OpenAPI 签名、重试和错误解析 |
| EFS 工具 | `efs_workspace.py` 封装 CreateSession、AsyncExecCommand、ViewAsyncCommand 和 DeleteSession |
| 本地客户端 | `client.py` 通过 SSE 调用本地 Agent 服务 |

## 链路图

```text
用户请求
  ↓
VeADK Agent
  ↓ 调用自定义工具 run_efs_workspace_demo
CreateSession(EfsMountConfigs)
  ↓
writer AsyncExecCommand 写入 /mnt/efs/agentkit-code-agent/...
  ↓
CreateSession(EfsMountConfigs，同一个 FilespaceName)
  ↓
reader AsyncExecCommand 执行 read_workspace.py
  ↓
可选：CreateSession(EfsMountConfigs，另一个 FilespaceName)
  ↓
可选：isolation AsyncExecCommand 校验同路径不可见
  ↓
返回 writer/reader session、工作区路径、报告路径、验证结果
```

## 目录结构说明

```text
efs_code_workspace_agent/
├── agent.py              # VeADK 智能体入口
├── agentkit_client.py    # AgentKit Tools OpenAPI 签名 HTTP client
├── efs_workspace.py      # EFS 沙箱工作区工具
├── client.py             # 本地 SSE 测试客户端
├── .env.example          # 环境变量示例
├── requirements.txt      # pip 依赖
├── pyproject.toml        # uv 项目配置
├── project.yaml          # 样例市场元数据
└── README.md             # 使用说明
```

## CreateSession 的 EFS 参数

自定义工具最终调用 CreateSession 时，会在请求体中传入 EFS 挂载配置：

```json
{
  "ToolId": "t-xxxxxxxx",
  "Ttl": 28800,
  "TtlUnit": "second",
  "UserSessionId": "efs-code-agent-xxxx-writer",
  "EfsMountConfigs": [
    {
      "FilespaceName": "agentkit-code-agent-demo",
      "LocalMountPath": "/mnt/efs/",
      "ReadOnly": false
    }
  ]
}
```

writer Session 和 reader Session 会分别调用一次 CreateSession。二者使用不同的 `UserSessionId`，但传入相同的 `EfsMountConfigs[0].FilespaceName` 和 `LocalMountPath`，因此 reader Session 可以访问 writer Session 写入的工作区。可选隔离校验会再创建一个 Session，并挂载另一个 `FilespaceName`。

字段来源：

| 字段 | 来源 |
| --- | --- |
| ToolId | 环境变量 AGENTKIT_TOOL_ID |
| Ttl | 环境变量 AGENTKIT_SESSION_TTL_SECONDS，默认 28800 秒 |
| UserSessionId | 环境变量 AGENTKIT_EFS_DEMO_RUN_ID；未设置时自动生成，并追加 writer、reader、isolation 后缀 |
| EfsMountConfigs[0].FilespaceName | 环境变量 AGENTKIT_EFS_FILESPACE_NAME，或工具参数 filespace_name |
| 隔离校验 FilespaceName | 环境变量 AGENTKIT_EFS_ISOLATION_FILESPACE_NAME，或工具参数 isolation_filespace_name；为空则跳过 |
| EfsMountConfigs[0].LocalMountPath | 环境变量 AGENTKIT_EFS_LOCAL_MOUNT_PATH，默认 /mnt/efs/ |
| EfsMountConfigs[0].ReadOnly | 本示例需要写文件，因此固定要求 false |

`LocalMountPath` 必须以 `/` 结尾，例如 `/mnt/efs/`。如果写成 `/mnt/efs`，CreateSession 会返回
`InvalidParameter: EFS LocalMountPath "/mnt/efs" must end with "/"`。

## 本地运行

### 1. 安装依赖

```bash
cd python/01-tutorials/04-agentkit-tools/efs_code_workspace_agent
uv venv --python /usr/bin/python3
source .venv/bin/activate
uv pip install -r requirements.txt
```

如果机器上有多个 Python，优先选择能正常导入 `sqlite3` 的 Python：

```bash
python3 -c "import sqlite3; print(sqlite3.sqlite_version)"
```

如果 `uv run agent.py` 自动选择了缺少 `_sqlite3` 的 `/usr/local/bin/python3.13`，可以显式重建虚拟环境：

```bash
uv venv --python /usr/bin/python3 --clear
source .venv/bin/activate
uv pip install -r requirements.txt
```

也可以使用 pip：

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env` 或直接导出环境变量：

```bash
export VOLCENGINE_ACCESS_KEY=<your-access-key>
export VOLCENGINE_SECRET_KEY=<your-secret-key>
export VOLCENGINE_AGENTKIT_REGION=cn-beijing
export AGENTKIT_TOOL_ID=t-xxxxxxxx
export AGENTKIT_EFS_FILESPACE_NAME=agentkit-code-agent-demo
export AGENTKIT_EFS_ISOLATION_FILESPACE_NAME=agentkit-code-agent-demo-isolated
export AGENTKIT_EFS_LOCAL_MOUNT_PATH=/mnt/efs/
export AGENTKIT_EFS_READ_ONLY=false
```

`AGENTKIT_EFS_ISOLATION_FILESPACE_NAME` 是可选项；配置后会额外创建一个挂载不同 filespace 的 Session，用来验证同一路径下看不到 writer 写入的文件。沙箱工具需要支持 AsyncExecCommand 和 ViewAsyncCommand，对应镜像内应有 python3。

### 3. 启动 Agent

```bash
uv run agent.py
```

默认服务监听 `http://0.0.0.0:8000`。

直接在浏览器访问 `http://<host>:8000` 返回 `Method Not Allowed` 是正常现象。该服务入口用于
`client.py` 调用 `/run_sse`，不是浏览器首页。

### 4. 运行本地客户端

新开一个终端：

```bash
cd python/01-tutorials/04-agentkit-tools/efs_code_workspace_agent
source .venv/bin/activate
uv run client.py
```

如果虚拟环境已经激活，也可以直接运行：

```bash
python client.py
```

也可以直接在 VeADK Web 调试界面中输入：

```text
请完整演示一次 EFS 代码工作区链路：创建 A 沙箱挂载 filespace 写入一份代码任务报告，再创建 B 沙箱挂载同一个 filespace，执行 A 写入的脚本并读取报告，最后清理沙箱。
```

### 5. 判断是否成功

`client.py` 会打印 SSE 原始事件，因此终端里会出现很多以 `data:` 开头的 JSON 行。等待最后的中文总结即可，不需要逐行阅读中间事件。

一次成功演示应同时满足以下条件：

1. 最终回复说明 writer、reader、可选 isolation 沙箱均已创建，且清理成功。
2. writer 沙箱在 EFS 下写入了工作区目录，路径形如 `/mnt/efs/agentkit-code-agent/efs-code-agent-xxxx`。
3. reader 沙箱挂载同一个 `FilespaceName`，读取并执行 writer 写入的 `read_workspace.py`。
4. 如果配置了 `AGENTKIT_EFS_ISOLATION_FILESPACE_NAME`，最终回复应说明另一个 filespace 下同路径不可见。

可进入任一挂载了同一 `FilespaceName` 的沙箱检查目录：

```bash
cd /mnt/efs/agentkit-code-agent/<run_id>
ls
```

应看到这些文件：

```text
activity.log  metadata.json  read_workspace.py  report.md  task.txt
```

也可以手动执行 reader 校验脚本：

```bash
python3 read_workspace.py "$(python3 -c 'import json; print(json.load(open("metadata.json"))["task_sha256"])')"
```

如果输出以 `EFS_SHARED_RUN_RESULT=` 开头，说明共享目录、报告文件和校验脚本均可从当前沙箱访问。

## AgentKit 部署

```bash
cd python/01-tutorials/04-agentkit-tools/efs_code_workspace_agent

agentkit config \
  --agent_name efs_code_workspace_agent \
  --entry_point agent.py \
  --runtime_envs AGENTKIT_TOOL_ID={{your_tool_id}} \
  --runtime_envs AGENTKIT_EFS_FILESPACE_NAME={{your_filespace_name}} \
  --runtime_envs AGENTKIT_EFS_ISOLATION_FILESPACE_NAME={{optional_other_filespace_name}} \
  --runtime_envs AGENTKIT_EFS_LOCAL_MOUNT_PATH=/mnt/efs/ \
  --launch_type cloud

agentkit launch
```

部署后可用 CLI 调用：

```bash
agentkit invoke '请完整演示一次 EFS 代码工作区链路'
```

## 示例提示词

- 请完整演示一次 EFS 代码工作区链路
- 创建 A/B 两个带 EFS 的沙箱，验证同一个 FilespaceName 下目录和脚本可以跨实例访问
- 生成一份代码审查任务报告，保存到 EFS 工作区，并让另一个沙箱实例运行这个目录下的校验脚本
- 使用第二个 filespace 做同路径不可见的隔离验证

## 效果展示

工具成功时会返回结构化结果，重点字段如下：

| 字段 | 含义 |
| --- | --- |
| ok | 是否执行成功 |
| run_id | 本次演示共用的运行 ID，也作为 EFS 工作区目录名的一部分 |
| efs_mount_config | 本次传给 CreateSession 的 EFS 挂载配置 |
| workspace | 智能体写入 EFS 的工作区目录 |
| writer_session.session_id | 写入 EFS 文件的 A Session ID |
| reader_session.session_id | 读取并执行共享脚本的 B Session ID |
| isolation_session.session_id | 可选的隔离校验 Session ID |
| created_artifact.report_file | 首次执行写入的报告文件 |
| created_artifact.reader_file | writer Session 写入、reader Session 执行的校验脚本 |
| verification.executed_file | reader Session 实际执行到的共享脚本路径 |
| verification.report_preview | reader Session 读取到的报告内容预览 |
| verification.verified_by_exit_code | ViewAsyncCommand 未回填 stdout marker 时，通过 ExitCode=0 确认执行成功 |
| verification.marker_missing | 为 true 时表示 stdout marker 未采集到，但不代表 reader 执行失败 |
| isolation_check | 未配置第二个 filespace 时为 skipped；配置后返回同路径不可见的校验结果 |
| async_tasks | writer、reader、isolation 的异步命令 TaskId |
| cleanup | 是否在验证后删除 Session |

## 常见问题

**Q：为什么必须使用 EFS？**

A：普通沙箱本地磁盘适合单次执行；EFS 适合把代码智能体的中间产物、报告、缓存或检查结果沉淀到共享文件系统中，让不同 Sandbox Session 挂载同一个 `FilespaceName` 后继续访问。

**Q：为什么不用 VeADK 内置 run_code 工具？**

A：本示例关注 CreateSession 的 EFS 参数、跨实例共享和 filespace 隔离，所以用自定义工具显式创建多个带 EFS 的 Session，再调用异步命令接口验证 EFS。普通代码执行场景仍可以使用 run_code。

**Q：可以保留 Session 不删除吗？**

A：可以。工具参数 cleanup 默认为 true；如果要排查现场，可让 Agent 调用工具时设置 cleanup=false。保留 Session 会继续占用资源，请排查后手动清理。

**Q：为什么 `client.py` 看起来一直在刷 `data:`？**

A：这是 SSE 流式事件。中间会包含模型思考、工具调用和工具结果片段，属于正常现象。以最终中文总结为准；成功时会明确写出 writer、reader、可选 isolation 的 Session ID、工作区路径、共享结论和清理结果。

**Q：为什么工具结果里有 `marker_missing=true`？**

A：部分环境里 ViewAsyncCommand 可能只稳定返回命令状态和 ExitCode，不一定回填完整 stdout。此时只要 `verified_by_exit_code=true` 且最终回复说明 reader 校验通过，就表示 reader 命令已经以退出码 0 完成；可按上面的手动命令进入 EFS 目录再次验证 `read_workspace.py`。

**Q：CreateSession 报 `LocalMountPath must end with "/"` 怎么办？**

A：确认 `.env` 或部署参数中 `AGENTKIT_EFS_LOCAL_MOUNT_PATH=/mnt/efs/`，末尾的 `/` 必须保留。修改后重启 `agent.py` 再重新运行 `client.py`。

## 代码许可

本工程遵循 Apache 2.0 License。
