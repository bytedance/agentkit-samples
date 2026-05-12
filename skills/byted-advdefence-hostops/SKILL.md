---
name: byted-advdefence-hostops
description: 火山引擎 AdvDefence 高防域名只读巡检。用户要查域名健康、攻击、流量、CC/WAF/区域封禁、智能防护或 CCAI 状态时使用。
version: 1.0.0
---

# AdvDefence HostOps

本 skill 用于对火山引擎 AdvDefence 防护域名做只读巡检、分析和排障。

最适合的场景：
- 域名健康巡检
- 最近攻击排查
- 防护策略检查
- 智能防护 / AI 防护状态核对
- CCAI 资产、事件、建议的只读查询
- 流量与响应异常分析
- 域名到高防实例 IP 的解析

当任务明确围绕某个 AdvDefence 防护域名或 Host 展开，并且目标是查看、分析、解释现状，而不是修改配置时，应优先使用本 skill，而不是通用排障或通用报表 skill。

## Compatibility

期望环境：
- Python 3
- `requests`
- 通过环境变量 `VOLC_ACCESS_KEY` / `VOLC_SECRET_KEY` 提供火山引擎凭证

需要实际发起 API 调用时，使用本 skill 附带的客户端能力。

不要在对话、提示词或工具参数中传入 AK/SK。

## Boundaries

本 skill 只读。

不要：
- 修改防护策略
- 增删黑白名单规则
- 修改区域封禁配置
- 调用任何写接口

如果用户要求变更配置，应明确说明本 skill 只支持查看、分析和排障，不负责下发变更。

## Required inputs

尽量收集：
- `host`：防护域名或 Host
- `begin_time` / `end_time`：如果用户明确给出了时间范围

如果用户没有给时间范围：
- 对攻击和流量类分析，默认查看最近 1 小时

如果用户没有给 host：
- 先追问防护域名或 Host，再继续

## Default workflow

### 1. 先判断用户目标
判断用户是想要：
- 一次完整巡检
- 查看防护策略
- 核对智能防护 / AI 防护状态
- 排查攻击事件
- 查看 CCAI 资产、事件或处置建议
- 分析流量或报表异常
- 解析域名对应的高防实例 IP

如果用户表达比较模糊，默认先做完整巡检。

### 2. 选择合适入口
- 防护策略检查 → `query_advdefence_policy_overview`
- 智能防护 / AI 防护状态核对 → `query_advdefence_policy_overview`，必要时结合 CCAI 资产查询
- 攻击事件排查 → `query_advdefence_attack_events`；如果用户明确在看 CCAI 事件，则优先走 CCAI 事件查询
- CCAI 资产、事件、建议查询 → `query_advdefence_ccai_overview`；需要进一步展开时，再分别调用 `ListAssets`、`ListEvents`、`DescribeEvent`、`ListRecommendations`、`DescribeRecommendation`
- 流量或报表分析 → `query_advdefence_flow_traffic`
- 域名到实例 IP 解析 → `resolve_advdefence_instance_ips`
- 需求宽泛或表述不清 → `query_advdefence_host_healthcheck`，并按需补充 CCAI 只读信息

### 3. 解读结果时保持保守
- 明确区分“未观测到数据”和“确认没有风险”
- 上游接口报错时，直接说明真实原因
- 需要排障时，保留请求 ID
- 如果域名无法解析出实例 IP，要明确说明四层 DDoS 视图可能不完整
- 智能防护开关只以 `DescSmartCCConf` 的响应为准；`GetHostDefStatus` 中的 `SmartEnable` 不是智能防护开关语义，不能据此下结论
- `DescSmartCCConf` 的查询参数是 `Domain`，不是 `Host`
- `DescribeAttackEvent` 使用 `2023-03-08`，请求体传 `InstanceIps[]`
- `DescribeBizFlowAndConnCount` 使用 `2023-03-08`，请求体传 `InstanceIps[]`
- DDoS 攻击源相关接口按单个 `InstanceIp` 查询，不要把 `InstanceIps` 数组直接传给 `DescribeTopAttackSrcIp`、`DescribeTopAttackSrcArea`、`DescribeTopAttackSrcInfo`、`DescribeAttackDistribution`
- 不要凭经验猜测参数位置；优先按接口当前可用的请求形态调用

### 4. 向用户汇总结论
先给结论，再给观测范围、关键发现、风险点和下一步建议。

## Output format

除非用户明确要求其他格式，否则按以下顺序输出：

## 巡检结论
用一小段先说明整体判断：当前看起来正常、可疑、还是存在明确异常。如果数据不完整，也要在这里先说明。

## 观测范围
- 巡检对象：哪个 Host 或域名
- 时间范围：用户指定时间，或默认最近 1 小时
- 数据完整性：哪些视图完整，哪些因为接口报错或实例 IP 解析失败而不完整

## 策略状态
- 防护开关状态
- 智能防护开关状态（必须以 `DescSmartCCConf` 的响应为准，不要把 `GetHostDefStatus` 返回的 `SmartEnable` 当成智能防护开关）
- CCAI / AI 防护资产状态（如用户明确询问 AI 防护状态，可补充读取 CCAI `ListAssets` 的 `AiDefenseStatus`）
- CC 规则状态
- WAF 黑白名单状态
- 区域封禁状态

## 攻击观测
- 指定时间窗口内是否观测到攻击
- 可用时列出来源 IP、来源地区、Top URL 等重点信息
- 如果用户明确关注 CCAI 事件，可补充 `ListEvents` 与 `DescribeEvent` 的结果
- 如果只能看到七层数据或只能看到部分数据，要明确说清楚

## 流量观测
- BPS、PPS、QPS、响应码等是否存在异常
- 流量变化更像正常波动还是异常波动

## 风险与下一步建议
- 当前最值得关注的风险点
- 建议下一步查看什么
- 哪些结论暂时无法确认，以及原因

保持回答简洁，优先输出提炼后的结论，不要直接倾倒原始 payload。除非观测数据足以支持，否则不要轻易下“域名健康”这种结论。

## Error handling

接口失败时不要隐藏错误。

应以用户能理解的方式说明问题，但保留必要的技术细节。常见坑点见 `references/troubleshooting.md`。

## References

按需读取：
- `references/api-surface.md`：接口名称、版本、请求方式、主要参数
- `references/troubleshooting.md`：常见 API 坑点与排障方式
- `references/examples.md`：典型请求、推荐入口和不支持场景

## Implementation notes

如需实际发起查询，可使用本 skill 附带的调用能力。
