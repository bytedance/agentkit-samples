# 连接管理（conn）

连接池、连接数上限与 serverless 策略——高并发或 serverless 部署的关键。

> 本目录 SQL 通过 `byted-supabase-cli db query "<sql>" --workspace-id ws-...` 执行；改完跑 `byted-supabase-cli db advisors` 巡检。
> 📌 译自 Supabase 官方 agent skills（MIT, © Supabase），适配火山引擎 Supabase 版。

## 目录

- 所有应用都要走连接池
- 把连接数上限调到合适的值
- 给空闲连接配上超时回收
- 连接池下正确使用预处理语句

## 所有应用都要走连接池

**影响（Impact）：** CRITICAL — 并发承载能力提升 10～100 倍。

Postgres 的连接很贵，每条要吃掉 1-3MB 内存。不走连接池，流量一上来连接很快就被打满。

**反例（每个请求都新建连接）：**

```sql
-- 每个请求都开一条新连接
-- 应用侧代码：每次请求都 db.connect()
-- 后果：500 个并发用户 = 500 条连接 = 数据库被打挂

-- 看看当前连接数
select count(*) from pg_stat_activity;  -- 487 条连接！
```

**正例（接入连接池）：**

```sql
-- 在应用和数据库之间架一层 pooler（如 PgBouncer）
-- 应用只连 pooler，由 pooler 用一小撮连接复用着打到 Postgres

-- pool_size 按这个公式估：(CPU 核数 * 2) + spindle_count
-- 4 核为例：pool_size = 10

-- 效果：500 个并发用户共用 10 条真实连接
select count(*) from pg_stat_activity;  -- 10 条连接
```

两种池化模式怎么选：

- **事务模式（transaction mode）**：每跑完一个事务就把连接还回池子，绝大多数应用都该用这个。
- **会话模式（session mode）**：整个会话期间独占一条连接，只有用到预处理语句、临时表这类场景才需要。

Reference: [Connection Pooling](https://supabase.com/docs/guides/database/connecting-to-postgres#connection-pooler)

## 把连接数上限调到合适的值

**影响（Impact）：** CRITICAL — 避免数据库被拖垮、内存被耗尽。

连接开太多，内存撑爆、性能也跟着下滑。上限得照着机器的实际资源来定，别拍脑袋。

**反例（不限或盲目调高）：**

```sql
-- max_connections 默认 100，但常被人不假思索地往上拉
show max_connections;  -- 500（对 4GB 内存来说高得离谱）

-- 每条连接吃 1-3MB 内存
-- 500 连接 * 2MB = 光连接就占掉 1GB！
-- 负载一上来就 OOM
```

**正例（按资源算出来）：**

```sql
-- 公式：max_connections = (内存 MB 数 / 每连接 5MB) - 预留
-- 4GB 内存：(4096 / 5) - 10 ≈ 理论上限 800
-- 但从查询性能角度看，100-200 才是更实在的取值

-- 4GB 内存的推荐配置
alter system set max_connections = 100;

-- work_mem 也得配套调
-- work_mem * max_connections 不要超过内存的 25%
alter system set work_mem = '8MB';  -- 8MB * 100 = 上限 800MB
```

> ⚠️ **火山引擎 Supabase 版注意**：连接角色 `postgres` 非 superuser，上面两条 `alter system set ...` 会直接报 `42501 permission denied`，改不动实例级参数。这类参数请走**平台控制台**调整；只想临时改本会话用 `set work_mem = '8MB'` 即可。另外本平台 `max_connections` 实测可能已是数百（实测某实例为 901），并非 vanilla PG 的默认 100——动手前先 `show max_connections` 看实值。

盯紧连接的使用情况：

```sql
select count(*), state from pg_stat_activity group by state;
```

Reference: [Database Connections](https://supabase.com/docs/guides/platform/performance#connection-management)

## 给空闲连接配上超时回收

**影响（Impact）：** HIGH — 从空闲客户端手里回收 30-50% 的连接槽位。

连接挂着不干活就是在白白占资源。配好空闲超时，让它们到点自动被踢掉、把槽位让出来。

**反例（连接一直挂着不回收）：**

```sql
-- 没配任何超时
show idle_in_transaction_session_timeout;  -- 0（已禁用）

-- 连接永远不释放，哪怕一直闲着
select pid, state, state_change, query
from pg_stat_activity
where state = 'idle in transaction';
-- 能看到一堆事务空闲好几个小时，锁还死死攥在手里
```

**正例（空闲连接自动清理）：**

```sql
-- 事务里空闲超过 30 秒就掐掉连接
alter system set idle_in_transaction_session_timeout = '30s';

-- 彻底空闲超过 10 分钟就掐掉连接
alter system set idle_session_timeout = '10min';

-- 重新加载配置
select pg_reload_conf();
```

> ⚠️ **火山引擎 Supabase 版注意**：上面的 `alter system set ...` 和 `select pg_reload_conf()` 对 `postgres` 角色都会报 `42501 permission denied`，在本平台跑不通。空闲超时这类实例级配置请走**平台控制台**；本平台 `idle_in_transaction_session_timeout` 实测可能已被预设为非 0（实测某实例为 5min），先 `show` 看实值。会话级 `set local idle_in_transaction_session_timeout = '30s'` 可用。

如果走的是连接池，超时就在 pooler 这一层配：

```ini
# pgbouncer.ini
server_idle_timeout = 60
client_idle_timeout = 300
```

Reference: [Connection Timeouts](https://www.postgresql.org/docs/current/runtime-config-client.html#GUC-IDLE-IN-TRANSACTION-SESSION-TIMEOUT)

## 连接池下正确使用预处理语句

**影响（Impact）：** HIGH — 规避池化环境里的预处理语句冲突。

预处理语句是绑死在某一条具体连接上的。可事务模式下连接是大家轮着用的，于是就撞车了。

**反例（事务模式池化 + 具名预处理语句）：**

```sql
-- 具名预处理语句
prepare get_user as select * from users where id = $1;

-- 事务模式下，下一个请求很可能落到另一条连接上
execute get_user(123);
-- ERROR: prepared statement "get_user" does not exist
```

**正例（改用匿名语句，或切到会话模式）：**

```sql
-- 方案一：用匿名预处理语句（大多数 ORM 默认就这么干）
-- 查询的预备和执行在同一条协议消息里完成

-- 方案二：事务模式下用完即 deallocate
prepare get_user as select * from users where id = $1;
execute get_user(123);
deallocate get_user;

-- 方案三：改用会话模式池化（端口 5432，而非 6543）
-- 连接整个会话期间不释放，预处理语句也就一直在
```

顺手检查一下驱动的配置：

```sql
-- 不少驱动默认就开了预处理语句
-- Node.js pg：{ prepare: false } 关掉
-- JDBC：prepareThreshold=0 关掉
```

Reference: [Prepared Statements with Pooling](https://supabase.com/docs/guides/database/connecting-to-postgres#connection-pool-modes)
