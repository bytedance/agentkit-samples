---
name: byted-supabase
description: Manage Volcengine's AI-native BaaS platform (Supabase edition / 火山引擎 AI 原生 BaaS 平台 Supabase 版) — a Volcengine-operated distribution that differs from official Supabase. Covers workspaces, branches, SQL queries, schema changes, Auth, Realtime, Edge Functions, Storage, and TypeScript type generation through the byted-supabase-cli command-line tool (installed via `npm i -g @byted-supabase/cli`; this is NOT the official `supabase` CLI). Run byted-supabase-cli subcommands to get real-time results. Use this skill when the user needs to create, inspect, or manage Volcengine Supabase resources (workspaces, databases, branches, Auth, Realtime, Edge Functions, Storage, API keys, or type generation). Do NOT use it for general database discussions, non-Supabase services, or pure client-side coding unrelated to Supabase backend management.
version: 2.2.7
license: Apache-2.0
metadata:
  openclaw:
    emoji: "🧩"
    homepage: "https://www.volcengine.com/"
    requires:
      bins:
        - byted-supabase-cli
    os:
      - darwin
      - linux
---

# 火山引擎 AI 原生 BaaS 平台 · Supabase 版

本 Skill 用于在对话中充当**火山引擎「AI 原生 BaaS 平台 Supabase 版」的智能运维与开发代理**。

> ℹ️ **这是火山引擎自研的 AI 原生 BaaS 平台（Supabase 版），不是官方开源 Supabase。** 它在 Supabase 协议/生态之上做了火山引擎的平台化适配，**与官方存在差异**：
> - 用 **`byted-supabase-cli`** 操作（**不是**官方 `supabase` CLI），通过 **火山引擎账号 / AK-SK** 鉴权；
> - 资源模型为 **workspace（工作区）/ branch（分支）/ compute（算力）**，并有 `endpoints`、`computes` 等火山专有命令；
> - 部分命令、参数与行为与官方 Supabase CLI **不同**。
>
> 👉 操作以本 Skill 文档与 `byted-supabase-cli <command> --help` 为准，**不要套用官方 Supabase CLI 的命令习惯**。

它会：
- 识别用户的 Supabase 自然语言需求
- 直接调用 **`byted-supabase-cli`** 命令行工具获取实时结果
- 基于返回结果做解释、排障和下一步建议

## 核心原则

> 本节为通用工作纪律，**任何 Supabase 任务都应遵守**。

**1. 平台演进快 —— 先查在线文档/发布记录，不要只信训练数据。**
命令、参数、`config` 项、API 约定会随版本变化。动手前先查火山引擎官方文档与发布记录（见文末[在线文档](#在线文档)），尤其涉及不确定的命令/参数时；CLI 子命令一律 `byted-supabase-cli <command> --help` 现查，**不要凭记忆猜命令**。

**2. 验证你的工作。** 任何变更落地后，**再跑一条只读查询确认生效**。没有验证的修复＝未完成。

**3. 从错误中恢复，不要死循环。** 同一方法连续失败 2-3 次就停下来换思路：换方法、查文档、更仔细地看报错、必要时查日志。Supabase 类问题不总是靠重试同一条命令解决。

**4. 把表暴露给 Data API（REST）。** 新建的表**不一定**自动通过 Data API 暴露。若要让 `anon` / `authenticated` 角色经 REST 访问某表，需显式 `GRANT`。

> 注意：这与 RLS 是两回事 —— Data API 暴露 + 角色授权决定**表是否可达**；RLS 决定表可达后**哪些行可见**。当用户反馈"SQL 建的表访问不到"，先确认是否已授权这两个角色。**对外（anon/authenticated）授权时务必同时启用 RLS。**

**5. ⛔ 高危红线：`projects stop`（暂停 workspace）会让客户业务彻底不可用。**
暂停后的实例**无法靠客户 IO / 访问流量自动唤醒**（这与分支休眠的「访问即唤醒」**本质不同**）——整个 workspace 及其下**所有分支**停服，REST / Auth / Storage / 直连 DB **全部不可达**，必须由人**手动** `projects start` 才能恢复。因此执行 `projects stop` 前**必须**：
> 1. **向用户明确复述影响并取得二次确认**——「这会停掉整个 workspace `<ref>`，期间客户业务完全不可用、且不会自动恢复，确认吗？」
> 2. **核对目标 `ref` 无误**，绝不停错 workspace；
> 3. **绝不**把它当作「重启 / 休眠 / 省资源」的手段——重启用 `branches restart`，休眠是平台自动行为，二者都**不会**导致业务停服。
>
> （`projects delete` 同属不可逆高危操作，同样需先确认。）

**6. 暴露 schema 内的表必须启用 RLS。** 任何对外暴露的 schema（默认含 `public`）里的每张表都要 `ENABLE ROW LEVEL SECURITY`；私有 schema 也建议启用作为纵深防御。启用后，按真实访问模型写策略，**不要无脑给每张表套同一个 `auth.uid()` 模式**。

**7. 安全 checklist。** 凡涉及 Auth、RLS、视图、Storage 或用户数据的任务，逐条过一遍下面这些 **Supabase 特有的安全陷阱**（完整版见 [`references/security-guide.md`](references/security-guide.md)）：

- **绝不**用 `user_metadata` / `raw_user_meta_data` 做鉴权判断 —— 它**用户可改**，放进 RLS/授权逻辑即可被伪造。鉴权数据存 `raw_app_meta_data` / `app_metadata`。
- **`service_role` / 密钥绝不出现在前端**。前端用 publishable / `anon` key；`service_role` 仅后端。
- **视图默认绕过 RLS** —— PG15+ 用 `CREATE VIEW ... WITH (security_invoker = true)`；更低版本则从 `anon`/`authenticated` 收回视图权限或放进未暴露 schema。
- **`auth.role()` 已弃用** —— 改用策略上的 `TO authenticated` / `TO anon`。开启匿名登录后，匿名用户也带 `authenticated` 角色，`auth.role() = 'authenticated'` 会**静默失效**。
- **只写 `TO authenticated` 是"认证而非授权"（BOLA/IDOR）** —— 必须配所有权谓词：`to authenticated using ( (select auth.uid()) = user_id )`。
- **UPDATE 策略要同时有 `USING` 和 `WITH CHECK`**，否则用户能把行的 `user_id` 改成别人。
- **UPDATE 需要 SELECT 策略** —— RLS 下 UPDATE 要先 SELECT 到行；缺 SELECT 策略时更新静默返回 0 行（无报错）。
- **`SECURITY DEFINER` 函数绕过 RLS**，且 `public` 下默认对所有角色可调用。别用它来"解决"权限报错；非用不可时放进未暴露 schema + 函数体内做 `auth.uid()` 检查 + 改完跑 `db advisors`。
- **Storage upsert 需要 INSERT + SELECT + UPDATE 三个权限**，只给 INSERT 会导致覆盖上传静默失败。
- **固定依赖版本并提交 lockfile**（`@supabase/supabase-js`、`@supabase/ssr`、`supabase-py` 等）。

## 何时使用本 Skill

**适用场景（应使用）：**

- 用户提到 **Supabase**、**火山引擎 Supabase** 相关的操作需求
- 需要创建、查看、暂停或恢复 Supabase **工作区（workspace / project）**，或**重启分支算力**
- 需要对 Supabase 数据库执行 **SQL 查询、建表、schema 变更**
- 需要管理 Supabase **分支**（创建、删除、恢复、设默认）
- 需要配置 **Auth（认证）** 或使用 **Realtime（实时）**
- 需要部署或管理 **Edge Functions**
- 需要操作 **Storage Bucket**（创建、删除、查看配置、上传/下载对象）
- 需要获取 Supabase 项目的 **API Key** 或 **连接信息**
- 需要为 Supabase 数据库 **生成 TypeScript 类型定义**

**不适用场景（无需使用）：**

- 仅讨论通用数据库概念，不涉及火山引擎 Supabase 实例
- 操作非 Supabase 的数据库服务（如 RDS MySQL、Redis）
- 纯前端 / 客户端代码编写，不涉及 Supabase 后端资源管理
- 用户只是询问 Supabase 文档 / 概念，无需调用 CLI

## 命令行工具

本 Skill 的所有能力都来自 `byted-supabase-cli` 这一个二进制：

```bash
npm i -g @byted-supabase/cli         # 安装（一次）；装后得到 byted-supabase-cli 命令
byted-supabase-cli --help            # 自检 / 看帮助
byted-supabase-cli <command> --help  # 任何子命令都可加 --help 看参数
```

> 文档示例统一写作 `byted-supabase-cli`；若你的环境已把它别名/软链为 `supabase`（CLI 二进制自身在 `--help` 里也自称 `supabase`），两种写法等价。（用 `--help` 现查命令结构、不要猜——见[核心原则 1](#核心原则)。）

## 鉴权与前置条件

`byted-supabase-cli` 用**火山引擎凭据**鉴权。**优先使用 CLI 自带的配置 / 登录方式**（写入 `~/.volcengine/config.json`，一次配置长期复用）：

**方式 1 · CLI 配置 / 登录（推荐）**

```bash
byted-supabase-cli login --region cn-beijing   # 1a. 浏览器 OAuth 登录（最省事，缓存临时 STS 凭据）；其他地域替换 cn-beijing
byted-supabase-cli configure set --access-key <AK> --secret-key <SK>   # 1b. 或用 AK/SK 写入默认 profile，可选 [--region <region>]
byted-supabase-cli configure list            # 管理 profile：列出
byted-supabase-cli configure get             # 查看当前 profile
byted-supabase-cli configure profile <name>  # 切换当前 profile
```

> region 可缺省；若在 `login` / `configure set` 时指定了，会写进 profile，后续命令无需再带 `--region`。

**方式 2 · 环境变量（次要，适合无法持久化的 headless / CI 场景）**

```bash
export VOLCENGINE_ACCESS_KEY=<AK>
export VOLCENGINE_SECRET_KEY=<SK>
export VOLCENGINE_REGION=<region>          # 例如 cn-beijing / cn-shanghai
export VOLCENGINE_SESSION_TOKEN=<token>    # 可选：使用临时凭据时才需要
```

> 在沙箱 / VeFaaS IAM 等已自带角色凭据的环境里，可不显式设置 AK/SK，CLI 会自动取临时凭据。

**地域（region）**：可缺省，不指定时默认 `cn-beijing`。需要指定到其他地域（如 `cn-shanghai`）时再用 `--region`，或在 `login` / `configure set` 时设好（写进 profile 后续无需重复）。解析优先级：`--region` > 环境变量 > profile > 已 link 的 region > 默认（`cn-beijing`）。

**鉴权自检**：能成功跑通 `byted-supabase-cli projects list` 即说明凭据 + region 可用。

## 目标定位（workspace / branch）

- **workspace（工作区/项目）**：用 `--workspace-id ws-...` 指定（其别名 `--project-ref` 与官方 Supabase CLI 兼容）。
- **branch（分支）**：用 `--branch-id br-...` 指定；不传则落到该 workspace 的**默认分支**。
- **默认目标（可选）**：`byted-supabase-cli link --workspace-id ws-... --region <region>` 把某 workspace 设为本目录的默认链接；之后数据面命令可用 `--linked`（多数命令默认 `--linked=true`）而不必每次重复 `--workspace-id`。
- **输出格式**：管理类命令加 `-o json` 便于解析；`db query` 默认即输出 JSON（agent 模式）。
- **列表分页（避免一次取太多）**：返回列表的命令（`projects list` / `branches list` / `projects operations`）支持 `--limit`(1-100) + `--offset`，**优先显式分页拉取，别一次性取回过多数据；建议每页 `--limit 10`，需要更多再递增 `--offset` 翻页**；尤其 **`branches list` 缺省会返回全部**，分支多时务必加 `--limit` 或用 `--search` 过滤。其余 list 命令暂无分页参数，详见 [tool-reference](references/tool-reference.md#目标定位规则)。

## 标准使用流程

1. 先确认目标资源：`workspace_id`（必要时 `branch_id`）
2. 优先执行**只读查询**，确认现状（`projects list`、`db query "select ..."` 等）
3. 需要变更时再执行写操作；破坏性操作（删除/停机）在非交互环境需加 `--yes`，**执行前向用户确认**。⛔ 尤其 `projects stop`（暂停 workspace）属高危红线——客户业务会彻底停服且无法靠 IO 自动唤醒，务必先二次确认（见[核心原则 5](#核心原则)）
4. 变更后**再次查询**确认结果已生效（对应[核心原则 2](#核心原则)）

## 能力范围（动作 → CLI 命令）

> 完整命令、参数与等价 SQL 见 [`references/tool-reference.md`](references/tool-reference.md)。下表为速查。

### 工作区（workspace / project）

| 需求 | 命令 |
|------|------|
| 列出 workspace | `projects list` |
| workspace 详情 / 概览 | `projects list --workspace-id ws-... --detail` ／ `projects overview` |
| 创建 workspace | `projects create <name>`（region 走全局/env/profile）。**创建成功后必须主动说明休眠超时并非阻塞询问**，见下方「💤 休眠超时」 |
| 调整算力 / 休眠超时 | `projects compute-settings <ref> --min-cu <n> --max-cu <n> [--suspend-timeout-seconds <秒>]`（底层 ModifyComputeSettings；**设休眠超时用 `--service-type Supabase --min-cu 0.5`**，见下方💤） |
| ⛔ 暂停 / 恢复**整个 workspace**（停机/开机，**高危**，见[核心原则 5](#核心原则)） | `projects stop <ref>` ／ `projects start <ref>` |
| 删除 workspace | `projects delete <ref> --yes` |
| 获取 API Keys | `projects api-keys --workspace-id ws-...` |
| 获取访问地址 / 连接串 | `endpoints list --workspace-id ws-...` ／ `db connection-string --workspace-id ws-...` |

> **💤 休眠超时（SuspendTimeoutSeconds）—— 创建后务必主动说明、非阻塞询问。**
> - **含义**：分支算力**无流量自动休眠（scale-to-zero）前的空闲等待秒数**。到点自动休眠，下次访问 exposeURL（或任意请求）即**自动唤醒**（冷启动）——这是「休眠」而**非**「暂停 workspace」（区别见[下方辨析](#分支branch)与[核心原则 5](#核心原则)）。
> - **取值语义**：`-1` = 显式关闭自动休眠（算力常驻 / 永不休眠）；`0` = 未设置的平台默认（行为上等同常驻）；`300`–`604800` 秒（5 分钟–7 天）= 启用，空闲到点休眠。**新建 workspace 默认不休眠**（`projects list --detail` 显示为 `0`）。想**关闭**已开启的自动休眠就传 `-1`（不是 `0`）。
> - **修改方式**：`projects compute-settings <ref> --service-type Supabase --min-cu 0.5 --max-cu 2 --suspend-timeout-seconds <秒> --yes`。⚠️ 必带 `--yes` + `--min-cu`/`--max-cu`，且 Supabase 服务 min CU 下限 0.5——这几个坑照抄即可，细节见 [tool-reference 的「💤 休眠超时」](references/tool-reference.md)。
> - **创建后协议（非阻塞）**：`projects create` 成功后，**主动向用户解释**上面的含义并**非阻塞地**提示是否设置休眠超时，可直接用这段话：「关于空闲休眠：当前算力常驻、不会自动休眠—稳定但更耗资源。如果想节省算力，可配置空闲自动休眠时间（再次访问无需手动操作，Supabase 自动唤醒），推荐 1 小时。」**推荐 1 小时（`--suspend-timeout-seconds 3600`）**；用户没回应或表示不需要就保持默认不休眠，**不要因此卡住或阻塞**后续流程。

### 分支（branch）

| 需求 | 命令 |
|------|------|
| 列出 / 创建 / 删除分支 | `branches list` ／ `branches create <name>` ／ `branches delete <branch-id>` |
| 查看 / 设默认分支 | `branches get <id>` ／ `branches get-default` ／ `branches set-default <id>` |
| **重启**分支算力（reboot）/ 时间点恢复 | `branches restart <id>` ／ `branches restore <id> --restore-time <ts>` |

> **⚠️ 暂停 / 重启 / 休眠 三者别混淆**（最常见的误判）：
> - **重启**分支算力（"重启""reboot""重启算力"）→ `branches restart <id>`，一条命令搞定；**切勿**用 `projects stop` + `projects start` 模拟（那是整个 workspace 停机再开机）。
> - **休眠 / 唤醒** = 分支算力的**平台自动行为**：空闲到点自动 scale-to-zero、访问即自动唤醒（**无需手动命令**）；阈值可配，详见上方[💤 休眠超时](#工作区workspace--project)。想手动重置算力用 `branches restart`，**别用 `projects stop` 代替**。
> - **⛔ 暂停 / 恢复** = **workspace 级**停机/开机（`projects stop` / `projects start`），影响其下**所有分支**。**高危红线**：停后客户业务彻底不可用且**无法靠 IO 自动唤醒**，必须人工 `projects start`——执行 `projects stop` 前务必复述影响并二次确认（详见[核心原则 5](#核心原则)）。
>
> 一句话记忆：**休眠/重启 → 客户访问能自愈或单命令恢复（低危）；暂停 → 客户访问救不回来，只能人工 start（高危，先确认）。**

### 数据库（database）

| 需求 | 命令 |
|------|------|
| 执行 SQL（行内 / 文件） | `db query "<sql>" --workspace-id ws-...` ／ `db query -f file.sql --workspace-id ws-...` |
| 列出表 / 扩展 / 已应用迁移 | 用 `db query` 跑对应 SQL（见 tool-reference） |
| 应用 schema 变更 | `db query -f file.sql`（即时）／ 声明式见 `db schema declarative` |
| 生成类型 | `gen types --lang typescript --workspace-id ws-... -s public` |
| 安全/性能巡检 | `db advisors --workspace-id ws-...` ／ `inspect db <subcmd>` |

> ⚠️ 本 fork 无独立 `migration` 子命令；schema 变更与提交流程见下方[「数据库 schema 变更与提交」](#数据库-schema-变更与提交)。

### Auth（认证）

> 平台支持 Supabase Authentication。Auth 多在**应用侧**通过 SDK 使用（注册/登录/会话/JWT），管理与配置见火山[Authentication 文档](https://www.volcengine.com/docs/87275/2277072?lang=zh)；SDK 用法见 [`references/app-integration-guide.md`](references/app-integration-guide.md)。

> 🔐 鉴权数据用 `app_metadata`（不可被用户改），**绝不**用 `user_metadata` 做授权判断（见[安全 checklist](#核心原则)）。

### Realtime（实时）

> 平台支持 Supabase Realtime（Postgres Changes / Broadcast / Presence），在应用侧通过 SDK 订阅。配置见火山[Realtime 文档](https://www.volcengine.com/docs/87275/2277058?lang=zh)；SDK 用法见 [`references/app-integration-guide.md`](references/app-integration-guide.md)。

### Edge Functions（边缘函数）

| 需求 | 命令 |
|------|------|
| 列出函数 | `functions list --workspace-id ws-...` |
| 新建函数（本地脚手架） | `functions new <name>` → 编辑 `supabase/functions/<name>/index.ts` |
| 部署函数 | `functions deploy <name> --workspace-id ws-...`（公开访问加 `--no-verify-jwt`） |
| 下载 / 删除函数 | `functions download <name>` ／ `functions delete <name>` |

> 部署从**本地函数目录**进行（`functions new` → 编辑 → `functions deploy`），不再支持单文件/内联代码。编写规范见 [`references/edge-function-dev-guide.md`](references/edge-function-dev-guide.md)。

### Storage（对象存储）

| 需求 | 命令 |
|------|------|
| 列出 / 创建 / 查看 / 删除 bucket | `storage buckets list` ／ `storage buckets create <id> [--public]` ／ `storage buckets get <id>` ／ `storage buckets delete <id>` |
| 对象列出 / 上传下载 | `storage ls <path>` ／ `storage cp <src> <dst>` |
| 对象移动 / 删除 | `storage mv <src> <dst>` ／ `storage rm <file...>` |

> 对象路径形如 `ss:///<bucket>/<path>`，目录操作加 `-r` 递归。

## 数据库 schema 变更与提交

**做 schema 变更用 `db query`（行内或 `-f file.sql`）直接对库执行**，可自由迭代。

- 本 fork **没有独立 `migration` 子命令**，不要套用官方 `supabase migration new` / `apply_migration` 的习惯。
- **变更前后都用只读查询确认**（核心原则 2）。
- **改完跑巡检** → `byted-supabase-cli db advisors --workspace-id ws-...`，修掉安全/性能告警。
- 若变更涉及视图、函数、触发器或 Storage，**回到[安全 checklist](#核心原则)逐条复核**。
- 需要版本化 / 可追溯的 schema 演进时，改用声明式管理：`byted-supabase-cli db schema declarative --help`。

## 注意事项

- 本 fork 无全局只读开关；写操作的安全边界依赖 RLS（anon vs service_role）+ 操作纪律。
- `db query` 默认连接 `--linked` 项目；未 link 时务必显式传 `--workspace-id`（必要时 `--branch-id`）。

## 在线文档

> 对应[核心原则 1](#核心原则)：不确定时先查这些。

- 新功能发布记录（changelog）：https://www.volcengine.com/docs/87275/2105759?lang=zh
- API 发布历史 / API 列表：https://www.volcengine.com/docs/87275/2105870?lang=zh ／ https://www.volcengine.com/docs/87275/2105871?lang=zh
- SDK 发布历史 / 概述：https://www.volcengine.com/docs/87275/2248647?lang=zh ／ https://www.volcengine.com/docs/87275/2248648?lang=zh
- 使用 Database：https://www.volcengine.com/docs/87275/2385100?lang=zh
- 使用 Authentication：https://www.volcengine.com/docs/87275/2277072?lang=zh
- 使用 Realtime：https://www.volcengine.com/docs/87275/2277058?lang=zh
- 使用 Edge Function：https://www.volcengine.com/docs/87275/2288709?lang=zh
- 使用 Storage：https://www.volcengine.com/docs/87275/2277057?lang=zh
- Go SDK：https://www.volcengine.com/docs/87275/2248650?lang=zh ／ Python SDK：https://www.volcengine.com/docs/87275/2375511?lang=zh

## 参考资料

| 文档 | 用途 |
|------|------|
| [`references/tool-reference.md`](references/tool-reference.md) | 命令速查：动作 → CLI + 等价 SQL |
| [`references/workflows.md`](references/workflows.md) | 常见操作流程（巡检 / 变更 / 发布） |
| [`references/sql-playbook.md`](references/sql-playbook.md) | 常用 SQL 示例（CRUD / JOIN / pgvector / RPC） |
| [`references/app-integration-guide.md`](references/app-integration-guide.md) | 接入 TS/Python 应用：SDK 初始化 + CRUD + Auth + Realtime |
| [`references/schema-guide.md`](references/schema-guide.md) | 表结构设计与变更规范 |
| [`references/rls-guide.md`](references/rls-guide.md) | 行级安全（RLS）策略配置 |
| [`references/security-guide.md`](references/security-guide.md) | Supabase 特有安全陷阱 checklist |
| [`references/pg-best-practices/index.md`](references/pg-best-practices/index.md) | Postgres 性能与最佳实践（索引 / 连接 / 锁 / 监控等） |
| [`references/edge-function-dev-guide.md`](references/edge-function-dev-guide.md) | Edge Function 编写与部署 |

> 📚 **Postgres 最佳实践细分**（均由上方 [`index.md`](references/pg-best-practices/index.md) 索引，可按需直达）：[`query.md`](references/pg-best-practices/query.md) · [`conn.md`](references/pg-best-practices/conn.md) · [`security.md`](references/pg-best-practices/security.md) · [`schema.md`](references/pg-best-practices/schema.md) · [`lock.md`](references/pg-best-practices/lock.md) · [`data.md`](references/pg-best-practices/data.md) · [`monitor.md`](references/pg-best-practices/monitor.md) · [`advanced.md`](references/pg-best-practices/advanced.md)

> 💡 **典型工作流**：先用 CLI 创建 workspace / 建表 / 配置 RLS，再参考应用集成文档在业务代码中集成 Supabase SDK。
</content>
</invoke>
