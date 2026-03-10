# 数据库 Schema 设计与迁移指南

本指南提供数据库表结构设计规范和迁移最佳实践，所有 SQL 均可通过 `apply-migration` 或 `execute-sql` 执行。

---

## 命名约定

| 对象 | 规则 | 示例 |
|------|------|------|
| 表名 | snake_case，复数 | `user_profiles`、`order_items` |
| 字段名 | snake_case | `created_at`、`user_id` |
| 主键 | `id` | `id bigserial PRIMARY KEY` |
| 外键字段 | `<关联表单数>_id` | `user_id`、`category_id` |
| 索引 | `ix_<表名>_<字段名>` | `ix_users_email` |
| 唯一约束 | `uq_<表名>_<字段名>` | `uq_users_email` |

---

## 字段类型速查表

| 用途 | 推荐类型 | 说明 |
|------|----------|------|
| 自增主键 | `bigserial` | 64 位自增整数 |
| UUID 主键 | `uuid DEFAULT gen_random_uuid()` | 随机 UUID v4 |
| 短文本 | `varchar(N)` | 有长度限制的字符串 |
| 长文本 | `text` | 无长度限制 |
| 整数 | `integer` / `bigint` | 32 位 / 64 位整数 |
| 小数 | `numeric(P,S)` | 精确小数（金额等） |
| 浮点 | `double precision` | 近似浮点（坐标等） |
| 布尔 | `boolean` | true / false |
| 时间戳 | `timestamptz` | 带时区（推荐） |
| 日期 | `date` | 仅日期 |
| JSON | `jsonb` | 二进制 JSON（可索引） |
| 数组 | `text[]`、`integer[]` | PostgreSQL 原生数组 |
| 向量 | `vector(N)` | pgvector 扩展（需先启用） |

> ⚠️ 时间类型**始终使用 `timestamptz`**（带时区），避免时区相关问题。

---

## 建表模板

### 基础表

```sql
CREATE TABLE IF NOT EXISTS public.todos (
  id bigserial PRIMARY KEY,
  title text NOT NULL,
  description text,
  done boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz
);
```

通过 migration 执行：

```bash
uv run ./scripts/call_volcengine_supabase.py apply-migration \
  --workspace-id ws-xxxx \
  --name create_todos_table \
  --query "CREATE TABLE IF NOT EXISTS public.todos (id bigserial PRIMARY KEY, title text NOT NULL, description text, done boolean NOT NULL DEFAULT false, created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz);"
```

### 带外键关联

```sql
CREATE TABLE IF NOT EXISTS public.categories (
  id bigserial PRIMARY KEY,
  name varchar(100) NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.posts (
  id bigserial PRIMARY KEY,
  title varchar(255) NOT NULL,
  content text,
  category_id bigint REFERENCES public.categories(id) ON DELETE SET NULL,
  published boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz
);

CREATE INDEX IF NOT EXISTS ix_posts_category_id ON public.posts(category_id);
CREATE INDEX IF NOT EXISTS ix_posts_created_at ON public.posts(created_at DESC);
```

### 带用户关联（配合 RLS 场景 D）

```sql
CREATE TABLE IF NOT EXISTS public.notes (
  id bigserial PRIMARY KEY,
  user_id uuid NOT NULL DEFAULT auth.uid(),
  title varchar(255) NOT NULL,
  content text,
  is_pinned boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz
);

CREATE INDEX IF NOT EXISTS ix_notes_user_id ON public.notes(user_id);
```

### 带 UUID 主键

```sql
CREATE TABLE IF NOT EXISTS public.projects (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name varchar(255) NOT NULL,
  slug varchar(100) NOT NULL UNIQUE,
  metadata jsonb DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);
```

---

## 常用 ALTER TABLE 操作

### 添加字段

```sql
-- 添加可空字段（安全，推荐）
ALTER TABLE public.posts ADD COLUMN tags text[];

-- 添加带默认值的非空字段（安全）
ALTER TABLE public.posts ADD COLUMN view_count integer NOT NULL DEFAULT 0;

-- ❌ 危险：添加非空字段且无默认值（已有数据会报错）
-- ALTER TABLE public.posts ADD COLUMN author_name text NOT NULL;
```

### 添加索引

```sql
-- 普通索引
CREATE INDEX IF NOT EXISTS ix_posts_title ON public.posts(title);

-- 唯一索引
CREATE UNIQUE INDEX IF NOT EXISTS uq_posts_slug ON public.posts(slug);

-- 复合索引
CREATE INDEX IF NOT EXISTS ix_posts_category_published ON public.posts(category_id, published);

-- GIN 索引（用于 jsonb 查询优化）
CREATE INDEX IF NOT EXISTS ix_posts_metadata ON public.posts USING gin(metadata);
```

### 添加/删除约束

```sql
-- 添加唯一约束
ALTER TABLE public.posts ADD CONSTRAINT uq_posts_slug UNIQUE (slug);

-- 添加外键约束
ALTER TABLE public.comments
  ADD CONSTRAINT fk_comments_post_id
  FOREIGN KEY (post_id) REFERENCES public.posts(id) ON DELETE CASCADE;

-- 删除约束
ALTER TABLE public.posts DROP CONSTRAINT IF EXISTS uq_posts_slug;
```

---

## 向后兼容变更注意事项

| 操作 | 是否安全 | 说明 |
|------|:--------:|------|
| 添加可空字段 | ✅ | 已有行该字段为 NULL |
| 添加带 DEFAULT 的非空字段 | ✅ | 已有行自动填充默认值 |
| 添加非空字段无默认值 | ❌ | 已有行填充失败 |
| 删除字段 | ⚠️ | 需确认无代码依赖 |
| 修改字段类型 | ⚠️ | 可能丢失数据 |
| 缩短 varchar 长度 | ❌ | 已有数据可能超长 |
| 添加索引 | ✅ | 不影响现有数据 |
| 添加唯一约束 | ⚠️ | 已有重复数据会失败 |

---

## 验证表结构

```bash
# 列出所有表
uv run ./scripts/call_volcengine_supabase.py list-tables --workspace-id ws-xxxx

# 查看表详细结构
uv run ./scripts/call_volcengine_supabase.py execute-sql \
  --workspace-id ws-xxxx \
  --query "SELECT column_name, data_type, is_nullable, column_default FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'posts' ORDER BY ordinal_position;"

# 查看索引
uv run ./scripts/call_volcengine_supabase.py execute-sql \
  --workspace-id ws-xxxx \
  --query "SELECT indexname, indexdef FROM pg_indexes WHERE schemaname = 'public' AND tablename = 'posts';"

# 查看外键
uv run ./scripts/call_volcengine_supabase.py execute-sql \
  --workspace-id ws-xxxx \
  --query "SELECT conname, conrelid::regclass, confrelid::regclass, pg_get_constraintdef(oid) FROM pg_constraint WHERE contype = 'f' AND connamespace = 'public'::regnamespace;"
```

---

## pgvector 支持

```sql
-- 1. 启用 pgvector 扩展
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. 创建带向量字段的表
CREATE TABLE IF NOT EXISTS public.documents (
  id bigserial PRIMARY KEY,
  content text NOT NULL,
  metadata jsonb,
  embedding vector(1536),
  created_at timestamptz NOT NULL DEFAULT now()
);

-- 3. 创建向量索引（IVFFlat 或 HNSW）
CREATE INDEX IF NOT EXISTS ix_documents_embedding ON public.documents
  USING hnsw (embedding vector_cosine_ops);
```

验证扩展是否已启用：

```bash
uv run ./scripts/call_volcengine_supabase.py list-extensions --workspace-id ws-xxxx
```
