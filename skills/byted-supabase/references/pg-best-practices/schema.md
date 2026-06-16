# Schema 设计（schema）

表设计、索引策略、分区与数据类型选择，是长期性能的基础。

> 本目录 SQL 通过 `byted-supabase-cli db query "<sql>" --workspace-id ws-...` 执行；改完跑 `byted-supabase-cli db advisors` 巡检。火山命名约定与建表模板另见 `../schema-guide.md`。
> 📌 译自 Supabase 官方 agent skills（MIT, © Supabase），适配火山引擎 Supabase 版。

## 目录

- 选对主键策略
- 用对数据类型
- 迁移里安全地加约束
- 给外键列建索引
- 标识符一律小写
- 大表做分区

## 选对主键策略

**影响（Impact）：** HIGH — 索引局部性更好，碎片更少。

主键怎么选，直接决定了写入性能、索引体积和复制效率，不是随手定个 `id` 就完事。

**错误示范（这几种主键有坑）：**

```sql
-- identity 是 SQL 标准写法
create table users (
  id serial primary key  -- 能用，但更推荐 IDENTITY
);

-- 随机 UUID（v4）会把索引搞得很碎
create table orders (
  id uuid default gen_random_uuid() primary key  -- UUIDv4 是随机的，插入位置乱跳
);
```

**正确示范（推荐的主键策略）：**

```sql
-- 顺序自增 ID 用 IDENTITY（SQL 标准，绝大多数场景的首选）
create table users (
  id bigint generated always as identity primary key
);

-- 分布式系统必须用 UUID 时，选 UUIDv7（带时间序）
-- 需要 pg_uuidv7 扩展：create extension pg_uuidv7;
create table orders (
  id uuid default uuid_generate_v7() primary key  -- 按时间有序，不产生碎片
);

-- 备选方案：时间前缀 ID，同样可排序、适合分布式，且无需任何扩展
create table events (
  id text default concat(
    to_char(now() at time zone 'utc', 'YYYYMMDDHH24MISSMS'),
    gen_random_uuid()::text
  ) primary key
);
```

选型要点：

- 单库场景：`bigint identity`（顺序、8 字节、SQL 标准）。
- 分布式或主键需要对外暴露：用 UUIDv7（依赖 pg_uuidv7）或 ULID，二者都带时间序、不产生碎片。
- `serial` 虽然能跑，但 `identity` 才是 SQL 标准，新项目优先用它。
- 大表别拿随机 UUID（v4）当主键，否则索引会严重碎片化。

Reference: [Identity Columns](https://www.postgresql.org/docs/current/sql-createtable.html#SQL-CREATETABLE-PARMS-GENERATED-IDENTITY)

## 用对数据类型

**影响（Impact）：** HIGH — 存储省一半，比较更快。

数据类型选得准，既能压缩存储、加速查询，还能从源头堵住一类 bug。

**错误示范（类型选错）：**

```sql
create table users (
  id int,                    -- 21 亿就溢出了
  email varchar(255),        -- 没必要的长度限制
  created_at timestamp,      -- 丢了时区信息
  is_active varchar(5),      -- 拿字符串存布尔值
  price varchar(20)          -- 拿字符串存数值
);
```

**正确示范（类型选对）：**

```sql
create table users (
  id bigint generated always as identity primary key,  -- 上限约 900 亿亿
  email text,                     -- 不设人为长度上限，性能与 varchar 一致
  created_at timestamptz,         -- 时间一律带时区
  is_active boolean default true, -- 仅 1 字节，强过变长字符串
  price numeric(10,2)             -- 精确的十进制运算
);
```

核心准则：

```sql
-- ID：用 bigint，别用 int（给未来留余量）
-- 字符串：用 text，除非确实要限长才用 varchar(n)
-- 时间：用 timestamptz，别用 timestamp
-- 金额：用 numeric，别用 float（精度是底线）
-- 枚举：用 text 加 check 约束，或单独建 enum 类型
```

Reference: [Data Types](https://www.postgresql.org/docs/current/datatype.html)

## 迁移里安全地加约束

**影响（Impact）：** HIGH — 避免迁移失败，让 schema 变更可重复执行。

PostgreSQL 不支持 `ADD CONSTRAINT IF NOT EXISTS`，迁移脚本里这么写一定报错。

**错误示范（直接语法报错）：**

```sql
-- ERROR: syntax error at or near "not" (SQLSTATE 42601)
alter table public.profiles
add constraint if not exists profiles_birthchart_id_unique unique (birthchart_id);
```

**正确示范（幂等地建约束）：**

```sql
-- 用 DO 块先判断再添加
do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conname = 'profiles_birthchart_id_unique'
    and conrelid = 'public.profiles'::regclass
  ) then
    alter table public.profiles
    add constraint profiles_birthchart_id_unique unique (birthchart_id);
  end if;
end $$;
```

各类约束都照此办理：

```sql
-- Check 约束
do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conname = 'check_age_positive'
  ) then
    alter table users add constraint check_age_positive check (age > 0);
  end if;
end $$;

-- 外键
do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conname = 'profiles_birthchart_id_fkey'
  ) then
    alter table profiles
    add constraint profiles_birthchart_id_fkey
    foreign key (birthchart_id) references birthcharts(id);
  end if;
end $$;
```

查约束是否已存在：

```sql
-- 查询某张表上的所有约束
select conname, contype, pg_get_constraintdef(oid)
from pg_constraint
where conrelid = 'public.profiles'::regclass;

-- contype 取值含义：
-- 'p' = PRIMARY KEY
-- 'f' = FOREIGN KEY
-- 'u' = UNIQUE
-- 'c' = CHECK
```

Reference: [Constraints](https://www.postgresql.org/docs/current/ddl-constraints.html)

## 给外键列建索引

**影响（Impact）：** HIGH — JOIN 与级联操作快 10 到 100 倍。

Postgres 不会自动给外键列建索引。少了这个索引，JOIN 和级联（CASCADE）操作都会变慢。

**错误示范（外键没建索引）：**

```sql
create table orders (
  id bigint generated always as identity primary key,
  customer_id bigint references customers(id) on delete cascade,
  total numeric(10,2)
);

-- customer_id 上没有索引！
-- JOIN 和 ON DELETE CASCADE 都得全表扫描
select * from orders where customer_id = 123;  -- 走 Seq Scan
delete from customers where id = 123;          -- 锁表，并扫遍所有 orders
```

**正确示范（外键已建索引）：**

```sql
create table orders (
  id bigint generated always as identity primary key,
  customer_id bigint references customers(id) on delete cascade,
  total numeric(10,2)
);

-- 外键列务必建索引
create index orders_customer_id_idx on orders (customer_id);

-- 现在 JOIN 和级联都很快
select * from orders where customer_id = 123;  -- 走 Index Scan
delete from customers where id = 123;          -- 走索引，级联很快
```

揪出缺索引的外键：

```sql
select
  conrelid::regclass as table_name,
  a.attname as fk_column
from pg_constraint c
join pg_attribute a on a.attrelid = c.conrelid and a.attnum = any(c.conkey)
where c.contype = 'f'
  and not exists (
    select 1 from pg_index i
    where i.indrelid = c.conrelid and a.attnum = any(i.indkey)
  );
```

Reference: [Foreign Keys](https://www.postgresql.org/docs/current/ddl-constraints.html#DDL-CONSTRAINTS-FK)

## 标识符一律小写

**影响（Impact）：** MEDIUM — 规避各类工具、ORM 和 AI 助手上的大小写敏感问题。

PostgreSQL 会把未加引号的标识符统一折叠成小写。一旦用引号包了混合大小写的标识符，从此每次引用都得带引号，而且各种工具、ORM 乃至 AI 助手往往认不出来，平添麻烦。

**错误示范（混合大小写标识符）：**

```sql
-- 带引号的标识符虽保留大小写，但处处都得加引号
CREATE TABLE "Users" (
  "userId" bigint PRIMARY KEY,
  "firstName" text,
  "lastName" text
);

-- 永远得加引号，否则查询失败
SELECT "firstName" FROM "Users" WHERE "userId" = 1;

-- 这句会失败——不加引号时 Users 被当成 users
SELECT firstName FROM Users;
-- ERROR: relation "users" does not exist
```

**正确示范（小写 snake_case）：**

```sql
-- 不加引号的小写标识符，可移植，对工具友好
CREATE TABLE users (
  user_id bigint PRIMARY KEY,
  first_name text,
  last_name text
);

-- 无需引号，所有工具都认得
SELECT first_name FROM users WHERE user_id = 1;
```

混合大小写常见的来源：

```sql
-- ORM 经常生成带引号的 camelCase——把它配置成 snake_case
-- 从其他数据库迁移过来，可能原样保留了大小写
-- 部分 GUI 工具默认给标识符加引号——关掉这个选项

-- 实在被混合大小写套牢，就建视图当兼容层
CREATE VIEW users AS SELECT "userId" AS user_id, "firstName" AS first_name FROM "Users";
```

Reference: [Identifiers and Key Words](https://www.postgresql.org/docs/current/sql-syntax-lexical.html#SQL-SYNTAX-IDENTIFIERS)

## 大表做分区

**影响（Impact）：** MEDIUM-HIGH — 大表上的查询与维护操作快 5 到 20 倍。

分区把一张大表拆成若干小块，查询性能和维护操作都能跟着受益。

**错误示范（单张大表）：**

```sql
create table events (
  id bigint generated always as identity,
  created_at timestamptz,
  data jsonb
);

-- 5 亿行，查询每次都扫全表
select * from events where created_at > '2024-01-01';  -- 慢
vacuum events;  -- 跑几个小时，还锁表
```

**正确示范（按时间范围分区）：**

```sql
create table events (
  id bigint generated always as identity,
  created_at timestamptz not null,
  data jsonb
) partition by range (created_at);

-- 按月建分区
create table events_2024_01 partition of events
  for values from ('2024-01-01') to ('2024-02-01');

create table events_2024_02 partition of events
  for values from ('2024-02-01') to ('2024-03-01');

-- 查询只扫命中的分区
select * from events where created_at > '2024-01-15';  -- 只扫 events_2024_01 及之后

-- 清旧数据瞬间完成
drop table events_2023_01;  -- 秒级，而 DELETE 要几个小时
```

什么时候该分区：

- 表超过 1 亿行。
- 时序数据，查询以日期为条件。
- 需要高效地清理旧数据。

Reference: [Table Partitioning](https://www.postgresql.org/docs/current/ddl-partitioning.html)
