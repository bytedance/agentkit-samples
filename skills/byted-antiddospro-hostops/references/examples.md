# Examples

用这些例子帮助模型把用户意图路由到正确入口，同时识别哪些请求不应由本 skill 处理。

## 正向示例 1
用户请求：
- 帮我看看这个高防域名最近有没有异常

建议处理：
- 如果缺少 host，先追问
- 默认做一次完整巡检
- 使用 `query_antiddospro_host_healthcheck`
- 汇总策略、攻击、流量三部分信息

## 正向示例 2
用户请求：
- 查下这个 host 最近有没有被打，顺便看下来源 IP

建议处理：
- 收集 host 和时间范围
- 如果没给时间范围，默认最近 1 小时
- 使用 `query_antiddospro_attack_events`
- 重点说明是否观测到攻击，以及来源 IP、来源地区等信息

## 正向示例 3
用户请求：
- 帮我看下这个域名的 CC 规则、黑白名单和区域封禁情况

建议处理：
- 使用 `query_antiddospro_policy_overview`
- 汇总防护开关、智能防护开关、CC 规则、黑白名单、区域封禁状态
- 智能防护开关必须读取 `DescSmartCCConf` 的响应，不要把 `GetHostDefStatus` 返回的 `SmartEnable` 当成智能防护开关

### 最小判定示例（接口名称与版本）
有些接口名称很像，容易误用。

正确做法：
- 四层攻击事件应调用 `DescribeAttackEvent`，优先使用 `2023-03-08`，请求体传 `InstanceIps[]`
- 业务流量 / 连接数应调用 `DescribeBizFlowAndConnCount`，优先使用 `2023-03-08`，请求体传 `InstanceIps[]`
- 当接口名称或请求形态容易混淆时，以当前可用的对外接口契约为准，不要自行改写 Action 名或版本

### 最小判定示例（攻击源接口参数）
如果已经解析到多个实例 IP：
- `InstanceIps = ["192.0.2.1", "198.51.100.1"]`

正确做法：
- `DescribeAttackEvent` 可以传 `InstanceIps`
- 但 `DescribeTopAttackSrcIp`、`DescribeTopAttackSrcArea`、`DescribeTopAttackSrcInfo`、`DescribeAttackDistribution` 应按单个 `InstanceIp` 分别查询，再汇总结果
- 不要把整个 `InstanceIps` 数组直接传给这些 GET 接口


用户请求：
- 这个高防域名昨天 QPS 掉了，帮我看下是不是有异常流量或者响应码问题

建议处理：
- 尽量收集明确时间范围
- 使用 `query_antiddospro_flow_traffic`
- 重点看 QPS、BPS、响应码和相关异常

## 正向示例 5
用户请求：
- 这个域名对应的高防实例 IP 是多少

建议处理：
- 使用 `resolve_antiddospro_instance_ips`
- 返回解析出的实例 IP，并说明四层接口依赖这一步

## 正向示例 6
用户请求：
- 帮我看下 example.com 的 AI 防护有没有开，顺便看看最近有没有 CCAI 事件和建议

建议处理：
- 这是域名级防护巡检场景，应由本 skill 处理
- 智能防护开关先看 `DescSmartCCConf`
- 如果用户明确提到 AI 防护、CCAI 事件或建议，可补充查询 CCAI Action：`ListAssets`、`ListEvents`、`ListRecommendations`
- 汇总时区分"智能防护开关状态"和"CCAI 资产 / 建议状态"，不要混为一个字段


## 反向示例 2
用户请求：
- 把这个域名的区域封禁改成只封海外

不应由本 skill 处理的原因：
- 这是策略修改，不属于只读场景

## 反向示例 3
用户请求：
- 帮我写一个 AntiDDoSPro 的 Python SDK

不应由本 skill 处理的原因：
- 这是开发实现任务，不是围绕具体防护域名做运维分析
- 不应把本 skill 当成通用 SDK 生成器

## 反向示例 4
用户请求：
- 看下我这台 Linux 机器的网络流量是不是异常

不应由本 skill 处理的原因：
- 这是主机层或系统层排障，不是 AntiDDoSPro 防护域名巡检