---
name: byted-sol-stability-sli-modeling
description: 将能力描述建模为结构化 SLI Spec，用于 SLO 与 Error Budget 管理。
version: 0.1.0
---

# SLI Modeling Skill

## 输入

- 能力/场景描述文本（必填）
- owner（必填）
- 参考文档路径（选填）

## 输出

固定输出到 `output/<slug>/`：

- `sli-spec.json`
- `sli-report.md`

## SLI Spec 字段（强约束）

- `capability`
- `user_journey`
- `sli_name`
- `sli_type`：`availability|latency|correctness|freshness|completeness|consistency`
- `measurement`
- `denominator`
- `dimension`
- `target_slo`
- `error_budget`
- `severity`：`P0|P1|P2`
- `owner`

## 执行规则

1. 不得输出缺失字段的 SLI Spec。
2. `sli_type` 与 `severity` 必须命中枚举。
3. 字段校验失败必须返回可诊断错误，不静默补全无意义默认值。
4. 允许通过输入文本中的 `key: value` 形式显式指定字段并覆盖推断。
5. 优先围绕关键用户旅程建模（如登录、核心请求、结算），避免使用 CPU/内存等内部资源指标直接充当 SLI。
6. 优先采用 request-based 口径（good requests / total requests）；确有需要时才采用 period-based 口径，并在 `target_slo` 中显式说明窗口。
7. 默认使用 rolling 30d 目标窗口，`error_budget` 默认遵循 `1 - target_slo` 的口径。
8. 不使用 100% 作为默认目标；建议使用 99.x 目标并通过 burn-rate 观察预算消耗。

## CLI

```bash
byted-sol-stablity-sli-modeling \
  --input examples/input.capability.md \
  --owner team-observability \
  --out-dir output
```
