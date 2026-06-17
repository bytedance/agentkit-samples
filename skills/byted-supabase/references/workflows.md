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

## 6. Pages 静态站点发布

**A. 手动链路 ——「Supabase 已就绪（workspace / SQL / Edge Functions 都好了），只部署前端」。⚠️ 这条完全不新建 Supabase。**

```bash
# 1. 上传构建产物，记下返回的 ProjectDeployResourceID
byted-supabase-cli pages upload ./dist.zip -o json
# 2. 先建 Pages 项目但不急着部署（拿到 PagesProjectID）
byted-supabase-cli pages create my-site --resource-id <resource-id> --no-deploy -o json
# 3. 【必做】绑定到“已有”的 workspace 分支 —— 建立 Pages↔Supabase 关联并注入 env，跳过则前端连不上后端
byted-supabase-cli pages bind <pages-project-id> --workspace-id <现有ws> [--branch-id br-...] --framework-prefix NEXT_PUBLIC_
# 4. 绑定后再部署，第一次部署即带上 Supabase env
byted-supabase-cli pages deploy <pages-project-id> --resource-id <resource-id>
# 5. 后续：env 变更重推 / 上传新产物发新部署 / 看历史
byted-supabase-cli pages sync --workspace-id <现有ws>
byted-supabase-cli pages deploy <pages-project-id> --resource-id <new-resource-id>
byted-supabase-cli pages deploy list <pages-project-id> -o json
```

> 🔗 **第 3 步 `pages bind` 是必做的**：只要前端要连这个 Supabase，就必须 bind 建立关联、由平台注入 env，不能省。（极少数情况——env 已在本地构建时硬编码进 `dist.zip`、确实不需要平台注入——才可能跳过，但仍建议 bind 以建立两者的关联关系。）

**B. 一键链路 ——「从零开始，前端 + 新建 Supabase 后端一把梭」。⚠️ 这条会新建一个全新 Supabase workspace（不可复用现有的）。**

```bash
# 目录约定：frontend/（前端）、backend/functions/<slug>/（Edge Functions）、migration/（SQL）
# 上传前端 → 建 Pages 项目 → 新建 workspace → 跑迁移/部署函数 → 绑定 → 部署（阻塞到成功）
byted-supabase-cli pages fast create my-app \
  --file-path ./frontend \
  --migrations-init ./migration \
  --functions-init ./backend \
  --framework-prefix NEXT_PUBLIC_
# 全程数分钟，过程会打印 ProjectDeployResourceID / PagesProjectID / WorkspaceID / BranchID / DeployID
```

**🎬 想直接体验?用官方 demo(Next.js + Supabase「资料盒子」)一条命令拉起完整应用:**

```bash
# 下载解压 → 解压后为 nextjs-supabase-filebox/{frontend,backend,migrations}（注意 migrations 是复数）
curl -fsSL https://lf3-static.bytednsdoc.com/obj/eden-cn/whkph/ljhwZthlaukjlkulzlp/nextjs-supabase-filebox.zip -o filebox.zip && unzip -q filebox.zip
byted-supabase-cli pages fast create my-filebox \
  --file-path nextjs-supabase-filebox/frontend \
  --functions-init nextjs-supabase-filebox/backend \
  --migrations-init nextjs-supabase-filebox/migrations \
  --framework-prefix NEXT_PUBLIC_
```

**部署完怎么访问？**（A / B 通用）部署成功后用 `pages binding` 取预览地址：

```bash
byted-supabase-cli pages binding --workspace-id <ws> -o json
# → 取 PagesProject.PreviewDomain，即站点预览 URL
```

> ⚠️ `PreviewDomain` 是**短效、一次性**的（带 `iga_token`，基本只能打开一次、很快失效）：拿到**立刻**发给用户打开，**别缓存/复用**；要再次访问就**重跑 `pages binding`** 取新的。`deploy` 命令本身不返回访问地址。
