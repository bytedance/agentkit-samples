# 并发与锁（lock）

事务管理、隔离级别、死锁预防与锁竞争模式。

> 本目录 SQL 通过 `byted-supabase-cli db query "<sql>" --workspace-id ws-...` 执行；改完跑 `byted-supabase-cli db advisors` 巡检。
> 📌 译自 Supabase 官方 agent skills（MIT, © Supabase），适配火山引擎 Supabase 版。

## 目录

- 事务越短越好，把锁竞争压到最低
- 统一加锁顺序，从源头掐掉死锁
- 应用级互斥，优先用咨询锁（advisory lock）
- 队列消费用 SKIP LOCKED，让 worker 不再互相干等

## 事务越短越好，把锁竞争压到最低

**影响（Impact）：** MEDIUM-HIGH — 吞吐提升 3-5 倍，死锁明显减少。

事务一旦拉长，它持有的锁就会把别的查询全堵在门外。原则很简单：事务能多短就多短，只在真正要改数据时才开。

**错误做法（事务里夹着外部调用，迟迟不提交）：**

```sql
begin;
select * from orders where id = 1 for update;  -- 拿到行锁

-- 应用此时去调支付 API 的 HTTP 接口（耗时 2-5 秒）
-- 这期间，所有访问这一行的查询全被卡住！

update orders set status = 'paid' where id = 1;
commit;  -- 锁在整个过程里一直被攥着
```

**正确做法（把事务范围收到最小）：**

```sql
-- 数据校验、调外部 API 这些活，统统挪到事务外面去做
-- 应用层先执行：response = await paymentAPI.charge(...)

-- 事务里只留下真正的那条更新
begin;
update orders
set status = 'paid', payment_id = $1
where id = $2 and status = 'pending'
returning *;
commit;  -- 锁只持有毫秒级
```

再配一道 `statement_timeout` 保险，防止失控的事务赖着不走：

```sql
-- 超过 30 秒还没跑完的查询直接中止
set statement_timeout = '30s';

-- 或者只对当前会话生效
set local statement_timeout = '5s';
```

Reference: [Transaction Management](https://www.postgresql.org/docs/current/tutorial-transactions.html)

## 统一加锁顺序，从源头掐掉死锁

**影响（Impact）：** MEDIUM-HIGH — 消除死锁报错，提升可靠性。

死锁的成因一句话就能说清：两个事务以相反的顺序去抢同一批资源，结果各自攥着一半、互相死等对方手里的锁。破解之道也只有一条——所有事务都按同一个固定顺序加锁。

**错误做法（加锁顺序各自为政）：**

```sql
-- Transaction A                    -- Transaction B
begin;                              begin;
update accounts                     update accounts
set balance = balance - 100         set balance = balance - 50
where id = 1;                       where id = 2;  -- B 锁住第 2 行

update accounts                     update accounts
set balance = balance + 100         set balance = balance + 50
where id = 2;  -- A 等 B 放锁        where id = 1;  -- B 等 A 放锁

-- 死锁！两边都在死等对方
```

**正确做法（动手前先按固定顺序把行锁齐）：**

```sql
-- 更新前，显式地按 ID 顺序一次性把锁加好
begin;
select * from accounts where id in (1, 2) order by id for update;

-- 锁已在手，后面爱怎么更新就怎么更新，顺序无所谓
update accounts set balance = balance - 100 where id = 1;
update accounts set balance = balance + 100 where id = 2;
commit;
```

另一种思路：用单条语句一把搞定，让加锁原子化：

```sql
-- 单条语句把所有锁原子地拿全
begin;
update accounts
set balance = balance + case id
  when 1 then -100
  when 2 then 100
end
where id in (1, 2);
commit;
```

从日志里揪出死锁：

```sql
-- 看看最近有没有发生过死锁
select * from pg_stat_database where deadlocks > 0;

-- 打开死锁日志
set log_lock_waits = on;
set deadlock_timeout = '1s';
```

Reference:
[Deadlocks](https://www.postgresql.org/docs/current/explicit-locking.html#LOCKING-DEADLOCKS)

## 应用级互斥，优先用咨询锁（advisory lock）

**影响（Impact）：** MEDIUM — 高效协调，免去行级锁的额外开销。

很多场景要锁的并不是某一行数据，而是一段"逻辑临界区"。这种应用层的协调，咨询锁（advisory lock）正合适——它不需要你真的去锁某条记录。

**错误做法（为了加锁专门造几行数据出来）：**

```sql
-- 凭空建表造行，只为有个东西可以锁
create table resource_locks (
  resource_name text primary key
);

insert into resource_locks values ('report_generator');

-- 靠 select 这一行来加锁
select * from resource_locks where resource_name = 'report_generator' for update;
```

**正确做法（直接用咨询锁）：**

```sql
-- 会话级咨询锁（断连或手动解锁时释放）
select pg_advisory_lock(hashtext('report_generator'));
-- ... 在这里做独占的工作 ...
select pg_advisory_unlock(hashtext('report_generator'));

-- 事务级咨询锁（commit/rollback 时释放）
begin;
select pg_advisory_xact_lock(hashtext('daily_report'));
-- ... 做事 ...
commit;  -- 锁随事务自动释放
```

不想干等的场景，用 try-lock：

```sql
-- 立刻返回 true/false，不阻塞等待
select pg_try_advisory_lock(hashtext('resource_name'));

-- 在应用里这样用
if (acquired) {
  -- 抢到了，干活
  select pg_advisory_unlock(hashtext('resource_name'));
} else {
  -- 没抢到，跳过或稍后重试
}
```

Reference: [Advisory Locks](https://www.postgresql.org/docs/current/explicit-locking.html#ADVISORY-LOCKS)

## 队列消费用 SKIP LOCKED，让 worker 不再互相干等

**影响（Impact）：** MEDIUM-HIGH — worker 队列吞吐提升 10 倍。

多个 worker 同时啃一个任务队列时，SKIP LOCKED 能让每个 worker 自动跳过已被别人锁住的行，各取各的活，谁也不用排队等谁。

**错误做法（worker 之间互相卡死）：**

```sql
-- Worker 1 和 Worker 2 都来抢下一个任务
begin;
select * from jobs where status = 'pending' order by created_at limit 1 for update;
-- Worker 2 只能干等 Worker 1 放锁！
```

**正确做法（用 SKIP LOCKED 实现并行消费）：**

```sql
-- 每个 worker 跳过被锁的行，直接领下一个可用任务
begin;
select * from jobs
where status = 'pending'
order by created_at
limit 1
for update skip locked;

-- Worker 1 领走 job 1，Worker 2 领走 job 2，互不等待

update jobs set status = 'processing' where id = $1;
commit;
```

完整的队列消费写法：

```sql
-- 单条语句原子地"领取并更新"
update jobs
set status = 'processing', worker_id = $1, started_at = now()
where id = (
  select id from jobs
  where status = 'pending'
  order by created_at
  limit 1
  for update skip locked
)
returning *;
```

Reference: [SELECT FOR UPDATE SKIP LOCKED](https://www.postgresql.org/docs/current/sql-select.html#SQL-FOR-UPDATE-SHARE)
