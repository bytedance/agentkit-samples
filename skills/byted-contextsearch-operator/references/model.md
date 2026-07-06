# 模型管理 (model)

## 列举公共模型 (list)

列举 ContextSearch 公共模型列表，内部调用 `ctxsearch` 的 `ListAIModel` 接口（POST，Version=`2025-09-01`）。

- **命令**: `model list`
- **支持参数**:
    - `--page-number <number>`: 查询的页码，默认为 `1`。
    - `--page-size <size>`: 每页返回的条目数量，默认为 `10`。
    - `--project <project>`: Project 名称，可选，默认值为 `default`。
    - `--name <name>`: 模型名称过滤条件，可选，默认为空字符串（不做名称过滤）。

调用该命令时，请求体中还会固定以下字段（不对外暴露为 CLI 参数）：

- `Types`: 固定为 `["SYSTEM", "ARK"]`。
- `SortField`: 固定为 `"priority"`。
- `SortOrder`: 固定为 `"DESC"`。

**示例：**

```bash
VOLCENGINE_AK=YOUR_AK VOLCENGINE_SK=YOUR_SK python scripts/contextsearch_cli.py model list --page-number 1 --page-size 10 --project default --name ""
```

## 列举自定义模型 (list_user)

列举 ContextSearch 自定义模型列表，与 `model list` 的参数与行为基本一致，唯一区别是请求体中的 `Types` 固定为 `["USER"]`，仅返回自定义模型。

- **命令**: `model list_user`
- **支持参数**:
    - `--page-number <number>`: 查询的页码，默认为 `1`。
    - `--page-size <size>`: 每页返回的条目数量，默认为 `10`。
    - `--project <project>`: Project 名称，可选，默认值为 `default`。
    - `--name <name>`: 模型名称过滤条件，可选，默认为空字符串（不做名称过滤）。

调用该命令时，请求体中的 `SortField`、`SortOrder` 等固定字段与 `model list` 保持一致，仅 `Types` 固定为 `["USER"]`。

**示例：**

```bash
VOLCENGINE_AK=YOUR_AK VOLCENGINE_SK=YOUR_SK python scripts/contextsearch_cli.py model list_user --page-number 1 --page-size 10 --project default --name ""
```

## 模型详情 (get)

查询单个 ContextSearch 模型的详细信息，内部调用 `ctxsearch` 的 `GetAIModel` 接口（POST，Version=`2025-09-01`）。

- **命令**: `model get`
- **支持参数**:
    - `--id <id>`: 模型 Id，必填。
    - `--project <project>`: Project 名称，可选，默认值为 `default`。

**示例：**

```bash
VOLCENGINE_AK=YOUR_AK VOLCENGINE_SK=YOUR_SK python scripts/contextsearch_cli.py model get --id 1000043 --project default
```
