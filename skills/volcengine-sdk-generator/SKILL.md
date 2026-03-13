---
name: volcengine-sdk-generator
description: >
  Generate complete, runnable Volcengine SDK code and provide SDK configuration guidance.
  Supports Go, Python, PHP, Java, and Node.js. Trigger this skill whenever the user wants to call
  a Volcengine API, generate Volcengine SDK code, or describes a cloud operation on Volcengine
  (e.g., "list ECS instances", "create a VPC on Volcengine", "query Volcengine billing with Python").
  Also trigger when the user asks about Volcengine SDK configuration and best practices — including
  retry, timeout, authentication (AK/SK, STS, AssumeRole), proxy, connection pooling, SSL, debug mode,
  and error handling (e.g., "how to configure retry for Volcengine Go SDK", "volcengine python sdk
  proxy setup"). Trigger when the user mentions Volcengine service names such as ECS, VPC, CDN, CLB,
  RDS, Redis, Kafka, billing, IAM, DNS with code generation or SDK usage intent.
  When the user only needs API specification queries (parameters, error codes, response structures),
  hand off to the volcengine-api skill. When the user needs CLI-based operations, hand off to
  the volcengine-cli skill. Supports both Chinese and English prompts.
---

# Volcengine SDK Code Generator

Generate complete, runnable Volcengine SDK code from natural-language descriptions, and answer SDK configuration questions.

## Workflow

When a user describes a Volcengine API operation, follow these steps:

### Step 1: Identify Target Service, Operation, and Advanced Configuration Needs

Parse the user's description to determine:
- **Target service**: which Volcengine service (e.g., ECS, VPC, TOS, billing)
- **Target operation**: what operation to perform (e.g., list instances, create a VPC, query billing)
- **Target language**: which programming language (Go, Python, PHP, Java, Node.js). If not specified, ask the user.
- **Advanced configuration needs**: whether the user mentions or the scenario implies any of the following:
  - **Retry**: user mentions "retry", "fault tolerance", or the operation is a write/create type (prone to throttling)
  - **Timeout**: user mentions "timeout", or the operation involves large data volumes (batch queries, file uploads)
  - **Credentials**: user mentions "STS", "AssumeRole", "temporary credentials", "OIDC", or explicitly wants to avoid hardcoding AK/SK
  - **Proxy/network**: user mentions "proxy" or "internal network"
  - **Debug mode**: user mentions "debug" or "logging"
  - **Connection pooling**: user mentions "connection pool", "high concurrency", or "pool"

  If the user explicitly requests these, include the corresponding configuration in the generated code. If not explicitly requested but implied by the scenario (e.g., resource creation naturally warrants retry), include suggested configuration as comments.

### Step 2: Query Service Metadata via Volcengine API Explorer

Use the following APIs to find the correct service code, version, and action name. This step is critical because guessing often produces incorrect code — the API Explorer is the authoritative source.

**2a. Find the ServiceCode**

Fetch the service catalog:
```
GET https://api.volcengine.com/api/common/explorer/services
```
Response structure:
```json
{
  "Result": {
    "Categories": [
      {
        "CategoryName": "...",
        "Services": [
          {
            "ServiceCn": "Cloud Server",
            "ServiceCode": "ecs",
            "Product": "ECS",
            "IsSdkAvailable": true,
            "RegionType": "regional"
          }
        ]
      }
    ]
  }
}
```
Match the user's intent to the correct `ServiceCode` based on `ServiceCn`, `Product`, and category name.

**2b. Find the API version**

```
GET https://api.volcengine.com/api/common/explorer/versions?ServiceCode={ServiceCode}
```
Response:
```json
{
  "Result": {
    "Versions": [
      {
        "ServiceCode": "billing",
        "Version": "2022-01-01",
        "IsDefault": 0
      }
    ]
  }
}
```
Use the version with `IsDefault == 1`. If no default version exists, use the latest available.

**2c. Find the Action name**

```
GET https://api.volcengine.com/api/common/explorer/apis?ServiceCode={ServiceCode}&Version={Version}&APIVersion={Version}
```
Response:
```json
{
  "Result": {
    "Groups": [
      {
        "Name": "Instance",
        "Apis": [
          {
            "Action": "DescribeInstances",
            "NameCn": "Query instance list",
            "Description": "..."
          }
        ]
      }
    ]
  }
}
```
Match user intent using the `Action` name and `NameCn` (Chinese name).

**2c-alt: Search API (when direct lookup fails)**

If the service catalog or API list cannot clearly match the user's description — for example, the user uses vague terms, Chinese names that don't map directly to a ServiceCode, or the API list doesn't seem to contain what the user wants — use the search API as a fallback:

```
GET https://api.volcengine.com/api/common/search/all?Query={URL-encoded search term}&Channel=api&Limit=10
```

Search terms can be Chinese or English — use whichever best matches the user's description.

Response structure:
```json
{
  "Result": {
    "List": [
      {
        "BizInfo": {
          "Action": "ListProjects",
          "ServiceCn": "Access Control",
          "ServiceCode": "iam",
          "Version": "2021-08-01"
        },
        "Highlight": [
          {"Field": "title", "Summary": "Get <em>project</em> <em>list</em>"}
        ]
      }
    ],
    "Total": 200
  }
}
```

Select the best match based on `ServiceCn`, `Action`, and highlight text, then continue to step 2d.

The search API is particularly useful when:
- The user describes the operation in natural language but doesn't know which service owns it
- A service has too many APIs to browse manually
- The description spans multiple services (search returns results across all services)

**2d. Get full API parameter details**

```
GET https://api.volcengine.com/api/common/explorer/api-swagger?ServiceCode={ServiceCode}&Version={Version}&APIVersion={Version}&ActionName={Action}
```
Returns the full Swagger/OpenAPI specification, including:
- HTTP method (GET/POST)
- All request parameters with types, required flags, and descriptions
- Response structure
- Constraints and validation rules
- **`x-demo` field**: contains `requestDemo` and `responseDemo` with official examples

Read this specification carefully — it is essential for generating accurate code.

**2e. Extract parameter example values (from x-demo requestDemo)**

The `info.x-demo` array in the Swagger response contains `requestDemo` — official request examples. Extract realistic parameter values from these to populate generated code.

Extraction process:
1. Locate `info.x-demo[0].requestDemo` and parse the request body JSON
2. Use requestDemo values as example values in generated code — they are more accurate and realistic than invented values
3. For masked values (e.g., `cc5silum********`), keep the masked format and add a comment prompting the user to replace with real values
4. If a parameter value is a JSON string (e.g., a `Config` field), format it clearly and comment each sub-field

Example: for VKE CreateAddon, requestDemo contains:
```json
{
    "ClusterId": "cc5silum********",
    "Name": "ingress-nginx",
    "DeployMode": "Unmanaged",
    "DeployNodeType": ["VirtualNode"],
    "Config": "{\"Replica\":1,\"Resource\":{\"Request\":{\"Cpu\":\"0.25\",\"Memory\":\"512Mi\"},\"Limit\":{\"Cpu\":\"0.5\",\"Memory\":\"1024Mi\"}},\"PrivateNetwork\":{\"SubnetId\":\"subnet-2d61qn69iji****\",\"IpVersion\":\"IPV4\"}}"
}
```
Use these example values directly instead of empty placeholders.

**2f. Retrieve detailed configuration for complex parameters**

Some parameter `description` fields contain documentation links (e.g., `https://www.volcengine.com/docs/...`) pointing to detailed configuration guides. For complex parameters, fetch these links for more information:

When to consult documentation:
- The parameter value is a JSON string with a "see detailed configuration" reference in the description (e.g., VKE `Config`)
- The parameter is a nested structure whose sub-field format is documented externally
- The `enum` values have unclear meanings that are explained in the documentation

Processing flow:
1. Check whether the parameter `description` contains a `volcengine.com/docs` link
2. If so, use WebFetch to retrieve the linked page and extract configuration details relevant to the parameter
3. Incorporate documentation examples into the generated code as comments or structured parameters
4. If the documentation is inaccessible, fall back to requestDemo example values

**2g. Determine required and recommended parameters**

Required-field detection relies on multiple sources, not just the `required` array:

1. **Explicitly required**: listed in the Swagger `required` array
2. **Implied by description**: the description contains phrases like "must specify", "required", or equivalent
3. **Logically required**: semantically essential even if not formally marked (e.g., instance type and network config when creating resources)
4. **Conditionally required**: the description states "required when X=Y" — if the user's scenario matches, include it

Parameter value priority:
1. **requestDemo example values** (highest priority): use the official examples directly
2. **`example` field**: individual parameter `example` values from the Swagger spec
3. **enum values**: pick the most common or general-purpose option
4. **Documentation recommendations**: values extracted from linked docs
5. **Industry conventions**: reasonable defaults following cloud-computing norms (e.g., `172.16.0.0/16` for CIDR, descriptive names for instances)

### Step 3: Consult SDK Configuration References (as needed)

If Step 1 identified advanced configuration needs, read the corresponding reference file for the target language to get accurate configuration code:

| Language | Reference File |
|----------|---------------|
| Go | `references/sdk-integration-go.md` |
| Python | `references/sdk-integration-python.md` |
| Java | `references/sdk-integration-java.md` |
| Node.js | `references/sdk-integration-nodejs.md` |
| PHP | `references/sdk-integration-php.md` |

These files contain verified code snippets for retry, timeout, credentials, proxy, connection pooling, and debug configuration. Use these patterns directly rather than writing from memory — SDK configuration varies significantly across languages, and the reference files ensure accuracy.

### Step 4: Generate Complete SDK Code

Generate a complete, runnable code example following these rules:

#### General Rules (all languages)

1. **Authentication**: read AK/SK from environment variables `VOLCENGINE_ACCESS_KEY` and `VOLCENGINE_SECRET_KEY` by default. If the user needs a different auth method (STS, AssumeRole, OIDC), use the corresponding pattern from the reference files. The exact reading mechanism varies by language — see each language section and the reference files.
2. **Region**: default to `cn-beijing` for regional services. Add a comment noting that users can change this.
3. **Required parameters**: include all required parameters (sources per step 2g), using realistic example values from requestDemo or example fields. Add a comment next to each value explaining its meaning and source.
4. **Parameter value quality**: values must follow realistic formats and business semantics, not simple placeholders:
   - Instance IDs: use masked format like `i-abc123******` (from requestDemo)
   - CIDRs: use reasonable ranges like `172.16.0.0/16`
   - Enums: use the most common option
   - Nested JSON configs: expand into readable multi-line format with per-field comments
5. **Complex parameter handling**: for parameters whose value is a JSON string (e.g., VKE Config), build a struct/dict first and then serialize to JSON, rather than hardcoding a long string. This makes the code more readable and easier to modify.
6. **Optional parameters**: include commonly-used optional parameters (e.g., pagination) as commented-out lines with explanations.
7. **Error handling**: include standard error handling for the target language.
8. **Output**: print the response in a readable format (e.g., formatted JSON).
9. **Comments**: add a header comment describing the code's purpose. Add inline comments for non-obvious parameters. Match comment language to the user's prompt language.
10. **Advanced configuration integration**: when the user has advanced config needs, weave the configuration naturally into the main code (not as a separate block), producing a single runnable file:
    - **Retry**: add retry settings during client/config initialization, with comments explaining defaults and tunable parameters
    - **Timeout**: set global timeout during client initialization; show per-request timeout usage if needed
    - **Credentials**: replace the default AK/SK auth code with the user-specified method (STS, AssumeRole, etc.)
    - **Proxy**: add proxy settings in client configuration
    - **Debug**: enable debug mode in client configuration
    - **Connection pooling**: set pool parameters in client configuration

#### Go

The Go SDK uses `{Action}Input` structs (not `Request`). Services are instantiated via `{service}.New(sess)`.

```go
package main

import (
    "fmt"
    "os"
    "github.com/volcengine/volcengine-go-sdk/service/{service}"
    "github.com/volcengine/volcengine-go-sdk/volcengine"
    "github.com/volcengine/volcengine-go-sdk/volcengine/credentials"
    "github.com/volcengine/volcengine-go-sdk/volcengine/session"
)

func main() {
    ak := os.Getenv("VOLCENGINE_ACCESS_KEY")
    sk := os.Getenv("VOLCENGINE_SECRET_KEY")
    region := "cn-beijing"

    config := volcengine.NewConfig().
        WithRegion(region).
        WithCredentials(credentials.NewStaticCredentials(ak, sk, ""))

    // [Advanced config — add as needed, see references/sdk-integration-go.md]
    // Retry: config.WithMaxRetries(5)
    // Timeout: config.WithHTTPClient(&http.Client{Timeout: 60 * time.Second})
    // Proxy: config.WithHTTPProxy("http://proxy:8080")
    // Debug: config.WithDebug(true)

    sess, err := session.NewSession(config)
    if err != nil {
        panic(err)
    }
    svc := {service}.New(sess)

    input := &{service}.{Action}Input{
        // Set required parameters here
    }
    resp, err := svc.{Action}(input)
    if err != nil {
        panic(err)
    }
    fmt.Println(resp)
}
```

Key points:
- Package path: `github.com/volcengine/volcengine-go-sdk/service/{service}` (lowercase, e.g., `billing`, `ecs`, `vpc`)
- Config chain: `volcengine.NewConfig().WithRegion(region).WithCredentials(credentials.NewStaticCredentials(ak, sk, ""))`
- Session: `session.NewSession(config)` (returns session and error)
- Service client: `{service}.New(sess)` (e.g., `billing.New(sess)`, `ecs.New(sess)`)
- Request struct: `{Action}Input` (e.g., `ListAvailableInstancesInput`, `DescribeInstancesInput`)
- Method: `svc.{Action}(input)`, PascalCase action name

#### Python

The Python SDK uses `{SERVICE}Api` (uppercase service name) and `{Action}Request` models.

```python
from __future__ import print_function
import os
import volcenginesdkcore
import volcenginesdk{service}
from volcenginesdkcore.rest import ApiException

if __name__ == '__main__':
    configuration = volcenginesdkcore.Configuration()
    configuration.ak = os.environ.get("VOLCENGINE_ACCESS_KEY")
    configuration.sk = os.environ.get("VOLCENGINE_SECRET_KEY")
    configuration.region = "cn-beijing"

    # [Advanced config — add as needed, see references/sdk-integration-python.md]
    # Retry: configuration.max_retry_attempts = 5
    # Timeout: configuration.connection_timeout = 10; configuration.read_timeout = 60
    # Proxy: configuration.proxy = "http://proxy:8080"
    # Debug: configuration.debug = True

    volcenginesdkcore.Configuration.set_default(configuration)

    api_instance = volcenginesdk{service}.{SERVICE}Api()
    request = volcenginesdk{service}.{Action}Request(
        # Set required parameters here
    )

    try:
        resp = api_instance.{action_snake_case}(request)
        print(resp)
    except ApiException as e:
        print("API exception: %s\n" % e)
```

Key points:
- Package: `volcenginesdkcore` + `volcenginesdk{service}` (all lowercase, no separators, e.g., `volcenginesdkbilling`, `volcenginesdkecs`)
- Config: `volcenginesdkcore.Configuration()`, set `.ak`, `.sk`, `.region`, then `set_default()`
- API class: `volcenginesdk{service}.{SERVICE}Api()` — service name ALL CAPS (e.g., `BILLINGApi`, `ECSApi`, `VPCApi`)
- Request class: `volcenginesdk{service}.{Action}Request(...)` (PascalCase, e.g., `ListAvailableInstancesRequest`)
- Method: `api_instance.{action_snake_case}(request)` — snake_case (e.g., `list_available_instances`, `describe_instances`)
- Exception: `from volcenginesdkcore.rest import ApiException`

#### Java

The Java SDK uses `{ServiceName}Api` and `{Action}Request` models under `com.volcengine.{service}`.

```java
package com.volcengine.sample;

import com.volcengine.ApiClient;
import com.volcengine.ApiException;
import com.volcengine.sign.Credentials;
import com.volcengine.{service}.{ServiceName}Api;
import com.volcengine.{service}.model.*;

public class Example {
    public static void main(String[] args) throws Exception {
        String ak = System.getenv("VOLCENGINE_ACCESS_KEY");
        String sk = System.getenv("VOLCENGINE_SECRET_KEY");
        String region = "cn-beijing";

        ApiClient apiClient = new ApiClient()
                .setCredentials(Credentials.getCredentials(ak, sk))
                .setRegion(region);

        // [Advanced config — add as needed, see references/sdk-integration-java.md]
        // Retry: apiClient.setRetrySettings(new RetrySettings().setMaxAttempts(5));
        // Timeout: apiClient.setConnectionTimeout(5000); apiClient.setReadTimeout(30000);
        // Proxy: apiClient.setHttpProxy("http://proxy:8080");
        // Debug: apiClient.setDebugging(true);

        {ServiceName}Api api = new {ServiceName}Api(apiClient);

        {Action}Request request = new {Action}Request();
        // request.setParamName(value);

        try {
            {Action}Response resp = api.{actionCamelCase}(request);
            System.out.println(resp);
        } catch (ApiException e) {
            System.out.println(e.getResponseBody());
        }
    }
}
```

Key points:
- Package: `com.volcengine.{service}` (lowercase, e.g., `com.volcengine.billing`, `com.volcengine.ecs`)
- ApiClient: `new ApiClient().setCredentials(Credentials.getCredentials(ak, sk)).setRegion(region)`
- API class: `{ServiceName}Api` (PascalCase, e.g., `BillingApi`, `EcsApi`) — constructor takes `apiClient`
- Request class: `{Action}Request` (e.g., `ListAvailableInstancesRequest`) — set params via setters
- Method: `api.{actionCamelCase}(request)` — camelCase (e.g., `listAvailableInstances`, `describeInstances`)
- Exception: `ApiException`, use `e.getResponseBody()` for details

#### Node.js

The Node.js SDK uses a command pattern: `{SERVICE}Client` + `{Action}Command`.

```javascript
import { {SERVICE}Client, {Action}Command } from "@volcengine/{service}";

// Automatically reads VOLCENGINE_ACCESS_KEY and VOLCENGINE_SECRET_KEY from env
const client = new {SERVICE}Client({
    region: "cn-beijing",
    // [Advanced config — add as needed, see references/sdk-integration-nodejs.md]
    // maxRetries: 5,                          // retry count
    // autoRetry: false,                       // disable auto-retry
    // httpOptions: { timeout: 30000 },        // timeout (ms)
    // httpOptions: { proxy: { protocol: "http", host: "127.0.0.1", port: 8888 } },  // proxy
});

async function main() {
    try {
        const command = new {Action}Command({
            // Set required parameters here
        });
        const response = await client.send(command);
        console.log(JSON.stringify(response, null, 2));
    } catch (error) {
        console.error("Error:", error);
    }
}

main();
```

Key points:
- Package: `@volcengine/{service}` (lowercase, e.g., `@volcengine/ecs`, `@volcengine/vpc`)
- Client: `{SERVICE}Client` (ALL CAPS service name, e.g., `ECSClient`, `VPCClient`)
- Command: `{Action}Command` (PascalCase, e.g., `DescribeInstancesCommand`, `CreateVpcCommand`)
- Invocation: `client.send(command)` — async, returns a Promise
- Auth: automatically reads `VOLCENGINE_ACCESS_KEY` and `VOLCENGINE_SECRET_KEY` from env; can also pass `accessKeyId`/`secretAccessKey` in the client constructor

#### PHP

The PHP SDK uses classes under the `\Volcengine\{Service}\` namespace.

```php
<?php
require_once(__DIR__ . '/vendor/autoload.php');

$config = \Volcengine\Common\Configuration::getDefaultConfiguration()
    ->setAk(getenv("VOLCENGINE_ACCESS_KEY"))
    ->setSk(getenv("VOLCENGINE_SECRET_KEY"))
    ->setRegion("cn-beijing");

// [Advanced config — add as needed, see references/sdk-integration-php.md]
// Proxy and timeout are configured via GuzzleHttp\Client options
$httpClient = new GuzzleHttp\Client([
    // 'proxy' => 'http://proxy:8080',              // proxy
    // 'timeout' => 60,                              // request timeout (seconds)
    // 'connect_timeout' => 10,                      // connection timeout (seconds)
]);

$apiInstance = new \Volcengine\{Service}\Api\{SERVICE}Api(
    $httpClient,
    $config
);

$request = new \Volcengine\{Service}\Model\{Action}Request();
// $request->setParamName("value");

try {
    $resp = $apiInstance->{actionCamelCase}($request);
    print_r($resp);
} catch (Exception $e) {
    echo 'API exception: ', $e->getMessage(), PHP_EOL;
}
```

Key points:
- Config: `\Volcengine\Common\Configuration::getDefaultConfiguration()->setAk()->setSk()->setRegion()`
- API class: `\Volcengine\{Service}\Api\{SERVICE}Api` — namespace uses PascalCase `Service` (e.g., `Billing`), class name uses ALL CAPS (e.g., `BILLINGApi`)
- Constructor: takes `GuzzleHttp\Client()` and `$config`
- Request class: `\Volcengine\{Service}\Model\{Action}Request` (e.g., `\Volcengine\Billing\Model\ListAvailableInstancesRequest`)
- Set params via setters: `$request->setProduct("value")`
- Method: `$apiInstance->{actionCamelCase}($request)` (e.g., `listAvailableInstances`)

### Step 5: Present Results

After generating code:

1. Display the complete code in a code block with the correct language tag
2. List the dependencies the user needs to install (`go get`, `pip install`, `npm install`, `composer require`, Maven/Gradle coordinates)
3. Remind the user to set environment variables:
   ```
   export VOLCENGINE_ACCESS_KEY="your-access-key"
   export VOLCENGINE_SECRET_KEY="your-secret-key"
   ```
4. Note important constraints from the API spec (rate limits, required permissions, data range limits, etc.)
5. If the code includes advanced configuration, briefly explain each setting's purpose, defaults, and tuning advice. For example:
   - "Retry defaults to 3 attempts, covers network errors and throttling — adjust via `WithMaxRetries`"
   - "Connection timeout defaults to 30s; consider increasing for large batch queries"

## Answering SDK Configuration Questions

When the user asks how to configure or use the Volcengine SDK (rather than generate API call code), follow this approach:

### Step 1: Identify the User's Need

Common configuration topics:
- **Authentication**: AK/SK, STS Token, AssumeRole, OIDC, SAML
- **Retry**: enable/disable, max attempts, backoff strategy, custom retry conditions
- **Timeout**: connection timeout, read timeout, per-request timeout
- **Proxy**: HTTP/HTTPS proxy configuration
- **Endpoint**: custom endpoint, region-based resolution, dual-stack (IPv6)
- **SSL/HTTPS**: disable SSL verification, TLS version, HTTP vs. HTTPS
- **Connection pooling**: pool size, keep-alive, idle connections
- **Debug**: debug mode, logging, middleware
- **Error handling**: exception types, retryable vs. non-retryable errors
- **Environment variables**: supported env vars per SDK

### Step 2: Consult the Reference Documentation

Read the reference file for the user's target language:

| Language | Reference File |
|----------|---------------|
| Go | `references/sdk-integration-go.md` |
| Python | `references/sdk-integration-python.md` |
| Java | `references/sdk-integration-java.md` |
| Node.js | `references/sdk-integration-nodejs.md` |
| PHP | `references/sdk-integration-php.md` |

These files contain concise code examples for each major configuration topic. Read the relevant file and answer with accurate, copy-paste-ready code.

If the user's question is not covered in the reference file or requires more detail, fetch the full upstream documentation from GitHub:

| Language | Upstream Documentation URL |
|----------|---------------------------|
| Go | `https://raw.githubusercontent.com/volcengine/volcengine-go-sdk/master/SDK_Integration.md` |
| Python | `https://raw.githubusercontent.com/volcengine/volcengine-python-sdk/master/SDK_Integration.md` |
| Java | `https://raw.githubusercontent.com/volcengine/volcengine-java-sdk/master/SDK_Integration.md` |
| Node.js | `https://raw.githubusercontent.com/volcengine/volcengine-nodejs-sdk/master/SDK_Integration.md` |
| PHP | `https://raw.githubusercontent.com/volcengine/volcengine-php-sdk/main/SDK_Integration.md` |

### Step 3: Provide a Clear Answer

- Show complete, runnable code snippets demonstrating the configuration
- Explain each setting's purpose and default value
- Mention caveats (e.g., "disabling SSL verification is only appropriate in test environments")
- If the user has not specified a language, ask which one they are using
- Match the answer language to the user's prompt language

## Important Notes

- Always fetch data from the API Explorer — Volcengine APIs are updated frequently, so the Explorer is the authoritative source. Do not rely on memory.
- If the user's description is ambiguous (could map to multiple services or operations), list the options and ask for confirmation.
- If a service has `IsSdkAvailable: false`, inform the user that the official SDK may not yet support this service, and provide a raw HTTP request example as an alternative.
- For regional services, remind the user to change the region setting if their resources are not in `cn-beijing`.
