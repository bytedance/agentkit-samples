## 火山方舟常用 PromQL 告警查询

### API 代理相关

| 告警项                  | PromQL                                                                                                                                                                                                                   |
| -------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Endpoint级别TPM**    | `(sum by(ark_endpoint) (increase(ark_api_proxy_request_token_count_sum{}[1m])+increase(ark_api_proxy_response_token_count_sum{}[1m])))`                                                                                  |
| **Endpoint每小时用量**    | `(sum by (ark_endpoint) (increase(ark_api_proxy_request_token_count_sum{}[1h])+increase(ark_api_proxy_response_token_count_sum{}[1h])))`                                                                                 |
| **一个账号下的所有ep每小时的用量** | `sum by(ark_endpoint) (increase(ark_api_proxy_request_token_count_sum{}[1h])+increase(ark_api_proxy_response_token_count_sum{}[1h]))`                                                                                    |
| **模型级别TPM**          | `doubao-1-5-pro-32k:(sum by(base_model) (increase(ark_api_proxy_request_token_count_sum{base_model=~"doubao-1-5-pro-32k"}[1m])+increase(ark_api_proxy_response_token_count_sum{base_model=~"doubao-1-5-pro-32k"}[1m])))` |
| <br />               | `doubao-seed-1-6:(sum by(base_model) (increase(ark_api_proxy_request_token_count_sum{base_model=~"doubao-seed-1-6"}[1m])+increase(ark_api_proxy_response_token_count_sum{base_model=~"doubao-seed-1-6"}[1m])))`          |
| **QPS**              | `sum by(ark_endpoint) (rate(ark_api_proxy_request_total{}[1m]))`                                                                                                                                                         |
| **RPM**              | `sum by(ark_endpoint) (increase(ark_api_proxy_request_total{}[1m]))`                                                                                                                                                     |
| **请求成功率**            | `1-((sum by(ark_endpoint) (rate(ark_api_proxy_request_total{code!~"Success"}[1m])) / sum by(ark_endpoint) (rate(ark_api_proxy_request_total{}[1m]))) OR on() vector(0))`                                                 |

### 流式请求相关

| 告警项                         | PromQL                                                                                                                      |
| --------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| **TTFT-首Token延时P95**        | `histogram_quantile(0.95, sum by (le)(rate(ark_api_proxy_stream_per_token_duration_seconds_bucket{is_first="true"}[1m])))`  |
| **TPOT-非首Token(中间字符)延时P95** | `histogram_quantile(0.95, sum by (le)(rate(ark_api_proxy_stream_per_token_duration_seconds_bucket{is_first="false"}[1m])))` |

### 内容生成相关

| 告警项                       | PromQL                                                                                                                                                                                                             |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **推理接入点 IPM 超过阈值**        | `sum by (ark_endpoint) (increase(ark_user_ark_content_generation_v2_image_generation_count_total{}[1m]))`                                                                                                          |
| <br />                    | `sum by (ark_endpoint,ark_model) (increase(ark_user_ark_content_generation_v2_request_total{ark_model="doubao-seedream-4-5"}[1m]))`                                                                                |
| **图片生成成功率异常**             | `sum by(ark_endpoint) (increase(ark_user_ark_content_generation_v2_request_total{http_status_code!="200"}[2m]))/sum by(ark_endpoint) (increase(ark_user_ark_content_generation_v2_request_total[2m]))or vector(0)` |
| **推理接入点请求 4xx 错误码速率超过阈值** | `sum by(ark_endpoint) (rate(ark_user_ark_content_generation_v2_request_total{http_status_code=~"4..",ark_endpoint="doubao-seedream-4-5"}[2m]))`                                                                    |
| **推理接入点请求 5xx 错误码速率超过阈值** | `sum by(ark_endpoint) (rate(ark_user_ark_content_generation_v2_request_total{http_status_code=~"5..",ark_endpoint="doubao-seedream-4-5"}[2m]))`                                                                    |

### 保障包相关

| 告警项                    | PromQL                                                                                                                    |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| **保障包输入TPM与购买量比值超过阈值** | `( sum by (ark_endpoint) ( increase(ark_api_proxy_request_token_count_sum{ark_endpoint="$Endpoint", tier=~"7"}[1m]) ) )`  |
| **保障包输出TPM与购买量比值超过阈值** | `( sum by (ark_endpoint) ( increase(ark_api_proxy_response_token_count_sum{ark_endpoint="$Endpoint", tier=~"7"}[1m]) ) )` |

***

## 使用说明

1. 这些 PromQL 查询可直接用于 byted-volcengine-vmp skill 的 `query_metrics.py` 和 `query_range_metrics.py` 脚本
2. 查询时需要指定工作区 ID：`--workspace-id <workspace-id>`
3. 范围查询还需要指定时间范围：`--start` 和 `--end`

### 示例

```bash
# 即时查询 QPS
python ~/.openclaw/workspace/skills/byted-volcengine-vmp/scripts/query_metrics.py \
  --workspace-id <workspace-id> \
  --query "sum by(ark_endpoint) (rate(ark_api_proxy_request_total{}[1m]))"

# 范围查询 Endpoint级别TPM
python ~/.openclaw/workspace/skills/byted-volcengine-vmp/scripts/query_range_metrics.py \
  --workspace-id <workspace-id> \
  --query "(sum by(ark_endpoint) (increase(ark_api_proxy_request_token_count_sum{}[1m])+increase(ark_api_proxy_response_token_count_sum{}[1m])))" \
  --start "2026-04-07T00:00:00+08:00" \
  --end "2026-04-07T23:59:59+08:00"
```

