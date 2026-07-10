---
name: byted-volcengine-capacity-auditor
description: 火山引擎资源巡检、水位评估、容量建议、趋势判断与预算优化 Skill。只要用户提到资源巡检、水位评估、容量评估、低利用率资源、扩缩容建议、预算优化、容量预测、未来7天/30天风险、ECS/CLB/ALB/RDS 巡检、近30天或90天监控分析、容量风险排查，或者希望把火山引擎资源做成巡检报告或容量判断时，都应该优先使用这个 skill，即使用户没有明确说“skill”或“巡检报告”。
---

# 火山引擎资源巡检与容量判断 Skill

## 能力定位

这个 Skill 用来把“资源清单 + 近 30/90 天监控 + 规则化判断 + 巡检建议 + 趋势判断”收成一条稳定流程。

当前 V1 已验证的范围：

- `ECS`：资源清单、CPU、内存、磁盘使用率、磁盘写 IOPS
- `CLB`：资源清单、监听器级 `QPS / 并发连接 / 新建连接 / 带宽` 摘要（默认先尝试拉取，失败时说明原因）
- `ALB`：资源清单、监听器级 `QPS / 并发连接 / 新建连接 / 带宽 / 丢连接 / HTTP 5xx` 摘要
- `RDS MySQL`：资源清单、当前 CPU/内存/磁盘快照、近 30 天 `QPS / ConnUsage`

当前 V1 的已知边界：

- `CLB` 当前已默认尝试拉取监听器级带宽、连接数和 `QPS` 摘要，但仍缺少规格上限换算与更完整口径，因此先给事实摘要和待补建议，不给结论性扩缩容判断
- `ALB` 当前已接入监听器级流量与异常摘要，但仍属于保守判断；如需更细粒度结论，还要继续补监听器/规则/服务器组维度口径
- `RDS MySQL` 的历史 `CPU / Mem / Disk` 监控口径尚未完全映射，当前先使用实例快照 + `QPS / ConnUsage` 做第一版评估

如果任务是在补监控口径或排查“为什么拿不到指标”，读取 [references/metric_gaps.md](references/metric_gaps.md)。

## 路由原则

这个 Skill 内部统一处理两类请求，不再拆成两个独立 skill：

- 巡检模式：用户想先看当前资源、水位、低利用率和风险点
- 趋势模式：用户已经拿到巡检结果，或者明确要看未来 `7/15/30` 天风险、预算方向、扩缩容时点

如果是趋势模式，读取 [references/forecasting.md](references/forecasting.md)。

## 适用场景

- 想快速盘点当前账号在某个地域下的 `ECS / CLB / ALB / RDS MySQL` 资源
- 想看近 30 天资源水位，找低利用率资源
- 想输出第一版扩缩容建议或预算优化建议
- 想基于近 30/90 天数据做容量趋势判断
- 想基于巡检结果继续判断未来 `7/15/30` 天风险
- 想基于“明年客户数增长 `10%` / 业务量增长 `20%` / 某条链路请求上涨”来判断整条链路应该怎么扩容
- 想做月度巡检、容量回顾、资源健康检查

## 不适用场景

- 用户要求执行高风险资源变更，例如直接停机、删实例、调规格
- 用户要求精确的 `CLB` 容量预测，但当前还没补齐连接/带宽/QPS 监控口径
- 用户要求严格财务级预算预测，但没有价格口径、计费方式和历史账单

## 前置条件

1. 当前工作空间有 `.env`
2. `.env` 至少包含：

```env
VOLCENGINE_AK=...
VOLCENGINE_SK=...
VOLCENGINE_REGION=cn-beijing
```

3. 本地 Python 环境已安装火山引擎 SDK

## 默认入口

优先使用内置脚本：

```bash
python3 <byted-volcengine-capacity-auditor-skill>/scripts/run_capacity_audit.py \
  --env-path ./.env \
  --project-name mysite \
  --region cn-beijing \
  --format markdown
```

如果用户没有给 `project-name`，默认输出整个地域下的结果。

如果是链路级趋势判断，使用：

```bash
python3 <byted-volcengine-capacity-auditor-skill>/scripts/run_capacity_audit.py \
  --env-path ./.env \
  --project-name mysite \
  --region cn-beijing \
  --mode forecast \
  --growth-factor 0.1 \
  --link-name payment-core \
  --format markdown
```

如果已经有拓扑产物，希望按拓扑链路范围评估链路内相关资源容量，优先使用：

```bash
python3 <byted-volcengine-capacity-auditor-skill>/scripts/run_capacity_audit.py \
  --env-path ./.env \
  --region cn-beijing \
  --mode forecast \
  --growth-factor 0.1 \
  --topology-file ./business_topologies/payment-core/topology.json \
  --link-name payment-core \
  --format markdown
```

说明：

- 传入 `--topology-file` 后，脚本会先从拓扑里提取链路内命中的资源，再按当前已支持的资源类型做容量评估
- 如果未传 `--topology-file`，但存在 `business_topologies/<link-name>/topology.json`，脚本会自动按该拓扑收敛评估范围
- 当前已支持按拓扑收敛并参与容量评估的资源类型是 `CLB / ALB / ECS / RDS MySQL`
- 这不是只针对某一条固定链路；只要拓扑里存在对应业务路径，脚本都会按该路径命中的已支持资源做整链评估
- 当前 `CLB / ALB` 若已位于拓扑链路内，也会被纳入整链评估；其中 `ALB` 已支持监听器级 `QPS / 连接 / 带宽 / 丢连接 / HTTP 5xx` 摘要，若关键指标仍缺失，报告会明确标记为数据缺口，而不是跳过入口层

## 输出产物

默认输出两种格式之一：

- `markdown`：适合直接给用户看
- `json`：适合继续给脚本、agent 或后续趋势判断流程消费

## 标准工作流

1. 读取 `.env` 或环境变量里的 `AK / SK / REGION`
2. 拉取 `ECS / CLB / ALB / RDS MySQL` 资源清单
3. 对 `ECS` 拉取近 30 天 CPU、内存监控；补充近期磁盘和 IOPS 摘要
4. 对 `RDS MySQL` 拉取当前实例快照和近 30 天 `QPS / ConnUsage`
5. 对 `CLB` 默认尝试拉取监听器级流量摘要，拉取不到时说明计费方式、监听器协议或口径缺口；对 `ALB` 输出监听器级流量与异常摘要
6. 基于阈值规则输出：
   - 低利用率资源
   - 容量风险资源
   - 建议缩容/继续观察/补监控
7. 如果用户要求趋势判断，再基于已有巡检结果继续给出：
   - 未来 `7/15/30` 天风险
   - 高/中/低置信度
   - 预算方向建议
   - 如果用户给的是业务增长目标（例如客户数、订单量、QPS、带宽或调用量增长），先做链路级场景建模，判断哪一层最可能先成为瓶颈，再给扩容顺序
8. 用统一结构返回报告

当前脚本入口已经支持：

- `--mode audit`：默认巡检
- `--mode forecast`：链路级趋势判断
- `--growth-factor 0.1`：表示场景增长 `10%`
- `--link-name xxx`：指定链路名称；若存在同名业务拓扑目录，会自动读取其 `topology.json`
- `--topology-file xxx`：显式指定拓扑文件，按拓扑链路筛选本次评估资源

## 阈值口径

读取 [references/thresholds.md](references/thresholds.md)。

如果用户没有给明确阈值，默认使用这套口径，不要临时自创一套不同规则。

## 监控口径补齐

如果用户不是单纯要巡检，而是在问“某些监控项为什么拿不到、应该怎么补”，按下面顺序处理：

1. 先确认该产品是否已经支持云监控 `GetMetricData`
2. 再确认 `Namespace / SubNamespace / MetricName / Dimensions`
3. 如果控制台可见但脚本拿不到，优先判断是不是口径写错、维度不对、粒度不匹配
4. 如果产品文档明确说明该指标不上报，就不要继续假设可以自动补齐
5. 在补不齐时，明确告诉用户哪些结论因此不能下

涉及具体排查路径时，读取 [references/metric_gaps.md](references/metric_gaps.md)。

## 报告结构

默认按下面结构输出：

```markdown
# 资源巡检报告
## 摘要
## ECS
## CLB
## RDS MySQL
## 建议清单
## 数据缺口
```

## 解释规则

- 先给整体结论，再给分资源类型明细
- 明确区分“已验证数据结论”和“尚未补齐的数据缺口”
- 对没有拉通的指标，不要装作已经评估完成
- 对缩容建议，优先用“建议进入候选池/建议验证后降配”这种保守措辞，不要直接断言必须缩容
- 对趋势结论，明确标注“高置信度/中置信度/低置信度”
- 如果只有 30 天数据，不要把预测说得过满

## 脚本资源

- `scripts/run_capacity_audit.py`：主入口，输出 JSON 或 Markdown 报告

## 测试用例

参考 [evals/evals.json](evals/evals.json)。
