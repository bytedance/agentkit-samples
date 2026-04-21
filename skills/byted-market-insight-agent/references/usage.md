# 使用与集成指南

本指南说明了如何与 `byted-market-insight-agent` Skill 交互，包括统一的接口参数、返回结构、最小化询问的触发条件以及持久化状态文件的字段含义。

## 统一接口与返回结构

无论底层使用 Gateway 还是 SDK，Skill 对外暴露的三个核心函数 (`scripts/client.py`) 始终保持一致的签名和返回结构。所有函数参数和返回值的键名均采用 `PascalCase`。

### 1. `list_custom_subs_task`

查询订阅/监控任务列表。

-   **调用参数**:
    -   `Status` (int, optional): 任务状态过滤。`1`=运行中, `2`=全部状态。默认 `2`。
    -   `TaskName` (str, optional): 按任务名称模糊搜索。默认不过滤。
    -   `PageNum` (int, optional): 页码，从 1 开始。默认 `1`。
    -   `PageSize` (int, optional): 每页条数。默认 `30`。

-   **返回结构**: `Dict[str, Any]`
    ```json
    {
      "InsightSaasTaskList": [
        {
          "TaskID": "1509",
          "Name": "某品牌声量监测",
          "Aim": "...",
          "Status": "1",
          "CreateTime": "1722409980",
          "...": "..."
        }
      ],
      "Total": 1
    }
    ```
    -   `InsightSaasTaskList` (list): 任务对象列表。
    -   `Total` (int): 符合条件的总任务数。

### 2. `pull_post`

拉取指定监测任务的 AI 精筛数据。

-   **调用参数**:
    -   `TaskID` (int, required): 监测任务 ID。
    -   `StartTime` (str, required): 数据起始时间，格式 `"YYYY-MM-DD HH:MM:SS"`。
    -   `EndTime` (str, required): 数据结束时间，格式 `"YYYY-MM-DD HH:MM:SS"`。
    -   `Size` (int, optional): 每页条数。默认 `50`。
    -   `PageToken` (str, optional): 分页游标，首次调用不传，后续从上一次响应中获取。

-   **返回结构**: `Dict[str, Any]`
    ```json
    {
      "ItemDocs": [
        {
          "PostID": "...",
          "Title": "...",
          "Summary": "...",
          "URL": "...",
          "Emotion": "positive",
          "...": "..."
        }
      ],
      "HasMore": true,
      "NextPageToken": "xxx-yyy-zzz"
    }
    ```
    -   `ItemDocs` (list): 数据对象列表。
    -   `HasMore` (bool): 是否还有更多数据可供拉取。
    -   `NextPageToken` (str | None): 下一页的游标。如果为 `None` 或不存在，表示已是最后一页。

### 3. `query_clue_info`

查询 AI 生成的商机信息。

-   **调用参数**:
    -   `StartTime` (str, required): 数据起始时间，格式 `"YYYY-MM-DD HH:MM:SS"`。
    -   `EndTime` (str, required): 数据结束时间，格式 `"YYYY-MM-DD HH:MM:SS"`。
    -   `MaxResults` (int, optional): 每页最大返回条数。默认 `10`。
    -   `NextToken` (str, optional): 分页游标，首次调用不传。

-   **返回结构**: `Dict[str, Any]`
    ```json
    {
      "ClueList": [
        {
          "ClueID": "...",
          "CreateTime": "...",
          "ClueText": {
            "opportunity_briefing": { "title": "...", "priority_level": "P2", "...": "..." },
            "company_profile": { "legal_name": "...", "...": "..." },
            "acorn_assessment": { "...": "..." },
            "...": "..."
          }
        }
      ],
      "NextToken": "1722409980123",
      "ResultCnt": 1
    }
    ```
    -   `ClueList` (list): 商机对象列表。注意 `ClueText` 字段已被自动解析为结构化 JSON 对象。
    -   `NextToken` (str | None): 下一页的游标。
    -   `ResultCnt` (int): 当前返回的商机数量。

## 最小化询问触发条件

Skill 自身不会直接与最终用户交互。当需要凭证时，它会抛出 `MissingCredentialsError` 异常，并附带明确的提示信息，交由调用方（例如 Agent）来决定如何处理。

**触发条件**：

-   在初次调用时，环境变量 (`ARK_*` 和 `VOLCSTACK_*`) 和持久化的 `persist/auth.json` 文件中均未找到任何有效的凭证。
-   已有的两套凭证（Gateway 和 SDK）都已因连续的 `AuthError` (401/403) 而被标记为“降级”状态。

**异常提示信息示例** (由 `auth_resolver.MINIMAL_ASK_HINT` 定义):

```
当前缺少可用的市场洞察访问凭证。
Agent 层应调用 ask_user，引导用户择一提供：
1) API Gateway 地址 + API Key (ARK_SKILL_API_BASE / ARK_SKILL_API_KEY)，或
2) 官方 AK/SK (VOLCSTACK_ACCESS_KEY_ID / VOLCSTACK_SECRET_ACCESS_KEY)。
一套凭证即可，Skill 会自动选择最合适的链路，并在本地持久化，后续会话复用。
```

当 Agent 捕获到此异常时，应向用户展示一个表单或通过对话引导用户提供上述凭证。获取后，Agent 应调用 `auth_resolver` 中的 `save_auth_gateway` 或 `save_auth_sdk` 方法将凭证持久化，然后再次尝试调用 `client.py` 中的函数。

## 持久化状态文件说明

Skill 会在 `persist/` 目录下创建两个 JSON 文件来维护状态和凭证。

### 1. `state.json`

记录 Skill 的运行时状态，用于实现会话粘性和动态决策。

-   **`provider`**: (str | null) 上一次成功使用的 Provider 名称，值为 `"gateway"` 或 `"sdk"`。用于实现会话粘性。
-   **`degraded`**: (dict) 记录每个 Provider 是否处于“降级”状态。
    -   `"gateway": true` 表示 Gateway 链路近期连续失败，应暂时避免使用。
    -   `"sdk": true` 表示 SDK 链路近期连续失败。
-   **`sdk_installed`**: (bool) 标记 `volcengine-python-sdk` 是否已在当前环境中成功安装。`true` 表示已安装，可以跳过安装检查。
-   **`sdk_install_failed`**: (bool) 标记 SDK 自动安装是否已失败过。`true` 表示安装失败，后续不再尝试自动安装，避免反复卡顿。
-   **`last_success_at`**: (float | null) 最近一次成功调用的 Unix 时间戳。可用于实现更复杂的状态过期逻辑。
-   **`last_error`**: (dict | null) 最近一次错误的摘要信息，包含 Provider 名称、错误类型和消息，用于调试。

### 2. `auth.json`

存储由“最小化询问”流程获取的用户凭证。**注意：环境变量中设置的凭证优先级高于此文件。**

-   **`gateway`**: (dict)
    -   `"api_base"`: (str) API Gateway 的基础 URL。
    -   `"api_key"`: (str) API Key (Bearer Token)。
-   **`sdk`**: (dict)
    -   `"access_key_id"`: (str) 官方 Access Key ID。
    -   `"secret_access_key"`: (str) 官方 Secret Access Key。
    -   `"region"`: (str) 服务区域，例如 `"cn-beijing"`。


## 环境变量来源与排查

为了减少对用户的打扰，本 Skill 会尽量“自己把凭证找全”，实际读取与决策的顺序为：

1.  **Shell 配置文件扫描 (rc)**：启动时首先扫描常见 rc 文件（`~/.bashrc`、`~/.bash_profile`、`~/.zshrc`、`~/.profile`）中的简单 `export ARK_*/VOLCSTACK_*` 行，只读解析出 Gateway 与 SDK 的候选凭证；
2.  **进程环境变量 (`os.environ`)**：默认假设用户已经在环境变量中配置了凭证，如果当前进程环境中存在 `ARK_*` / `VOLCSTACK_*`，则视为“已生效”的配置，**会覆盖前面从 rc 中收集到的同名候选值**；
3.  **持久化凭证文件 (`persist/auth.json`)**：当环境变量中仍缺少成对凭证时，Skill 会再尝试从该文件中读取由“最小化询问”流程保存的 Gateway / SDK 凭证，用于补全；
4.  如果上述三处都无法提供任意一套完整的 Gateway 或 SDK 凭证，才会抛出 `MissingCredentialsError`，交给 Agent 层向用户发起最小化询问。

顺序可以概括为：**先扫描 rc → 再读取 os.environ（若已生效覆盖候选）→ 再读 persist/auth.json → 最后触发最小化询问**。

在实现上，对 rc 文件的处理始终是安全、只读的：

- 只解析形如 `export VAR=VALUE` 的简单常量行，不执行 `source`，不会展开包含 `$`、`` ` ``、`$(` 等符号的表达式（此类行会被跳过）；
- 仅关注以下变量：`ARK_SKILL_API_BASE`、`ARK_SKILL_API_KEY`、`VOLCSTACK_ACCESS_KEY_ID`、`VOLCSTACK_SECRET_ACCESS_KEY`、`VOLCSTACK_REGION`；
- 解析成功的值只在内存中生效，不会写回 `auth.json`，日志中也不会打印明文凭证，只输出脱敏后的摘要信息。

### 常见定义位置

- **交互式终端或启动脚本**：`export ARK_SKILL_API_BASE=...`
- **用户 Home 目录下的配置文件**：`~/.bashrc`、`~/.bash_profile`、`~/.zshrc`、`~/.profile`。
- **平台或容器注入**：在启动命令前通过 `export ... && python ...` 注入。

### 如何自查

1.  **检查当前进程环境是否生效**：
    ```bash
    # 查看单个变量
    echo $ARK_SKILL_API_BASE

    # 在所有环境变量中搜索
    env | grep ARK_SKILL_API_BASE
    ```

2.  **在配置文件中搜索定义**：
    ```bash
    # 在常见 rc 文件中搜索 export 语句，忽略不存在的文件错误
    grep -n "^export ARK_SKILL_API_BASE" ~/.bashrc ~/.bash_profile ~/.zshrc ~/.profile 2>/dev/null
    ```

### 重要提示

- 在绝大多数情况下，只要你在 rc 文件或启动命令中正确写了 `export ARK_*` / `VOLCSTACK_*`，Skill 就能通过“先扫描 rc、再读取环境变量、再看 auth.json”的顺序自动找到并采用合适的凭证，无需你在对话中重复说明“已经配在环境变量里了”。
- 当两套凭证（Gateway 与 SDK）在环境变量、`auth.json` 和 rc 文件中都缺失时，Skill 会抛出 `MissingCredentialsError`，并附带在这些 rc 文件中找到的候选凭证提示，帮助你快速定位问题。
