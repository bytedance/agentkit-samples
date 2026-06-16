# 查询性能（query）

慢查询、缺失索引、低效查询计划——Postgres 性能问题最常见的来源。

> 本目录 SQL 通过 `byted-supabase-cli db query "<sql>" --workspace-id ws-...` 执行；改完跑 `byted-supabase-cli db advisors` 巡检。
> 📌 译自 Supabase 官方 agent skills（MIT, © Supabase），适配火山引擎 Supabase 版。

## 目录

- 给 WHERE 和 JOIN 的列建索引
- 多列过滤优先上复合索引
- 用覆盖索引省掉回表
- 按数据特征挑对索引类型
- 固定过滤条件就用部分索引

## 给 WHERE 和 JOIN 的列建索引

**影响（Impact）：** CRITICAL — 大表查询可提速 100 到 1000 倍。

在没有索引的列上做过滤或关联，Postgres 只能走全表扫描。表一大，扫描代价会随之指数级飙升。

写法不对，大表上触发了顺序扫描（全表扫描）：

```sql
-- customer_id 上没索引，只能全表扫描
select * from orders where customer_id = 123;

-- EXPLAIN shows: Seq Scan on orders (cost=0.00..25000.00 rows=100 width=85)
```

正确做法是让查询走索引扫描：

```sql
-- 给高频过滤的列建索引
create index orders_customer_id_idx on orders (customer_id);

select * from orders where customer_id = 123;

-- EXPLAIN shows: Index Scan using orders_customer_id_idx (cost=0.42..8.44 rows=100 width=85)
```

关联查询同理，外键所在的那一侧务必建索引：

```sql
-- 给引用方的列建索引
create index orders_customer_id_idx on orders (customer_id);

select c.name, o.total
from customers c
join orders o on o.customer_id = c.id;
```

Reference: [Query Optimization](https://supabase.com/docs/guides/database/query-optimization)

## 多列过滤优先上复合索引

**影响（Impact）：** HIGH — 多列查询可提速 5 到 10 倍。

查询条件同时命中多个列时，与其给每列各建一个单列索引，不如建一个复合索引来得高效。

写法不对，多个独立索引迫使 Postgres 走 bitmap 扫描把它们拼起来：

```sql
-- 两个独立索引
create index orders_status_idx on orders (status);
create index orders_created_idx on orders (created_at);

-- 查询得把两个索引合并起来用，反而更慢
select * from orders where status = 'pending' and created_at > '2024-01-01';
```

正确做法是合并成一个复合索引：

```sql
-- 单个复合索引，等值匹配的列放最左
create index orders_status_created_idx on orders (status, created_at);

-- 一次高效的索引扫描就够了
select * from orders where status = 'pending' and created_at > '2024-01-01';
```

**列顺序很关键**——等值匹配的列靠前，范围匹配的列靠后：

```sql
-- 推荐：等值的 status 排在范围的 created_at 之前
create index idx on orders (status, created_at);

-- 高效：WHERE status = 'pending'（前导列等值，可 seek 收窄范围）
-- 高效：WHERE status = 'pending' AND created_at > '2024-01-01'
-- 低效：WHERE created_at > '2024-01-01'（缺前导列 status，无法用最左列收窄；
--        PG 仍可能用该索引，但退化成全索引扫描后过滤，远不如把 created_at 当前导列）
```

Reference: [Multicolumn Indexes](https://www.postgresql.org/docs/current/indexes-multicolumn.html)

## 用覆盖索引省掉回表

**影响（Impact）：** MEDIUM-HIGH — 免去回表取数，查询可提速 2 到 5 倍。

覆盖索引把查询要用到的列全都带进索引里，于是 Postgres 走 index-only scan 就能拿到结果，根本不必再去碰底层数据表。

写法不对，先走索引扫描，再回表（heap fetch）取剩下的列：

```sql
create index users_email_idx on users (email);

-- name 和 created_at 还得回表去取
select email, name, created_at from users where email = 'user@example.com';
```

正确做法是用 INCLUDE 让查询走 index-only scan：

```sql
-- 把不参与检索的列一并塞进索引
create index users_email_idx on users (email) include (name, created_at);

-- 所有列都从索引出，不再访问数据表
select email, name, created_at from users where email = 'user@example.com';
```

凡是只在 SELECT 里输出、不参与过滤的列，都适合放进 INCLUDE：

```sql
-- 按 status 检索，但还要返回 customer_id 和 total
create index orders_status_idx on orders (status) include (customer_id, total);

select status, customer_id, total from orders where status = 'shipped';
```

Reference: [Index-Only Scans](https://www.postgresql.org/docs/current/indexes-index-only-scans.html)

## 按数据特征挑对索引类型

**影响（Impact）：** HIGH — 选对索引类型能带来 10 到 100 倍的性能提升。

不同的查询模式各有称手的索引类型，默认的 B-tree 并非万能。

写法不对，拿 B-tree 去扛 JSONB 的包含查询：

```sql
-- B-tree 优化不了包含类操作符
create index products_attrs_idx on products (attributes);
select * from products where attributes @> '{"color": "red"}';
-- 仍然全表扫描——B-tree 不支持 @> 操作符
```

正确做法是 JSONB 改用 GIN：

```sql
-- GIN 支持 @>、?、?&、?| 等操作符
create index products_attrs_idx on products using gin (attributes);
select * from products where attributes @> '{"color": "red"}';
```

索引类型选型速查：

```sql
-- B-tree（默认）：=、<、>、BETWEEN、IN、IS NULL
create index users_created_idx on users (created_at);

-- GIN：数组、JSONB、全文检索
create index posts_tags_idx on posts using gin (tags);

-- GiST：几何数据、范围类型、最近邻（KNN）查询
create index locations_idx on places using gist (location);

-- BRIN：超大时序表（体积可缩小到 1/10 至 1/100）
create index events_time_idx on events using brin (created_at);

-- Hash：仅等值匹配（= 上比 B-tree 略快）
create index sessions_token_idx on sessions using hash (token);
```

Reference: [Index Types](https://www.postgresql.org/docs/current/indexes-types.html)

## 固定过滤条件就用部分索引

**影响（Impact）：** HIGH — 索引体积缩小 5 到 20 倍，写入和查询都更快。

部分索引只收录满足某个 WHERE 条件的行。当查询总是带着同一个过滤条件时，这样的索引更小、更快。

写法不对，整张表都进索引，连软删除的行也一并收录：

```sql
-- 索引收录了所有行，连软删除的也算进去
create index users_email_idx on users (email);

-- 查询却始终只看活跃用户
select * from users where email = 'user@example.com' and deleted_at is null;
```

正确做法是让索引条件与查询过滤对齐：

```sql
-- 索引只收录活跃用户
create index users_active_email_idx on users (email)
where deleted_at is null;

-- 查询命中这个更小更快的索引
select * from users where email = 'user@example.com' and deleted_at is null;
```

部分索引的几个典型场景：

```sql
-- 只索引待处理订单（一旦完成，status 基本不再变）
create index orders_pending_idx on orders (created_at)
where status = 'pending';

-- 只索引非空值
create index products_sku_idx on products (sku)
where sku is not null;
```

Reference: [Partial Indexes](https://www.postgresql.org/docs/current/indexes-partial.html)
