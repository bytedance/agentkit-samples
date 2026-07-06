# 推理服务 (deployment)

## 目录

- 列举预置推理服务 (list_builtin)
- 列举自定义推理服务 (list_user)
- 推理服务详情 (get)
- 使用量查询 (usage)

## 列举预置推理服务 (list_builtin)

列举 ContextSearch 中的预置推理服务列表，内部调用 `ctxsearch` 的 `ListAIDeployment` 接口（POST，Version=`2025-09-01`）。

- **命令**: `deployment list_builtin`
- **支持参数**:
    - `--page-number <number>`: 查询的页码，默认为 `1`。
    - `--page-size <size>`: 每页返回的条目数量，默认为 `10`。
    - `--project <project>`: Project 名称，可选，默认值为 `default`。
    - `--name <name>`: 推理服务名称过滤条件，可选，默认为空字符串（不做名称过滤）。

调用该命令时，请求体中还会固定以下字段（不对外暴露为 CLI 参数）：

- `SortField`: 固定为 `"create_time"`。
- `SortOrder`: 固定为 `"DESC"`。
- `IsBuiltin`: 固定为 `true`，仅返回预置推理服务。

**示例：**

```bash
VOLCENGINE_AK=YOUR_AK VOLCENGINE_SK=YOUR_SK python scripts/contextsearch_cli.py deployment list_builtin --page-number 1 --page-size 10 --project default --name ""
```

## 列举自定义推理服务 (list_user)

列举 ContextSearch 中的自定义推理服务列表，与 `deployment list_builtin` 的参数与行为基本一致，唯一区别是请求体中的 `IsBuiltin` 固定为 `false`，仅返回自定义推理服务。

- **命令**: `deployment list_user`
- **支持参数**:
    - `--page-number <number>`: 查询的页码，默认为 `1`。
    - `--page-size <size>`: 每页返回的条目数量，默认为 `10`。
    - `--project <project>`: Project 名称，可选，默认值为 `default`。
    - `--name <name>`: 推理服务名称过滤条件，可选，默认为空字符串（不做名称过滤）。

调用该命令时，请求体中的分页与排序字段保持固定：

- `PageNumber`: 默认值为 `1`。
- `PageSize`: 默认值为 `10`。
- `Project`: 默认值为 `"default"`。
- `Name`: 默认值为空字符串 `""`。
- `SortField`: 固定为 `"create_time"`。
- `SortOrder`: 固定为 `"DESC"`。
- `IsBuiltin`: 固定为 `false`，仅返回自定义推理服务。

**示例：**

```bash
VOLCENGINE_AK=YOUR_AK VOLCENGINE_SK=YOUR_SK python scripts/contextsearch_cli.py deployment list_user --page-number 1 --page-size 10 --project default --name ""
```

## 推理服务详情 (get)

查询单个 ContextSearch 推理服务的详细信息，内部调用 `ctxsearch` 的 `GetAIDeployment` 接口（POST，Version=`2025-09-01`）。

- **命令**: `deployment get`
- **支持参数**:
    - `--id <id>`: 推理服务 Id，必填。
    - `--project <project>`: Project 名称，可选，默认值为 `default`。

**示例：**

```bash
VOLCENGINE_AK=YOUR_AK VOLCENGINE_SK=YOUR_SK python scripts/contextsearch_cli.py deployment get --id 2041355986031497217 --project default
```

## 使用量查询 (usage)

查询单个 ContextSearch 推理服务在指定时间范围内的用量，内部调用 `ctxsearch` 的 `GetArkEndpointUsage` 接口（POST，Version=`2025-09-01`）。

- **命令**: `deployment usage`
- **支持参数**:
    - `--id <id>`: 推理服务 Id，必填。
    - `--start-time <ts>`: 可选，Unix 秒级时间戳（字符串或整数），与 `--end-time` 需成对提供。
    - `--end-time <ts>`: 可选，Unix 秒级时间戳（字符串或整数），与 `--start-time` 需成对提供。
    - `--interval <seconds>`: 可选，聚合时间间隔（秒），默认 `86400`，要求大于 0。

调用该命令时，时间范围与聚合规则如下：

- 当 `--start-time` 与 `--end-time` 均未提供时：
  - `StartTime`: 当天 00:00:00 的 Unix 秒级时间戳（字符串形式，按本机时区）。
  - `EndTime`: 次日 00:00:00 的 Unix 秒级时间戳（字符串形式，按本机时区）。
  - `Interval`: 默认 `86400`（按天聚合）。
- 当 `--start-time` 与 `--end-time` 同时提供时：
  - `StartTime`: 取 `--start-time`，以字符串形式写入请求体。
  - `EndTime`: 取 `--end-time`，以字符串形式写入请求体。
  - `Interval`: 取 `--interval` 的值（秒），要求大于 0。
- 当仅提供其中一个时，CLI 会报错提示 `--start-time/--end-time` 必须成对提供。

**示例：**

- 默认查询当天用量：

```bash
VOLCENGINE_AK=YOUR_AK VOLCENGINE_SK=YOUR_SK python scripts/contextsearch_cli.py deployment usage --id 2041355986031497217
```

- 查询自定义时间范围用量：

```bash
VOLCENGINE_AK=YOUR_AK VOLCENGINE_SK=YOUR_SK python scripts/contextsearch_cli.py deployment usage --id 2041355986031497217 --start-time 1775664000 --end-time 1775750400 --interval 86400
```
