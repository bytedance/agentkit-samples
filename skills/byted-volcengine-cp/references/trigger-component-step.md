# 触发器与账号级自定义步骤

API 版本：`2023-05-01`。仅适用于北京/柔佛生产环境。

## Webhook URL 与触发器

`trigger.py webhook-url` 调用 `CreatePipelineWebhookURL`，必填 `WorkspaceId` / `PipelineId`，
可选 `ResourceId` 和 `Type`。返回 Webhook URL 按敏感 URL 处理：默认遮蔽，仅可用
`--output-file` 写入 `0600` 文件，不提供终端明文输出开关。

`trigger.py create/update` 从单个 JSON object 读取嵌套配置，显式注入 workspace、pipeline 和
update 的 trigger ID。Create 公共字段包括 `Name`、`Description`、`Type`、
`Configuration`、`Parameters`、`Resources`、`Sources`；Update 对应字段均可选，但目标 ID 必填。

Trigger type：`Webhook`、`GitWebhook`、`PerforceWebhook`、`CRWebhook`、`Schedule`。
配置结构按 type 使用 `Configuration.Webhook` 或 `Configuration.Schedule`。复杂事件 filter 保留为
JSON，不转换成易漂移的参数树。

`trigger.py list` 支持 `Filter.Ids` / `Filter.Name` 和分页。`delete` 必须 dry-run、`--yes`，
并要求精确 trigger ID 确认（`--force` 才跳过）。

## 账号级自定义步骤

`component_step.py list` 调用 `ListComponentStep`，默认 `IsBuiltin=false`，即查询当前账号的
自定义步骤。可用 `--builtin` 显式查询系统步骤；支持 Status、Name、ExactStepName、Category、
Ids、Version filter 和分页。

该 API 与 `list_component_inputs.py` 不同：后者读取 skill 打包的离线系统组件索引，不访问账号。

- create/upgrade：`--yaml-file` 内容作为 `ComponentStepYaml`。
- update：显式 `--identifier`，并提供 `--yaml-file` 和/或 `--status Enabled|Disabled`。
- delete：显式 `--identifier`，并执行删除强确认。

YAML 可能包含默认 token/password，因此 dry-run 将整个 `ComponentStepYaml` 视为敏感字段，不回显。
