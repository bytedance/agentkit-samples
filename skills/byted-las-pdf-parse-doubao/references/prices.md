# 计费信息

- PDF 解析 normal 模式：0.02 元/页
- PDF 解析 detail 模式：0.04 元/页

## 预估方式（元）

- 用 `lasutil pdf-pages <pdf_url>` 获取页数（page\_count）
- `estimated_price_yuan = page_count * rate_yuan_per_page`

`rate_yuan_per_page` 取决于请求体里的 `parse_mode`（normal/detail）。
