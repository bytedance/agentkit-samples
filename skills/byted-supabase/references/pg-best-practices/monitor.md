# 监控与诊断（monitor）

用 pg_stat_statements、EXPLAIN ANALYZE、指标采集做性能诊断。

> 本目录 SQL 通过 `byted-supabase-cli db query "<sql>" --workspace-id ws-...` 执行；也可用 `byted-supabase-cli inspect db <subcmd>`（如 long-running-queries / table-stats）。
> 📌 译自 Supabase 官方 agent skills（MIT, © Supabase），适配火山引擎 Supabase 版。

## 目录

- 开启 pg_stat_statements 分析查询
- 用 EXPLAIN ANALYZE 诊断慢查询
- 用 VACUUM 和 ANALYZE 维护表统计信息

## 开启 pg_stat_statements 分析查询

**影响（Impact）：** LOW-MEDIUM — 一眼定位最吃资源的查询。

pg_stat_statements 会记录所有查询的执行统计信息，帮你定位运行慢、调用频繁的语句。

**错误（对查询行为两眼一抹黑）：**

```sql
-- 数据库很慢,可到底是哪条查询拖的后腿?
-- 没有 pg_stat_statements 根本无从查起
```

**正确（开启扩展并查询 pg_stat_statements）：**

```sql
-- 启用扩展
create extension if not exists pg_stat_statements;

-- 按累计耗时找出最慢的查询
select
  calls,
  round(total_exec_time::numeric, 2) as total_time_ms,
  round(mean_exec_time::numeric, 2) as mean_time_ms,
  query
from pg_stat_statements
order by total_exec_time desc
limit 10;

-- 找出调用最频繁的查询
select calls, query
from pg_stat_statements
order by calls desc
limit 10;

-- 优化完成后重置统计信息
select pg_stat_statements_reset();
```

重点盯这几个指标：

```sql
-- 平均耗时偏高的查询(优化的首选目标)
select query, mean_exec_time, calls
from pg_stat_statements
where mean_exec_time > 100  -- 平均超过 100ms
order by mean_exec_time desc;
```

Reference: [pg_stat_statements](https://supabase.com/docs/guides/database/extensions/pg_stat_statements)

## 用 EXPLAIN ANALYZE 诊断慢查询

**影响（Impact）：** LOW-MEDIUM — 精确锁定查询执行的真实瓶颈。

EXPLAIN ANALYZE 会真正跑一遍查询并给出实测耗时，瓶颈到底卡在哪一目了然，不必靠猜。

**错误（凭感觉猜性能问题）：**

```sql
-- 查询慢,可为什么慢?
select * from orders where customer_id = 123 and status = 'pending';
-- "肯定是少了个索引" —— 但到底该建哪个?
```

**正确（使用 EXPLAIN ANALYZE）：**

```sql
explain (analyze, buffers, format text)
select * from orders where customer_id = 123 and status = 'pending';

-- 输出直接暴露了问题:
-- Seq Scan on orders (cost=0.00..25000.00 rows=50 width=100) (actual time=0.015..450.123 rows=50 loops=1)
--   Filter: ((customer_id = 123) AND (status = 'pending'::text))
--   Rows Removed by Filter: 999950
--   Buffers: shared hit=5000 read=15000
-- Planning Time: 0.150 ms
-- Execution Time: 450.500 ms
```

读查询计划时重点关注这些信号：

```sql
-- 大表上出现 Seq Scan = 缺索引
-- Rows Removed by Filter = 选择性差或缺索引
-- Buffers: read 远大于 hit = 数据没命中缓存,内存需加大
-- Nested Loop 且 loops 很大 = 该换一种 join 策略了
-- Sort Method: external merge = work_mem 给小了
```

Reference: [EXPLAIN](https://supabase.com/docs/guides/database/inspect)

## 用 VACUUM 和 ANALYZE 维护表统计信息

**影响（Impact）：** MEDIUM — 统计信息准确后查询计划质量提升 2-10 倍。

统计信息一旦过时，查询规划器就会做出糟糕的决策。VACUUM 负责回收空间，ANALYZE 负责更新统计信息。

**错误（统计信息陈旧）：**

```sql
-- 表里实际有 100 万行,统计信息却说只有 1000 行
-- 查询规划器据此选了错误的策略
explain select * from orders where status = 'pending';
-- 结果走了: Seq Scan(因为统计信息显示这是张小表)
-- 实际上: 走 Index Scan 会快得多
```

**正确（让统计信息保持最新）：**

```sql
-- 大批量数据变更后手动 analyze
analyze orders;

-- 针对 WHERE 子句中用到的列做 analyze
analyze orders (status, created_at);

-- 查看各表最近一次 analyze 的时间
select
  relname,
  last_vacuum,
  last_autovacuum,
  last_analyze,
  last_autoanalyze
from pg_stat_user_tables
order by last_analyze nulls first;
```

为高写入量的表调优 autovacuum：

```sql
-- 给高频变更的表提高触发频率
alter table orders set (
  autovacuum_vacuum_scale_factor = 0.05,     -- 死元组达 5% 即 vacuum(默认 20%)
  autovacuum_analyze_scale_factor = 0.02     -- 变更达 2% 即 analyze(默认 10%)
);

-- 查看 autovacuum 当前进度
select * from pg_stat_progress_vacuum;
```

Reference: [VACUUM](https://supabase.com/docs/guides/database/database-size#vacuum-operations)
