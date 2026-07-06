# 场景管理 (scene)

## 目录

- 列举场景 (list)
- 场景详情 (get)
- 创建场景 (create)
- 场景存储配置 (storage_set)
- 数据导入 (data_import)
- 查看数据列表 (data_list)
- 查看切片列表 (chunks)
- 发布场景 (publish)
- 版本管理 (versions)
- 停止场景 (stop)
- 启动场景 (start)
- 编辑名称 (rename)
- 删除场景 (delete)
- 规格查询 (specs)

## 列举场景 (list)

查询当前账号下已创建的 ContextSearch 场景列表。

- **命令**: `scene list`
- **支持参数**:
    - `--page-number <number>`: 查询的页码，默认为 `1`。
    - `--page-size <size>`: 每页返回的条目数量，默认为 `12`。

**示例：**

```bash
# 配置环境变量
export VOLCENGINE_AK="YOUR_AK"
export VOLCENGINE_SK="YOUR_SK"

# 运行命令
python scripts/contextsearch_cli.py scene list --page-number 1 --page-size 10
```

## 场景详情 (get)

查询单个 ContextSearch 场景的详细信息，内部调用 `ctxsearch` 的 `GetScene` 接口（GET，Version=`2025-09-01`）。

- **命令**: `scene get`
- **支持参数**:
    - `--id <id>`: 场景 Id，必填。
    - `--scene-type <type>`: 场景类型 SceneType，必填，例如 `RAG`。
    - `--project <project>`: Project 名称，可选，默认值为 `default`。
    - `--is-demo`: 是否为 Demo 场景，可选，默认值为 `false`；传入该开关则为 `true`。

**示例：**

```bash
python scripts/contextsearch_cli.py scene get --id 2036358376137789442 --scene-type RAG --project default
```

## 创建场景 (create)

按应用控制台相同的逻辑，在创建场景前会基于场景模板检查并（如有必要）自动部署预置推理服务。普通检索场景内部串联 `ListSceneTemplate`、`CheckBuiltinDeployment`、`DeployBuiltinDeployment` 与 `CreateScene`；AgenticSearch 内部串联 `ListAgenticSceneTemplate`、`CheckBuiltinDeployment`、`DeployBuiltinDeployment` 与 `CreateAgenticScene`。

- **命令**: `scene create`
- **支持参数**:
    - `--scene-type <type>`: 场景类型 SceneType，必填，可选：`RAG`、`IMAGE_SEARCH`、`VIDEO_SEARCH`、`AGENTIC_SEARCH`。
    - `--project <project>`: Project 名称，可选，默认值为 `default`。
    - `--name <name>`: 场景名称，必填。
    - `--description <desc>`: 场景描述，可选，默认空字符串。
    - `--resource-tags <json>`: 自定义资源标签，可选，默认空。格式为 JSON 数组，例如 `'[{"Key":"env","Value":"boe"}]'`，内部会组装为 `ResourceTags: [{Type:"CUSTOM", TagKvs:{k:v}}]`。
    - `--max-attempts <n>`: 部署状态轮询最大次数，可选，默认 `30`，与控制台 AgenticSearch 创建流程一致。
    - `--poll-interval-ms <ms>`: 部署状态轮询间隔（毫秒），可选，默认 `1000`，与控制台 AgenticSearch 创建流程一致。

调用流程如下：

1. 调用模板接口读取 `Items[0].Detail.Models` 作为预置模型列表：
   - 普通检索场景：`ListSceneTemplate`（GET，Version=`2025-09-01`），请求体为 `{PageNumber:1, PageSize:1, SceneType:<scene-type>}`；
   - AgenticSearch：`ListAgenticSceneTemplate`（GET，Version=`2025-09-01`），请求体为 `{PageNumber:1, PageSize:1}`。
2. 若 `Models` 不为空，则调用 `CheckBuiltinDeployment`（POST，Version=`2025-09-01`），请求体为 `{Project:<project>, Models:[{Name: m.ModelName, Version?: m.ModelVersion}]}`，检查这些预置推理服务的部署/授权状态。注意：模板中部分模型没有 `ModelVersion`，仍必须带着 `Name` 参与检查，否则可能漏掉未开通的预置模型。
3. 若返回结果中存在 `Status == "UNPROVISIONED"` 的条目，则先调用 `DeployBuiltinDeployment`（POST，Version=`2025-09-01`），请求体保持与 `CheckBuiltinDeployment` 一致，然后进入轮询阶段：
   - 按 `--max-attempts` 和 `--poll-interval-ms` 配置，循环调用 `CheckBuiltinDeployment`；
   - 当 `Items.every(i => i.InstanceStatus == "RUNNING")` 时视为全部就绪；
   - 若超过最大轮询次数仍未全部就绪，则与控制台一致终止创建，避免在预置推理服务未就绪时继续创建场景。
4. 组装 `ResourceTags`：
   - 若未传入 `--resource-tags`，则默认 `{Type:"CUSTOM", TagKvs:{}}`；
   - 若传入 JSON 数组，则按 `[{Key, Value}]` 规约归并为单个 `TagKvs` 对象。
5. 最终调用创建接口，并将接口响应透传为统一 JSON 输出：
   - 普通检索场景：`CreateScene`（POST，Version=`2025-09-01`），请求体为 `{ResourceTags, SceneType, Project, Name, Description}`；
   - AgenticSearch：`CreateAgenticScene`（POST，Version=`2025-09-01`），请求体为 `{ResourceTags, Project, Name, Description}`，不传 `SceneType`，与控制台创建流程保持一致。

**示例：**

```bash
VOLCENGINE_AK=YOUR_AK VOLCENGINE_SK=YOUR_SK python scripts/contextsearch_cli.py scene create --scene-type RAG --project default --name "jyf-test1" --description "desc" --resource-tags '[{"Key":"env","Value":"boe"}]' --max-attempts 20 --poll-interval-ms 500
```

创建 AgenticSearch：

```bash
VOLCENGINE_AK=YOUR_AK VOLCENGINE_SK=YOUR_SK python scripts/contextsearch_cli.py scene create --scene-type AGENTIC_SEARCH --project default --name "agentic-demo" --description "desc"
```

## 场景存储配置 (storage_set)

为已创建但仍处于可配置阶段（`Status = UNINITIALIZED`）的场景配置存储实例与网络信息。内部串联 `GetScene`、`DescribeInstance` 与 `UpdateScene` 三个接口。

- **命令**: `scene storage_set`
- **支持参数**:
    - `--id <id>`: 场景 Id，必填。
    - `--scene-type <type>`: 场景类型 SceneType，必填，可选：`RAG`、`IMAGE_SEARCH`、`VIDEO_SEARCH`。
    - `--project <project>`: Project 名称，可选，默认值为 `default`。
    - `--instance-type <type>`: 存储实例类型，必填，目前仅支持 `OPENSEARCH`。
    - `--instance-id <id>`: 存储实例 InstanceId，必填。
    - `--username <name>`: 存储实例用户名，必填。
    - `--password <value>`: 存储实例密码，必填。
    - `--is-demo`: 是否为 Demo 场景，可选，默认值为 `false`；传入该开关则为 `true`（用于 `GetScene` 调用）。

调用流程如下：

1. 调用 `GetScene`（GET，Version=`2025-09-01`），请求体为 `{Id, SceneType, Project, IsDemo}`，读取 `Status` 和 `Config.EmbeddingConfig`：
   - 若 `Status != "UNINITIALIZED"`，CLI 会报错：`当前状态不允许配置存储位置（需为 UNINITIALIZED）`；
   - 若未返回有效的 `EmbeddingConfig`，CLI 会报错并终止。
2. 调用 `DescribeInstance`（POST，service=`escloud`，Version=`2023-01-01`），请求体为 `{InstanceId:<instance-id>}`，从 `InstanceInfo.InstanceConfiguration` 中抽取：
   - `VPC`：`VpcId`、`VpcName`；
   - `Subnet`：`Subnet.SubnetId`、`Subnet.SubnetName`，若 `Subnet` 为空则回退到 `SubnetList[0]`；
   - `ZoneId`：可用区 ID；
   若上述任一字段缺失或非法，CLI 会报错并终止。
3. 基于上述信息组装 `UpdateScene`（POST，Version=`2025-09-01`）的请求体，并调用 `ctxsearch` 的 `UpdateScene` 接口写入场景配置：

```json
{
  "Project": "<project>",
  "Id": "<id>",
  "SceneType": "<scene-type>",
  "Config": {
    "StorageConfig": {
      "InstanceId": "<instance-id>",
      "Type": "OPENSEARCH",
      "AuthType": "BASIC",
      "Username": "<username>"
    },
    "NetworkConfig": {
      "VPC": {"VpcId": "...", "VpcName": "..."},
      "Subnets": [{"SubnetId": "...", "SubnetName": "..."}],
      "ZoneIds": ["<zone_id>"]
    },
    "EmbeddingConfig": { 从 `GetScene.Config.EmbeddingConfig` 透传 }
  }
}
```

存储密码字段需要按运行环境提供，避免写入文档示例或命令历史。

实际请求体由 CLI 直接构造原始 Python `dict` 并以 JSON 形式发送，字段名称与上面示意保持一致。

**示例：**

```bash
VOLCENGINE_AK=YOUR_AK VOLCENGINE_SK=YOUR_SK python scripts/contextsearch_cli.py scene storage_set --id 2042492662139453441 --scene-type RAG --project default --instance-type OPENSEARCH --instance-id o-dev-00o8ptglykg8 --username admin --password "$OPENSEARCH_STORAGE_SECRET" --is-demo false
```

## 数据导入 (data_import)

通过 TOS 为指定场景导入数据，内部调用 `ctxsearch` 的 `AddSceneData` 接口（POST，Version=`2025-09-01`）。当前仅支持 TOS 导入，要求 Path 必须以斜杠结尾。

- **命令**: `scene data_import`
- **支持参数**:
    - `--scene-id <id>`: 场景 Id，必填。
    - `--scene-type <type>`: 场景类型 SceneType，必填，可选：`RAG`、`IMAGE_SEARCH`、`VIDEO_SEARCH`。
    - `--project <project>`: Project 名称，可选，默认值为 `default`。
    - `--bucket <bucket>`: TOS Bucket 名称，必填。
    - `--path <path>`: TOS Path，必填，必须以斜杠结尾，例如 `rag/`、`image/`、`video/`。若不以 `/` 结尾，CLI 会直接报错退出。

不同场景类型下，CLI 会自动填充默认的 `IngestConfig` 字段：

- RAG 场景：

  ```json
  {
    "SceneId": "<scene-id>",
    "Project": "<project>",
    "Type": "TOS",
    "SceneType": "RAG",
    "IngestConfig": {
      "EnabledAsrConfig": "false",
      "EnabledLlmConfig": "false",
      "EnabledOcrConfig": "false",
      "Prompt": "",
      "MaxChunkDuration": 30,
      "SceneType": "RAG"
    },
    "TosConfig": {
      "Bucket": "<bucket>",
      "Path": "<path>"
    }
  }
  ```

- IMAGE_SEARCH 场景（图搜），额外包含 `CustomContent: {}`：

  ```json
  {
    "SceneId": "<scene-id>",
    "Project": "<project>",
    "Type": "TOS",
    "SceneType": "IMAGE_SEARCH",
    "IngestConfig": {
      "EnabledAsrConfig": "false",
      "EnabledLlmConfig": "false",
      "EnabledOcrConfig": "false",
      "Prompt": "描述图片内容",
      "MaxChunkDuration": 30,
      "SceneType": "IMAGE_SEARCH"
    },
    "CustomContent": {},
    "TosConfig": {
      "Bucket": "<bucket>",
      "Path": "<path>"
    }
  }
  ```

- VIDEO_SEARCH 场景（视频搜索）：

  ```json
  {
    "SceneId": "<scene-id>",
    "Project": "<project>",
    "Type": "TOS",
    "SceneType": "VIDEO_SEARCH",
    "IngestConfig": {
      "EnabledAsrConfig": "false",
      "EnabledLlmConfig": "false",
      "EnabledOcrConfig": "false",
      "Prompt": "Summarize the video content",
      "SceneType": "VIDEO_SEARCH"
    },
    "TosConfig": {
      "Bucket": "<bucket>",
      "Path": "<path>"
    }
  }
  ```

**示例：**

```bash
VOLCENGINE_AK=YOUR_AK VOLCENGINE_SK=YOUR_SK python scripts/contextsearch_cli.py scene data_import --scene-id 2042490062736326658 --scene-type RAG --project default --bucket jyf-test2 --path rag/
```

## 查看数据列表 (data_list)

查看指定场景下的数据导入记录列表，内部调用 `ctxsearch` 的 `ListSceneData` 接口（GET，Version=`2025-09-01`）。

- **命令**: `scene data_list`
- **支持参数**:
    - `--scene-id <id>`: 场景 Id，必填。
    - `--scene-type <type>`: 场景类型 SceneType，必填，可选：`RAG`、`IMAGE_SEARCH`、`VIDEO_SEARCH`。
    - `--project <project>`: Project 名称，可选，默认值为 `default`。
    - `--page-number <number>`: 页码，可选，默认 `1`。
    - `--page-size <size>`: 每页条数，可选，默认 `10`。

请求体示例（固定字段由 CLI 自动补全）：

```plain
Project=default&SceneId=2042490062736326658&SceneType=RAG&PageNumber=1&PageSize=10&WithImageData=false&NameKey=&IsDemo=false
```

其中：

- `WithImageData`: 固定为 `false`。
- `NameKey`: 固定为空字符串 `""`。
- `IsDemo`: 固定为 `false`。

**示例：**

```bash
VOLCENGINE_AK=YOUR_AK VOLCENGINE_SK=YOUR_SK python scripts/contextsearch_cli.py scene data_list --scene-id 2042490062736326658 --scene-type RAG --project default --page-number 1 --page-size 10
```

## 查看切片列表 (chunks)

查看指定场景下的数据切片列表，内部调用 `ctxsearch` 的 `ListSceneDataChunk` 接口（GET，Version=`2025-09-01`）。

- **命令**: `scene chunks`
- **支持参数**:
    - `--scene-id <id>`: 场景 Id，必填。
    - `--scene-type <type>`: 场景类型 SceneType，必填，可选：`RAG`、`IMAGE_SEARCH`、`VIDEO_SEARCH`。
    - `--project <project>`: Project 名称，可选，默认值为 `default`。
    - `--data-id <id>`: 数据 Id，可选，默认空字符串（不按数据 Id 过滤）。
    - `--page-number <number>`: 页码，可选，默认 `1`。
    - `--page-size <size>`: 每页条数，可选，默认 `5`。

请求体示例（默认值如下）：

```plain
Project=default&SceneId=2042490062736326658&DataId=&SceneType=RAG&PageNumber=1&PageSize=5&IsDemo=false
```

其中：

- `DataId`: 默认为空字符串。
- `IsDemo`: 固定为 `false`。

**示例：**

```bash
VOLCENGINE_AK=YOUR_AK VOLCENGINE_SK=YOUR_SK python scripts/contextsearch_cli.py scene chunks --scene-id 2042490062736326658 --scene-type RAG --project default --data-id '' --page-number 1 --page-size 5
```

## 发布场景 (publish)

基于已存在的场景发布一个新版本，内部串联 `GetScene`、`GetAIInstanceSpec` 与 `CreateSceneVersion` 接口。

- **命令**: `scene publish`
- **支持参数**:
    - `--id <id>`: 场景 Id，必填。
    - `--scene-type <type>`: 场景类型 SceneType，必填，可选：`RAG`、`IMAGE_SEARCH`、`VIDEO_SEARCH`。
    - `--project <project>`: Project 名称，可选，默认值为 `default`。
    - `--version <x.y.z>`: 发布的版本号，必填，必须满足正则 `^\d+\.\d+\.\d+$`，例如 `1.0.0`。
    - `--resource-spec <spec>`: 资源规格，可选，默认值为 `"vci.n3i.2c-4gi"`。
    - `--replicas <n>`: 副本数，可选，默认 `2`，要求为正整数。

调用流程如下：

1. 调用 `GetScene`（GET，Version=`2025-09-01`）校验当前场景状态：仅当 `Status ∈ {DRAFT, RUNNING, STOPPED}` 时允许发布，否则 CLI 会返回错误：`当前状态不允许发布场景（仅支持 DRAFT/RUNNING/STOPPED）。`
2. 调用 `GetAIInstanceSpec`（GET，Version=`2025-09-01`）获取规格列表：
   - 从响应的 `Specs` 中筛掉 `GpuType` 非空的规格，仅保留 CPU-only 规格；
   - 若未显式传入 `--resource-spec`，CLI 会使用默认值 `"vci.n3i.2c-4gi"`；
   - 若传入的 `--resource-spec` 不在筛选后的 CPU-only 规格名单中，CLI 只会在 stderr 打印一条中文警告提示，但仍会继续执行发布流程。
3. 最终调用 `CreateSceneVersion`（POST，Version=`2025-09-01`），请求体结构如下：

```json
{
  "SceneId": "<id>",
  "Version": "<version>",
  "Project": "<project>",
  "SceneType": "<scene-type>",
  "Config": {
    "ResourceSpec": "<resource-spec>",
    "Replicas": <replicas>
  }
}
```

**示例：**

```bash
VOLCENGINE_AK=YOUR_AK VOLCENGINE_SK=YOUR_SK python scripts/contextsearch_cli.py scene publish --id 2042490062736326658 --scene-type RAG --project default --version 1.0.0 --resource-spec vci.n3i.2c-4gi --replicas 2
```

## 版本管理 (versions)

列举指定场景的版本列表，内部调用 `ctxsearch` 的 `ListSceneVersion` 接口（GET，Version=`2025-09-01`）。

- **命令**: `scene versions`
- **支持参数**:
    - `--id <id>`: 场景 Id，必填。
    - `--scene-type <type>`: 场景类型 SceneType，必填，可选：`RAG`、`IMAGE_SEARCH`、`VIDEO_SEARCH`。
    - `--project <project>`: Project 名称，可选，默认值为 `default`。
    - `--page-number <number>`: 页码，可选，默认 `1`，要求为正整数。
    - `--page-size <size>`: 每页条数，可选，默认 `6`，要求为正整数。

请求体示例：

```json
{
  "SceneId": "2042490062736326658",
  "Project": "default",
  "PageNumber": 1,
  "PageSize": 6,
  "SceneType": "RAG"
}
```

**示例：**

```bash
VOLCENGINE_AK=YOUR_AK VOLCENGINE_SK=YOUR_SK python scripts/contextsearch_cli.py scene versions --id 2042490062736326658 --scene-type RAG --project default --page-number 1 --page-size 6
```

## 停止场景 (stop)

停止指定场景在 `PROD` 环境下的实例，内部调用 `ctxsearch` 的 `StopSceneInstance` 接口（POST，Version=`2025-09-01`），其中 `Environment` 固定为 `"PROD"`。

- **命令**: `scene stop`
- **支持参数**:
    - `--id <id>`: 场景 Id，必填。
    - `--scene-type <type>`: 场景类型 SceneType，必填，可选：`RAG`、`IMAGE_SEARCH`、`VIDEO_SEARCH`。
    - `--project <project>`: Project 名称，可选，默认值为 `default`。

请求体示例：

```json
{
  "SceneId": "2042490062736326658",
  "Project": "default",
  "Environment": "PROD",
  "SceneType": "RAG"
}
```

**示例：**

```bash
VOLCENGINE_AK=YOUR_AK VOLCENGINE_SK=YOUR_SK python scripts/contextsearch_cli.py scene stop --id 2042490062736326658 --scene-type RAG --project default
```

## 启动场景 (start)

启动指定场景在 `PROD` 环境下的实例，内部调用 `ctxsearch` 的 `StartSceneInstance` 接口（POST，Version=`2025-09-01`），其中 `Environment` 固定为 `"PROD"`。

- **命令**: `scene start`
- **支持参数**:
    - `--id <id>`: 场景 Id，必填。
    - `--scene-type <type>`: 场景类型 SceneType，必填，可选：`RAG`、`IMAGE_SEARCH`、`VIDEO_SEARCH`。
    - `--project <project>`: Project 名称，可选，默认值为 `default`。

请求体示例：

```json
{
  "SceneId": "2042490062736326658",
  "Project": "default",
  "Environment": "PROD",
  "SceneType": "RAG"
}
```

**示例：**

```bash
VOLCENGINE_AK=YOUR_AK VOLCENGINE_SK=YOUR_SK python scripts/contextsearch_cli.py scene start --id 2042490062736326658 --scene-type RAG --project default
```

## 编辑名称 (rename)

编辑已有场景的名称，内部调用 `ctxsearch` 的 `UpdateScene` 接口（POST，Version=`2025-09-01`），仅更新 `Name` 字段。

- **命令**: `scene rename`
- **支持参数**:
    - `--id <id>`: 场景 Id，必填。
    - `--scene-type <type>`: 场景类型 SceneType，必填，可选：`RAG`、`IMAGE_SEARCH`、`VIDEO_SEARCH`。
    - `--name <name>`: 新的场景名称，必填，不能为空字符串。

请求体示例：

```json
{
  "Id": "2042492662139453441",
  "SceneType": "RAG",
  "Name": "jyf-test-rag11"
}
```

**示例：**

```bash
VOLCENGINE_AK=YOUR_AK VOLCENGINE_SK=YOUR_SK python scripts/contextsearch_cli.py scene rename --id 2042492662139453441 --scene-type RAG --name jyf-test-rag11
```

## 删除场景 (delete)

删除指定 Project 下的场景，属于危险操作，CLI 要求必须显式传入 `--confirm` 二次确认，内部调用 `ctxsearch` 的 `DeleteScene` 接口（POST，Version=`2025-09-01`）。

- **命令**: `scene delete`
- **支持参数**:
    - `--id <id>`: 场景 Id，必填。
    - `--scene-type <type>`: 场景类型 SceneType，必填，可选：`RAG`、`IMAGE_SEARCH`、`VIDEO_SEARCH`。
    - `--project <project>`: Project 名称，可选，默认值为 `default`。
    - `--confirm`: 二次确认开关，必须显式提供，否则命令会拒绝执行。

请求体示例：

```json
{
  "Id": "2042492662139453441",
  "Project": "default",
  "SceneType": "RAG"
}
```

**示例：**

```bash
VOLCENGINE_AK=YOUR_AK VOLCENGINE_SK=YOUR_SK python scripts/contextsearch_cli.py scene delete --id 2042492662139453441 --scene-type RAG --project default --confirm
```

## 规格查询 (specs)

查询当前可用的推理规格列表。内部调用 `ctxsearch` 的 `GetAIInstanceSpec` 接口（GET，Version=`2025-09-01`），默认只返回 CPU-only 规格（过滤掉 `GpuType` 非空的项），也可以通过参数切换为展示全部规格。

- **命令**: `scene specs`
- **支持参数**:
    - `--show-all`: 可选布尔开关，默认不传。缺省情况下 CLI 会仅返回 CPU-only 规格；传入该开关时会返回接口原始的全部规格列表（包括 GPU 规格）。

- 当不携带 `--show-all` 时，CLI 会从接口响应的 `Specs` 中筛选掉 `GpuType` 非空的规格，并以统一 JSON 形式输出过滤后的数组，便于作为 `scene publish --resource-spec` 的参考；
- 当携带 `--show-all` 时，CLI 会直接输出原始 `Specs` 数组。

**示例（默认仅 CPU-only）**：

```bash
VOLCENGINE_AK=YOUR_AK VOLCENGINE_SK=YOUR_SK python scripts/contextsearch_cli.py scene specs
```

**示例（展示全部规格）**：

```bash
VOLCENGINE_AK=YOUR_AK VOLCENGINE_SK=YOUR_SK python scripts/contextsearch_cli.py scene specs --show-all
```
