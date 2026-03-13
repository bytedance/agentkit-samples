# PHP SDK Integration Reference

Source: https://github.com/volcengine/volcengine-php-sdk/blob/main/SDK_Integration.md

## Requirements

PHP >= 5.5. Install via Composer.

## Authentication

### AK/SK

```php
$config = \Volcengine\Common\Configuration::getDefaultConfiguration()
    ->setAk(getenv("VOLCENGINE_ACCESS_KEY"))
    ->setSk(getenv("VOLCENGINE_SECRET_KEY"))
    ->setRegion("cn-beijing");
```

### STS Token

```php
$config = \Volcengine\Common\Configuration::getDefaultConfiguration()
    ->setAk("TEMP_AK")
    ->setSk("TEMP_SK")
    ->setSessionToken("SESSION_TOKEN")
    ->setRegion("cn-beijing");
```

### STS AssumeRole

```php
$config = \Volcengine\Common\Configuration::getDefaultConfiguration()
    ->setAk("SUB_ACCOUNT_AK")
    ->setSk("SUB_ACCOUNT_SK")
    ->setRegion("cn-beijing")
    ->setAssumeRoleTrn("trn:iam::accountId:role/roleName")
    ->setAssumeRoleSessionName("session-name")
    ->setAssumeRoleDurationSeconds(3600);
```

## Endpoint Configuration

```php
// Custom endpoint
$config->setHost("custom-endpoint.volcengineapi.com");

// Custom region (auto-resolves endpoint)
$config->setRegion("cn-shanghai");

// DualStack (IPv6)
$config->setUseDualStack(true);
```

## SSL / HTTPS

```php
// Use HTTP instead of HTTPS
$config->setScheme("http");

// Disable SSL verification (testing only)
$config->setVerifySsl(false);

// Custom TLS version
$apiInstance = new \Volcengine\Ecs\Api\ECSApi(
    new GuzzleHttp\Client([
        'curl' => [CURLOPT_SSLVERSION => CURL_SSLVERSION_TLSv1_2],
    ]),
    $config
);
```

## Proxy

```php
$apiInstance = new \Volcengine\Ecs\Api\ECSApi(
    new GuzzleHttp\Client([
        'proxy' => 'http://proxy:8080',
    ]),
    $config
);
```

## Notes

The PHP SDK documentation does not currently cover retry, timeout, or logging configuration.
For the latest details, see: https://github.com/volcengine/volcengine-php-sdk/blob/main/SDK_Integration.md
