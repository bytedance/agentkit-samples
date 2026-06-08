---
name: byted-sol-stability-observability-asset-governance
description: 检测并治理可观测资产漂移、增量更新与质量问题，输出资产登记与治理报告。
version: 0.1.0
---

# Observability Asset Governance Skill

## 解决问题

1. 代码变化后 dashboard/metric 漂移治理
2. 新能力上线时 SLI -> 链路 -> panel 自动增量补齐
3. dashboard 资产质量治理（使用率、空图、重复、口径冲突）

## 输入

- `--sli-spec`（必填）
- `--architecture-spec`（必填）
- `--metric-mapping-spec`（必填）
- `--existing-dashboard`（必填）
- `--metrics-catalog`（可选）
- `--usage-stats`（可选）
- `--asset-registry`（可选）

## 输出

固定输出到 `output/<repo_slug>/`：

- `governance-summary.json`
- `dashboard-drift-report.json`
- `metric-drift-report.json`
- `usage-analysis-report.json`
- `stale-panel-report.json`
- `duplicate-dashboard-report.json`
- `definition-conflict-report.json`
- `incremental-update-plan.json`
- `asset-registry.json`
- `validation-report.json`
- `traceability.json`
- `evidence-index.enriched.json`
