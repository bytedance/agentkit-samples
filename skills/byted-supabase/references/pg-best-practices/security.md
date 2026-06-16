# 安全与 RLS（security）

行级安全策略、权限管理与认证模式。

> 本目录 SQL 通过 `byted-supabase-cli db query "<sql>" --workspace-id ws-...` 执行；改完跑 `byted-supabase-cli db advisors` 巡检。更完整的 Supabase 特有安全陷阱见 `../security-guide.md`，RLS 配置模板见 `../rls-guide.md`。
> 📌 译自 Supabase 官方 agent skills（MIT, © Supabase），适配火山引擎 Supabase 版。

## 目录

- 多租户数据务必启用行级安全（RLS）
- 把 RLS 策略写得跑得快
- 坚持最小权限原则

## 多租户数据务必启用行级安全（RLS）

**影响（Impact）：** CRITICAL — 把租户隔离下沉到数据库强制执行，从根上堵住数据泄露。

多租户系统里，隔离这件事不能只靠应用层那句 `where` 条件。行级安全（RLS）把访问控制规则交给数据库本身把关，无论查询从哪儿发出，用户都只能拿到属于自己的那部分数据。

**错误做法（只靠应用层过滤）：**

只要应用代码出一个 bug，或者有人绕过了那层过滤逻辑，全表数据就一览无余——这道防线太脆。

```sql
-- 仅依赖应用层做过滤
select * from orders where user_id = $current_user_id;

-- 一旦逻辑出错或被绕过，所有数据都会暴露！
select * from orders;  -- 会返回全部订单
```

**正确做法（由数据库强制实施 RLS）：**

开启 RLS 后，策略会自动套到每一条查询上；再用 `force row level security` 把表的 owner（所有者）也一并管住，谁都别想绕过去。

```sql
-- 在表上启用 RLS
alter table orders enable row level security;

-- 创建策略，让用户只能看到自己的订单
create policy orders_user_policy on orders
  for all
  using (user_id = current_setting('app.current_user_id')::bigint);

-- 连表 owner 也强制走 RLS
alter table orders force row level security;

-- 设置用户上下文后再查询
set app.current_user_id = '123';
select * from orders;  -- 只返回用户 123 的订单
```

> ⚠️ **验证 RLS 时别用表 owner / 超级角色直连**：`force row level security` 能管住表 **owner（所有者）**，但带 `BYPASSRLS` 属性的角色（火山引擎 Supabase 版的 `postgres` 连接角色就带这个属性）仍会绕过所有 RLS——你会看到全部行，误以为策略没生效。要验证策略，请切到不带 BYPASSRLS 的角色，例如 `set local role authenticated;` 再查，结束 `reset role;`。

针对 authenticated 角色的策略写法：

```sql
create policy orders_user_policy on orders
  for all
  to authenticated
  using (user_id = auth.uid());
```

Reference: [Row Level Security](https://supabase.com/docs/guides/database/postgres/row-level-security)

## 把 RLS 策略写得跑得快

**影响（Impact）：** HIGH — 用对写法，RLS 查询能快上 5-10 倍。

RLS 策略写得糙，性能会塌得很惨。关键就两点：把函数调用包进子查询让它只算一次，以及给策略里用到的列加索引。

**错误做法（每一行都要调一次函数）：**

```sql
create policy orders_policy on orders
  using (auth.uid() = user_id);  -- auth.uid() 会被逐行调用！

-- 100 万行就意味着 auth.uid() 被调 100 万次
```

**正确做法（用 SELECT 把函数包起来）：**

包进 `(select ...)` 之后，规划器会把结果当成常量算一次再缓存下来，逐行重复计算的开销就没了。

```sql
create policy orders_policy on orders
  using ((select auth.uid()) = user_id);  -- 只算一次（计划里体现为 InitPlan），结果被缓存

-- 大表上常能快数倍到一个数量级（实测约 10x，量级取决于是否走索引与计划形态；
-- 注意：PG 较新版本里，裸写 auth.uid() 若能被内联进 Index Cond 也不慢，
-- 逐行重算的惩罚主要出现在 seq scan / filter 场景——但用 (select ...) 包一层总是更稳）
```

复杂的权限判断交给 security definer 函数：

`SECURITY DEFINER` 函数以创建者的权限运行，会绕过它所访问的任意表上的 RLS——这正是它适合做内部查找的原因，但用错了也同样危险。务必在函数体内部显式校验一次 `auth.uid()`，把它放在不对外暴露的 schema 里，并对任何不该直接调用它的角色 `revoke` 掉 `EXECUTE` 权限。

```sql
-- 在私有 schema 里创建辅助函数
create or replace function private.is_team_member(team_id bigint)
returns boolean
language sql
security definer
set search_path = ''
as $$
  select exists (
    select 1 from public.team_members
    -- 始终在函数内部校验调用方的身份
    where team_id = $1 and user_id = (select auth.uid())
  );
$$;

-- 回收 public 角色的直接执行权限
revoke execute on function private.is_team_member(bigint) from PUBLIC, anon, authenticated, service_role;

-- 在策略中使用（走索引查找，而非逐行判断）
create policy team_orders_policy on orders
  using ((select private.is_team_member(team_id)));
```

策略里用到的列，一律记得加索引：

```sql
create index orders_user_id_idx on orders (user_id);
```

Reference: [RLS Performance](https://supabase.com/docs/guides/database/postgres/row-level-security#rls-performance-recommendations)

## 坚持最小权限原则

**影响（Impact）：** MEDIUM — 收窄攻击面，审计链路也更清晰。

只授予完成工作所需的最小权限。应用查询绝不能用超级用户身份去跑。

**错误做法（权限给得太宽）：**

应用直接用超级用户连库，或者把 `ALL` 一股脑授给应用角色——这种情况下，任何一次 SQL 注入都可能酿成灾难：一句 `drop table users` 就能顺着级联把整个库带塌。

```sql
-- 应用使用超级用户连接
-- 或者把 ALL 权限授给应用角色
grant all privileges on all tables in schema public to app_user;
grant all privileges on all sequences in schema public to app_user;

-- 任何一次 SQL 注入都会演变成灾难
-- drop table users; 会级联波及一切
```

**正确做法（精确、按需地授予）：**

按读、写拆出独立角色，各自只拿够用的权限，再让登录角色从中继承。这样即便某个角色被攻破，影响也被框死在很小的范围内。

```sql
-- 创建一个默认没有任何权限的角色
create role app_readonly nologin;

-- 只在特定表上授予 SELECT
grant usage on schema public to app_readonly;
grant select on public.products, public.categories to app_readonly;

-- 创建写入角色，权限范围有限
create role app_writer nologin;
grant usage on schema public to app_writer;
grant select, insert, update on public.orders to app_writer;
grant usage on sequence orders_id_seq to app_writer;
-- 不授予 DELETE 权限

-- 登录角色从上面这些角色继承权限
create role app_user login password 'xxx';
grant app_writer to app_user;
```

回收 public 的默认权限：

```sql
-- 回收 public 的默认访问权限
revoke all on schema public from public;
revoke all on all tables in schema public from public;
```

Reference: [Roles and Privileges](https://supabase.com/blog/postgres-roles-and-privileges)
