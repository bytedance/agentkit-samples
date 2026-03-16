---
name: byted-supabase
description: Manage Volcengine Supabase workspaces, branches, SQL queries, migrations, Edge Functions, Storage, and TypeScript type generation via a local CLI. Run uv run ./scripts/call_volcengine_supabase.py to get real-time results. Use this skill when the user needs to create, inspect, or manage Volcengine Supabase resources (workspaces, databases, branches, Edge Functions, Storage, API keys, or type generation). Do NOT use it for general database discussions, non-Supabase services, or pure client-side coding unrelated to Supabase backend management.
metadata: {"clawdbot":{"emoji":"🧩","homepage":"https://www.volcengine.com/","requires":{"bins":["uv"]},"os":["darwin","linux"]},"openclaw":{"emoji":"🧩","homepage":"https://www.volcengine.com/","requires":{"bins":["uv"]},"os":["darwin","linux"]},"moltbot":{"emoji":"🧩","homepage":"https://www.volcengine.com/","requires":{"bins":["uv"]},"os":["darwin","linux"]}}
---

# 火山引擎 Supabase

本 Skill 用于在对话中充当**火山引擎 Supabase 的智能运维与开发代理**。

它会：
- 识别用户的 Supabase 自然语言需求
- 直接调用 `scripts/call_volcengine_supabase.py` 获取实时结果
- 基于返回结果做解释、排障和下一步建议

## 何时使用本 Skill

**适用场景（应使用）：**

- 用户提到 **Supabase**、**火山引擎 Supabase** 相关的操作需求
- 需要创建、查看、暂停或恢复 Supabase **工作区（workspace）**
- 需要对 Supabase 数据库执行 **SQL 查询、建表、迁移**
- 需要管理 Supabase **分支**（创建、删除、重置）
- 需要部署或管理 **Edge Functions**
- 需要操作 **Storage Bucket**（创建、删除、查看配置）
- 需要获取 Supabase 项目的 **API Key** 或 **连接信息**
- 需要为 Supabase 数据库 **生成 TypeScript 类型定义**

**不适用场景（无需使用）：**

- 仅讨论通用数据库概念，不涉及火山引擎 Supabase 实例
- 操作非 Supabase 的数据库服务（如 RDS MySQL、Redis）
- 纯前端 / 客户端代码编写，不涉及 Supabase 后端资源管理
- 用户只是询问 Supabase 文档 / 概念，无需调用 CLI

## 运行方式

```bash
# 方式 1：使用 uv（推荐）
uv run ./scripts/call_volcengine_supabase.py <action> [options]

# 方式 2：使用 python（需预装依赖）
python ./scripts/call_volcengine_supabase.py <action> [options]
```

## 前置条件

- 必需环境变量：`VOLCENGINE_ACCESS_KEY`、`VOLCENGINE_SECRET_KEY`（如果在沙箱环境/vefaas IAM 环境下运行，将自动获取临时凭证，可不配置环境变量）
- 可选环境变量：`VOLCENGINE_REGION`、`DEFAULT_WORKSPACE_ID`、`READ_ONLY`、`SUPABASE_WORKSPACE_SLUG`、`SUPABASE_ENDPOINT_SCHEME`
- 若未配置依赖，可先执行：`uv pip install -r requirements.txt` 或 `pip install -r requirements.txt`

## 标准使用流程

1. 先确认目标资源：`workspace_id` 或 `branch_id`
2. 优先执行只读查询，确认现状
3. 需要变更时，再执行写操作
4. 变更后再次查询，确认结果已生效

## 常用命令示例

```bash
# 查看可访问的 workspace
uv run ./scripts/call_volcengine_supabase.py list-workspaces

# 查看 workspace 详情
uv run ./scripts/call_volcengine_supabase.py describe-workspace --workspace-id ws-xxxx

# 获取 workspace URL
uv run ./scripts/call_volcengine_supabase.py get-workspace-url --workspace-id ws-xxxx

# 查看分支
uv run ./scripts/call_volcengine_supabase.py list-branches --workspace-id ws-xxxx

# 执行 SQL
uv run ./scripts/call_volcengine_supabase.py execute-sql --workspace-id ws-xxxx --query "SELECT * FROM pg_tables LIMIT 5"

# 从文件执行 migration
uv run ./scripts/call_volcengine_supabase.py apply-migration --workspace-id ws-xxxx --name create_todos_table --query-file ./migration.sql

# 部署 Edge Function
uv run ./scripts/call_volcengine_supabase.py deploy-edge-function --workspace-id ws-xxxx --function-name hello --source-file ./index.ts

# 创建 Storage bucket
uv run ./scripts/call_volcengine_supabase.py create-storage-bucket --workspace-id ws-xxxx --bucket-name uploads --public
```

## 能力范围

### 工作区与分支

- `list-workspaces`
- `describe-workspace`
- `create-workspace`
- `pause-workspace`
- `restore-workspace`
- `get-workspace-url`
- `get-keys`
- `list-branches`
- `create-branch`
- `delete-branch`
- `reset-branch`

### 数据库

- `execute-sql`
- `list-tables`
- `list-migrations`
- `list-extensions`
- `apply-migration`
- `generate-typescript-types`

### Edge Functions / Storage

- `list-edge-functions`
- `get-edge-function`
- `deploy-edge-function`
- `delete-edge-function`
- `list-storage-buckets`
- `create-storage-bucket`
- `delete-storage-bucket`
- `get-storage-config`

## 应用开发参考

在使用本 Skill 管理 Supabase 资源的同时，以下文档提供应用开发场景的指导：

| 需求 | 文档 |
|------|------|
| 将 Supabase 接入 TS/Python 应用（SDK 初始化 + CRUD） | `references/app-integration-guide.md` |
| 数据库表结构设计与迁移规范 | `references/schema-guide.md` |
| 行级安全策略（RLS）配置 | `references/rls-guide.md` |
| Edge Function 编写与部署 | `references/edge-function-dev-guide.md` |

> 💡 **典型工作流**：先用 CLI 创建 workspace / 建表 / 配置 RLS，再参考应用开发文档在业务代码中集成 Supabase SDK。

## 注意事项

- 默认遵循“先查后改”
- `get-keys` 默认脱敏，只有明确需要时才加 `--reveal`
- `reset-branch` 会丢失未追踪变更，且后端当前会忽略 `migration_version`
- `READ_ONLY=true` 时，所有写操作会被拒绝

## 参考资料

- 工具说明：`references/tool-reference.md`
- 操作流程：`references/workflows.md`
- SQL 示例：`references/sql-playbook.md`
- 应用集成：`references/app-integration-guide.md`
- Schema 设计：`references/schema-guide.md`
- RLS 策略：`references/rls-guide.md`
- Edge Function 开发：`references/edge-function-dev-guide.md`
