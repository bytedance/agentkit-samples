# 控制台能力覆盖

本文件根据 ContextSearch 控制台页面代码整理。当前 skill 已把控制台实际使用的 `@/codegen/apis/ai/2025-09-01` action 注册到 `console` 命名空间中。

## 目录

- 使用原则
- 已实现对比
- 全量清单
- 核心页面与 Action 摘要
- 示例

## 使用原则

- 优先使用已经封装好的高层命令：`scene`、`model`、`deployment`、`apikey`。
- 当控制台动作还没有高层命令时，使用 `console <action_snake_case>` 直接调用对应 action。
- `network.postV2` 对应 `--method POST`，请求体使用 JSON 对象；`network.getV2` 对应 `--method GET`，CLI 会自动将 JSON 对象 Flatten 为查询参数。
- 请求体只放业务字段，不要在 body 里塞 `Action`、`Version`、`Service` 等签名元信息。
- `console list` 会输出当前覆盖的全部 action、请求方法、来源模块和对应 command；当前覆盖 190 个控制台 action。
- 删除类 action 需要 `--confirm`，否则 CLI 会拒绝执行；所有 `console` 子命令都支持 `--dry-run` 查看最终 action/method/body。

## 已实现对比

| 来源 | 控制台能力 | Skill 实现 |
| --- | --- | --- |
| SceneDevelopment / Home | 场景创建、详情、发布、版本、实例、数据、切片、草稿、网络、升级 | 高层 `scene ...` 覆盖主链路；其余逐一注册为 `console <action>` |
| SceneDevelopment | AgenticSearch 场景创建 | 高层 `scene create --scene-type AGENTIC_SEARCH`，对齐 `ListAgenticSceneTemplate -> CheckBuiltinDeployment -> DeployBuiltinDeployment -> CreateAgenticScene` |
| AgenticDataSource / SceneDevelopment | Agentic 数据源、绑定、变量、技能、工具、Chat、用户访问 | `console create_agentic_data_source`、`console list_agentic_skills`、`console create_agentic_mcp_tool` 等逐一覆盖 |
| DataSource / NodeForm | 数据源、索引任务、文件元信息、搜索配置版本 | `console list_indexer_data_source`、`console create_indexer`、`console create_search_config_v2` 等逐一覆盖 |
| InferenceService | 推理服务创建、更新、启停、授权、价格、网络、用量 | 高层 `deployment ...` 覆盖常用查询；其余逐一注册为 `console <action>` |
| ModelsManagement | 模型列表、详情、创建、更新、删除 | 高层 `model ...` 覆盖查询；创建/更新/删除逐一注册为 `console <action>` |
| ApiKey | API Key 列表、创建、删除 | 高层 `apikey ...` 已覆盖，同时注册为 `console <action>` |
| PsrDetails | PSR 场景、数据集、Pipeline、模型服务、灰度发布 | `console create_psr_scene`、`console create_psr_dataset`、`console start_gray_release` 等逐一覆盖 |

## 全量清单

运行以下命令查看完整、机器可读的覆盖矩阵：

```bash
python3 scripts/contextsearch_cli.py console list
```

输出中每一项都包含：

- `command`: CLI 子命令名，例如 `create_agentic_data_source`。
- `action`: 控制台实际调用的 OpenAPI action，例如 `CreateAgenticDataSource`。
- `method`: 控制台请求层 `network.getV2` / `network.postV2` 对应的 `GET` / `POST`。
- `pages`: 该 action 出现的 tenant 顶层页面目录。

## 核心页面与 Action 摘要

### 场景开发

- 普通检索场景：`ListScene`、`GetScene`、`CreateScene`、`UpdateScene`、`DeleteScene`、`CreateSceneVersion`、`DeleteSceneVersion`、`ListSceneVersion`、`GetSceneDraftVersion`、`UpdateSceneDraftVersion`、`UpgradeScene`。
- 创建 AgenticSearch 已封装为高层命令：`scene create --scene-type AGENTIC_SEARCH`，内部对齐控制台 `ListAgenticSceneTemplate` -> `CheckBuiltinDeployment` -> `DeployBuiltinDeployment` -> `CreateAgenticScene`。
- 场景运行实例：`GetSceneInstance`、`StartSceneInstance`、`StopSceneInstance`、`RestartSceneInstance`、`UpdateSceneInstance`、`GetAIInstanceSpec`。
- 数据导入与切片：`AddSceneData`、`RemoveSceneData`、`ListSceneData`、`GetSceneData`、`ListSceneDataChunk`、`GetSceneDataChunk`、`GetSceneIngestConfig`、`TestSceneConnection`、`GetIndexerUploadFileInfo`。
- 网络访问：`CreateAINetwork`、`DescribeAINetwork`、`DeleteAINetwork`、`UpdateIpAllowlist`、`DescribeZones`、`EditDeploymentTag`。

### Agentic Search

- Agentic 场景：`ListAgenticSceneTemplate`、`CreateAgenticScene`、`GetAgenticScene`、`UpdateAgenticScene`、`DeleteAgenticScene`、`ResumeAgenticScene`、`StopAgenticScene`、`RestartAgenticScene`。
- Agentic 数据源：`ListAgenticDataSources`、`GetAgenticDataSource`、`CreateAgenticDataSource`、`UpdateAgenticDataSource`、`DeleteAgenticDataSource`、`CreateAgenticDataSourceSceneBinding`、`ListAgenticDataSourceSceneBinding`。
- Agentic 变量、技能、工具：`ListAgenticVariables`、`CreateAgenticVariable`、`UpdateAgenticVariable`、`DeleteAgenticVariable`、`ListAgenticSkills`、`UploadAgenticSkill`、`UpdateAgenticSkill`、`DeleteAgenticSkill`、`GetAgenticSkillUploadInfo`、`GetAgenticSkillDownloadInfo`、`ListAgenticSkillFiles`、`GetAgenticSkillFile`、`ListAgenticTools`、`CreateAgenticMcpTool`、`UpdateAgenticTool`、`DeleteAgenticTool`。
- Agentic Chat：`ListAgenticChats`、`GetAgenticChat`、`ListAgenticChatTurns`、`GetAgenticChatTurn`、`GetAgenticChatTurnEvents`、`CancelAgenticChatTurn`、`GetAgenticCtxUploadInfo`、`UploadAgenticCtxFile`。
- 用户访问：`ListAgenticUsers`、`DeleteAgenticUser`。

### 数据源与索引任务

- 数据源：`ListIndexerDataSource`、`GetIndexerDataSource`、`CreateIndexerDataSource`、`UpdateIndexerDataSource`、`DeleteIndexerDataSource`、`CheckIndexerDataSourceNameExist`、`ListIndexerDataSourceByVpc`、`ListIndexerFileMeta`。
- 索引任务：`ListIndexer`、`GetIndexer`、`CreateIndexer`、`ModifyIndexer`、`DeleteIndexer`、`CheckIndexerNameExist`、`CheckJobUnderIndexer`、`StartIndexerJob`、`StopIndexerJob`、`ListIndexerJob`、`GetIndexerJob`。
- 搜索配置：`ListSearchConfigV2`、`CreateSearchConfigV2`、`ExistSearchConfigV2`、`ListSearchConfigVersion`、`ApplySearchConfigVersion`、`DeleteSearchConfigVersion`、`GetBasicSearchConfigResource`、`GetBasicSearchConfigVersion`、`GetAdvancedSearchConfigVersion`、`CheckAdvancedSearchConfigVersion`、`SaveAdvancedSearchConfigVersion`、`GetSearchConfigVersionPluginInfo`、`TestSearchConfigVersion`、`TransCustomConfig`、`TransNativeConfig`。

### 模型与推理服务

- 模型管理：`ListAIModel`、`GetAIModel`、`CreateAIModel`、`UpdateAIModel`、`DeleteAIModel`。
- 推理服务：`ListAIDeployment`、`GetAIDeployment`、`CreateAIDeployment`、`UpdateAIDeployment`、`CreateArkDeployment`、`CheckBuiltinDeployment`、`DeployBuiltinDeployment`、`GetArkEndpointUsage`、`ListModelRateLimit`。
- 网络与价格辅助：`DescribeInstancePriceV2`、`DescribeArkEndpointPrice`、`DescribeAINetwork`、`CreateAINetwork`、`DeleteAINetwork`。

### PSR 场景

- PSR 场景：`CreatePsrScene`、`GetPsrScene`、`UpdatePsrScene`、`DeletePsrScene`、`RestartPsrScene`、`StopPsrScene`、`GetCurrentPsrServe`。
- 数据集：`ListPsrDataset`、`GetPsrDataset`、`CreatePsrDataset`、`UpdatePsrDataset`、`DeletePsrDataset`、`UploadDatasetFiles`、`ListDatasetFiles`、`DeleteDatasetFiles`、`FetchSchemaFieldProperties`、`ParseSchema`、`FetchDatasetExampleData`、`FetchDatasetFileExampleData`。
- Pipeline：`ListPsrPipelines`、`GetPsrPipeline`、`CreatePsrPipeline`、`UpdatePsrPipeline`、`DeletePsrPipeline`、`StartPsrPipeline`、`StopPsrPipeline`、`ListPsrPipelineRuns`、`GetPsrPipelineRuninstance`、`GetModelTemplate`。
- 模型服务与灰度：`GetPsrServe`、`StartPsrServe`、`StopPsrServe`、`RestartPsrServe`、`DeletePsrServe`、`ListPsrServeConfigKeys`、`UpdatePsrServeConfig`、`StartGrayRelease`、`GetGrayReleaseDetail`、`ListGrayReleaseHistory`。

## 示例

创建 Agentic 场景：

```bash
python3 scripts/contextsearch_cli.py scene create \
  --scene-type AGENTIC_SEARCH \
  --project default \
  --name agentic-demo \
  --description ""
```

查询 Agentic 场景详情：

```bash
python3 scripts/contextsearch_cli.py console get_agentic_scene \
  --id "<scene-id>" \
  --project default
```

创建 Agentic OpenSearch 数据源：

```bash
python3 scripts/contextsearch_cli.py console create_agentic_data_source \
  --body-file ./agentic-data-source-body.json
```

在 `agentic-data-source-body.json` 中填写控制台导出的业务字段；不要把真实凭证写进文档或命令历史。

删除技能：

```bash
python3 scripts/contextsearch_cli.py console delete_agentic_skill \
  --id "<skill-id>" \
  --project default \
  --confirm "<skill-id>"
```

查询数据源索引任务：

```bash
python3 scripts/contextsearch_cli.py console list_indexer \
  --project default \
  --data-source-id "<data-source-id>" \
  --page-number 1 \
  --page-size 10
```
