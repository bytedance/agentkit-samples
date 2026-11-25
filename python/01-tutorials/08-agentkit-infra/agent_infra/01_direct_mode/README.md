# 01 Direct模式：Harness App 直连

Direct 模式采用手脑分离架构：Agent 在 AgentKit Runtime 中完成模型推理和任务编排，通过远程调用让 Sandbox 执行文件读写、命令等操作，再根据工具结果继续对话。Sandbox 接通业务 VPC 后，可访问内网服务和数据。

本例采用 Direct 调用方式，客户端直接访问 Runtime 的 Harness App。操作顺序为：**准备配置 → 创建资源 → 运行 Direct 模式 → 清理资源**。

```text
调用者
    │ 创建会话、调用 /run_sse
    ▼
AgentKit Runtime(VPC)
    └── Agent / Harness：模型推理、任务编排
      │ 远程工具调用      ▲ 执行结果返回
      ▼                 │
        Cloud Sandbox(VPC)
                  │
                  ▼
      业务 VPC：业务服务、数据
```

## 进入项目并配置 uv

从仓库根目录执行。后面的命令均在 `01_direct_mode/` 中运行：

```bash
cd python/01-tutorials/08-agentkit-infra/agent_infra/01_direct_mode
uv venv --python 3.12
source .venv/bin/activate
uv pip install -r ../requirements.txt --default-index https://mirrors.aliyun.com/pypi/simple/

test -f ../config.yaml ||
  install -m 600 ../config.yaml.example ../config.yaml
```

编辑 `agent_infra/` 下的 `../config.yaml`：

- `volcengine`：填写账号 AK/SK 和地域。AK/SK 留空时读取 `HARNESS_INFRA_ACCESS_KEY`、`HARNESS_INFRA_SECRET_KEY`。
- `workspace_id`：填写目标 Workspace；留空时使用服务端默认 Workspace。
- `harness.model`：填写方舟模型 ID 和模型地址。本例通过 Runtime 执行角色访问模型，`api_key_name` 可留空。
- `harness.agent_loop`：使用 `adk`；`harness.system_prompt` 填写 Agent 的系统提示词。
- `runtime_template`：填写 Runtime 镜像、执行角色和规格；`environment.resources` 配置 Cloud Sandbox 的 CPU 和内存规格。
- `environment.apig_gateway_id`：账号没有 Endpoint 时填写，用于 `CreateRoute`；已有多个 Endpoint 时，用 `environment.endpoint_id` 指定要复用的就绪 Endpoint。
模型、MCP、Skill 都在 `harness` 下配置，见[共享配置说明](../README.md#agent-能力)。Direct 将它们转换为 Harness App 的 Runtime 环境变量；模型 Key 可用 `harness.model.api_key: "${MODEL_API_KEY}"`，也可留空通过 Runtime IAM 获取。`api_key_name` 非空时使用命名 Key（当前 IAM 取 Key 实现使用 `default` 方舟项目）。

`harness.mcp_servers` 支持远程 `streamable-http` / `sse`，可选 `api_key` 作为 Bearer。`harness.skills` 只在本模式生效，接受 Hub/Space 字符串引用；ZIP 来源对象不受支持。需要选用包含 MCP、Skill 加载能力的 Harness App 镜像，并在实际调用中确认能力可用。

## 逐步创建资源

将 `harness.tools` 中 `agent_toolset_20260401` 的 `DefaultConfig.Enabled` 改为 `true`，开启文件和命令工具，保留模板中的其他工具配置：

```yaml
DefaultConfig:
  Enabled: true
  PermissionPolicy:
    Type: "always_allow"
```

Runtime 镜像需提供 `veadk.cloud.harness_app.server` 的 Harness App，支持会话绑定，并通过 Runtime KeyAuth 调用。选择未启用 Harness Identity 的镜像，Identity 模式暂不支持本例的三 ID 会话绑定。Cloud Sandbox 需支持 AIO Sandbox 接口；Runtime 执行角色需具备模型调用、读取 Harness / Environment 配置和管理工具实例的权限。

本例暂不透传 `environment.network` 和 `runtime_template.network`。如需访问业务 VPC，须在平台完成对应 Sandbox 的网络接入和访问权限配置。

## 创建资源

按顺序执行以下五步。每步都可加 `--dry-run` 查看计划，不读取配置、不访问网络。实际执行会创建计费资源。

### 1. CreateRoute

```bash
python run.py create-route
```

已有 Endpoint 时复用；有多个时设置 `route.endpoint_id`，没有时设置 `route.apig_gateway_id` 后调用 `CreateRoute`。Direct 会话走 Runtime Endpoint，因此可以跳过这一步。

### 2. CreateEnvironment（Cloud）

```bash
python run.py create-environment
```

创建 Cloud Environment，等待 Environment 为 `Active`、Sandbox 为 `Ready`，保存 Sandbox 的 `ToolId`。

`run.py` 发送 `Config.Type=Cloud` 的环境创建命令。

### 3. CreateHarness

```bash
python run.py create-harness
```

保存模型、系统提示词和工具配置，取得 `HarnessId`，供运行 Direct 模式时绑定会话。

### 4. CreateSessionStore

```bash
python run.py create-session-store
```

创建 `SERVERLESS_PG` 类型的 SessionStore，等待 `Ready`，保存 `SessionStoreId`。

### 5. CreateRuntimeTemplate

```bash
python run.py create-runtime-template
```

准备 IAM 执行角色，使用 `SessionStoreId` 和 Sandbox `ToolId` 创建 Runtime，再通过 `GetRuntime` 等待 `Ready`。

五步完成后，继续下一节。资源 ID 保存在 `../.local/direct/resources.json`；Runtime 的 Endpoint 和调用凭证由脚本读取，无需手动复制。

## 运行 Direct 模式

### 1. 创建会话

```bash
python run.py create-session
```

向 Runtime 创建会话，将 `workspaceId`、`harnessId` 和 `environmentId` 作为顶层字段传入，遵循 ADK 的驼峰命名规范。服务端加载 Harness 和 Environment 配置，并绑定到当前 Session。

### 2. 调用 run_sse

```bash
python run.py run-sse --prompt "请只回复 CLOUD_OK"
python run.py run-sse --prompt "上一轮我要求你回复什么？只输出那个标记。"
```

两次调用向 Runtime 的 `/run_sse` 发送消息，复用同一 Session，流式返回 Agent 回复。两轮均应返回 `CLOUD_OK`，用于检查基础对话和上下文记忆。

### 3. 验证远程工具执行

```bash
# 在远端沙箱执行命令
python run.py run-sse --prompt '请在沙箱中执行 echo CLOUD_SANDBOX_OK，只回复真实命令输出。'

# 在远端沙箱写入并读取文件
python run.py run-sse --prompt '请在沙箱的 /tmp/cloud-demo.txt 写入 CLOUD_FILE_OK，然后读取该文件，只回复读取到的内容。'
```

检查 SSE 中的 `functionCall` 和 `functionResponse`，确认工具执行成功，且工具结果包含对应的 `CLOUD_SANDBOX_OK` 或 `CLOUD_FILE_OK`。这些操作发生在远端 Sandbox，验证时以工具返回结果为准。

完成业务 VPC 网络接入后，可继续发送“请在沙箱中访问 `<业务服务健康检查地址>`，返回实际状态码和响应内容”，检查内网访问。

## MCP 与 Skill 使用

在创建 Runtime 前填写 `harness.mcp_servers` 和 `harness.skills`，具体格式及环境变量设置见[共享使用说明](../README.md#mcp-与-skill-验证命令)。资源和会话就绪后，在本目录执行：

```bash
python run.py run-sse --prompt "请实际调用已配置的 docs MCP 的一个只读工具，给出工具名称和真实返回结果。"
python run.py run-sse --prompt "请加载并遵循 your-skill-hub-slug 技能，完成该技能支持的一项任务，说明你读取的技能说明和实际执行结果。"
```

替换 `docs`、`your-skill-hub-slug` 及任务描述为实际配置。核对 SSE 中的工具调用与结果，通过 Runtime 日志或实际读取的技能文件确认 Skill 加载成功。修改配置后先执行下面的清理命令，再重新创建 Environment、SessionStore、Runtime 和 Session。

## 清理资源

```bash
python run.py cleanup --dry-run
python run.py cleanup
```

脚本按依赖顺序删除 Session、Runtime、SessionStore、Cloud Sandbox 和 Environment，并归档 Harness。共享 Route 和 IAM 角色保留。

创建或清理中断后，保留 `../.local/direct/resources.json`，修复问题后重新执行清理命令。
