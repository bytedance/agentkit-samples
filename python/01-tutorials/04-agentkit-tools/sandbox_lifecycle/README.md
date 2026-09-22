# 沙箱实例 (Session) 生命周期脚本

本目录包含六个脚本，覆盖 Session 的创建、查询、调用、暂停、恢复和删除。
其中 `02_list_and_get_session.py` 是只读查询脚本。脚本使用 AgentKit SDK 的
`agentkit.sdk.tools` 客户端，不会保存 AK/SK。带签名的 endpoint 中如果包含
`Authorization` 查询参数，脚本会在输出或保存状态前自动脱敏。

`PauseSession` / `ResumeSession` 用于暂停和恢复同一个 Session。

英文说明请参阅 [README_en.md](README_en.md)。

## 安装依赖

需要 Python 3.10 或更高版本。本示例固定使用 `agentkit-sdk-python==0.8.7`，
该版本包含 `PauseSession` / `ResumeSession` 接口。在仓库根目录安装：

```bash
pip install -r python/01-tutorials/04-agentkit-tools/sandbox_lifecycle/requirements.txt
```

## 环境变量

根据沙箱所在云平台，选择下面一组配置。六个脚本共用同一套凭证和区域配置。

**火山引擎：**

```bash
export AGENTKIT_CLOUD_PROVIDER=volcengine
export VOLCENGINE_ACCESS_KEY="<Your Access Key>"
export VOLCENGINE_SECRET_KEY="<Your Secret Key>"
export VOLCENGINE_REGION=cn-beijing
export AGENTKIT_TOOL_ID=t-xxxxxxxx
```

**BytePlus：**

```bash
export AGENTKIT_CLOUD_PROVIDER=byteplus
export BYTEPLUS_ACCESS_KEY="<Your Access Key>"
export BYTEPLUS_SECRET_KEY="<Your Secret Key>"
export BYTEPLUS_REGION=ap-southeast-1
export AGENTKIT_TOOL_ID=t-xxxxxxxx
```

Tool ID 必须属于所选云平台、账号和区域。
SDK 会按云平台自动选择服务地址；BytePlus 新加坡区域默认为
`https://agentkit.ap-southeast-1.byteplusapi.com`。
火山引擎的 `InvokeTool` 使用独立的数据面地址
`https://agentkit.<region>.volces.com`，脚本 03 会自动选择该地址。

`AGENTKIT_CLOUD_PROVIDER` 优先于兼容变量 `CLOUD_PROVIDER`；均未设置时沿用 SDK
全局配置中的云平台，未配置则使用火山引擎。火山引擎凭证兼容旧变量名
`VOLC_ACCESSKEY` / `VOLC_SECRETKEY`，BytePlus 使用独立的 `BYTEPLUS_*` 凭证。
使用临时凭证时，还需设置对应的 `VOLCENGINE_SESSION_TOKEN` 或 `BYTEPLUS_SESSION_TOKEN`。

可选配置：

- `AGENTKIT_SESSION_TTL_SECONDS`：脚本 01 创建 Session 时的生命周期，默认
  `28800` 秒（8 小时）；脚本 03 调用和脚本 05 恢复时不传入 TTL。
- `AGENTKIT_USER_SESSION_ID`：仅供脚本 01 使用的逻辑会话 ID；未指定时自动生成。
- `AGENTKIT_SESSION_ID`：仅供脚本 02 使用的实例 ID，优先于状态文件中的 `instance_id`。
- `AGENTKIT_INVOKE_CODE`：脚本 03 执行的 Python 代码，默认
  `print('Hello from AgentKit sandbox!')`。
- `AGENTKIT_INVOKE_TIMEOUT_SECONDS`：脚本 03 的代码执行超时，默认 30 秒，必须为正整数。
- `AGENTKIT_INVOKE_KERNEL_NAME`：脚本 03 使用的内核，默认 `python3`。
- `AGENTKIT_SANDBOX_TOOL_ID`：`AGENTKIT_TOOL_ID` 的兼容变量；同时设置时，两者必须一致。
- `AGENTKIT_LIFECYCLE_STATE`：共享状态文件路径；默认是脚本所在目录中的
  `.sandbox_state.json`，不是运行命令时所在的目录。查询脚本只读取该文件。
- `AGENTKIT_WAIT_TIMEOUT_SECONDS`：创建、暂停和恢复时的状态等待超时，默认 600 秒；
  删除脚本不轮询删除状态。
- `AGENTKIT_POLL_INTERVAL_SECONDS`：状态轮询间隔，默认 5 秒。
- `BYTEPLUS_AGENTKIT_REGION`（BytePlus）或 `VOLCENGINE_AGENTKIT_REGION`（火山引擎）：
  当前云平台的 AgentKit 区域，优先于通用覆盖变量 `AGENTKIT_REGION`；均未设置时，
  由 SDK 按 `BYTEPLUS_REGION` / `VOLCENGINE_REGION`、全局配置及默认区域解析。
- `BYTEPLUS_AGENTKIT_HOST` 或 `VOLCENGINE_AGENTKIT_HOST`：可选的当前云平台服务域名
  覆盖，仅填写主机名，不含 `https://`；通常无需设置。脚本 03 也会遵循该覆盖，
  所填地址必须支持 `InvokeTool`，不能为其配置火山引擎通用 OpenAPI 域名。

切换云平台或区域时，请同步更换 Tool ID，并通过 `AGENTKIT_LIFECYCLE_STATE` 指定
不同的状态文件。生命周期操作从脚本 01 开始；查询已有 Session 无需创建新实例。

## 查询 Session 列表与详情

`02_list_and_get_session.py` 分页调用 `ListSessions`，输出当前 Tool 下的全部 Session，
再调用 `GetSession` 查询指定实例的详情。脚本只读取云端资源和本地状态，不修改状态文件。

在仓库根目录运行：

```bash
pip install -r python/01-tutorials/04-agentkit-tools/sandbox_lifecycle/requirements.txt
python python/01-tutorials/04-agentkit-tools/sandbox_lifecycle/02_list_and_get_session.py
```

默认读取本目录状态文件中的 `tool_id` 和 `instance_id`，也支持
`AGENTKIT_LIFECYCLE_STATE` 指定状态文件。可以在创建、暂停或恢复 Session 后执行。

也可以通过环境变量指定查询目标，无需先运行创建脚本：

```bash
export AGENTKIT_TOOL_ID=t-xxxxxxxx
export AGENTKIT_SESSION_ID="<SessionId>"
python python/01-tutorials/04-agentkit-tools/sandbox_lifecycle/02_list_and_get_session.py
```

`AGENTKIT_SESSION_ID` 优先于状态文件中的 `instance_id`，填写 API 返回的实例
`SessionId`，不是逻辑会话 `UserSessionId`。Tool ID 沿用环境变量与状态文件的一致性检查。
如果没有指定实例 ID，且状态文件中也没有 `instance_id`，则只列出 Session，
输出中的 `session` 为 `null`。空列表正常输出，`GetSession` 返回的 API 错误会直接报告。
列表和详情中的带签名 endpoint 都会自动脱敏。

## 调用 Session 执行代码

`03_invoke_session.py` 通过 [InvokeTool](https://docs.volcengine.com/docs/AgentKit/InvokeTool-Executescommandinatool?lang=zh)
在状态文件记录的沙箱实例中执行 Python 代码。请先运行脚本 01 创建实例，
并确保实例已就绪；暂停后应先运行脚本 05 恢复，再调用脚本 03。
沙箱镜像需要支持 `RunCode` 对应的 `/v1/jupyter/execute` 接口和所选 Python 内核。

请求传入 `ToolId`、状态中的 `instance_id`（作为 `SessionId`）、
`OperationType="RunCode"`，以及 JSON 字符串形式的 `OperationPayload`，
其中包含 `code`、`timeout` 和 `kernel_name`。本示例显式传入已有 `SessionId`，
并校验返回的实例 ID 一致；不通过 `UserSessionId` 查找或创建新实例。

在仓库根目录运行，也可以自定义要执行的代码：

```bash
export AGENTKIT_INVOKE_CODE="print(sum([1, 2, 3]))"
python python/01-tutorials/04-agentkit-tools/sandbox_lifecycle/03_invoke_session.py
```

脚本保存 `invoked_at`、`invoke_response` 和 `invoke_result`，并将返回的 `Result`
JSON 字符串解析为可读结果；标准输出通常位于 `invoke_result.data.outputs`。
API 错误直接报告；代码执行结果中的 `success: false` 或 `data.status: error`
会在保存和打印结果后报错退出。

SDK 0.8.7 尚未提供 `InvokeTool` 专用方法，因此脚本补充该 Action 的注册，
复用 SDK 的签名、凭证刷新和 API 错误处理，无需升级依赖。

## 脚本与运行顺序

六个脚本的作用如下：

| 脚本 | 作用 |
| --- | --- |
| `01_create_session.py` | 创建 Session，默认 TTL 为 8 小时；等待就绪并保存实例 ID。 |
| `02_list_and_get_session.py` | 分页列出 Session，查询指定实例详情；只读操作。 |
| `03_invoke_session.py` | 通过 `InvokeTool` 在已有 Session 中执行 Python 代码，校验实例 ID 并保存执行结果。 |
| `04_pause_session.py` | 暂停状态文件中的 Session，等待 `Paused` 并记录 `paused_at`。 |
| `05_resume_session.py` | 要求状态文件中有 `paused_at`，恢复同一个 Session，校验实例 ID 不变并等待就绪。 |
| `06_delete_session.py` | 根据 Tool ID 和状态中的 `instance_id` 调用 `DeleteSession` 并保存响应，不等待后台删除完成。 |

验证调用、暂停和恢复时，按 **01 → 02 → 03 → 04 → 05 → 02 → 03** 执行：
先创建、查询和调用，再暂停、恢复，最后查询并再次调用恢复后的实例。
脚本 06 是删除操作，放在完成验证后清理资源时使用。

在仓库根目录执行：

```bash
python python/01-tutorials/04-agentkit-tools/sandbox_lifecycle/01_create_session.py
python python/01-tutorials/04-agentkit-tools/sandbox_lifecycle/02_list_and_get_session.py
python python/01-tutorials/04-agentkit-tools/sandbox_lifecycle/03_invoke_session.py
python python/01-tutorials/04-agentkit-tools/sandbox_lifecycle/04_pause_session.py
python python/01-tutorials/04-agentkit-tools/sandbox_lifecycle/05_resume_session.py
python python/01-tutorials/04-agentkit-tools/sandbox_lifecycle/02_list_and_get_session.py
python python/01-tutorials/04-agentkit-tools/sandbox_lifecycle/03_invoke_session.py
```

执行以下命令清理状态文件记录的实例：

```bash
python python/01-tutorials/04-agentkit-tools/sandbox_lifecycle/06_delete_session.py
```

## 状态文件

默认状态文件是本目录下的 `.sandbox_state.json`，保存 `tool_id`、
`user_session_id`、`instance_id`、生命周期时间和 API 响应。脚本 01、03、04、05、06
会写入状态，脚本 02 只读取。该文件名已被仓库根目录的 `.gitignore` 忽略；
通过 `AGENTKIT_LIFECYCLE_STATE` 使用其他文件名时，是否忽略取决于对应路径的 Git 规则。

脚本 03、04、05、06 根据状态文件中的 `instance_id` 操作实例，不读取
`AGENTKIT_USER_SESSION_ID` 或 `AGENTKIT_SESSION_ID` 来选择目标。

重复运行脚本 01 且不指定 `AGENTKIT_USER_SESSION_ID` 时，会生成新的逻辑会话 ID、
创建新的沙箱实例并覆盖状态文件；之前创建的实例不会被自动删除。
