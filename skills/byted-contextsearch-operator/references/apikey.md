# API Key 管理 (apikey)

本文档说明 ContextSearch API Key 管理相关的 CLI 能力，包括列举、创建和删除 API Key。

## 概述

`apikey` 命令用于管理 ContextSearch 中的 API Key。当前支持按 Project 查询 API Key、在数量限制内创建新 API Key，以及显式确认后删除指定 API Key。

## 核心功能

- 列举 API Key：调用 `ListMLApiKeys` 查询 API Key 列表。
- 创建 API Key：创建前先检查当前 Project 下 API Key 总数，少于 5 个时才允许创建。
- 删除 API Key：必须传入 `--confirm` 后才会调用删除接口。

## Agent 能力

Agent 可以根据用户意图选择以下命令：

| 能力 | 命令 | 说明 |
| --- | --- | --- |
| 列举 API Key | `apikey list` | 查询指定 Project 下的 API Key 列表 |
| 创建 API Key | `apikey create` | 在数量限制内创建新的 API Key |
| 删除 API Key | `apikey delete` | 删除指定 Project 下的单个 API Key |

## 目录结构说明

API Key 管理能力由以下文件提供：

```text
skills/byted-contextsearch-operator/
├── SKILL.md
├── scripts/
│   ├── contextsearch_cli.py
│   └── modules/
│       └── apikey.py
└── references/
    └── apikey.md
```

## 本地运行

运行前需要配置火山引擎访问凭证：

```bash
export VOLCENGINE_AK=YOUR_AK
export VOLCENGINE_SK=YOUR_SK
```

列举 ContextSearch 中的 API Key 列表：

```bash
python scripts/contextsearch_cli.py apikey list --page-number 1 --page-size 10 --project default --name ""
```

创建新的 ContextSearch API Key：

```bash
python scripts/contextsearch_cli.py apikey create --name test1 --project default
```

删除指定 Project 下的单个 ContextSearch API Key：

```bash
python scripts/contextsearch_cli.py apikey delete --id 2042224690871406593 --project default --confirm
```

## AgentKit 部署

该能力是 ContextSearch skill 的本地工具说明，不需要单独部署到 AgentKit Runtime。将 `skills/byted-contextsearch-operator/` 安装到 AgentKit 或 Codex 可发现的 skills 目录后，Agent 可按 `SKILL.md` 中的路由说明调用对应脚本。

## 示例提示词

- “帮我列一下 default 项目下的 ContextSearch API Key。”
- “帮我创建一个名为 test1 的 ContextSearch API Key。”
- “删除 ID 为 2042224690871406593 的 API Key，我确认删除。”

## 效果展示

列举 API Key 时，CLI 会返回接口响应中的 API Key 条目和分页信息。创建 API Key 时，CLI 会先检查当前 Project 下的 API Key 总数；当总数达到 5 个时，会拒绝继续创建并提示用户先删除不再使用的 API Key。

删除 API Key 时，如果缺少 `--confirm`，CLI 会拒绝执行危险操作，并输出重试示例：

```text
Refusing to delete without --confirm. Rerun with: apikey delete --id <id> --project <project> --confirm
```

## 常见问题

### 为什么最多只能创建 5 个 API Key？

创建前会调用 `ListMLApiKeys` 按 Project 统计当前已有 API Key 数量。仅当 `total < 5` 时，CLI 才会继续调用 `CreateMLApiKey`。

### 删除 API Key 为什么必须加 `--confirm`？

删除属于危险操作。CLI 通过显式确认标记避免误删。

### `apikey list` 为什么默认返回加密后的 API Key？

请求体中固定传入 `Encrypt=true`，用于要求服务端返回加密后的 API Key 内容。

## 代码许可

本文件随仓库代码一起分发，许可信息以仓库根目录的 `LICENSE` 文件为准。

## 命令细节

### 列举 API Key

列举命令内部调用 `ctxsearch` 的 `ListMLApiKeys` 接口，HTTP 方法为 POST，Version 为 `2025-09-01`。

- **命令**: `apikey list`
- **支持参数**:
  - `--page-number <number>`: 查询的页码，默认为 `1`。
  - `--page-size <size>`: 每页返回的条目数量，默认为 `10`。
  - `--project <project>`: Project 名称，可选，默认值为 `default`。
  - `--name <name>`: API Key 名称过滤条件，可选，默认为空字符串。

请求体中还会固定以下字段：

- `Encrypt`: 固定为 `true`，表示返回加密后的 API Key 内容。
- `PageNumber`: 默认值为 `1`。
- `PageSize`: 默认值为 `10`。
- `Project`: 默认值为 `"default"`。
- `Name`: 默认值为空字符串 `""`，按名称模糊匹配。

### 创建 API Key

创建前会自动调用 `ListMLApiKeys` 按 Project 查询当前已有的 API Key 总数，仅当总数小于 5 时才会继续调用 `CreateMLApiKey` 创建。否则会提示“最多创建 5 个 API Key，不允许继续创建，请删除不用的 API Key 后再继续”。

- **命令**: `apikey create`
- **支持参数**:
  - `--name <name>`: API Key 名称，必填。
  - `--project <project>`: Project 名称，可选，默认值为 `default`。

调用顺序与接口如下：

- 先调用 `ListMLApiKeys`，按 Project 统计总数：
  - 请求体包含字段：`PageSize=1`、`PageNumber=1`、`Project=<project>`、`Name=""`、`Encrypt=true`。
  - 总数计算逻辑：优先使用响应中的 `Total`；若不存在则使用 `TotalNum`；如都为空，则退回到 `len(Items)`。
- 当 `total < 5` 时，再调用 `CreateMLApiKey` 执行创建：
  - 请求体包含字段：`Project=<project>`、`Name=<name>`。
- 当 `total >= 5` 时，CLI 会返回错误：
  - `最多创建 5 个 API Key，不允许继续创建，请删除不用的 API Key 后再继续`。

### 删除 API Key

删除操作直接调用 `DeleteMLApiKey` 接口，HTTP 方法为 POST，Version 为 `2025-09-01`。

- **命令**: `apikey delete`
- **支持参数**:
  - `--id <id>`: API Key Id，必填，例如 `2042224690871406593`。
  - `--project <project>`: Project 名称，可选，默认值为 `default`。
  - `--confirm`: 二次确认开关，必须显式提供，否则命令会拒绝执行。

请求体结构为 `{Project, Id}`：

- `Project`: 取自 `--project`，默认 `default`。
- `Id`: 取自 `--id`，为要删除的 API Key 标识。
