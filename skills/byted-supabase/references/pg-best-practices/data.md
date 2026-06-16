# 数据访问模式（data）

消除 N+1 查询、批量操作、游标分页与高效取数。

> 本目录 SQL 通过 `byted-supabase-cli db query "<sql>" --workspace-id ws-...` 执行；改完跑 `byted-supabase-cli db advisors` 巡检。
> 📌 译自 Supabase 官方 agent skills（MIT, © Supabase），适配火山引擎 Supabase 版。

## 目录

- 用批量加载干掉 N+1 查询
- 大批量写入用批量 INSERT
- 用游标分页替代 OFFSET
- 插入或更新统一用 UPSERT

## 用批量加载干掉 N+1 查询

**影响（Impact）：** MEDIUM-HIGH — 数据库往返次数砍到原来的 1/10～1/100。

所谓 N+1 查询，就是在循环里逐条发请求：先查出一批数据，再针对每一条单独发一次查询。正确的做法是合并成一条，靠数组参数或 JOIN 一次取全。

**错误做法（N+1 查询）：**

```sql
-- 第一条查询：取出所有用户
select id from users where active = true;  -- 返回 100 个 ID

-- 接着 N 条查询，每个用户一条
select * from orders where user_id = 1;
select * from orders where user_id = 2;
select * from orders where user_id = 3;
-- ……还有 97 条！

-- 合计：往返数据库 101 次
```

**正确做法（单条批量查询）：**

```sql
-- 收齐 ID，用 ANY 一次查完
select * from orders where user_id = any(array[1, 2, 3, ...]);

-- 或者直接用 JOIN 替代循环
select u.id, u.name, o.*
from users u
left join orders o on o.user_id = u.id
where u.active = true;

-- 合计：往返 1 次
```

落到应用代码里：

```sql
-- 不要在应用层这样循环：
-- for user in users: db.query("SELECT * FROM orders WHERE user_id = $1", user.id)

-- 改成传数组参数：
select * from orders where user_id = any($1::bigint[]);
-- 应用层传入：[1, 2, 3, 4, 5, ...]
```

Reference: [N+1 Query Problem](https://supabase.com/docs/guides/database/query-optimization)

## 大批量写入用批量 INSERT

**影响（Impact）：** MEDIUM — 批量插入快 10～50 倍。

单条单条地 INSERT 开销很高。要么把多行塞进一条语句，要么直接上 COPY。

**错误做法（逐条插入）：**

```sql
-- 每条 insert 都是一次独立的事务和一次往返
insert into events (user_id, action) values (1, 'click');
insert into events (user_id, action) values (1, 'view');
insert into events (user_id, action) values (2, 'click');
-- ……还有 1000 条这样的单条插入

-- 1000 条插入 = 1000 次往返 = 慢
```

**正确做法（批量插入）：**

```sql
-- 一条语句写多行
insert into events (user_id, action) values
  (1, 'click'),
  (1, 'view'),
  (2, 'click'),
  -- ……每批最多约 1000 行
  (999, 'view');

-- 1000 行只需一次往返
```

大规模导入，请用 COPY：

```sql
-- 批量加载首选 COPY，最快
copy events (user_id, action, created_at)
from '/path/to/data.csv'
with (format csv, header true);

-- 也可以在应用里从标准输入喂数据
copy events (user_id, action) from stdin with (format csv);
1,click
1,view
2,click
\.
```

> ⚠️ **火山引擎 Supabase 版注意**：通过 `byted-supabase-cli db query`（REST 网关）执行 COPY 会被拦截，返回 `403 COPY is forbidden`——`COPY FROM 文件`、`COPY FROM stdin`、`COPY TO stdout` 在这条路径上都不可用。在本平台批量导入请改用上面的**多行 INSERT**；确需 COPY 时，用能**直连 Postgres** 的客户端（如 psql 的 `\copy`，连接串见 `db connection-string`）。

Reference: [COPY](https://www.postgresql.org/docs/current/sql-copy.html)

## 用游标分页替代 OFFSET

**影响（Impact）：** MEDIUM-HIGH — 无论翻到多深，性能都稳定在 O(1)。

OFFSET 分页会把跳过的行全部扫一遍，翻得越深越慢。游标分页（keyset 分页）则是 O(1)。

**错误做法（OFFSET 分页）：**

```sql
-- 第 1 页：扫 20 行
select * from products order by id limit 20 offset 0;

-- 第 100 页：要扫 2000 行才能跳过前 1980 行
select * from products order by id limit 20 offset 1980;

-- 第 10000 页：得扫 200,000 行！
select * from products order by id limit 20 offset 199980;
```

**正确做法（游标分页 / keyset 分页）：**

```sql
-- 第 1 页：取前 20 条
select * from products order by id limit 20;
-- 应用层记下 last_id = 20

-- 第 2 页：从上一页最后一个 ID 之后接着取
select * from products where id > 20 order by id limit 20;
-- 走索引，翻多深都一样快

-- 第 10000 页：和第 1 页一个速度
select * from products where id > 199980 order by id limit 20;
```

多列排序时：

```sql
-- 游标要把所有排序列都带上
select * from products
where (created_at, id) > ('2024-01-15 10:00:00', 12345)
order by created_at, id
limit 20;
```

Reference: [Pagination](https://supabase.com/docs/guides/database/pagination)

## 插入或更新统一用 UPSERT

**影响（Impact）：** MEDIUM — 操作原子化，根除竞态条件。

先 SELECT 再 INSERT/UPDATE 这种分两步的写法会留下竞态隐患。用 INSERT ... ON CONFLICT 一步到位，天然原子。

**错误做法（先查后插，存在竞态）：**

```sql
-- 竞态：两个请求同时检查
select * from settings where user_id = 123 and key = 'theme';
-- 两边都查不到记录

-- 两边都尝试插入
insert into settings (user_id, key, value) values (123, 'theme', 'dark');
-- 一个成功，另一个撞上主键冲突报错！
```

**正确做法（原子 UPSERT）：**

```sql
-- 单条原子操作
insert into settings (user_id, key, value)
values (123, 'theme', 'dark')
on conflict (user_id, key)
do update set value = excluded.value, updated_at = now();

-- 返回写入 / 更新后的行
insert into settings (user_id, key, value)
values (123, 'theme', 'dark')
on conflict (user_id, key)
do update set value = excluded.value
returning *;
```

存在即跳过的写法：

```sql
-- 不存在才插入，已存在就不动（不更新）
insert into page_views (page_id, user_id)
values (1, 123)
on conflict (page_id, user_id) do nothing;
```

Reference: [INSERT ON CONFLICT](https://www.postgresql.org/docs/current/sql-insert.html#SQL-ON-CONFLICT)
