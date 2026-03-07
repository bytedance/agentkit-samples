# SQL Playbook

## 目录

- 查看表结构
- 常见 CRUD
- Migration 示例
- pgvector 示例
- RLS 检查

## 1. 查看表结构

```sql
SELECT table_schema, table_name
FROM information_schema.tables
WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
ORDER BY table_schema, table_name;
```

## 2. 常见 CRUD

```sql
SELECT * FROM public.profiles ORDER BY created_at DESC LIMIT 20;
```

```sql
INSERT INTO public.profiles (id, nickname)
VALUES ('user-001', 'alice');
```

```sql
UPDATE public.profiles
SET nickname = 'alice-updated'
WHERE id = 'user-001';
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

## 4. pgvector 示例

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

## 5. RLS 检查

```sql
SELECT schemaname, tablename, rowsecurity
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY tablename;
```
