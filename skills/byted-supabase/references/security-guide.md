# Supabase 安全 checklist（特有陷阱）

> 📌 本文内容改编并翻译自 Supabase 官方 agent skills（MIT License, Copyright © Supabase），并适配火山引擎 Supabase 版（`byted-supabase-cli`、workspace/branch 模型）。署名见文末。

凡涉及 **Auth、RLS、视图、Storage 或用户数据**的任务，落地前逐条过一遍。这些都是 **Supabase 特有、会静默制造漏洞**的陷阱 —— 不报错，但门是开的。

所有 SQL 通过 `byted-supabase-cli db query "<sql>" --workspace-id ws-...`（或 `-f file.sql`）执行；改完务必跑 `byted-supabase-cli db advisors --workspace-id ws-...` 巡检。

---

## 目录

- 认证与会话安全
- API Key 与客户端暴露
- RLS、视图与特权数据库代码
- Storage 访问控制
- 依赖与供应链安全
- 兜底

## 1. 认证与会话安全

### 绝不用 `user_metadata` 做鉴权判断

在 Supabase 中，`raw_user_meta_data`（即 `auth.jwt()` 里的 `user_metadata`）**用户自己可改**，把它用于 RLS 策略或任何授权逻辑都可被伪造。**鉴权数据一律存 `raw_app_meta_data` / `app_metadata`。**

```sql
-- ❌ 危险：user_metadata 用户可改
create policy admin_only on reports for select
  using ( (auth.jwt() -> 'user_metadata' ->> 'role') = 'admin' );

-- ✅ 正确：用 app_metadata（用户不可改）
create policy admin_only on reports for select
  to authenticated
  using ( (auth.jwt() -> 'app_metadata' ->> 'role') = 'admin' );
```

### 删除用户不会让已签发的 access token 失效

删用户**不会**吊销其现有 token。敏感操作前先 sign out / 吊销会话；JWT 过期时间设短；要严格保证时，在敏感操作里校验 `session_id` 是否还在 `auth.sessions` 中。

### `app_metadata` / `auth.jwt()` 的声明不一定是最新的

只有用户的 token 刷新后，JWT 里的声明才会更新。授权依赖这些声明时要意识到这点。

---

## 2. API Key 与客户端暴露

### `service_role` / 密钥绝不进前端

前端用 publishable key（旧的 `anon` key 仅作兼容）。`service_role` 拥有完整权限、**绕过 RLS**，**仅后端使用**。

- 在 Next.js 里，任何 `NEXT_PUBLIC_` 前缀的环境变量都会发到浏览器，**绝不**把 `service_role` 放进去。
- `byted-supabase-cli projects api-keys` 返回的 `service_role` 不要回显给前端或写进客户端代码；非必要不要打印完整密钥。

---

## 3. RLS、视图与特权数据库代码

### 视图默认绕过 RLS

视图以视图**创建者**的权限运行，会绕过底层表的 RLS。

```sql
-- ✅ PG15+：让视图以调用者权限执行，从而尊重 RLS
create view public.my_orders with (security_invoker = true) as
  select * from public.orders;
```

更低版本的 Postgres：从 `anon` / `authenticated` 收回视图权限，或把视图放进**未暴露的 schema**。

### `auth.role()` 已弃用 —— 改用 `TO` 子句

Supabase 已弃用 `auth.role()`，改为在策略上直接用 `TO authenticated` / `TO anon` 指定目标角色。

除弃用外更危险的是：一旦开启**匿名登录**，匿名用户也携带 `authenticated` 这个 Postgres 角色，`auth.role() = 'authenticated'` 会**静默通过**，无论用户是否真正登录。

```sql
-- ❌ 弃用且危险，不要用
create policy "example" on table_name for select
  using ( auth.role() = 'authenticated' );

-- ✅ 用 TO 子句
create policy "example" on table_name for select
  to authenticated
  using ( true );
```

### 只写 `TO authenticated` 是"认证而非授权"（BOLA / IDOR）

`TO authenticated` 只校验角色，**不限制能访问哪些行**。正确做法是配上所有权谓词：

```sql
create policy "example" on table_name for select
  to authenticated
  using ( (select auth.uid()) = user_id );
```

### UPDATE 策略要同时有 `USING` 和 `WITH CHECK`

缺 `WITH CHECK`，用户能把某行的 `user_id` 改成别人的：

```sql
create policy "example" on table_name for update
  to authenticated
  using ( (select auth.uid()) = user_id )
  with check ( (select auth.uid()) = user_id );
```

### UPDATE 需要 SELECT 策略

RLS 下 UPDATE 要先 SELECT 到行。**没有 SELECT 策略时，更新静默返回 0 行**——不报错，也不改任何东西。

### `SECURITY DEFINER` 函数绕过 RLS

`SECURITY DEFINER` 函数以**创建者**权限运行（通常是带 `bypassrls` 的 `postgres`）。**绝不**用加 `SECURITY DEFINER` 的方式去"解决"权限报错——它会静默移除访问控制却不解决根因。优先 `SECURITY INVOKER`。

### `public` 下的 `SECURITY DEFINER` 函数对所有角色可调用

Postgres 默认对每个新函数把 `EXECUTE` 授给 `PUBLIC`，所以 `public` schema 下任何 `SECURITY DEFINER` 函数都是 `anon` / `authenticated`（继承自 `PUBLIC`）可直接调用的公开端点。确实需要 `SECURITY DEFINER` 时（如绕过 RLS 查内部表）：

- 函数放进**未暴露 schema**；
- 函数体内**始终做 `auth.uid()` 检查**；
- 从不该直接调用的角色收回 `EXECUTE`；
- 改完跑 `db advisors`。

```sql
create or replace function private.is_team_member(team_id bigint)
returns boolean
language sql
security definer
set search_path = ''
as $$
  select exists (
    select 1 from public.team_members
    where team_id = $1 and user_id = (select auth.uid())  -- 始终校验调用者身份
  );
$$;

revoke execute on function private.is_team_member(bigint) from PUBLIC, anon, authenticated, service_role;
```

---

## 4. Storage 访问控制

### Storage upsert 需要 INSERT + SELECT + UPDATE 三个权限

只给 INSERT 能新上传，但**覆盖上传（upsert）会静默失败**。三个权限都要给。

---

## 5. 依赖与供应链安全

### 固定依赖版本并提交 lockfile

安装 Supabase 相关包（`@supabase/supabase-js`、`@supabase/ssr`、`supabase-py` 等）时固定版本、提交 lockfile。

---

## 兜底

上面没覆盖的安全问题，查 Supabase 官方产品安全索引：
`https://supabase.com/docs/guides/security/product-security.md`，以及火山引擎 [Database 文档](https://www.volcengine.com/docs/87275/2385100?lang=zh)。

---

> **Attribution**：本文改编自 Supabase 官方 agent skills（`supabase/agent-skills`，MIT License，Copyright © Supabase），翻译为中文并适配火山引擎 Supabase 版。
