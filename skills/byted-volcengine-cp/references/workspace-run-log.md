# 工作区、TaskRun 与日志下载 URI

API 版本：`2023-05-01`。仅适用于北京/柔佛生产环境。

## 工作区

`workspace.py list` 调用 `ListWorkspaces`，支持 `Filter.Name` 模糊过滤、重复
`Filter.Ids`、分页、`--max`、`--all` 和 `--json`。

`workspace.py update` 调用 `UpdateWorkspace`。JSON 可包含 `Name`、`Description`、
`Visibility`、`VisibleUsers`、`VisibleUserGroups`；`Id` 由 `--workspace-id` 注入并校验。
`Visibility=Specified` 时应同时提供目标用户/用户组，并保留主账号可见性。

## TaskRun

`task_run.py list` 调用 `ListTaskRuns`，必填 workspace、pipeline、pipeline run 和 task ID；
`Filter.Ids` / `Filter.Statuses` 可重复。支持分页和摘要/JSON 输出。该正式入口不会改变
`get_logs.py` 原有的内部下钻行为。

## 日志下载 URI

`task_run.py download-uri` 调用 `GetTaskRunLogDownloadURI`，必填：

- `WorkspaceId`
- `PipelineId`
- `PipelineRunId`
- `TaskId`
- `TaskRunId`
- `StepName`

返回 URL 可能包含短期签名，按凭证等价信息处理：默认只显示 `<redacted>` 和 RequestId；
仅可用 `--output-file` 写入 mode `0600` 文件。脚本只返回 URL，
不会自动访问或下载其内容。
