# Java SDK Integration Reference

Source: https://github.com/volcengine/volcengine-java-sdk/blob/master/SDK_Integration.md

## Requirements

Java 1.8.0_131+. For Java 9+, add `javax.annotation-api` dependency.

## Authentication

### AK/SK

```java
String ak = System.getenv("VOLCENGINE_ACCESS_KEY");
String sk = System.getenv("VOLCENGINE_SECRET_KEY");
ApiClient apiClient = new ApiClient()
        .setCredentials(Credentials.getCredentials(ak, sk))
        .setRegion("cn-beijing");
```

### STS Token

```java
String ak = System.getenv("VOLCENGINE_ACCESS_KEY");
String sk = System.getenv("VOLCENGINE_SECRET_KEY");
String token = System.getenv("VOLCENGINE_SESSION_TOKEN");
ApiClient apiClient = new ApiClient()
        .setCredentials(Credentials.getCredentials(ak, sk, token))
        .setRegion("cn-beijing");
```

### STS AssumeRole

```java
ApiClient apiClient = new ApiClient();
apiClient.setCredentials(Credentials.getAssumeRoleCredentials(
        ak, sk,
        "trn:iam::accountId:role/roleName",
        "sessionName",
        3600,    // durationSeconds
        null     // policy (optional)
));
apiClient.setRegion("cn-beijing");
```

## Endpoint Configuration

```java
// Custom endpoint
apiClient.setEndPoint("custom-endpoint.volcengineapi.com");

// Custom region (auto-resolves endpoint)
apiClient.setRegion("cn-shanghai");

// DualStack (IPv6)
apiClient.setUseDualStack(true);
```

## HTTP Connection Pool

```java
// Default: 5 idle connections, 5 min keep-alive
apiClient.setMaxIdleConns(10);
apiClient.setKeepAliveDurationMs(300000);
```

## SSL / HTTPS

```java
// Disable SSL verification (testing only)
apiClient.setVerifyingSsl(false);

// Use HTTP instead of HTTPS
apiClient.setDisableSSL(true);
```

## Proxy

```java
apiClient.setHttpProxy("http://proxy:8080");
apiClient.setHttpsProxy("https://proxy:8080");
// Also supports env vars: http_proxy, https_proxy
```

## Timeouts

```java
// All in milliseconds, default 10000 (10s)
apiClient.setConnectionTimeout(5000);
apiClient.setReadTimeout(30000);
apiClient.setWriteTimeout(30000);
```

## Retry

```java
// Retry is enabled by default with exponential backoff
// Configure retry attempts
apiClient.setRetrySettings(new RetrySettings()
        .setMaxAttempts(5)
        .setMinDelay(300)       // ms
        .setMaxDelay(300000)    // ms
);

// Disable retry
apiClient.setRetrySettings(new RetrySettings().setMaxAttempts(0));

// Custom retry error codes
apiClient.setRetrySettings(new RetrySettings()
        .setRetryableErrorCodes(Arrays.asList("Throttling", "ResourceIsBusy"))
);
```

## Debugging

```java
// Enable debug logging (uses SLF4J)
apiClient.setDebugging(true);
// Configure logger: com.volcengine.sdkcore
```
