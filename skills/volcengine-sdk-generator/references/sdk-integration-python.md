# Python SDK Integration Reference

Source: https://github.com/volcengine/volcengine-python-sdk/blob/master/SDK_Integration.md

## Requirements

Python >= 2.7 (Python 3.6+ for Ark runtime).

## Authentication

### AK/SK

```python
import volcenginesdkcore

configuration = volcenginesdkcore.Configuration()
configuration.ak = os.environ.get("VOLCENGINE_ACCESS_KEY")
configuration.sk = os.environ.get("VOLCENGINE_SECRET_KEY")
configuration.region = "cn-beijing"
volcenginesdkcore.Configuration.set_default(configuration)
```

### STS Token

```python
configuration = volcenginesdkcore.Configuration()
configuration.ak = "TEMP_AK"
configuration.sk = "TEMP_SK"
configuration.session_token = "SESSION_TOKEN"
configuration.region = "cn-beijing"
volcenginesdkcore.Configuration.set_default(configuration)
```

### STS AssumeRole

```python
configuration = volcenginesdkcore.Configuration()
configuration.ak = "SUB_ACCOUNT_AK"
configuration.sk = "SUB_ACCOUNT_SK"
configuration.region = "cn-beijing"
configuration.assume_role_trn = "trn:iam::accountId:role/roleName"
configuration.assume_role_session_name = "session-name"
configuration.assume_role_duration_seconds = 3600
volcenginesdkcore.Configuration.set_default(configuration)
```

### STS AssumeRoleWithOIDC / SAML

```python
# OIDC
configuration.assume_role_with_oidc_trn = "trn:iam::accountId:role/roleName"
configuration.assume_role_with_oidc_provider = "trn:iam::accountId:oidc-provider/providerName"
configuration.assume_role_with_oidc_token = "oidc-token"

# SAML
configuration.assume_role_with_saml_trn = "trn:iam::accountId:role/roleName"
configuration.assume_role_with_saml_principal = "trn:iam::accountId:saml-provider/providerName"
configuration.assume_role_with_saml_assertion = "saml-assertion"
```

## Endpoint Configuration

```python
# Custom endpoint
configuration.host = "custom-endpoint.volcengineapi.com"

# Custom region (auto-resolves endpoint)
configuration.region = "cn-shanghai"

# DualStack (IPv6)
configuration.use_dual_stack = True
```

## Connection Pool

```python
# Default: 4 pools, maxsize = cpu_count * 5
configuration.connection_pool_maxsize = 20
configuration.connection_pools_count = 8
```

## SSL / HTTPS

```python
# Use HTTP instead of HTTPS
configuration.scheme = "http"

# Disable SSL verification (testing only)
configuration.verify_ssl = False

# Custom SSL CA cert
configuration.ssl_ca_cert = "/path/to/ca-bundle.crt"
```

## Proxy

```python
configuration.proxy = "http://proxy:8080"
configuration.proxy_https = "https://proxy:8080"
# Also reads env vars: http_proxy, https_proxy (code takes precedence)
```

## Timeouts

```python
# Default: 30s each
configuration.connection_timeout = 10   # seconds
configuration.read_timeout = 60         # seconds

# Per-request timeout via RuntimeOption
runtime_option = volcenginesdkcore.RuntimeOption()
runtime_option.connection_timeout = 5
runtime_option.read_timeout = 30
resp = api_instance.some_action(request, _runtime_option=runtime_option)
```

## Retry

```python
# Retry is enabled by default for network errors and throttling
configuration.max_retry_attempts = 5
configuration.min_retry_delay = 300      # ms
configuration.max_retry_delay = 300000   # ms

# Disable retry
configuration.max_retry_attempts = 0

# Custom retry error codes
configuration.retry_error_codes = ["Throttling", "ResourceIsBusy"]

# Backoff strategies: ExponentialBackoff, ExponentialBackoffWithJitter (default)
configuration.retry_backoff_strategy = "ExponentialBackoffWithJitter"
```

## Debugging

```python
configuration.debug = True
# Log level: configuration.log_level = "DEBUG"
# Log file: configuration.log_file = "/path/to/sdk.log"
```
