---
name: byted-sol-stability-grafana-metric-explorer
description: 基于 SLI 模型、架构链路模型和源代码线索，生成 Dashboard IA、Panel Spec 与 Grafana JSON。
version: 0.1.0
---

# Grafana Dashboard Design Skill

## 输入

- `--sli-model`：SLI 模型 JSON 文件或目录（必填）
- `--arch-model`：架构链路模型目录（必填）
- `--repo`：源码目录（必填）

## 输出

固定输出到 `output/<repo_slug>/`：

- `dashboard-ia.json`
- `panel-specs.json`
- `grafana-dashboard.json`
- `traceability.json`
- `validation-report.json`
- `evidence-index.enriched.json`

## 规则

1. IA 必须包含 6 个固定页面：总览页、核心链路页、服务分层页、依赖资源页、错误分析页、变更/灰度/容量页。
2. 总览页必须同时包含 Health 区域与 Diagnostic 区域。
3. 每个 panel 必须包含：标题、图表类型、指标公式、维度变量、刷新周期、阈值颜色、drill-down、SLI/链路关联。
4. 没有证据支撑的指标不得伪造查询，输出 placeholder spec 并在校验报告标记。
