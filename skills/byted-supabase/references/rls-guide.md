# Row Level Security (RLS) 策略配置指南

> 🔴 **所有暴露 schema（默认含 `public`）里的表必须启用 RLS**。即使是公开数据表，也必须启用 RLS 并配置允许公开访问的策略。不启用 RLS 的表，任何人都可以通过 anon key 直接读写所有数据，这是严重的安全隐患。

> 📌 本文 SQL 写法对齐 Supabase 官方最新安全建议（MIT，Copyright © Supabase）。更完整的安全陷阱见 [`security-guide.md`](security-guide.md)。

---

## 目录

- 写法要点（务必遵守）
- 策略选择（决策表）
- 操作方式
- 策略 SQL 模板
- user_id 字段定义
- RLS 性能
- 检查当前 RLS 状态
- 常见错误

## 写法要点（务必遵守）

这几条是 Supabase RLS 的硬规则，违反会静默制造漏洞或性能问题：

1. **用 `TO authenticated` / `TO anon` 指定角色，不要用 `auth.role()`。** `auth.role()` 已弃用；且开启匿名登录后，匿名用户也带 `authenticated` 角色，`auth.role() = 'authenticated'` 会**静默失效**。
2. **`TO authenticated` 必须配所有权谓词。** 只写 `TO authenticated` 是"认证而非授权"（BOLA/IDOR），任何登录用户都能看所有行。
3. **把 `auth.uid()` 包进子查询：`(select auth.uid())`。** 否则每行都会调用一次，百万行就调用百万次；包一层后只算一次，大表上快 100×+。
4. **UPDATE 策略同时写 `USING` 和 `WITH CHECK`。** 缺 `WITH CHECK`，用户能把行的 `user_id` 改成别人的。
5. **UPDATE 需要 SELECT 策略。** RLS 下 UPDATE 要先 SELECT 到行；缺 SELECT 策略会静默返回 0 行。
6. **RLS 策略里用到的列要建索引**（如 `user_id`）。

---

## 策略选择（决策表）

根据数据访问需求，选择对应的策略场景：

| 场景 | 说明 | 需要 user_id？ | 示例 |
|------|------|:-----------:|------|
| **A. 公开读写** | 所有人可读写 | ❌ | 公告、公共配置 |
| **B. 公开读 + 登录写** | 所有人可读，仅登录用户可写 | ❌ | 博客文章、商品展示 |
| **C. 仅登录用户** | 登录用户才能读写 | ❌ | 内部数据、会员内容 |
| **D. 用户私有数据** | 用户只能操作自己的数据 | ✅ | 用户订单、个人笔记、私人设置 |

> ⚠️ **常见误解**：`user_id` 字段**不是** RLS 的前提条件。只有场景 D（用户私有数据）才需要 `user_id`。

---

## 操作方式

所有 RLS SQL 均可通过 `byted-supabase-cli db query` 直接执行：

```bash
byted-supabase-cli db query "ALTER TABLE my_table ENABLE ROW LEVEL SECURITY;" --workspace-id ws-xxxx
```

对于成组、需要复用的 RLS 变更，建议写入 `.sql` 文件后整体应用：

```bash
# rls_migration.sql 内含 ENABLE RLS + 一组 CREATE POLICY
byted-supabase-cli db query -f ./rls_migration.sql --workspace-id ws-xxxx
```

> 改完跑巡检：`byted-supabase-cli db advisors --workspace-id ws-xxxx`。需要版本化 / 可追溯的策略演进时，改用声明式管理：`byted-supabase-cli db schema declarative --help`。

---

## 策略 SQL 模板

> 💡 **命名规范**：Policy 名称应包含表名前缀（如 `posts_allow_public_read`），便于在多表环境中区分管理。以下模板使用 `<table_name>` 作为占位符，实际使用时替换为真实表名。

> ⚠️ **幂等性**：`CREATE POLICY` 在策略已存在时会报错。如需重新配置，先删除再创建：
> ```sql
> DROP POLICY IF EXISTS "policy_name" ON <table_name>;
> CREATE POLICY "policy_name" ON <table_name> ...;
> ```
> 修改已有表（如加字段）时，已有的 RLS 策略仍然生效，**无需重复配置**。

### 场景 A：公开读写

公开数据也要启用 RLS，并显式开放给 `anon` 和 `authenticated`：

```sql
ALTER TABLE <table_name> ENABLE ROW LEVEL SECURITY;

CREATE POLICY "<table_name>_public_select" ON <table_name>
  FOR SELECT TO anon, authenticated USING (true);

CREATE POLICY "<table_name>_public_insert" ON <table_name>
  FOR INSERT TO anon, authenticated WITH CHECK (true);

CREATE POLICY "<table_name>_public_update" ON <table_name>
  FOR UPDATE TO anon, authenticated USING (true) WITH CHECK (true);

CREATE POLICY "<table_name>_public_delete" ON <table_name>
  FOR DELETE TO anon, authenticated USING (true);
```

### 场景 B：公开读 + 登录写

```sql
ALTER TABLE <table_name> ENABLE ROW LEVEL SECURITY;

CREATE POLICY "<table_name>_public_select" ON <table_name>
  FOR SELECT TO anon, authenticated USING (true);

CREATE POLICY "<table_name>_auth_insert" ON <table_name>
  FOR INSERT TO authenticated WITH CHECK (true);

CREATE POLICY "<table_name>_auth_update" ON <table_name>
  FOR UPDATE TO authenticated USING (true) WITH CHECK (true);

CREATE POLICY "<table_name>_auth_delete" ON <table_name>
  FOR DELETE TO authenticated USING (true);
```

### 场景 C：仅登录用户

```sql
ALTER TABLE <table_name> ENABLE ROW LEVEL SECURITY;

CREATE POLICY "<table_name>_auth_select" ON <table_name>
  FOR SELECT TO authenticated USING (true);

CREATE POLICY "<table_name>_auth_insert" ON <table_name>
  FOR INSERT TO authenticated WITH CHECK (true);

CREATE POLICY "<table_name>_auth_update" ON <table_name>
  FOR UPDATE TO authenticated USING (true) WITH CHECK (true);

CREATE POLICY "<table_name>_auth_delete" ON <table_name>
  FOR DELETE TO authenticated USING (true);
```

> ⚠️ 场景 C 只校验"是否登录"。若还要限制"只能操作自己的数据"，用场景 D 的所有权谓词。

### 场景 D：用户私有数据

> ⚠️ 表中必须包含 `user_id` 字段（见下方 [user_id 字段定义](#user_id-字段定义)）。注意 `auth.uid()` 包进 `(select ...)`，并对 UPDATE 写全 `USING` + `WITH CHECK`。

```sql
ALTER TABLE <table_name> ENABLE ROW LEVEL SECURITY;

CREATE POLICY "<table_name>_owner_select" ON <table_name>
  FOR SELECT TO authenticated
  USING ( (select auth.uid()) = user_id );

CREATE POLICY "<table_name>_owner_insert" ON <table_name>
  FOR INSERT TO authenticated
  WITH CHECK ( (select auth.uid()) = user_id );

CREATE POLICY "<table_name>_owner_update" ON <table_name>
  FOR UPDATE TO authenticated
  USING ( (select auth.uid()) = user_id )
  WITH CHECK ( (select auth.uid()) = user_id );

CREATE POLICY "<table_name>_owner_delete" ON <table_name>
  FOR DELETE TO authenticated
  USING ( (select auth.uid()) = user_id );
```

---

## user_id 字段定义

仅在场景 D（用户私有数据）时，需要在表中添加 `user_id` 字段。

### 建表时添加

```sql
CREATE TABLE <table_name> (
  id bigserial PRIMARY KEY,
  user_id uuid NOT NULL DEFAULT auth.uid(),
  -- 其他字段 ...
  created_at timestamptz NOT NULL DEFAULT now()
);

-- 务必给 RLS 谓词用到的列建索引
CREATE INDEX IF NOT EXISTS ix_<table_name>_user_id ON <table_name>(user_id);
```

### 为已有表添加

```sql
ALTER TABLE <table_name>
  ADD COLUMN user_id uuid NOT NULL DEFAULT auth.uid();

CREATE INDEX IF NOT EXISTS ix_<table_name>_user_id ON <table_name>(user_id);
```

> 💡 使用 `auth.uid()` 作为默认值，Supabase 会在插入时自动填充当前用户 ID，防止客户端伪造。

---

## RLS 性能

RLS 谓词每行都会求值，写不好会严重拖慢查询：

- **把函数包进子查询**：`(select auth.uid()) = user_id` 而非 `auth.uid() = user_id`（只算一次，大表快 100×+）。
- **给谓词列建索引**：`CREATE INDEX ... ON <table>(user_id);`。
- **复杂多表判断用 `SECURITY DEFINER` 辅助函数**（放进未暴露 schema、函数体内做 `auth.uid()` 检查、收回多余 `EXECUTE`），避免在策略里跨表关联导致的逐行开销。详见 [`security-guide.md`](security-guide.md) 与 [`pg-best-practices/security.md`](pg-best-practices/security.md)。

---

## 检查当前 RLS 状态

查看哪些表已启用 RLS：

```bash
byted-supabase-cli db query "SELECT schemaname, tablename, rowsecurity FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename;" --workspace-id ws-xxxx
```

查看已有的 Policy：

```bash
byted-supabase-cli db query "SELECT schemaname, tablename, policyname, permissive, roles, cmd, qual, with_check FROM pg_policies WHERE schemaname = 'public' ORDER BY tablename, policyname;" --workspace-id ws-xxxx
```

---

## 常见错误

```sql
-- ❌ 错误：忘记启用 RLS（表对所有人完全开放）
CREATE TABLE posts (id serial PRIMARY KEY, title text);
-- 缺少 ALTER TABLE posts ENABLE ROW LEVEL SECURITY;

-- ❌ 错误：启用了 RLS 但没有创建策略（所有人都无法访问）
ALTER TABLE posts ENABLE ROW LEVEL SECURITY;
-- 缺少 CREATE POLICY ...

-- ❌ 错误：用已弃用的 auth.role()（开启匿名登录后静默失效）
CREATE POLICY "auth_write" ON posts FOR INSERT
  WITH CHECK (auth.role() = 'authenticated');
-- ✅ 正确：用 TO 子句
CREATE POLICY "auth_write" ON posts FOR INSERT
  TO authenticated WITH CHECK (true);

-- ❌ 错误：只写 TO authenticated，任何登录用户都能改所有行（IDOR）
CREATE POLICY "bad_update" ON notes FOR UPDATE TO authenticated USING (true);
-- ✅ 正确：配所有权谓词 + WITH CHECK
CREATE POLICY "owner_update" ON notes FOR UPDATE TO authenticated
  USING ((select auth.uid()) = user_id)
  WITH CHECK ((select auth.uid()) = user_id);

-- ❌ 错误：公开表也要求 user_id（增加了不必要的复杂度）
CREATE POLICY "public_read" ON announcements FOR SELECT
  USING (auth.uid() = user_id);
-- ✅ 正确：公开表用 USING (true) + 指定角色
CREATE POLICY "public_read" ON announcements FOR SELECT
  TO anon, authenticated USING (true);
```
