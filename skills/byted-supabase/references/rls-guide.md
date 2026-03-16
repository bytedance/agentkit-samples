# Row Level Security (RLS) 策略配置指南

> 🔴 **所有表必须启用 RLS**。即使是公开数据表，也必须启用 RLS 并配置允许公开访问的策略。不启用 RLS 的表任何人都可以通过 anon key 直接读写所有数据，这是严重的安全隐患。

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

所有 RLS SQL 均可通过本 Skill 的 `execute-sql` 直接执行：

```bash
uv run ./scripts/call_volcengine_supabase.py execute-sql \
  --workspace-id ws-xxxx \
  --query "ALTER TABLE my_table ENABLE ROW LEVEL SECURITY;"
```

对于需要版本管理的 RLS 变更，建议通过 `apply-migration` 执行：

```bash
uv run ./scripts/call_volcengine_supabase.py apply-migration \
  --workspace-id ws-xxxx \
  --name enable_rls_for_posts \
  --query-file ./rls_migration.sql
```

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

```sql
ALTER TABLE <table_name> ENABLE ROW LEVEL SECURITY;

CREATE POLICY "<table_name>_allow_public_select" ON <table_name>
  FOR SELECT USING (true);

CREATE POLICY "<table_name>_allow_public_insert" ON <table_name>
  FOR INSERT WITH CHECK (true);

CREATE POLICY "<table_name>_allow_public_update" ON <table_name>
  FOR UPDATE USING (true) WITH CHECK (true);

CREATE POLICY "<table_name>_allow_public_delete" ON <table_name>
  FOR DELETE USING (true);
```

### 场景 B：公开读 + 登录写

```sql
ALTER TABLE <table_name> ENABLE ROW LEVEL SECURITY;

CREATE POLICY "<table_name>_allow_public_select" ON <table_name>
  FOR SELECT USING (true);

CREATE POLICY "<table_name>_auth_insert" ON <table_name>
  FOR INSERT WITH CHECK (auth.role() = 'authenticated');

CREATE POLICY "<table_name>_auth_update" ON <table_name>
  FOR UPDATE USING (auth.role() = 'authenticated')
  WITH CHECK (auth.role() = 'authenticated');

CREATE POLICY "<table_name>_auth_delete" ON <table_name>
  FOR DELETE USING (auth.role() = 'authenticated');
```

### 场景 C：仅登录用户

```sql
ALTER TABLE <table_name> ENABLE ROW LEVEL SECURITY;

CREATE POLICY "<table_name>_auth_select" ON <table_name>
  FOR SELECT USING (auth.role() = 'authenticated');

CREATE POLICY "<table_name>_auth_insert" ON <table_name>
  FOR INSERT WITH CHECK (auth.role() = 'authenticated');

CREATE POLICY "<table_name>_auth_update" ON <table_name>
  FOR UPDATE USING (auth.role() = 'authenticated')
  WITH CHECK (auth.role() = 'authenticated');

CREATE POLICY "<table_name>_auth_delete" ON <table_name>
  FOR DELETE USING (auth.role() = 'authenticated');
```

### 场景 D：用户私有数据

> ⚠️ 表中必须包含 `user_id` 字段（见下方 [user_id 字段定义](#user_id-字段定义)）。

```sql
ALTER TABLE <table_name> ENABLE ROW LEVEL SECURITY;

CREATE POLICY "<table_name>_owner_select" ON <table_name>
  FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "<table_name>_owner_insert" ON <table_name>
  FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "<table_name>_owner_update" ON <table_name>
  FOR UPDATE USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "<table_name>_owner_delete" ON <table_name>
  FOR DELETE USING (auth.uid() = user_id);
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
```

### 为已有表添加

```sql
ALTER TABLE <table_name>
  ADD COLUMN user_id uuid NOT NULL DEFAULT auth.uid();
```

> 💡 使用 `auth.uid()` 作为默认值，Supabase 会在插入时自动填充当前用户 ID，防止客户端伪造。

---

## 检查当前 RLS 状态

查看哪些表已启用 RLS：

```bash
uv run ./scripts/call_volcengine_supabase.py execute-sql \
  --workspace-id ws-xxxx \
  --query "SELECT schemaname, tablename, rowsecurity FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename;"
```

查看已有的 Policy：

```bash
uv run ./scripts/call_volcengine_supabase.py execute-sql \
  --workspace-id ws-xxxx \
  --query "SELECT schemaname, tablename, policyname, permissive, roles, cmd, qual, with_check FROM pg_policies WHERE schemaname = 'public' ORDER BY tablename, policyname;"
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

-- ❌ 错误：公开表也要求 user_id（增加了不必要的复杂度）
CREATE POLICY "公开读" ON announcements
  FOR SELECT USING (auth.uid() = user_id);
-- 公开表应该用 USING (true)

-- ✅ 正确：公开表使用 USING (true)
CREATE POLICY "allow_public_read" ON announcements
  FOR SELECT USING (true);
```
