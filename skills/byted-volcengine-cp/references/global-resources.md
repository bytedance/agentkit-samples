# 服务连接与部署资源

API 版本：`2023-05-01`。两者都是账号级全局资源，删除前必须评估其他工作区/流水线依赖。

## 服务连接

`service_connection.py create/update` 从单个 JSON object 加载请求，并通过 `--connection-id`
注入/校验 `Id`。Create 关键字段：`Name`、`Type`、`Credential`、`IsAllWsShared`；可选
`Description`、`URL`、`SharedWorkspaceIds`、`DisableNetworkVerify`。Update 要求 `Name` 和
`IsAllWsShared`，Credential 可选。

支持类型：`DockerRegistry`、`ArtifactRegistry`、`Github`、`Gitlab`、`Gitee`、
`BitbucketCloud`、`Codeup`、`PrivateGitLab`、`BitbucketServer`、`Gerrit`、`Git`、
`Perforce`、`Codebase`、`Coding`、`GitCode`。

`Credential` 可含 Token、Username、Password、AccessKey、SecretKey；全部默认递归脱敏。list 支持
Name、Category（Registry/CodeRepo）、Type、Ids 和 WorkspaceId filter。删除服务连接前检查流水线
引用，执行时需要精确 ID 确认。

## 部署资源

`deploy_resource.py create/update` 从 JSON object 加载请求。Create 关键字段为 `Name` / `Source`，
并按 source 使用 VkeClusterId、Region、Kubeconfig 等公开字段；Update 通过 `--resource-id` 注入
`Id`。不要传 IDL 中标记 `api.ignore` 的内部字段。

`deploy_resource.py list` 支持 Name、Regions、Source、WorkspaceId 和 Ids filter，调用
`ListDeployResources`，默认发送 `HideKubeconfig=true`。即使服务端意外返回 kubeconfig，输出也会
脱敏。

删除部署资源可能影响多个工作区或应用，需要 `--dry-run`、`--yes` 和精确 ID 确认；只有明确的
非交互流程才使用 `--force`。

## JSON 输入安全

含 Credential 或 Kubeconfig 的 body 应保存在权限 `0600` 且被 Git 忽略的本地文件，通过
`--body-file` 读取。不要把真实密钥放进 `--body-json`、示例、日志、commit 或评审描述。
