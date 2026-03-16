# SQL Playbook

## 目录

- 查看表结构
- 常见 CRUD
- Migration 示例
- 关联查询与聚合
- UPSERT 与批量操作
- pgvector 示例
- RLS 检查与配置

## 1. 查看表结构

```sql
SELECT table_schema, table_name
FROM information_schema.tables
WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
ORDER BY table_schema, table_name;
```

查看字段详情：

```sql
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_schema = 'public' AND table_name = 'your_table'
ORDER BY ordinal_position;
```

查看索引：

```sql
SELECT indexname, indexdef
FROM pg_indexes
WHERE schemaname = 'public' AND tablename = 'your_table';
```

## 2. 常见 CRUD

```sql
-- 查询
SELECT * FROM public.profiles ORDER BY created_at DESC LIMIT 20;
```

```sql
-- 条件查询
SELECT * FROM public.profiles
WHERE status = 'active' AND created_at >= '2024-01-01'
ORDER BY created_at DESC;
```

```sql
-- 插入
INSERT INTO public.profiles (id, nickname)
VALUES ('user-001', 'alice');
```

```sql
-- 更新
UPDATE public.profiles
SET nickname = 'alice-updated', updated_at = now()
WHERE id = 'user-001';
```

```sql
-- 删除
DELETE FROM public.profiles WHERE id = 'user-001';
```

## 3. Migration 示例

```sql
CREATE TABLE IF NOT EXISTS public.todos (
  id bigserial PRIMARY KEY,
  title text NOT NULL,
  done boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now()
);
```

添加字段（安全方式）：

```sql
ALTER TABLE public.todos ADD COLUMN description text;
ALTER TABLE public.todos ADD COLUMN priority integer NOT NULL DEFAULT 0;
```

> 更多 Schema 设计规范请参考 [schema-guide.md](schema-guide.md)

## 4. 关联查询与聚合

```sql
-- JOIN 查询
SELECT p.title, p.content, u.name AS author_name
FROM public.posts p
JOIN public.users u ON p.author_id = u.id
ORDER BY p.created_at DESC
LIMIT 20;
```

```sql
-- LEFT JOIN（包含无关联的数据）
SELECT p.title, c.name AS category_name
FROM public.posts p
LEFT JOIN public.categories c ON p.category_id = c.id;
```

```sql
-- 聚合统计
SELECT
  category_id,
  COUNT(*) AS post_count,
  MAX(created_at) AS latest_post
FROM public.posts
GROUP BY category_id
ORDER BY post_count DESC;
```

```sql
-- 分页查询
SELECT * FROM public.posts
ORDER BY created_at DESC
LIMIT 20 OFFSET 40;  -- 第 3 页，每页 20 条
```

## 5. UPSERT 与批量操作

```sql
-- UPSERT（插入或更新）
INSERT INTO public.settings (key, value)
VALUES ('theme', 'dark')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;
```

```sql
-- 批量 UPSERT
INSERT INTO public.settings (key, value)
VALUES
  ('theme', 'dark'),
  ('language', 'zh-CN'),
  ('timezone', 'Asia/Shanghai')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;
```

```sql
-- 使用 CTE 进行复杂操作
WITH updated AS (
  UPDATE public.posts
  SET published = true
  WHERE status = 'draft' AND created_at < now() - interval '7 days'
  RETURNING id
)
SELECT COUNT(*) AS published_count FROM updated;
```

## 6. pgvector 示例

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

```sql
CREATE TABLE IF NOT EXISTS public.documents (
  id bigserial PRIMARY KEY,
  content text NOT NULL,
  metadata jsonb,
  embedding vector(1536)
);
```

```sql
-- 向量相似度搜索（余弦相似度）
SELECT id, content, 1 - (embedding <=> '[0.1, 0.2, ...]'::vector) AS similarity
FROM public.documents
ORDER BY embedding <=> '[0.1, 0.2, ...]'::vector
LIMIT 10;
```

## 7. RLS 检查与配置

检查 RLS 状态：

```sql
SELECT schemaname, tablename, rowsecurity
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY tablename;
```

查看已有策略：

```sql
SELECT tablename, policyname, permissive, roles, cmd, qual
FROM pg_policies
WHERE schemaname = 'public'
ORDER BY tablename, policyname;
```

快速启用 RLS + 公开读写策略：

```sql
ALTER TABLE public.your_table ENABLE ROW LEVEL SECURITY;

CREATE POLICY "allow_public_select" ON public.your_table FOR SELECT USING (true);
CREATE POLICY "allow_public_insert" ON public.your_table FOR INSERT WITH CHECK (true);
CREATE POLICY "allow_public_update" ON public.your_table FOR UPDATE USING (true) WITH CHECK (true);
CREATE POLICY "allow_public_delete" ON public.your_table FOR DELETE USING (true);
```

> 更多 RLS 场景模板请参考 [rls-guide.md](rls-guide.md)

## 8. 存储过程（RPC）

```sql
-- 创建存储过程
CREATE OR REPLACE FUNCTION search_posts(keyword text)
RETURNS SETOF public.posts AS $$
  SELECT * FROM public.posts
  WHERE title ILIKE '%' || keyword || '%'
     OR content ILIKE '%' || keyword || '%'
  ORDER BY created_at DESC;
$$ LANGUAGE sql STABLE;
```

```sql
-- 创建聚合统计函数
CREATE OR REPLACE FUNCTION get_dashboard_stats()
RETURNS json AS $$
  SELECT json_build_object(
    'total_users', (SELECT COUNT(*) FROM public.users),
    'total_posts', (SELECT COUNT(*) FROM public.posts),
    'active_users', (SELECT COUNT(*) FROM public.users WHERE last_login > now() - interval '30 days')
  );
$$ LANGUAGE sql STABLE;
```
