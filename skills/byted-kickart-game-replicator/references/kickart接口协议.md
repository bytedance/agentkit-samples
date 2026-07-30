# 游戏视频复刻 · KickArt OpenAPI 接口协议

> 本文档由 `byted-kickart-skill-apidoc-parser` 基于源接口文档《创作Agent（Kickart）-爆款复刻-游戏行业-OpenAPI 接入指引（APIKey 版）》解析而成，并已通过真实的 submit + query 两阶段调用验证参数可用。

## 1. 文档基础信息

| 项 | 内容 |
|---|---|
| 文档名称 | 游戏视频复刻（爆款复刻-游戏行业）接口协议 |
| 业务场景 | 输入单个参考视频 + 角色图片 + 游戏名称 + 语言 + 可选 prompt，输出复刻后的成品视频 |
| 维护人 | 赵剑 |

## 2. 全局信息

| 项 | 值 | 说明 |
|---|---|---|
| 对外域名 | `https://kickart.volces.com` | 所有接口共用域名 |
| Content-Type | `application/json` | 固定为 JSON 格式 |
| 鉴权方式 | Header 传 `x-muse-token`（AK/SK 通过 `core/core.py` 的 `token()` 函数换取，支持 `KICKART_ACCESS_KEY/KICKART_SECRET_KEY` 或 `ACCESS_KEY_ID/SECRET_ACCESS_KEY` 两种环境变量命名方式） | 不再使用 APIKey 或 Bearer Token |
| 默认超时 | `30s` | 指 HTTP 连接/响应超时，非异步任务处理时长 |

> **鉴权改写提示**：源接口文档中使用的鉴权方式是 `Authorization: Bearer <API_KEY>`，已按平台规范统一改写为 **AK/SK → `x-muse-token`**；源文档中的 API Key Bearer 方式已忽略，本协议只保留 `x-muse-token`。

---

## 3. 提交异步任务

该接口用于提交一个「游戏视频复刻」的异步处理任务。调用成功后立即返回 `task_id`，用于后续查询。

- **请求方法**：`POST`
- **请求路径**：`/openapi/ai_effect/submit`

### 请求参数

| 字段名 | 类型 | 必填 | 示例 | 描述 |
|---|---|---|---|---|
| `template_id` | `string` | 是 | `"463631106"` | 业务模板 ID。当前支持：`604911874`（专业模式 2.0，720p）、`463631106`（进阶模式 2.0fast，720p） |
| `payload` | `object` | 是 | 见下方示例 | 业务参数对象，具体结构见下表 |
| `callback_url` | `string` | 否 | `https://example.com/callback` | 任务完成后主动回调地址；回调结果与 query 响应一致 |
| `watermark` | `boolean` | 否 | `true` | 视频右下角是否添加"AI 生成"明水印，默认 `false` |

**`payload` 内部结构（JSON Schema 风格）：**

| 字段名 | 类型 | 是否必传 | 默认值 | 描述 |
|---|---|---|---|---|
| `ref_video` | `string` | 是 | - | 参考视频链接。支持格式：MP4/MOV；文件大小：≤50MB；视频时长：>5 秒且 ≤60 秒；分辨率：≥480p；支持的画面比例：9:16、16:9、3:4、4:3、1:1 |
| `role_images` | `list<string>` | 是 | - | 角色图片列表。图片数量：1–10 张；图片格式：JPEG/PNG；单张大小：≤8MB；单张分辨率：≥480p；图片长宽比：(0.4, 2.5)；宽高像素范围：(300, 6000) |
| `location_images` | `list<string>` | 否 | 不传默认"智能匹配" | 模型参考图（场景图）。图片数量：0–3 张；图片格式：JPEG/PNG；单张大小：≤8MB；单张分辨率：≥480p；最小像素总数 300×300，最大像素总数 3600 万；最短边 ≥300px，最长边 ≤6000px |
| `language` | `string` | 是 | - | 视频语言，影响口播和字幕。取值：`zh`（中文）/ `en`（英文）/ `en-us`（英语-美国）/ `pt-br`（葡萄牙语）/ `ja`（日语）/ `es-mx`（西班牙语-墨西哥）/ `id`（印尼语）/ `ms`（马来语）/ `tl`（他加禄语） |
| `game_name` | `string` | 是 | - | 游戏名称，≤500 字符 |
| `prompt` | `string` | 否 | - | 自定义创意策略/爆点描述，用于指导故事板生成方向；不传使用系统默认策略。≤5000 字符 |

### 响应参数

| 字段名 | 类型 | 描述 |
|---|---|---|
| `code` | `int32` | 状态码。`0` 表示提交成功，非 `0` 表示提交失败 |
| `message` | `string` | 状态描述信息 |
| `request_id` | `string` | 本次请求的唯一标识，用于问题排查 |
| `data.task_id` | `string` | 提交成功后返回的任务 ID，用于后续查询 |

### cURL 示例（真实跑通的参数）

```bash
curl --location 'https://kickart.volces.com/openapi/ai_effect/submit' \
--header "x-muse-token: ${MUSE_TOKEN}" \
--header 'Content-Type: application/json' \
--data '{
    "template_id": "463631106",
    "payload": {
        "ref_video": "https://lf3-static.bytednsdoc.com/obj/eden-cn/nulobf/ljhwZthlaukjlkulzlp/20260701_7657607084086693141.mp4",
        "role_images": [
            "https://vevos.tos-cn-beijing.volces.com/video/mihayou_role_3.jpeg",
            "https://vevos.tos-cn-beijing.volces.com/video/screenshot-20260722-170257.png"
        ],
        "language": "zh",
        "game_name": "GTA",
        "prompt": "把视频中的人物形象换成图像中的形象"
    }
}'
```

真实响应（`request_id=202607231543550717B308786C58F2F5CC`）：

```json
{
    "code": 0,
    "data": { "task_id": "7665544479945540247" },
    "message": "success",
    "request_id": "202607231543550717B308786C58F2F5CC"
}
```

---

## 4. 查询任务结果

使用提交任务返回的 `task_id` 轮询任务状态和最终结果。

- **请求方法**：`POST`
- **请求路径**：`/openapi/ai_effect/query`

### 请求参数

| 字段名 | 类型 | 必填 | 示例 | 描述 |
|---|---|---|---|---|
| `task_id` | `string` | 是 | `"7665544479945540247"` | 来源于"提交异步任务"接口的成功响应 |

### 响应参数

**成功条件**：`code = 0` 且 `data.payload` 中包含 `result_url`。

| 字段名 | 类型 | 描述 |
|---|---|---|
| `code` | `int32` | 状态码。`0` = 成功；`1000` = 任务运行中；其他非零值 = 失败，详见错误码表 |
| `message` | `string` | 状态描述（如 `success` / `running`） |
| `request_id` | `string` | 请求唯一标识 |
| `data.task_id` | `string` | 任务 ID |
| `data.progress` | `int32` | 任务进度（0–100） |
| `data.usage` | `double` | 本次任务消耗的创点数，仅在成功时有效 |
| `data.payload` | `object` | 任务结果详情，具体结构见下表 |

**`data.payload` 内部结构（真实返回字段）：**

| 字段名 | 类型 | 描述 |
|---|---|---|
| `result_url` | `string` | 成品视频链接。有效期 24 小时，请尽快下载 |
| `produce_id` | `string` | 结果产物唯一标识 |

### cURL 示例（真实跑通的参数）

```bash
curl --location 'https://kickart.volces.com/openapi/ai_effect/query' \
--header "x-muse-token: ${MUSE_TOKEN}" \
--header 'Content-Type: application/json' \
--data '{
    "task_id": "7665544479945540247"
}'
```

真实响应（`request_id=20260723155329EBE0AF344C229CF7A630`，任务完成）：

```json
{
    "code": 0,
    "data": {
        "payload": {
            "produce_id": "424fbce1-5f96-4c60-a3eb-37be3e4efbc3",
            "result_url": "https://lf11-river-service-sign.volccdn.com/river-service/tmp/df01ad58-079d-4e35-af89-4bb9195abb82.mp4?x-expires=1784879551&x-signature=OL2UIrJSV5nguLdkPlL61k87aME%3D"
        },
        "progress": 100,
        "task_id": "7665544479945540247",
        "usage": 1.58
    },
    "message": "success",
    "request_id": "20260723155329EBE0AF344C229CF7A630"
}
```

---

## 5. 取消异步任务（补充）

- **请求方法**：`POST`
- **请求路径**：`/openapi/ai_effect/cancel`

请求参数：

| 字段名 | 类型 | 必填 | 示例 | 描述 |
|---|---|---|---|---|
| `task_id` | `string` | 是 | `"7620360162389278779"` | 需要取消的任务 ID |

响应关键状态：`0` 取消成功；`1602` 任务已取消；`1603` 任务已结束不可取消；`1604` 取消失败请稍后重试。

---

## 6. 错误码说明

### 通用错误码

| 错误码 | 类型 | 说明 |
|---|---|---|
| `1300` | `AuthFailed` | 认证失败：token 无效、过期或未激活 |
| `1400` | `ParamErr` | 参数错误：请求中包含无效或缺失参数 |
| `1401` | `ConcurrentErr` | 并发超限 |
| `1402` | `InsufficientPoints` | 创点不足 |
| `1403` | `QuotaErr` | 无权限 |
| `1500` | `InternalErr` | 内部错误：请记录 `request_id` 联系技术支持 |

### 接口特定错误码

| 错误码 | 类型 | 说明 |
|---|---|---|
| `0` | `Success` | 任务成功 |
| `1000` | `AsyncTaskRunning` | 任务运行中，请稍后轮询 |
| `1410` | `TemplateIdNotExist` | 模板不存在或未上线 |
| `1411` | `InputResolutionErr` | 分辨率不在模板支持的 `resolutions` 列表内 |
| `1412` | `ImageFormatErr` | 图片格式错误或文件损坏 |
| `1413` | `InvalidMediaUrlErr` | 媒体 URL 无法访问 |
| `1414` | `MediaSensitiveErr` | 输入内容触发安全审核 |
| `1415` | `OutputMediaSensitiveErr` | 输出包含敏感信息 |
| `1416` | `InvalidMediaCountErr` | 媒体数量不符合规格 |
| `1417` | `ChatCompletionError` | 大模型调用错误 |
| `1418` | `InvalidDurationBillingErr` | 时长计费参数错误 |
| `1419` | `TemplateIdErr` | 模板 ID 错误 |
| `1420` | `ImageDetectionRulesError` | 图片内容检测未匹配到规则 |
| `1421` | `DurationEnumError` | 入参时长枚举值错误 |
| `1423` | `VideoResolutionError` | 参考视频分辨率错误 |
| `1424` | `VideoDurationError` | 参考视频时长错误 |
| `1425` | `VideoFormatError` | 参考视频格式错误 |
| `1426` | `VideoSizeError` | 参考视频大小错误 |
| `1427` | `RefVideoError` | 参考视频链接错误 |
| `1428` | `LanguageEnumError` | 语言枚举值错误 |
| `1429` | `ModelImageCountError` | 模型 `image_count` 与模板配置不一致 |
| `1430` | `InputRatioError` | 输入图片比例错误 |
| `1431` | `CopyrightCheckFailed` | 版权校验失败 |
| `1432` | `NoCopyright` | 输入媒资无版权 |
| `1435` | `OutputNoCopyright` | 输出媒资无版权 |
| `1450` | `InputValidationErr` | 模板入参校验失败，`message` 会同时列出违反的字段和规则 |
| `1600` | `AsyncTaskNotExist` | 任务不存在 |
| `1601` | `AsyncTaskTimeoutErr` | 任务超时（最长 1 小时） |
| `1602` | `AsyncTaskCanceled` | 任务已取消 |
| `1603` | `AsyncTaskFinished` | 任务已结束，不可取消 |
| `1604` | `CancelFailed` | 任务取消失败，稍后重试 |
| `2000` | `AsyncTaskFailed` | 任务执行失败 |
| `3000` | `TaskCallbackFailed` | 回调失败 |

---

## 7. 已验证声明

本文档所有参数与结构均已通过真实的 submit + query 两阶段调用验证：

- **submit**：`request_id=202607231543550717B308786C58F2F5CC`，`code=0`，返回 `task_id=7665544479945540247`
- **query（完成态）**：`request_id=20260723155329EBE0AF344C229CF7A630`，`code=0`，`progress=100`，`usage=1.58`，成功拿到 `result_url` 与 `produce_id`

文档中的字段命名、类型、必填项与响应结构均以真实调用返回为准。
