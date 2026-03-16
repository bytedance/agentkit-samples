# Tool Reference

## 环境变量

- `VOLCENGINE_ACCESS_KEY`：火山引擎 Access Key
- `VOLCENGINE_SECRET_KEY`：火山引擎 Secret Key
- `VOLCENGINE_REGION`：地域，默认 `cn-beijing`
- `DEFAULT_WORKSPACE_ID`：默认目标 workspace
- `READ_ONLY`：设为 `true` 时禁止写操作
- `SUPABASE_WORKSPACE_SLUG`：Edge Functions 使用的项目 slug
- `SUPABASE_ENDPOINT_SCHEME`：生成 URL 的协议，默认 `http`

## 目标参数规则

- `--workspace-id` 既可传 `ws-...`，也可直接传 `br-...`
- 若不传 `--workspace-id`，会尝试使用 `DEFAULT_WORKSPACE_ID`
- 破坏性操作前，优先先查再改

## 工作区与分支动作

- `list-workspaces`
- `describe-workspace --workspace-id ws-...`
- `create-workspace --workspace-name demo`
- `pause-workspace --workspace-id ws-...`
- `restore-workspace --workspace-id ws-...`
- `get-workspace-url --workspace-id ws-...`
- `get-keys --workspace-id ws-... [--reveal]`
- `list-branches --workspace-id ws-...`
- `create-branch --workspace-id ws-... [--name develop]`
- `delete-branch --workspace-id ws-... --branch-id br-...`
- `reset-branch --workspace-id ws-... --branch-id br-... [--migration-version xxx]`

## 数据库动作

- `execute-sql --workspace-id ws-... --query "SELECT 1"`
- `execute-sql --workspace-id ws-... --query-file ./query.sql`
- `list-tables --workspace-id ws-... [--schemas public,auth]`
- `list-migrations --workspace-id ws-...`
- `list-extensions --workspace-id ws-...`
- `apply-migration --workspace-id ws-... --name add_table --query-file ./migration.sql`
- `generate-typescript-types --workspace-id ws-... [--schemas public]`

## Edge Functions / Storage 动作

- `list-edge-functions --workspace-id ws-...`
- `get-edge-function --workspace-id ws-... --function-name hello`
- `deploy-edge-function --workspace-id ws-... --function-name hello --source-file ./index.ts`
- `delete-edge-function --workspace-id ws-... --function-name hello`
- `list-storage-buckets --workspace-id ws-...`
- `create-storage-bucket --workspace-id ws-... --bucket-name uploads --public`
- `delete-storage-bucket --workspace-id ws-... --bucket-name uploads`
- `get-storage-config --workspace-id ws-...`
