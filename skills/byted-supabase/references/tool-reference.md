# 命令速查（byted-supabase-cli）

本 Skill 通过 `byted-supabase-cli` 实现全部能力。本文给出**动作 → CLI 命令**的完整映射，以及若干没有专用子命令、需用 `db query` 跑 SQL 实现的能力的等价 SQL。

> 命令名统一写作 `byted-supabase-cli`；若已别名为 `supabase` 则等价。任何子命令加 `--help` 可查看完整参数。
>
> 📖 命令/参数随版本变化，不确定时先查火山在线文档（[新功能发布记录](https://www.volcengine.com/docs/87275/2105759?lang=zh)、[API 列表](https://www.volcengine.com/docs/87275/2105871?lang=zh)）或 `--help`，不要凭记忆猜。完整文档链接见 SKILL.md「在线文档」。

## 目录

- 鉴权（优先 CLI 配置 / 登录）
- 目标定位规则
- 工作区与分支动作
- 数据库动作
- Edge Functions 动作
- Storage 动作

## 鉴权（优先 CLI 配置 / 登录）

- **推荐**：`byted-supabase-cli login --region cn-beijing`（OAuth 交互式登录），或 `byted-supabase-cli configure set --access-key <AK> --secret-key <SK>`（AK/SK）。凭据写入 `~/.volcengine/config.json`，一次配置长期复用。
- **次要（headless / CI）**：环境变量 `VOLCENGINE_ACCESS_KEY` / `VOLCENGINE_SECRET_KEY`（临时凭据再加 `VOLCENGINE_SESSION_TOKEN`）。
- **region 可缺省**，不指定时默认 `cn-beijing`；需指定到其他地域（如 `cn-shanghai`）时加 `--region`（或环境变量 `VOLCENGINE_REGION`）。

## 目标定位规则

- `--workspace-id ws-...`（别名 `--project-ref`）指定工作区；`--branch-id br-...` 指定分支，不传落到默认分支。
- 数据面命令（`db query` / `functions` / `storage` / `gen types` 等）默认 `--linked=true`：可先 `byted-supabase-cli link --workspace-id ws-... --region <region>` 设默认，之后用 `--linked`；否则每次显式传 `--workspace-id`。
- 管理类命令加 `-o json` 便于解析；`db query` 默认输出 JSON。
- 破坏性操作（delete / stop）在非交互环境加 `--yes`。
- **list 命令优先分页**：返回列表的命令（`projects list` / `branches list` / `projects operations`）支持 `--limit`（1-100）+ `--offset` 翻页。**推荐显式分页拉取，避免一次性取回过多数据**（既省 token、也省接口压力）：**默认每页 `--limit 10`**，需要看更多再按页递增 `--offset`（第 2 页 `--offset 10`、第 3 页 `--offset 20`，以此类推）。注意缺省值不一致：`projects list` 缺省最多 100、`projects operations` 缺省 10，而 **`branches list` 缺省（省略 `--limit` 或 `--limit 0`）会返回全部**——所以这几个都建议统一显式带上 `--limit 10`；分支多时还可优先用 `--search` 关键字过滤。其余 list 命令（`endpoints list` / `functions list` / `storage buckets list`）暂无分页参数。

---

## 工作区与分支动作

| 旧动作（已废弃） | 新 CLI 命令 |
|---|---|
| `list-workspaces` | `byted-supabase-cli projects list -o json`（支持分页 `--limit`(1-100，缺省 100) / `--offset`，**建议每页 `--limit 10`** 翻页） |
| `describe-workspace` | `byted-supabase-cli projects list --workspace-id ws-... --detail -o json`（或 `projects overview`） |
| `create-workspace` | `byted-supabase-cli projects create <name>`（region 走 `--region`/env/profile；`--volc-project-name` 可指定火山项目名）。**默认不休眠**；创建成功后须主动说明休眠超时并非阻塞询问（见下方「💤 休眠超时」）。Agent Plan 渠道场景另见下方「🔌 Agent Plan 实例」（可选，普通用户无需关心） |
| `pause-workspace`（⛔ **高危**，见下方辨析） | `byted-supabase-cli projects stop <ref> --yes` |
| `restore-workspace` | `byted-supabase-cli projects start <ref> --yes` |
| `get-workspace-url` | `byted-supabase-cli endpoints list --workspace-id ws-... -o json`（访问地址）；`byted-supabase-cli db connection-string --workspace-id ws-...`（Postgres 连接串） |
| `get-keys` | `byted-supabase-cli projects api-keys --workspace-id ws-... -o json`（返回 anon / service_role 等） |
| `list-branches` | `byted-supabase-cli branches list --workspace-id ws-... -o json`（⚠️ 缺省返回全部；**建议显式 `--limit 10`** 配合 `--offset` 翻页，或用 `--search <kw>` 过滤） |
| `create-branch` | `byted-supabase-cli branches create <name> --workspace-id ws-... [--parent-id br-... | --parent-time <RFC3339>]` |
| `delete-branch` | `byted-supabase-cli branches delete <branch-id> --workspace-id ws-...` |

补充分支命令：`branches get <id>`、`branches get-default`、`branches set-default <id>`、`branches restart <id>`（重启算力）、`branches restore <id> --restore-time <RFC3339>`（时间点恢复）、`branches restorable --restore-time <ts>`、`branches restore-window <id>`、`branches update <id> --name <new>`。

补充 workspace 命令：`projects delete <ref> --yes`、`projects rename <ref> --name <new>`、`projects deletion-protection <ref> --enable|--disable`、`projects compute-settings <ref> --min-cu/--max-cu [--suspend-timeout-seconds <秒>]`（即 ModifyComputeSettings；改休眠超时见下方「💤 休眠超时」）、`projects api-keys`、`projects operations <ref>`（审计日志，缺省只返回最近 10 条；翻页用 `--limit`(1-100) / `--offset`）。

> **💤 休眠超时（SuspendTimeoutSeconds）**：分支算力**空闲多少秒后自动休眠（scale-to-zero）**的阈值，到点休眠、下次访问自动唤醒（这是「休眠」非「暂停」）。**取值语义**：`-1` = 显式关闭自动休眠（算力常驻 / 永不休眠）；`0` = 未设置的平台默认（行为等同常驻）；`300`–`604800` 秒（5 分钟–7 天）= 启用。**新建 workspace 默认不休眠**（`projects list --detail` 显示为 `0`）；想**关闭**已开启的自动休眠传 `-1`（不是 `0`）。改它用 `projects compute-settings <ref> --service-type Supabase --min-cu 0.5 --max-cu 2 --suspend-timeout-seconds <秒> --yes`；**非交互/agent 模式 `--yes`（变更操作，缺它报 `missing required flag: --yes`）与 `--min-cu`/`--max-cu` 都不能少**。⚠️ **Supabase 服务的 min CU 下限是 `0.5`，必须 ≥0.5**（直接用 `0.5`/`2`）；**千万别用 `projects list --detail` 查到的值回填 min** —— 那是 Database 服务的 `0.25`，`<0.5` 配 Supabase 会被服务端拒为 `InvalidParameter`。休眠超时是 workspace 级单值，经 Supabase 服务设置即生效。`projects create` 成功后应**主动说明并非阻塞地询问**是否设置，**推荐 1 小时（`--suspend-timeout-seconds 3600`）**，用户无需要则保持默认不休眠。

> **🔌 Agent Plan 实例（特定渠道/合作方场景，可选，非通用）**：默认创建的是**普通实例**，绝大多数用户都走这条路。仅当用户经 **Agent Plan 渠道**接入、并**主动提供** plan API key 时，才在创建时加 `--agent-plan-api-key <key>`，把新实例绑定为 Agent Plan 实例（也可省略该 flag、改由环境变量 `ARK_AGENT_PLAN_API_KEY` 提供；两者都没有就是普通实例）。**只能在创建时设定，事后不可更改**。绑定后 `projects list --workspace-id ws-... --detail -o json` 会带上 `is_agent_plan_instance` / `agent_plan_api_key_id` / `agent_plan_api_key` 字段，可据此判断与取回 key。
> ⚠️ **不要主动向普通用户建议或索要 plan key**——仅在用户主动问起 Agent Plan、或主动给出 key 时，按本说明处理；其余情况当作普通实例创建即可。

> **⚠️ 暂停 / 重启 / 休眠 辨析**（别混淆，危险等级递增）：
> - **重启**分支算力 → `branches restart <id>`（**单条命令**；**不要**用 `projects stop` + `projects start` 模拟重启，那是整个 workspace 停机再开机）。**低危**。
> - **休眠 / 唤醒** → 分支算力的**平台自动行为**：空闲超过 `SuspendTimeoutSeconds` 自动 scale-to-zero，下次访问 exposeURL 自动唤醒，**唤醒无手动命令**；超时阈值可配（`projects compute-settings <ref> --service-type Supabase --min-cu 0.5 --max-cu 2 --suspend-timeout-seconds <秒> --yes`，**新建默认不休眠**），更不要用 `projects stop` 代替。**低危**。
> - **⛔ 暂停 / 恢复** → `projects stop` / `projects start`，作用于**整个 workspace**（含其下所有分支）。**高危红线**：暂停后客户业务彻底不可用，且**无法靠客户 IO 自动唤醒**，只能人工 `projects start`。执行 `projects stop` 前**必须向用户复述影响并二次确认**、核对 `ref`，**绝不**拿它当重启/休眠/省资源的手段。

---

## 数据库动作

| 旧动作（已废弃） | 新 CLI 命令 |
|---|---|
| `execute-sql --query "..."` | `byted-supabase-cli db query "<sql>" --workspace-id ws-... [--branch-id br-...]` |
| `execute-sql --query-file f.sql` | `byted-supabase-cli db query -f f.sql --workspace-id ws-...` |
| `apply-migration --name X --query-file f.sql` | 即时应用：`byted-supabase-cli db query -f f.sql --workspace-id ws-...`。版本化/声明式：见下方「Schema 变更」 |
| `generate-typescript-types` | `byted-supabase-cli gen types --lang typescript --workspace-id ws-... [-s public] > database.types.ts`（`--lang` 还支持 `go` / `swift`） |
| `list-tables` | `db query` 跑等价 SQL（见下）；或 `byted-supabase-cli inspect db table-stats --workspace-id ws-...` |
| `list-extensions` | `db query` 跑等价 SQL（见下） |
| `list-migrations` | `db query` 查迁移历史表（见下） |

`db query` 输出格式：`-o json`（默认）/ `table` / `csv`。

### 没有专用子命令的能力 → 等价 SQL

```bash
# list-tables：列出所有用户表
byted-supabase-cli db query "SELECT table_schema, table_name FROM information_schema.tables WHERE table_schema NOT IN ('pg_catalog','information_schema') ORDER BY 1,2;" --workspace-id ws-xxxx

# list-extensions：列出已安装扩展
byted-supabase-cli db query "SELECT name, default_version, installed_version FROM pg_available_extensions WHERE installed_version IS NOT NULL ORDER BY name;" --workspace-id ws-xxxx

# list-migrations：查看已应用的迁移历史（若用过迁移历史表）
byted-supabase-cli db query "SELECT version, name FROM supabase_migrations.schema_migrations ORDER BY version;" --workspace-id ws-xxxx
```

### Schema 变更

- **即时应用一段 SQL**（建表 / ALTER / 建策略等）：把 SQL 写入文件后 `byted-supabase-cli db query -f change.sql --workspace-id ws-...`。
- **声明式 schema 管理**：`byted-supabase-cli db schema declarative --help` —— 维护期望 schema 的声明文件，由 CLI 计算并应用差异。适合需要可追溯、可重复的 schema 演进。
- **巡检**：`byted-supabase-cli db advisors --workspace-id ws-...`（安全/性能建议）；`byted-supabase-cli inspect db <subcmd>`（如 `table-stats` / `index-stats` / `bloat` / `long-running-queries` 等）。

---

## Edge Functions 动作

> 本 fork 的 `functions deploy` 从**本地函数目录**部署（`supabase/functions/<name>/`），不再是「单文件 / 内联代码」。标准流程：`functions new` 生成脚手架 → 编辑 → `functions deploy`。

| 旧动作（已废弃） | 新 CLI 命令 |
|---|---|
| `list-edge-functions` | `byted-supabase-cli functions list --workspace-id ws-... -o json` |
| `get-edge-function` | `byted-supabase-cli functions download <name> --workspace-id ws-...`（拉取源码到本地） |
| `deploy-edge-function --source-file index.ts` | `byted-supabase-cli functions new <name>` → 编辑 `supabase/functions/<name>/index.ts` → `byted-supabase-cli functions deploy <name> --workspace-id ws-... [--no-verify-jwt]` |
| `delete-edge-function` | `byted-supabase-cli functions delete <name> --workspace-id ws-...` |

`functions deploy` 关键参数：`--no-verify-jwt`（公开访问，如 Webhook）、`--runtime auto|deno|native-node20/v1|python3.9|python3.10|python3.12`、`--import-map <path>`。

---

## Storage 动作

| 旧动作（已废弃） | 新 CLI 命令 |
|---|---|
| `list-storage-buckets` | `byted-supabase-cli storage buckets list --workspace-id ws-... -o json` |
| `create-storage-bucket --bucket-name X --public` | `byted-supabase-cli storage buckets create <bucket-id> [--public] [--file-size-limit <bytes>] [--allowed-mime-type <type>] --workspace-id ws-...` |
| `delete-storage-bucket` | `byted-supabase-cli storage buckets delete <bucket-id> --workspace-id ws-...` |
| `get-storage-config` | `byted-supabase-cli storage buckets get <bucket-id> --workspace-id ws-... -o json`（按 bucket 查看配置） |

补充：`storage buckets update <id> [--public|--private]`；对象操作 `storage ls <path>`、`storage cp <src> <dst>`、`storage mv <src> <dst>`、`storage rm <file...>`（对象路径形如 `ss:///<bucket>/<path>`，可加 `-r` 递归）。
</content>
