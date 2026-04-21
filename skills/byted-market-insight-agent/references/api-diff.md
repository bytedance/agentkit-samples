# API 差异说明

本 Skill 在内部封装了 Gateway 和 SDK 两种调用方式，它们在 HTTP 方法、参数命名风格等方面存在差异。本 Skill 的 `client.py` 已经将这些差异完全抹平，对外暴露统一的 `PascalCase` 风格接口。

了解这些底层差异有助于在排查问题时更好地理解 Debug 日志。

## HTTP 方法与参数传递差异

| 接口                 | Gateway (urllib)                                  | SDK (`volcengine-python-sdk`)                     |
| -------------------- | ------------------------------------------------- | ------------------------------------------------- |
| `ListCustomSubsTask` | `GET` 方法，但请求体为 JSON (`application/json`)  | `POST` 方法，请求体为 JSON (`application/json`)   |
| `PullPost`           | `POST` 方法，请求体为 JSON (`application/json`)   | `POST` 方法，请求体为 JSON (`application/json`)   |
| `QueryClueInfo`      | `GET` 方法，但请求体为 JSON (`application/json`)  | `POST` 方法，请求体为 JSON (`application/json`)   |

**核心差异点**：

-   通过 Gateway 调用 `ListCustomSubsTask` 和 `QueryClueInfo` 时，虽然是 `GET` 请求，但业务参数是通过 JSON Body 传递的，这与标准的 RESTful `GET` 请求不同。`gateway_provider.py` 内部通过重写 `urllib.request.Request.get_method` 来实现这一特殊需求。
-   SDK 调用则统一使用 `POST` 方法，更符合其 RPC 风格。

## 参数命名风格差异

| 统一接口参数（`client.py`） | Gateway (`gateway_provider.py`) | SDK (`sdk_provider.py`)           |
| --------------------------- | ------------------------------- | --------------------------------- |
| `TaskID`                    | `TaskID`                        | `task_id`                         |
| `TaskName`                  | `TaskName`                      | `task_name`                       |
| `StartTime`                 | `StartTime`                     | `start_time`                      |
| `EndTime`                   | `EndTime`                       | `end_time`                        |
| `PageNum`                   | `PageNum`                       | `page_num`                        |
| `PageSize`                  | `PageSize`                      | `page_size`                       |
| `PageToken`                 | `PageToken`                     | `page_token`                      |
| `Size` (for PullPost)       | `Size`                          | `size`                            |
| `MaxResults`                | `MaxResults`                    | `max_results`                     |
| `NextToken`                 | `NextToken`                     | `next_token`                      |

-   **Gateway Provider**：直接使用与 `client.py` 相同的 `PascalCase` 参数。
-   **SDK Provider**：在内部将 `PascalCase` 参数转换为 SDK 请求体对象所需的 `snake_case` 参数。

## 关键返回字段差异

| 统一返回字段                | Gateway (`Result` 字段内) | SDK (响应对象属性)          |
| --------------------------- | ------------------------- | --------------------------- |
| `InsightSaasTaskList`       | `InsightSaasTaskList`     | `insight_saas_task_list`    |
| `ItemDocs`                  | `ItemDocs`                | `item_docs`                 |
| `ClueList`                  | `ClueList`                | `clue_list`                 |
| `Total`                     | `Total`                   | `total`                     |
| `HasMore`                   | `HasMore`                 | `has_more`                  |
| `NextPageToken`             | `NextPageToken`           | `next_page_token`           |
| `ResultCnt`                 | `ResultCnt`               | `result_cnt`                |

`sdk_provider.py` 在返回前，会将 SDK 响应对象的 `snake_case` 属性名转换为与其他 Provider 一致的 `PascalCase` 键名。

## 重要提醒：`QueryClueInfo` 的 `ClueText` 必须解析

在 `QueryClueInfo` 接口的返回结果中，`ClueList` 里的每一个商机对象都包含一个 `ClueText` 字段。

-   **原始类型**：无论通过 Gateway 还是 SDK 获取，`ClueText` 的原始类型都是一个 **JSON 字符串**。
-   **统一处理**：本 Skill 的 `gateway_provider.py` 和 `sdk_provider.py` 在返回数据前，都会自动尝试对 `ClueText` 字段进行 `json.loads()` 解析。
    -   如果解析成功，`ClueText` 的值会变为一个结构化的 Python 字典。
    -   如果解析失败（例如内容为空或格式错误），将保持其原始的字符串形态，避免因单条数据异常导致整个请求失败。

因此，使用本 Skill 的 `client.py` 调用 `query_clue_info` 时，可以直接像操作字典一样访问 `ClueText` 的内部字段，例如 `clue['ClueText']['opportunity_briefing']['title']`。
