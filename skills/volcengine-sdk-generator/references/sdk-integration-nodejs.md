# Node.js SDK Integration Reference

Source: https://github.com/volcengine/volcengine-nodejs-sdk/blob/master/SDK_Integration.md

## Requirements

Node.js >= 18. Install via pnpm/npm/yarn.

```bash
pnpm add @volcengine/sdk-core
pnpm add @volcengine/ecs  # service-specific package
```

## Authentication

Credential priority: Code config > Environment variables > Config file (`~/.volc/config`)

### AK/SK

```typescript
// Method 1: Code (not recommended for plain text)
const client = new EcsClient({
    accessKeyId: "YOUR_AK",
    secretAccessKey: "YOUR_SK",
    region: "cn-beijing",
});

// Method 2: Environment variables (recommended)
// export VOLCSTACK_ACCESS_KEY_ID="YOUR_AK"
// export VOLCSTACK_SECRET_ACCESS_KEY="YOUR_SK"
const client = new EcsClient({ region: "cn-beijing" });

// Method 3: Config file (~/.volc/config)
// { "VOLC_ACCESSKEY": "AK", "VOLC_SECRETKEY": "SK" }
```

### STS Token

```typescript
const client = new EcsClient({
    accessKeyId: "TEMP_AK",
    secretAccessKey: "TEMP_SK",
    sessionToken: "SESSION_TOKEN",
    region: "cn-beijing",
});
// Or via env: VOLCSTACK_SESSION_TOKEN
```

### STS AssumeRole

```typescript
const client = new EcsClient({
    region: "cn-beijing",
    assumeRoleParams: {
        accessKeyId: "SUB_ACCOUNT_AK",
        secretAccessKey: "SUB_ACCOUNT_SK",
        roleName: "role123",
        accountId: "2110400000",
        region: "cn-beijing",
        host: "sts.volcengineapi.com",
        durationSeconds: 3600,
        policy: '{"Statement":[...]}',  // optional
        tags: [{ Key: "project", Value: "test" }],  // optional
    },
});
```

## Endpoint Configuration

```typescript
// Custom endpoint (highest priority)
const client = new EcsClient({ host: "open.volcengineapi.com" });

// Custom region (auto-resolves endpoint)
const client = new EcsClient({ region: "cn-shanghai" });

// DualStack (IPv6) - suffix changes to volcengine-api.com
const client = new EcsClient({ region: "cn-beijing", useDualStack: true });

// Custom bootstrap region list
const client = new EcsClient({
    region: "my-private-region",
    customBootstrapRegion: { "my-private-region": {} },
});
// Or via env: VOLC_BOOTSTRAP_REGION_LIST_CONF=/path/to/regions.conf
```

### Endpoint Resolution Rules

| Global Service | DualStack | Format |
|---|---|---|
| Yes | No | `{Service}.volcengineapi.com` |
| Yes | Yes | `{Service}.volcengine-api.com` |
| No | No | `{Service}.{region}.volcengineapi.com` |
| No | Yes | `{Service}.{region}.volcengine-api.com` |

## Network Configuration

```typescript
// Protocol (default: https)
const client = new EcsClient({ protocol: "http" });

// Proxy
const client = new EcsClient({
    httpOptions: {
        proxy: { protocol: "http", host: "127.0.0.1", port: 8888 },
    },
});
// Or via env: VOLC_PROXY_PROTOCOL, VOLC_PROXY_HOST, VOLC_PROXY_PORT

// Ignore SSL verification (testing only)
const client = new EcsClient({ httpOptions: { ignoreSSL: true } });

// Connection pool
const client = new EcsClient({
    httpOptions: {
        pool: {
            keepAlive: true,
            keepAliveMsecs: 1000,
            maxSockets: 50,
            maxFreeSockets: 10,
        },
    },
});
```

## Timeouts

```typescript
// Client-level (default: 30000ms)
const client = new EcsClient({ httpOptions: { timeout: 5000 } });

// Request-level (overrides client)
await client.send(command, { timeout: 30000 });
```

## Retry

```typescript
// Default: 4 attempts (1 initial + 3 retries)
// Retries on: network errors, HTTP 429/500/502/503/504

// Custom max retries
const client = new EcsClient({ maxRetries: 5 });

// Disable retry
const client = new EcsClient({ autoRetry: false });

// Backoff strategies
import { StrategyName } from "@volcengine/sdk-core";
const client = new EcsClient({
    strategyName: StrategyName.ExponentialWithRandomJitterBackoffStrategy, // default
});
// Options: NoBackoffStrategy, ExponentialBackoffStrategy, ExponentialWithRandomJitterBackoffStrategy

// Custom retry strategy
const client = new EcsClient({
    retryStrategy: {
        minRetryDelay: 500,
        maxRetryDelay: 20000,
        retryIf: (error) => {
            if (error.data?.ResponseMetadata?.Error?.Code === "ResourceIsBusy") return true;
            return false;
        },
        delay: (attemptNumber) => 1000,
    },
});
```

## Exception Handling

```typescript
import { HttpRequestError } from "@volcengine/sdk-core";

try {
    await client.send(command);
} catch (error) {
    if (error instanceof HttpRequestError) {
        if (error.status !== undefined) {
            if (error.status === 0) {
                // SSL error
            } else if (error.data?.ResponseMetadata?.Error) {
                const { Code, Message } = error.data.ResponseMetadata.Error;
                const { RequestId } = error.data.ResponseMetadata;
                // API error
            }
        } else if (error.name === "NetworkError") {
            // Network error (timeout, DNS, connection refused)
        }
    }
}
```

## Resource Cleanup

```typescript
client.destroy();  // Release network connections before app exit
```

## Debugging

```typescript
// Add logging middleware
client.middlewareStack.add(
    (next, context) => async (args) => {
        console.log("Request:", args.request.method, args.request.host);
        const result = await next(args);
        console.log("Response:", result.response?.status);
        return result;
    },
    { step: "finalizeRequest", name: "LogMiddleware", priority: 10 }
);
```

## Environment Variables

| Variable | Description |
|---|---|
| `VOLCSTACK_ACCESS_KEY_ID` / `VOLCSTACK_ACCESS_KEY` | Access Key ID |
| `VOLCSTACK_SECRET_ACCESS_KEY` / `VOLCSTACK_SECRET_KEY` | Secret Access Key |
| `VOLCSTACK_SESSION_TOKEN` | Session Token |
| `VOLC_ENABLE_DUALSTACK` | Enable DualStack (IPv6) |
| `VOLC_BOOTSTRAP_REGION_LIST_CONF` | Custom bootstrap region list file |
| `VOLC_PROXY_PROTOCOL` | Proxy protocol |
| `VOLC_PROXY_HOST` | Proxy host |
| `VOLC_PROXY_PORT` | Proxy port |
