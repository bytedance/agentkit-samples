# Go SDK Integration Reference

Source: https://github.com/volcengine/volcengine-go-sdk/blob/master/SDK_Integration.md

## Requirements

Go 1.14+ (1.18+ for Ark service). Use `go mod` for dependency management.

## Authentication

### AK/SK

```go
ak := os.Getenv("VOLCENGINE_ACCESS_KEY")
sk := os.Getenv("VOLCENGINE_SECRET_KEY")
config := volcengine.NewConfig().
    WithRegion("cn-beijing").
    WithCredentials(credentials.NewStaticCredentials(ak, sk, ""))
sess, _ := session.NewSession(config)
```

Env vars: `VOLCSTACK_ACCESS_KEY_ID`, `VOLCSTACK_SECRET_ACCESS_KEY`

### STS Token

```go
config := volcengine.NewConfig().
    WithRegion("cn-beijing").
    WithCredentials(credentials.NewStaticCredentials(ak, sk, sessionToken))
```

### STS AssumeRole

```go
config := volcengine.NewConfig().
    WithRegion("cn-beijing").
    WithCredentials(credentials.NewAssumeRoleCredentials(
        ak, sk,
        "trn:iam::accountId:role/roleName",
        "sessionName",
        3600,    // durationSeconds
    ))
```

### STS AssumeRoleWithOIDC (file-based)

```go
config := volcengine.NewConfig().
    WithRegion("cn-beijing").
    WithCredentials(credentials.NewOIDCRoleCredentials(
        ak, sk,
        "trn:iam::accountId:role/roleName",
        "trn:iam::accountId:oidc-provider/providerName",
        "/path/to/oidc-token-file",
        "sessionName",
        3600,
    ))
```

## Endpoint Configuration

```go
// Custom endpoint
config.WithEndpoint("custom-endpoint.volcengineapi.com")

// Custom region
config.WithRegion("cn-shanghai")

// DualStack (IPv6)
config.WithUseDualStack(true)
```

## HTTP Connection Pool

```go
// Default: 100 max idle connections, 90s timeout
// Customize via custom http.Client
httpClient := &http.Client{
    Transport: &http.Transport{
        MaxIdleConns:    200,
        IdleConnTimeout: 120 * time.Second,
    },
}
config.WithHTTPClient(httpClient)
```

## SSL / HTTPS

```go
// Disable SSL (use HTTP)
config.WithDisableSSL(true)

// Custom TLS config
tlsConfig := &tls.Config{
    MinVersion: tls.VersionTLS12,
    MaxVersion: tls.VersionTLS13,
}
```

## Proxy

```go
config.WithHTTPProxy("http://proxy:8080")
config.WithHTTPSProxy("https://proxy:8080")
// Also reads env vars: http_proxy, https_proxy
```

## Timeouts

```go
// Global client-level (default: 30s connection)
config.WithHTTPClient(&http.Client{
    Timeout: 60 * time.Second,
})

// Per-API timeout via context (use {Action}WithContext methods)
ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
defer cancel()
resp, err := svc.DescribeInstancesWithContext(ctx, input)
```

## Retry

```go
// Default: 3 retries for network errors
// Disable retry
config.WithMaxRetries(0)

// Custom max retries
config.WithMaxRetries(5)

// Custom retry error codes (per-request)
input.SetRetryableErrorCodes([]string{"Throttling", "ResourceIsBusy"})
```

## Debugging

```go
config.WithDebug(true)
// Custom log writer
config.WithLogWriter(os.Stderr)
```
