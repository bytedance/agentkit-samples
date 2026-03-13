---
name: volcengine-api
description: >
  Query and answer questions about Volcengine API specifications. Trigger this skill whenever a user
  asks about Volcengine API parameters, error codes, request methods, enum values, required fields,
  response structures, pagination, parameter dependencies, or API comparisons — even if they don't
  explicitly say "API". Typical triggers include questions like "What parameters does DescribeInstances
  have?", "What values does Status support?", "What does InvalidInstanceId.NotFound mean?",
  "Does Volcengine have a batch tag deletion API?", "Which APIs does ECS support?",
  "How do I pass parameters to CreateDatabase?", "Is ChargeType required?",
  "What fields does DescribeInstances return?", "How do I paginate instance lists?",
  "What's the difference between these two APIs?", "RunInstances returns InvalidParameterValue".
  When the user needs runnable SDK code, hand off to the volcengine-sdk-generator skill.
  When the user needs CLI-based operations, hand off to the volcengine-cli skill.
  Supports both Chinese and English prompts.
---

# Volcengine API Query Assistant

Answer user questions about Volcengine APIs by querying the API Explorer for authoritative, up-to-date information.

## Applicable Scenarios

| Scenario | Example Questions |
|----------|-------------------|
| Find an API | "How do I list ECS instances?", "Is there a batch tag creation API?" |
| Query parameters | "What are the required params for RunInstances?", "What values does ChargeType accept?" |
| Response structure | "What fields does DescribeInstances return?", "What statuses can Status have?" |
| Parameter dependencies | "If I set Ipv6Isp, how should I fill Ipv6MaskLen?", "When is SpotPriceLimit required?" |
| Pagination | "How do I paginate instance queries?", "How does NextToken work?" |
| Error codes | "What does InvalidInstanceId.NotFound mean?", "CreateVpc returns QuotaExceeded" |
| Browse services | "Which APIs does ECS have?", "What operations does VPC support?" |
| API comparison | "What's the difference between DescribeInstances and DescribeInstancesByIds?" |

## Workflow

### Step 1: Understand User Intent

Determine what the user is looking for:

| Intent | Signal | Query Path |
|--------|--------|------------|
| **Find an API** | Describes an operation but doesn't know the API name | Search (2e) or Services (2a) -> API list (2c) -> Details (2d) |
| **Query parameters** | Knows the API name, asks about params/enums/required fields | Go directly to Details (2d) |
| **Query response** | Asks about return fields or status values | Go directly to Details (2d), focus on response schema |
| **Query parameter dependencies** | Asks "when is X required?" or "how does X relate to Y?" | Go directly to Details (2d), focus on conditional rules in descriptions |
| **Query error codes** | Provides an error code or error message | Error code handling (Step 3) |
| **Browse a service** | Asks what capabilities a service offers | Services (2a) -> API list (2c) |
| **Compare APIs** | Asks about differences between two APIs | Query Details (2d) for each, compare params and functionality |

### Step 2: Query API Information Progressively

Start from the appropriate sub-step based on what is already known. When the user describes a requirement in natural language, Search (2e) is often faster than browsing level by level.

#### 2a. Query service list (when the service is unknown)

```
GET https://api.volcengine.com/api/common/explorer/services
```

Each service in the response contains:
- `ServiceCode`: service identifier (e.g., `ecs`, `vpc`)
- `ServiceCn`: Chinese name (e.g., "cloud server", "virtual private cloud")
- `Product`: product identifier (e.g., `ECS`, `VPC`)
- `RegionType`: `regional` or `global`

Match the most appropriate `ServiceCode` based on the user's description.

#### 2b. Query version list (when the version is unknown)

```
GET https://api.volcengine.com/api/common/explorer/versions?ServiceCode={ServiceCode}
```

Each version contains:
- `Version`: version string (e.g., `2020-04-01`)
- `IsDefault`: `1` indicates the default version

Prefer the version with `IsDefault=1`. If none is marked default, use the latest version.

#### 2c. Query API list (when the specific API is unknown)

```
GET https://api.volcengine.com/api/common/explorer/apis?ServiceCode={ServiceCode}&Version={Version}&APIVersion={Version}
```

The response groups APIs by category. Each API contains:
- `Action`: API name (e.g., `DescribeInstances`)
- `NameCn`: Chinese name (e.g., "Query instance list")
- `ApiGroup`: group name (e.g., "Instance", "Image")
- `Description`: functional description
- `UsageScenario`: usage scenarios
- `Attentions`: constraints and caveats

Match user intent using `Action`, `NameCn`, and `Description`.

#### 2d. Query API details (core step)

```
GET https://api.volcengine.com/api/common/explorer/api-swagger?ServiceCode={ServiceCode}&Version={Version}&APIVersion={Version}&ActionName={ActionName}
```

Returns the full Swagger/OpenAPI specification for the API. Extract key information as follows.

##### HTTP Method

The key under `paths["/{ActionName}"]` (`get` or `post`) indicates the HTTP method.

##### Request Parameters

Parameter location depends on the HTTP method:

**GET requests:** parameters are in `paths["/{ActionName}"].get.parameters`. Each parameter includes:
- `name`: parameter name
- `required`: whether it is required
- `schema.type`: data type
- `schema.description`: parameter description (often contains enum values, conditional rules, and value ranges)
- `schema.enum`: allowed values (if any)
- `schema.default`: default value (if any)
- `schema.example`: example value (if any)

Arrays and nested objects in GET parameters use naming conventions:
- Arrays: `ParamName.N` (N starts from 1), e.g., `InstanceIds.1`, `InstanceIds.2`
- Nested objects: `Parent.Child`, e.g., `TagFilters.N.Key`, `TagFilters.N.Values.N`

**POST requests:** parameters are in `paths["/{ActionName}"].post.requestBody.content["application/json"].schema`, using JSON Schema:
- `properties`: parameter definitions, keyed by name
- `required`: array of required parameter names

POST parameters often have nested structures that require recursive parsing:
- `type: object` -> inspect `properties` for child parameters
- `type: array` -> inspect `items` for element structure
- `$ref: "#/components/schemas/XxxObject"` -> look up the definition in `components.schemas` and expand recursively

Present nested parameters in a tree structure:
```
- InstanceId (string, required): instance ID
- DatabasePrivileges (array, optional): database privilege list
  - AccountName (string, required): account name
  - AccountPrivilege (string, required): privilege type — enum: ReadWrite, ReadOnly, ...
  - AccountPrivilegeDetail (string, optional): privilege detail, comma-separated
```

##### Parameter Dependencies

Many parameters have conditional dependencies, typically described in the `description` field. Watch for:

- **Conditionally required**: e.g., "required when `EnableIpv6` is true"
- **Mutually exclusive**: e.g., "when `Ipv6CidrBlock` is specified, `Ipv6MaskLen` is ignored"
- **Value constraints**: e.g., "when `Ipv6Isp` is BGP, only 56 is supported"
- **Prerequisites**: e.g., "`TagFilters.N.Values.N` requires `TagFilters.N.Key` to be set first"

Highlight these dependencies in the answer to help users avoid misconfiguration.

##### Pagination Parameters

Volcengine APIs use two common pagination patterns, identifiable from the Swagger parameters:

- **Token-based**: uses `MaxResults` (page size) + `NextToken` (continuation token). The response includes `NextToken`; an empty value means the last page.
- **Offset-based**: uses `PageSize` + `PageNumber` (or `Offset`/`Limit`). The response includes `TotalCount`.

Specify which pagination pattern the API uses, along with default values and upper limits.

##### Response Structure

The response schema is defined at `paths["/{ActionName}"].{method}.responses["200"].content["application/json"].schema`, and may reference `components.schemas` via `$ref`.

Key response information:
- Field names, types, and descriptions
- Enum fields and their possible values (e.g., `Status`: RUNNING / STOPPED / CREATING)
- Nested object structures (e.g., fields within each item in an `Instances` array)

The `info.x-demo` section also provides useful reference — `responseDemo[0].Code` shows the complete response structure with example values.

##### Request/Response Examples

In the `info.x-demo` array:
- `requestDemo[0].Code`: request example (shows how parameters are filled)
- `responseDemo[0].Code`: response example (shows the full return structure with sample values)

These are official examples and highly valuable. Proactively include them in the answer.

##### Associated Error Codes

In `paths["/{ActionName}"].{method}.responses["x-error-code"].content["application/json"].schema.oneOf`, each error code contains:
- `code`: error code identifier (e.g., `InvalidInstanceId.NotFound`)
- `http_code`: HTTP status code (e.g., 400, 404, 409, 429, 500)
- `message`: English description
- `description`: Chinese description

#### 2e. Search APIs (quick lookup)

When the user describes a requirement in natural language, searching is often the fastest approach. This can be used alongside steps 2a–2c.

```
GET https://api.volcengine.com/api/common/search/all?Query={keyword}&Channel=api
```

Search terms can be in Chinese or English. If one keyword yields poor results, try synonyms, different granularity, or English Action-name style (e.g., "DescribeXxx").

Each result contains:
- `BizInfo.Action`: API name
- `BizInfo.ServiceCode`: service identifier
- `BizInfo.ServiceCn`: service Chinese name
- `BizInfo.Version`: version
- `Highlight`: matched highlight text

After finding the target API, use step 2d to get full details.

### Step 3: Handle Error Code Queries

Error code queries need special handling because the same error code (e.g., `InvalidParameter`) may appear across dozens of APIs with different meanings.

#### Common Error Code Categories

| Category | Common Patterns | Typical Cause |
|----------|----------------|---------------|
| Parameter error | `InvalidParameter`, `InvalidParameterValue`, `MissingParameter` | Typo in parameter name, value outside enum range, missing required parameter |
| Resource not found | `InvalidXxx.NotFound`, `ResourceNotFound` | Wrong resource ID, resource in a different region, already deleted |
| Resource status | `InvalidXxx.InvalidStatus`, `IncorrectInstanceStatus` | Current resource state does not allow this operation (e.g., modifying config without stopping the instance) |
| Quota/limit | `QuotaExceeded`, `LimitExceeded` | Account quota or API rate limit exceeded |
| Permission denied | `UnauthorizedOperation`, `Forbidden` | IAM policy not authorized, sub-account lacks permissions |
| Throttling | `Throttling`, `RequestLimitExceeded` | API call rate too high — reduce request rate or use exponential backoff |
| Server error | `InternalError`, `ServiceUnavailable` | Temporary server-side issue, usually retryable |
| Resource conflict | `ResourceInUse`, `DuplicateXxx`, `OperationConflict` | Resource is in use or name already exists |

#### When the user provides a specific API name

Query the API Swagger via step 2d and locate the error code in `x-error-code`. This is the most accurate approach because the same error code can have different meanings across APIs.

Combine the `description` (Chinese) and `message` (English) fields to provide:
1. Error meaning
2. Specific trigger conditions in the context of this API
3. Troubleshooting steps and resolution suggestions

#### When the user provides only the error code

1. **Ask for context first**: ask which API triggered the error — this enables precise diagnosis. The same `InvalidParameter` means entirely different things in `RunInstances` vs. `CreateVpc`.
2. **If the user provides a service name but no API name**: infer the most likely API from the error pattern and context, then query its Swagger to confirm.
3. **Fallback search**: if the user cannot provide more context, use the error code search endpoint:

```
GET https://api.volcengine.com/api/common/search/all?Query={error_code}&Channel=error_code
```

Each result contains:
- `Type`: `error_code`
- `BizInfo.ServiceCode`: service identifier
- `BizInfo.ServiceCn`: service Chinese name
- `BizInfo.Version`: version
- `URL`: error code documentation link
- `Highlight`: matched highlight text

Since the same error code appears across multiple services, results may be numerous. Filter by any context the user has provided (service name, operation type, scenario).

### Step 4: Compose the Answer

Organize a clear, professional answer based on the question type. Core principle: **center on the user's question** — extract the information the user needs rather than dumping the entire Swagger.

#### Finding an API

1. Recommend the API and explain why
2. Briefly describe its functionality and use case
3. List core required parameters
4. If multiple candidates exist, compare their use cases and let the user choose

#### Querying Parameters

1. State the HTTP method (GET/POST)
2. **Required parameters first**: list with type, description, and enum values
3. Use tree structure for nested parameters, marking required/optional at each level
4. **Parameter dependencies**: highlight conditional requirements, mutual exclusions, and value constraints
5. Describe the pagination pattern and default values separately
6. Show the request example (from x-demo)
7. Group optional parameters by function (filters, sorting, advanced config) and list briefly

#### Querying Response Structure

1. List key return fields with type and description
2. Show all possible values for enum fields
3. Use tree structure for nested objects
4. Show the response example (from x-demo responseDemo)

#### Querying Error Codes

1. Error meaning (Chinese and English descriptions)
2. Error category (parameter error / resource not found / permission denied, etc.)
3. Common causes
4. Specific troubleshooting steps and resolution suggestions
5. For throttling errors, recommend a retry strategy

#### Browsing Service Capabilities

1. Organize the API list by `ApiGroup`
2. Show Action name + Chinese name + one-line description for each API
3. If there are many APIs, prioritize core/commonly-used ones

#### Comparing APIs

1. Describe the functional purpose of each API
2. Compare applicable scenarios
3. Compare parameter differences (which is simpler, which is more flexible)
4. Provide a usage recommendation

### Query Efficiency Tips

- **API name known**: go directly to 2d — one step
- **Service name known**: 2b -> 2c -> 2d, or search in parallel via 2e
- **Only a natural-language description**: prefer 2e search — faster than browsing level by level
- **Completely uncertain**: combine 2a (service list) + 2e (keyword search)
- **Error code lookup**: if an API name is available, go to 2d; otherwise, ask the user for context first

### Important Notes

- Always fetch the latest data from the API Explorer endpoints — Volcengine APIs are updated frequently, so do not rely on memory
- Match the answer language to the user's language (Chinese question -> Chinese answer, English -> English)
- If the user's description is ambiguous, list possible options and ask for confirmation rather than guessing
- If the user needs runnable SDK code, direct them to the `volcengine-sdk-generator` skill
- If the user needs CLI-based operations, direct them to the `volcengine-cli` skill
- When presenting parameter information, enum values, conditional rules, and value ranges in the description field are the most valuable content — do not omit them
- If a network error occurs during queries, inform the user and suggest retrying later
