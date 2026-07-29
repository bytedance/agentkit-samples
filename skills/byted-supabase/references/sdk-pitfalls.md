# Supabase SDK 与查询常见陷阱

本文档汇总 AI 生成 Supabase 相关代码时容易忽略的三类实战问题。在为用户编写 Supabase 查询、SDK 调用或建表 SQL 时，必须逐条检查。

## 目录

1. [URL 长度限制](#1-url-长度限制)
2. [SDK 错误捕获](#2-sdk-错误捕获)
3. [索引评估](#3-索引评估)

## 1. URL 长度限制

### 问题

Supabase REST API 的 `.in()` / `filter('id', 'in', [...])` 查询会将所有 ID 编码进 URL query string。当 ID 数量较多时（如 200+ room ID + 230+ agent ID，URL 约 9000 字符），会超过 Nginx / 代理层的默认 URL 长度限制（~4096 字符），导致查询**静默失败返回空结果**（无报错）。

### 典型表现

- `limit=5~100` 正常（ID 少，URL 短）
- `limit=200` 全部字段为 null（URL 超长，查询静默失败）
- 沙箱环境正常（数据少，只有 49 条记录）
- 详情页正常（单条记录只查 2~6 个关联项）

### 解决方案

**方案 A — RPC 函数（推荐）**：将大批量 ID 查询包装为 Postgres 函数，通过 `db query` 调用，参数走函数体而非 URL：

```sql
CREATE OR REPLACE FUNCTION get_rooms_by_ids(p_ids uuid[])
RETURNS SETOF rooms AS $$
  SELECT * FROM rooms WHERE id = ANY(p_ids);
$$ LANGUAGE sql STABLE;
```

调用：`byted-supabase-cli db query "SELECT * FROM get_rooms_by_ids(ARRAY['id1','id2',...]::uuid[])" --workspace-id ws-...`

**方案 B — 分批查询**：将 ID 列表拆分为每批 50-100 个，多次查询后合并结果。

## 2. SDK 错误捕获

### 问题

Supabase SDK（JS / Python / Go）在查询失败、限流、网络异常时**不一定抛异常**，可能返回 `null` / `undefined` / 空 data 且 error 字段有值。AI 生成代码时如果不明确要求，通常不会主动 catch 错误。

### 典型表现

- API 返回 500 时，fetch 不会 reject，`json.data` 为 `undefined`，前端保持空数组
- API 返回空数组 `{ data: [] }` 时，`[]` 是 truthy，进入正常分支，前端渲染空
- 限流时 response 返回 NULL，前端界面显示"查不出来"但无任何错误提示

以上情况都可能导致 `loaded && sites.length === 0` → 组件不渲染，且无任何报错信息。

### 规范要求

写 Supabase 相关代码时**必须**：

1. **每次查询后检查 error 字段**：`if (error) throw error` 或等价处理
2. **用 try-catch 包裹所有 SDK 调用**：确保异常能被上层感知
3. **对 data 做空值防御**：`data ?? []`、`data?.length > 0` 等

示例（JS）：

```javascript
const { data, error } = await supabase.from('rooms').select('*').limit(200);
if (error) {
  console.error('Query failed:', error.message);
  throw error; // 或 fallback 处理
}
const rooms = data ?? [];
```

示例（Python）：

```python
result = supabase.table('rooms').select('*').limit(200).execute()
if result.error:
    raise Exception(f"Query failed: {result.error}")
rooms = result.data or []
```

## 3. 索引评估

### 问题

AI 生成 SQL 时往往只关注功能正确性，不会主动评估索引需求。初期数据量小时无感知，一旦表行数超过几十万，缺少索引的查询性能会急剧劣化。

### 规范要求

1. **主键**自动有索引（Postgres 默认行为）
2. 所有频繁用于 `WHERE` 过滤的列、外键列、`ORDER BY` 列**都应建索引**
3. 复合查询考虑**复合索引**（注意列顺序：等值条件列在前，范围条件列在后）
4. 建表或写查询后，用 `db advisors` 巡检是否缺少索引建议：
   ```bash
   byted-supabase-cli db advisors --workspace-id ws-...
   ```

### 示例

```sql
-- 用户房间关联表：频繁按 user_id 查询 + 按 created_at 排序
CREATE TABLE user_rooms (
  user_id uuid REFERENCES users(id),
  room_id uuid REFERENCES rooms(id),
  joined_at timestamptz DEFAULT now(),
  PRIMARY KEY (user_id, room_id)
);

-- 必须为常用查询模式建索引
CREATE INDEX idx_user_rooms_user_id ON user_rooms(user_id);
CREATE INDEX idx_user_rooms_user_joined ON user_rooms(user_id, joined_at DESC);
```
