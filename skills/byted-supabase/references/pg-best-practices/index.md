# Postgres 性能与最佳实践

> 📌 译自 Supabase 官方 agent skills（`supabase/agent-skills` → `supabase-postgres-best-practices`，MIT License, © Supabase），翻译为中文并适配火山引擎 Supabase 版。

按影响优先级组织的 Postgres 性能优化与最佳实践规则，共 8 类、31 条。每条含「错误 / 正确」SQL 对比与适用说明。所有 SQL 通过 `byted-supabase-cli db query "<sql>" --workspace-id ws-...` 执行；改完跑 `byted-supabase-cli db advisors --workspace-id ws-...` 巡检。

## 何时查阅

- 写 SQL 查询或设计 schema
- 实现索引或查询优化
- 排查数据库性能问题
- 配置连接池或扩容
- 配置行级安全（RLS）

## 分类（按影响优先级）

| 优先级 | 分类 | 影响 | 文件 |
|--------|------|------|------|
| 1 | 查询性能 | CRITICAL | [`query.md`](query.md) |
| 2 | 连接管理 | CRITICAL | [`conn.md`](conn.md) |
| 3 | 安全与 RLS | CRITICAL | [`security.md`](security.md) |
| 4 | Schema 设计 | HIGH | [`schema.md`](schema.md) |
| 5 | 并发与锁 | MEDIUM-HIGH | [`lock.md`](lock.md) |
| 6 | 数据访问模式 | MEDIUM | [`data.md`](data.md) |
| 7 | 监控与诊断 | LOW-MEDIUM | [`monitor.md`](monitor.md) |
| 8 | 高级特性 | LOW | [`advanced.md`](advanced.md) |

> 相关：Supabase 特有安全陷阱见 [`../security-guide.md`](../security-guide.md)，RLS 配置模板见 [`../rls-guide.md`](../rls-guide.md)，火山命名约定与建表模板见 [`../schema-guide.md`](../schema-guide.md)。

## 参考

- https://www.postgresql.org/docs/current/
- https://supabase.com/docs/guides/database/overview
- https://supabase.com/docs/guides/auth/row-level-security
- 火山引擎 Database 文档：https://www.volcengine.com/docs/87275/2385100?lang=zh
