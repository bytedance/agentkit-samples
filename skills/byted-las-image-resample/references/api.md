---
title: las_image_resample API 参考
---

# `las_image_resample` API 参考

## Base / Region

- API Base: `https://operator.las.<region>.volces.com/api/v1`
- Region:
  - `cn-beijing`
  - `cn-shanghai`

鉴权：`Authorization: Bearer $LAS_API_KEY`

## 请求体定义

| 字段名 | 类型 | 是否必选 | 说明 |
| :--- | :--- | :--- | :--- |
| operator_id | string | 是 | 固定为 `las_image_resample`（CLI 自动填充） |
| operator_version | string | 是 | 固定为 `v1`（CLI 自动填充） |
| data | ImageResampleReqParams | 是 | **`data.json` 的内容对应此字段**，详情见下表 |

### ImageResampleReqParams

| 字段名 | 类型 | 是否必选 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- | :--- |
| image_src_type | string | 是 | - | 输入图像格式类型：`image_url`、`image_tos`、`image_base64`、`image_binary` |
| image | string | 是 | - | 输入图像（URL、TOS路径或base64编码） |
| tos_dir | string | 是 | - | 输出 TOS 目录路径 |
| target_size | list[int] | 否 | [200, 200] | 重采样后的图像尺寸 [width, height] |
| target_dpi | list[int] | 否 | [72, 72] | 图像 DPI [x, y] |
| method | string | 否 | lanczos | 插值算法：`nearest`、`bilinear`、`bicubic`、`lanczos` |
| image_suffix | string | 否 | .jpg | 输出格式：`.jpg` 或 `.png` |
| image_name | string | 否 | - | 图像标识名，用于生成输出文件名（不带后缀） |

## 响应体定义

| 字段名 | 类型 | 备注 |
| :--- | :--- | :--- |
| metadata | metadata | 请求元信息，包含 task_status, business_code, request_id 等 |
| data | ImageResampleResponse | 返回数据 |

### ImageResampleResponse

| 字段名 | 类型 | 备注 |
| :--- | :--- | :--- |
| image_path | string | 重采样后图像的 TOS 存储路径 |

## 插值算法说明

| 方法 | 特点 | 适用场景 |
| :--- | :--- | :--- |
| nearest | 速度最快 | 像素风格图像 |
| bilinear | 速度与质量平衡 | 一般用途 |
| bicubic | 更平滑的高质量缩放 | 需要较高质量的场景 |
| lanczos | 抗锯齿效果更好 | 照片（推荐） |

## 使用限制

- 仅支持降采样：target_size 的宽高不得超过原图
- 输入图像格式支持：JPEG/PNG/TIFF（JPG/TIF 作为别名支持）
- 输入图像大小限制：文件大小不超过 100MB；像素总数不超过 225,000,000
- 需要能访问输入图像（公网 URL 或账号下的 TOS 地址）

## 业务码

| 业务码 | 含义 |
| :--- | :--- |
| 0 | 正常返回 |
| 1001 | 通用请求端异常 |
| 1002 | 缺失鉴权请求头 |
| 1003 | API Key 无效 |
| 1004 | 指定的 Operator 无效 |
| 1006 | 请求入参格式有误 |
| 2001 | 通用服务端异常 |

## 请求示例

> 以下为直接调用 HTTP API 的完整示例。通过 `lasutil` CLI 调用时，`data.json` 只需填写 `data` 字段内部的内容，`operator_id`/`operator_version` 由 CLI 的 `--operator-id` 参数自动注入。

```bash
curl --location "https://operator.las.cn-beijing.volces.com/api/v1/process" \
--header "Content-Type: application/json" \
--header "Authorization: Bearer $LAS_API_KEY" \
--data '{
  "operator_id": "las_image_resample",
  "operator_version": "v1",
  "data": {
    "image_src_type": "image_url",
    "image": "https://example.com/sample.jpg",
    "tos_dir": "tos://bucket/output/",
    "image_suffix": ".jpg",
    "target_size": [1024, 1024],
    "target_dpi": [72, 72],
    "method": "lanczos"
  }
}'
```

## 响应示例

```json
{
    "metadata": {
        "task_status": "COMPLETED",
        "business_code": "0",
        "error_msg": "",
        "request_id": "c7b29d78a99f88beda5497753ed60816"
    },
    "data": {
        "image_path": "tos://bucket/output/sample_resample.jpg"
    }
}
```
