# Edge Function 开发指南

本指南介绍 Edge Function 的编写规范和常见模式。本 fork 的部署从**本地函数目录**进行：`byted-supabase-cli functions new <name>` 生成 `supabase/functions/<name>/index.ts` 脚手架 → 编辑 → `byted-supabase-cli functions deploy <name>`。

---

## 目录

- 基础结构
- CORS 配置
- 请求处理
- 带数据库访问
- 常见模式
- 部署与管理
- 注意事项

## 基础结构

每个 Edge Function 是一个 Deno 函数，使用 `Deno.serve()` 处理 HTTP 请求：

```typescript
Deno.serve(async (req: Request) => {
  return new Response(JSON.stringify({ message: 'Hello World' }), {
    headers: { 'Content-Type': 'application/json' },
  });
});
```

部署：

```bash
byted-supabase-cli functions new hello                     # 生成 supabase/functions/hello/index.ts
# 把上面的代码写入该文件后部署
byted-supabase-cli functions deploy hello --workspace-id ws-xxxx
```

---

## CORS 配置

大多数前端调用都需要 CORS 支持：

```typescript
const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
  'Access-Control-Allow-Headers': 'Authorization, Content-Type, x-client-info, apikey',
};

Deno.serve(async (req: Request) => {
  // 处理 CORS 预检请求
  if (req.method === 'OPTIONS') {
    return new Response('ok', { headers: corsHeaders });
  }

  try {
    const data = { message: 'Hello World' };

    return new Response(JSON.stringify(data), {
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    });
  } catch (error) {
    return new Response(JSON.stringify({ error: error.message }), {
      status: 500,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    });
  }
});
```

---

## 请求处理

### 读取请求体

```typescript
Deno.serve(async (req: Request) => {
  // JSON 请求体
  const body = await req.json();
  const { name, email } = body;

  // URL 参数
  const url = new URL(req.url);
  const page = url.searchParams.get('page') || '1';

  // 请求头
  const authHeader = req.headers.get('Authorization');

  return new Response(JSON.stringify({ name, email, page }), {
    headers: { 'Content-Type': 'application/json' },
  });
});
```

### 路由分发

```typescript
Deno.serve(async (req: Request) => {
  const url = new URL(req.url);
  const path = url.pathname;

  if (req.method === 'GET' && path === '/') {
    return handleList(req);
  }
  if (req.method === 'POST' && path === '/') {
    return handleCreate(req);
  }
  if (req.method === 'PUT') {
    return handleUpdate(req);
  }
  if (req.method === 'DELETE') {
    return handleDelete(req);
  }

  return new Response('Not Found', { status: 404 });
});
```

---

## 带数据库访问

Edge Function 可以通过 Supabase SDK 或直接使用环境变量中的连接信息访问数据库：

```typescript
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2';

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'Authorization, Content-Type, x-client-info, apikey',
};

Deno.serve(async (req: Request) => {
  if (req.method === 'OPTIONS') {
    return new Response('ok', { headers: corsHeaders });
  }

  try {
    // 使用环境变量创建 Supabase 客户端
    const supabaseUrl = Deno.env.get('SUPABASE_URL')!;
    const supabaseKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;
    const supabase = createClient(supabaseUrl, supabaseKey);

    // 如果需要以用户身份访问（尊重 RLS）
    const authHeader = req.headers.get('Authorization');
    if (authHeader) {
      const userToken = authHeader.replace('Bearer ', '');
      const userClient = createClient(supabaseUrl, Deno.env.get('SUPABASE_ANON_KEY')!, {
        global: { headers: { Authorization: `Bearer ${userToken}` } },
      });
      // 使用 userClient 进行受 RLS 保护的操作
    }

    // 示例：查询数据
    const { data, error } = await supabase
      .from('posts')
      .select('*')
      .order('created_at', { ascending: false })
      .limit(10);

    if (error) throw error;

    return new Response(JSON.stringify(data), {
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    });
  } catch (error) {
    return new Response(JSON.stringify({ error: error.message }), {
      status: 500,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    });
  }
});
```

---

## 常见模式

### CRUD API

```typescript
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2';

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'Authorization, Content-Type, x-client-info, apikey',
};

Deno.serve(async (req: Request) => {
  if (req.method === 'OPTIONS') {
    return new Response('ok', { headers: corsHeaders });
  }

  const supabase = createClient(
    Deno.env.get('SUPABASE_URL')!,
    Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!,
  );

  try {
    let result;

    switch (req.method) {
      case 'GET': {
        const url = new URL(req.url);
        const id = url.searchParams.get('id');
        if (id) {
          result = await supabase.from('items').select('*').eq('id', id).single();
        } else {
          result = await supabase.from('items').select('*').order('created_at', { ascending: false });
        }
        break;
      }
      case 'POST': {
        const body = await req.json();
        result = await supabase.from('items').insert(body).select();
        break;
      }
      case 'PUT': {
        const body = await req.json();
        const { id, ...updates } = body;
        result = await supabase.from('items').update(updates).eq('id', id).select();
        break;
      }
      case 'DELETE': {
        const url = new URL(req.url);
        const id = url.searchParams.get('id');
        result = await supabase.from('items').delete().eq('id', id!);
        break;
      }
    }

    if (result?.error) throw result.error;

    return new Response(JSON.stringify(result?.data), {
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    });
  } catch (error) {
    return new Response(JSON.stringify({ error: error.message }), {
      status: 500,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    });
  }
});
```

### Webhook 处理器

```typescript
Deno.serve(async (req: Request) => {
  if (req.method !== 'POST') {
    return new Response('Method Not Allowed', { status: 405 });
  }

  try {
    const payload = await req.json();

    // 验证 Webhook 签名（根据实际来源调整）
    const signature = req.headers.get('x-webhook-signature');
    if (!signature) {
      return new Response('Unauthorized', { status: 401 });
    }

    // 处理事件
    console.log('Received webhook:', payload.type);

    switch (payload.type) {
      case 'order.created':
        // 处理订单创建事件
        break;
      case 'payment.completed':
        // 处理支付完成事件
        break;
      default:
        console.log('Unhandled event type:', payload.type);
    }

    return new Response(JSON.stringify({ received: true }), {
      headers: { 'Content-Type': 'application/json' },
    });
  } catch (error) {
    return new Response(JSON.stringify({ error: error.message }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' },
    });
  }
});
```

### 数据聚合 / 报表

```typescript
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2';

Deno.serve(async (req: Request) => {
  const supabase = createClient(
    Deno.env.get('SUPABASE_URL')!,
    Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!,
  );

  try {
    // 使用 RPC 调用数据库函数进行聚合
    const { data: stats, error } = await supabase.rpc('get_dashboard_stats');
    if (error) throw error;

    return new Response(JSON.stringify(stats), {
      headers: {
        'Content-Type': 'application/json',
        'Cache-Control': 'public, max-age=300', // 缓存 5 分钟
      },
    });
  } catch (error) {
    return new Response(JSON.stringify({ error: error.message }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' },
    });
  }
});
```

---

## 部署与管理

```bash
# 1. 新建函数脚手架（本地 supabase/functions/my-api/index.ts）
byted-supabase-cli functions new my-api
# 2. 编辑该文件写入逻辑，然后部署
byted-supabase-cli functions deploy my-api --workspace-id ws-xxxx

# 部署时禁用 JWT 验证（公开 API，如 Webhook）
byted-supabase-cli functions deploy public-api --workspace-id ws-xxxx --no-verify-jwt

# 指定运行时（默认 auto；可选 deno / native-node20/v1 / python3.9|3.10|3.12）
byted-supabase-cli functions deploy my-api --workspace-id ws-xxxx --runtime deno

# 查看已部署函数
byted-supabase-cli functions list --workspace-id ws-xxxx -o json

# 拉取线上函数源码到本地
byted-supabase-cli functions download my-api --workspace-id ws-xxxx

# 删除函数
byted-supabase-cli functions delete my-api --workspace-id ws-xxxx
```

---

## 注意事项

- **JWT 验证**：默认启用。如果函数需要公开访问（如 Webhook），使用 `--no-verify-jwt`
- **函数命名**：只能使用小写字母、数字和连字符（如 `my-api`、`process-order`）
- **超时**：Edge Function 有执行时间限制，避免长时间阻塞操作
- **日志**：使用 `console.log()` 记录日志，可在平台控制台查看
- **依赖导入**：使用 `https://esm.sh/` 导入 npm 包，或使用 `https://deno.land/` 导入 Deno 标准库
