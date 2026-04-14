# `las_pdf_parse_doubao` API 速查

LAS-AI PDF 内容视觉解析算子（异步任务：submit -> poll）。

## Base / Region

- API Base: `https://operator.las.<region>.volces.com/api/v1`
- Region:
  - `cn-beijing`
  - `cn-shanghai`

## 鉴权

控制台通过 Header 形式（以控制台“请求示例”为准）：

- `Authorization: Bearer <API_KEY>`

## submit

请求体（完整 HTTP body；通过 `lasutil` CLI 调用时，`data.json` 只需填写 `data` 内部的内容）：

```json
{
  "operator_id": "las_pdf_parse_doubao",   // CLI 自动填充
  "operator_version": "v1",                 // CLI 自动填充
  "data": {
    "url": "https://...pdf",
    "parse_mode": "normal",
    "start_page": 1,
    "num_pages": 10
  }
}
```

`data` 字段（即 `data.json` 中应填写的内容）：

| 字段名 | 类型 | 必选 | 说明 |
|---|---|---:|---|
| `url` | string | 是 | PDF 可下载地址，支持 `http/https` 以及 `tos://bucket/key` |
| `parse_mode` | string | 否 | 解析模式：`normal`（默认，不进行深度思考，速度更快，适用于绝大多数文档）或 `detail`（开启深度思考，更细致但耗时更长） |
| `start_page` | int | 否 | 起始页（从 1 开始），默认 1 |
| `num_pages` | int | 否 | 解析页数，缺省则从 `start_page` 到文档末尾；最大不超过 200 |

返回体关键字段：

- `metadata.task_id`：后续轮询用
- `metadata.task_status`：通常为 `PENDING/RUNNING/...`

## poll

请求体（`lasutil poll` 自动构造，无需手动编写）：

```json
{
  "operator_id": "las_pdf_parse_doubao",   // CLI 自动填充
  "operator_version": "v1",                 // CLI 自动填充
  "task_id": "<task_id>"                    // CLI 自动填充
}
```

返回体：

- `metadata.task_status`：`PENDING` / `RUNNING` / `COMPLETED` / `FAILED`
- `metadata.business_code` / `metadata.error_msg`：业务错误信息
- `data.markdown`：合并后的最终 Markdown
- `data.detail[]`：逐页结构化详情

`data.detail[]` 常见字段：

| 字段名 | 类型 | 说明 |
|---|---|---|
| `page_id` | int | 页码（从 1 开始） |
| `page_md` | string | 单页 Markdown |
| `page_image_hw` | object | 页渲染图片宽高（像素） |
| `text_blocks` | list | 文本/图片块（阅读顺序） |

`text_blocks[]` 常见字段：

| 字段名 | 类型 | 说明 |
|---|---|---|
| `label` | string | `text` / `image` |
| `text` | string | 文本内容（当 `label=text`） |
| `url` | string | 图片裁剪预签名 URL（当 `label=image`，通常有有效期） |
| `box` / `norm_box` | object/array | bbox 信息（坐标/归一化坐标） |

## 业务码与错误处理

控制台页面“错误码”示例（HTTP 层）：

| HttpCode | 错误码 | 错误信息 | 说明 |
|---:|---|---|---|
| 400 | `Model.InvalidName` | The model name is invalid. | 模型名称不合法 |
| 401 | `Authorization.Missing` | Missing Authorization. | 缺少鉴权 |
| 401 | `ApiKey.InValid` | The api key is invalid. | API 不合法 |

常见 `metadata.business_code`：

| 业务码 | 含义 |
|---:|---|
| `0` | 正常返回 |
| `1002` | 缺失鉴权请求头 |
| `1003` | API Key 无效 |
| `1004` | Operator 无效 |
| `1005` | Operator 版本无效 |
| `1006` | 请求入参格式有误 |
| `1007` | 缺少 `task_id` |
| `1008` | `task_id` 无效 |
| `2002` | 请求超时 |
| `2003` | 服务端限流（SERVER_BUSY） |

## 常见踩坑

- 并发限制：默认 1 QPM，过快调用可能触发限流（建议退避重试）
- URL 不可访问：私有链接/过期链接会导致任务失败
- 页数超限：单次最多 200 页，超长文档建议分段解析
