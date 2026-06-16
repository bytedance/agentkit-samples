# Workflows

> 命令统一用 `byted-supabase-cli`（已别名为 `supabase` 亦可）。目标用 `--workspace-id ws-...`（必要时 `--branch-id br-...`）。
>
> 📖 不确定命令/参数时先查 `--help` 或火山在线文档（见 SKILL.md「在线文档」）。

## 1. 初次巡检

```bash
byted-supabase-cli projects list -o json                                  # 1. 看有哪些 workspace
byted-supabase-cli projects list --workspace-id ws-xxxx --detail -o json  # 2. 看目标状态
byted-supabase-cli endpoints list --workspace-id ws-xxxx -o json          # 3. 取访问地址
byted-supabase-cli projects api-keys --workspace-id ws-xxxx -o json       #    取 anon / service_role key
```

## 1.5 创建 workspace 并按需设置休眠超时

```bash
byted-supabase-cli projects create my-project -o json   # 1. 创建（region 走 profile/env，无需重复 --region；默认不休眠，算力常驻）
```

> 💡 region **默认走 `login`/`configure` 时写进 profile 的地域**（缺省 `cn-beijing`）。用户没特别指定地域时**不要画蛇添足加 `--region`**；只有用户明确要建到其他地域（如 `cn-shanghai`）才显式加 `--region cn-shanghai`。其余命令同理。

2. **创建成功后**：主动向用户解释 **SuspendTimeoutSeconds（休眠超时）**并**非阻塞地**询问是否设置，可直接用这段话：「关于空时休眠：当前为 0，即算力常驻、不会自动休眠—稳定但更耗资源。如果想节省算力，可配置空闲自动休眠时间（再次访问无需手动操作，Supabase 自动唤醒），推荐 1 小时。」用户没回应或不需要就保持默认，别卡流程。
3. 用户要设置时（以 1 小时为例）：

```bash
# ⚠️ 三个必带项：① --yes（compute-settings 是变更操作，非交互/agent 模式缺它直接报
#    "missing required flag: --yes"）；② --service-type Supabase（休眠作用于用户面的 Supabase 服务）；
#    ③ --min-cu/--max-cu：Supabase 服务的 min CU 下限是 0.5，必须 ≥0.5（用 0.5/2 即可；
#    千万别用 `projects list --detail` 查到的 0.25 回填——那是 Database 服务的值，<0.5 会被拒为 InvalidParameter）。
byted-supabase-cli projects compute-settings ws-xxxx --service-type Supabase --min-cu 0.5 --max-cu 2 --suspend-timeout-seconds 3600 --yes
```

## 2. 安全变更流程（用分支隔离）

```bash
byted-supabase-cli branches list --workspace-id ws-xxxx -o json           # 1. 确认现状
byted-supabase-cli branches create dev --workspace-id ws-xxxx             # 2. 建隔离分支
# 3. 在分支上做变更（SQL / function / storage），用 --branch-id 指向该分支
byted-supabase-cli db query -f change.sql --workspace-id ws-xxxx --branch-id br-yyyy
byted-supabase-cli db query "SELECT ..." --workspace-id ws-xxxx --branch-id br-yyyy  # 4. 验证
# 5. 出问题可时间点恢复或删除分支
byted-supabase-cli branches restore br-yyyy --restore-time <RFC3339> --workspace-id ws-xxxx
byted-supabase-cli branches delete br-yyyy --workspace-id ws-xxxx
```

## 3. 数据库排障

```bash
# 列表 / 扩展（无专用子命令，用 db query 跑 SQL）
byted-supabase-cli db query "SELECT table_schema, table_name FROM information_schema.tables WHERE table_schema NOT IN ('pg_catalog','information_schema') ORDER BY 1,2;" --workspace-id ws-xxxx
byted-supabase-cli db query "SELECT name, installed_version FROM pg_available_extensions WHERE installed_version IS NOT NULL ORDER BY name;" --workspace-id ws-xxxx
# 临时查询
byted-supabase-cli db query "SELECT ..." --workspace-id ws-xxxx
# 安全/性能巡检
byted-supabase-cli db advisors --workspace-id ws-xxxx
byted-supabase-cli inspect db long-running-queries --workspace-id ws-xxxx
# 可复用的 schema 变更：写入文件后应用
byted-supabase-cli db query -f migration.sql --workspace-id ws-xxxx
```

## 4. Edge Function 发布

```bash
byted-supabase-cli functions list --workspace-id ws-xxxx -o json   # 1. 看现状
byted-supabase-cli functions new my-api                            # 2. 生成本地脚手架
# 3. 编辑 supabase/functions/my-api/index.ts
byted-supabase-cli functions deploy my-api --workspace-id ws-xxxx  # 4. 部署（Webhook 等公开 API 加 --no-verify-jwt）
byted-supabase-cli functions list --workspace-id ws-xxxx -o json   # 5. 确认发布结果
```

## 5. Storage 管理

```bash
byted-supabase-cli storage buckets list --workspace-id ws-xxxx -o json          # 1. 现有 bucket
byted-supabase-cli storage buckets get <bucket-id> --workspace-id ws-xxxx -o json # 2. 查看配置
byted-supabase-cli storage buckets create uploads --public --workspace-id ws-xxxx # 3. 创建
# 删除前确认数据影响
byted-supabase-cli storage buckets delete uploads --workspace-id ws-xxxx
```
</content>
