# 高级特性（advanced）

全文检索、JSONB 优化等 Postgres 高级特性。

> 本目录 SQL 通过 `byted-supabase-cli db query "<sql>" --workspace-id ws-...` 执行；改完跑 `byted-supabase-cli db advisors` 巡检。
> 📌 译自 Supabase 官方 agent skills（MIT, © Supabase），适配火山引擎 Supabase 版。

## 目录

- 全文检索请用 tsvector，别再用 LIKE 模糊匹配
- 给 JSONB 列建索引，避免全表扫描

## 全文检索请用 tsvector，别再用 LIKE 模糊匹配

**影响（Impact）：** MEDIUM — 比 LIKE 快约 100 倍，还自带相关度排序

`LIKE '%关键词%'` 这种前后都带通配符的写法，索引根本用不上，每次查询都得全表扫一遍。改用基于 tsvector 的全文检索，性能能甩开几个数量级，而且天生支持按相关度排序。

反面写法（LIKE 模糊匹配）：

```sql
-- 用不上索引，全表扫描
select * from articles where content like '%postgresql%';

-- 套个 lower() 做大小写不敏感，反而更慢
select * from articles where lower(content) like '%postgresql%';
```

推荐写法（用 tsvector 做全文检索）：

```sql
-- 加一个 tsvector 生成列，并建索引
alter table articles add column search_vector tsvector
  generated always as (to_tsvector('english', coalesce(title,'') || ' ' || coalesce(content,''))) stored;

create index articles_search_idx on articles using gin (search_vector);

-- 高速全文检索
select * from articles
where search_vector @@ to_tsquery('english', 'postgresql & performance');

-- 带相关度排序
select *, ts_rank(search_vector, query) as rank
from articles, to_tsquery('english', 'postgresql') query
where search_vector @@ query
order by rank desc;
```

多关键词的几种组合方式（⚠️ `to_tsquery` 的 config 必须与 tsvector 列建列时一致，本例都用 `'english'`；若漏掉 config，会落到实例的 `default_text_search_config`（火山引擎 Supabase 版默认是 `simple`，不做词干化），与 `'english'` 向量对不上，可能一行都查不到）：

```sql
-- AND：两个词都要命中
to_tsquery('english', 'postgresql & performance')

-- OR：命中任意一个即可
to_tsquery('english', 'postgresql | mysql')

-- 前缀匹配
to_tsquery('english', 'post:*')
```

Reference: [Full Text Search](https://supabase.com/docs/guides/database/full-text-search)

## 给 JSONB 列建索引，避免全表扫描

**影响（Impact）：** MEDIUM — 索引到位后 JSONB 查询提速 10～100 倍

JSONB 列不建索引，每条查询都得把整张表扫一遍。这类按包含关系（containment）过滤的查询，交给 GIN 倒排索引来扛最合适。

反面写法（JSONB 列没建索引）：

```sql
create table products (
  id bigint primary key,
  attributes jsonb
);

-- 每条查询都全表扫描
select * from products where attributes @> '{"color": "red"}';
select * from products where attributes->>'brand' = 'Nike';
```

推荐写法（给 JSONB 建 GIN 索引）：

```sql
-- GIN 索引覆盖包含类操作符（@>, ?, ?&, ?|）
create index products_attrs_gin on products using gin (attributes);

-- 包含关系查询现在能走索引了
select * from products where attributes @> '{"color": "red"}';

-- 只查固定某个 key 时，改用表达式索引
create index products_brand_idx on products ((attributes->>'brand'));
select * from products where attributes->>'brand' = 'Nike';
```

按需挑选合适的操作符类（operator class）：

```sql
-- jsonb_ops（默认）：支持全部操作符，但索引体积偏大
create index idx1 on products using gin (attributes);

-- jsonb_path_ops：只支持 @> 操作符，但索引体积通常更小（幅度随数据而定，常见约 1.5～3 倍）
create index idx2 on products using gin (attributes jsonb_path_ops);
```

Reference: [JSONB Indexes](https://www.postgresql.org/docs/current/datatype-json.html#JSON-INDEXING)
