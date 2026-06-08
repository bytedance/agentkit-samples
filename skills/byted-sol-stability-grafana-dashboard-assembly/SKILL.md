---
name: byted-sol-stability-grafana-dashboard-assembly
description: 组装并联调 Grafana dashboard，自动检查、修复并输出验收通过产物。
version: 0.1.0
---

# Grafana Dashboard Assembly Skill

## 输入

- `--sli-spec`：SLI Spec JSON（必填）
- `--metric-mapping-spec`：Metric Mapping Spec JSON（必填）
- `--metrics-catalog`：Metrics catalog JSON（必填）
- `--log-dict`：日志字段字典 JSON（必填）
- `--trace-spans`：tracing span 名称 JSON（必填）
- `--existing-dashboard`：现有 dashboard JSON（必填）

## 五个子步骤

1. 数据源连通性检查
2. Query 适配
3. 空图 / 错图识别
4. 自动修复
5. 验收测试

## 输出

固定输出到 `output/<repo_slug>/`：

- `dashboard-assembled.json`
- `validation-report.json`
- `autofix-report.json`
- `acceptance-report.json`
- `traceability.json`
- `evidence-index.enriched.json`

## 验收指标

- `success_rate`
- `empty_panels_count`
- `error_query_count`
- `manual_confirmation_items`
