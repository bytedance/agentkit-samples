# 应用集成指南

本指南介绍如何将 Supabase 集成到 TypeScript 或 Python 应用中，包括获取连接信息、初始化 SDK 客户端、和执行 CRUD 操作。

---

## 1. 获取连接信息

使用本 Skill 获取 Supabase 实例的连接 URL 和密钥：

```bash
# 获取 Supabase API URL
uv run ./scripts/call_volcengine_supabase.py get-workspace-url --workspace-id ws-xxxx

# 获取 API Keys（默认脱敏）
uv run ./scripts/call_volcengine_supabase.py get-keys --workspace-id ws-xxxx

# 获取完整密钥（需要时）
uv run ./scripts/call_volcengine_supabase.py get-keys --workspace-id ws-xxxx --reveal
```

你将获得以下信息，用于应用配置：

| 信息 | 用途 |
|------|------|
| **Supabase URL** | API 端点地址 |
| **anon key** | 客户端公开访问密钥（受 RLS 限制） |
| **service_role key** | 服务端管理密钥（绕过 RLS，仅限后端使用） |

> ⚠️ **安全提醒**：`service_role key` 拥有完整权限，**永远不要**暴露给客户端或前端代码。

---

## 2. 环境变量配置

建议在 `.env` 文件中配置：

```bash
SUPABASE_URL=https://your-project-url.supabase.co
SUPABASE_ANON_KEY=eyJ...your-anon-key
SUPABASE_SERVICE_ROLE_KEY=eyJ...your-service-role-key  # 仅后端使用
```

---

## 3. TypeScript 应用接入

### 安装依赖

```bash
npm install @supabase/supabase-js
```

### 初始化客户端

```typescript
import { createClient, SupabaseClient } from '@supabase/supabase-js';

// 服务端客户端（用于 API 路由、后端服务）
function getSupabaseClient(token?: string): SupabaseClient {
  const url = process.env.SUPABASE_URL!;
  const key = process.env.SUPABASE_ANON_KEY!;

  if (token) {
    // 带用户认证的客户端（RLS 按用户过滤）
    return createClient(url, key, {
      global: {
        headers: { Authorization: `Bearer ${token}` },
      },
      db: { timeout: 60000 },
      auth: { autoRefreshToken: false, persistSession: false },
    });
  }

  // 匿名客户端（RLS 按 anon 角色过滤）
  return createClient(url, key, {
    db: { timeout: 60000 },
    auth: { autoRefreshToken: false, persistSession: false },
  });
}
```

### CRUD 操作示例

#### 查询数据

```typescript
const client = getSupabaseClient();

// 基础查询
const { data, error } = await client.from('posts').select('*').limit(10);

// 带过滤条件
const { data: activePosts } = await client
  .from('posts')
  .select('*')
  .eq('published', true)
  .order('created_at', { ascending: false })
  .limit(20);

// 选择特定列
const { data: titles } = await client.from('posts').select('id, title, created_at');

// 模糊搜索
const { data: results } = await client.from('posts').select('*').ilike('title', '%keyword%');

// 范围查询
const { data: recent } = await client
  .from('posts')
  .select('*')
  .gte('created_at', '2024-01-01')
  .lte('created_at', '2024-12-31');

// 分页查询
const { data: page } = await client
  .from('posts')
  .select('*')
  .range(0, 9); // 第 1-10 条

// 关联查询（需要外键关系）
const { data: postsWithAuthor } = await client
  .from('posts')
  .select('*, users(name, email)');

// 统计数量
const { count } = await client
  .from('posts')
  .select('*', { count: 'exact', head: true });
```

#### 插入数据

```typescript
// 单条插入
const { data, error } = await client
  .from('posts')
  .insert({ title: 'Hello World', content: 'My first post' })
  .select(); // 返回插入的数据

// 批量插入
const { data: batch } = await client
  .from('posts')
  .insert([
    { title: 'Post 1', content: 'Content 1' },
    { title: 'Post 2', content: 'Content 2' },
  ])
  .select();
```

#### 更新数据

```typescript
// 按条件更新
const { data, error } = await client
  .from('posts')
  .update({ published: true, updated_at: new Date().toISOString() })
  .eq('id', 1)
  .select();

// UPSERT（存在则更新，不存在则插入）
const { data: upserted } = await client
  .from('settings')
  .upsert({ key: 'theme', value: 'dark' }, { onConflict: 'key' })
  .select();
```

#### 删除数据

```typescript
// 按条件删除
const { error } = await client.from('posts').delete().eq('id', 1);

// 多条件删除
const { error: batchError } = await client
  .from('posts')
  .delete()
  .eq('published', false)
  .lt('created_at', '2023-01-01');
```

#### 错误处理

```typescript
const { data, error } = await client.from('posts').select('*');

if (error) {
  console.error(`Error code: ${error.code}, message: ${error.message}`);
  // 常见错误码：
  // PGRST116 - 查询结果为空（使用 .single() 时）
  // PGRST200 - 关联查询缺少外键关系
  // 42501    - RLS 策略拒绝访问
  // 23505    - 唯一约束冲突
  return;
}

console.log(data);
```

---

## 4. Python 应用接入

### 安装依赖

```bash
pip install supabase httpx
```

### 初始化客户端

```python
import os
from typing import Optional
import httpx
from supabase import create_client, Client, ClientOptions


def get_supabase_client(token: Optional[str] = None) -> Client:
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_ANON_KEY"]

    http_client = httpx.Client(
        timeout=httpx.Timeout(connect=20.0, read=60.0, write=60.0, pool=10.0),
        limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
        follow_redirects=True,
    )

    if token:
        # 带用户认证的客户端
        options = ClientOptions(
            httpx_client=http_client,
            headers={"Authorization": f"Bearer {token}"},
            auto_refresh_token=False,
        )
    else:
        # 匿名客户端
        options = ClientOptions(
            httpx_client=http_client,
            auto_refresh_token=False,
        )

    return create_client(url, key, options=options)
```

### CRUD 操作示例

#### 查询数据

```python
client = get_supabase_client()

# 基础查询
response = client.table('posts').select('*').limit(10).execute()
print(response.data)

# 带过滤条件
response = (client.table('posts')
    .select('*')
    .eq('published', True)
    .order('created_at', desc=True)
    .limit(20)
    .execute())

# 选择特定列
response = client.table('posts').select('id, title, created_at').execute()

# 模糊搜索
response = client.table('posts').select('*').ilike('title', '%keyword%').execute()

# 范围查询
response = (client.table('posts')
    .select('*')
    .gte('created_at', '2024-01-01')
    .lte('created_at', '2024-12-31')
    .execute())

# 分页查询
response = client.table('posts').select('*').range(0, 9).execute()

# 关联查询（需要外键）
response = client.table('posts').select('*, users(name, email)').execute()

# 统计数量
response = client.table('posts').select('*', count='exact').execute()
print(response.count)
```

#### 插入数据

```python
# 单条插入
response = client.table('posts').insert({
    'title': 'Hello World',
    'content': 'My first post'
}).execute()
print(response.data)

# 批量插入
response = client.table('posts').insert([
    {'title': 'Post 1', 'content': 'Content 1'},
    {'title': 'Post 2', 'content': 'Content 2'},
]).execute()
```

#### 更新数据

```python
# 按条件更新
response = (client.table('posts')
    .update({'published': True})
    .eq('id', 1)
    .execute())

# UPSERT
response = (client.table('settings')
    .upsert({'key': 'theme', 'value': 'dark'})
    .execute())
```

#### 删除数据

```python
# 按条件删除
response = client.table('posts').delete().eq('id', 1).execute()
```

#### 错误处理

```python
try:
    response = client.table('posts').select('*').execute()
    print(response.data)
except Exception as e:
    print(f"Error: {e}")
```

---

## 5. RPC 调用（存储过程）

如果需要复杂的数据库操作，可以先通过 `execute-sql` 创建存储过程，然后通过 SDK 调用。

### 创建存储过程

```bash
uv run ./scripts/call_volcengine_supabase.py execute-sql \
  --workspace-id ws-xxxx \
  --query "
CREATE OR REPLACE FUNCTION search_posts(keyword text)
RETURNS SETOF posts AS \$\$
  SELECT * FROM posts
  WHERE title ILIKE '%' || keyword || '%'
     OR content ILIKE '%' || keyword || '%'
  ORDER BY created_at DESC;
\$\$ LANGUAGE sql STABLE;
"
```

### SDK 调用

```typescript
// TypeScript
const { data, error } = await client.rpc('search_posts', { keyword: 'supabase' });
```

```python
# Python
response = client.rpc('search_posts', {'keyword': 'supabase'}).execute()
```

---

## 6. Storage 文件操作

通过本 Skill 创建 Storage Bucket 后，可以在应用中使用 SDK 操作文件。

### 创建 Bucket（通过 CLI）

```bash
# 创建公开 bucket
uv run ./scripts/call_volcengine_supabase.py create-storage-bucket \
  --workspace-id ws-xxxx --bucket-name avatars --public

# 创建私有 bucket
uv run ./scripts/call_volcengine_supabase.py create-storage-bucket \
  --workspace-id ws-xxxx --bucket-name documents
```

### SDK 文件操作（TypeScript）

```typescript
const client = getSupabaseClient();

// 上传文件
const { data, error } = await client.storage
  .from('avatars')
  .upload('user1/avatar.png', fileBuffer, {
    contentType: 'image/png',
    cacheControl: '3600',
  });

// 获取公开 URL
const { data: urlData } = client.storage
  .from('avatars')
  .getPublicUrl('user1/avatar.png');

// 获取签名 URL（临时访问私有文件）
const { data: signedUrl } = await client.storage
  .from('documents')
  .createSignedUrl('report.pdf', 3600); // 1 小时有效

// 下载文件
const { data: fileData } = await client.storage
  .from('documents')
  .download('report.pdf');

// 删除文件
const { data: deleteData } = await client.storage
  .from('avatars')
  .remove(['user1/old-avatar.png']);

// 列出文件
const { data: files } = await client.storage
  .from('avatars')
  .list('user1/', { limit: 100, offset: 0 });
```

### SDK 文件操作（Python）

```python
client = get_supabase_client()

# 上传文件
with open('avatar.png', 'rb') as f:
    response = client.storage.from_('avatars').upload('user1/avatar.png', f.read())

# 获取公开 URL
url = client.storage.from_('avatars').get_public_url('user1/avatar.png')

# 获取签名 URL
signed_url = client.storage.from_('documents').create_signed_url('report.pdf', 3600)

# 下载文件
file_data = client.storage.from_('documents').download('report.pdf')

# 删除文件
response = client.storage.from_('avatars').remove(['user1/old-avatar.png'])

# 列出文件
files = client.storage.from_('avatars').list('user1/')
```
