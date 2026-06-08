---
name: byted-sol-stability-architecture-path-extractor
description: 联合代码、配置、API、依赖与文档输入，提取核心链路、组件拓扑、依赖风险与观测埋点缺口。
version: 0.1.0
---

# Architecture Path Extractor Skill

## 输入

- 代码仓库地址或本地路径（必填）
- 产品架构图路径（选填，可多次）
- 产品文档路径（选填，可多次）

## 输出

固定输出到 `output/<repo_slug>/`：

- `topology-model.json`
- `core-links.md`
- `dependency-risk.md`
- `observability-gaps.md`
- `evidence-index.json`

## 建模维度

- `service graph`
- `request path`
- `async path`
- `dependency graph`（DB / Cache / MQ / Third-party）
- `failure point`
- `observability hook point`

## 执行规则

1. 每条链路与风险项必须包含证据来源（文件路径）。
2. 核心用户链路、控制面链路、数据面链路必须分别输出。
3. 风险与埋点缺口必须能映射到服务或依赖节点。
4. 解析失败时输出可诊断信息，不得静默忽略关键输入。

## CLI

```bash
byted-sol-stability-architecture-path-extractor \
  --repo tests/integration/fixtures/sample_repo \
  --product-doc examples/product-doc.md \
  --arch-diagram examples/arch-diagram.md \
  --out-dir output
```
