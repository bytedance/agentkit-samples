# API surface

This reference captures the main interface names, versions, request methods, and request parameters used by this skill.

## Policy interfaces

| Interface | Version | Request method | Purpose | Main parameters |
|---|---|---|---|---|
| `GetHostDefStatus` | 2021-06-15 | GET | Web protection switches | `Host` |
| `DescSmartCCConf` | 2021-06-15 | GET | Smart CC / 智能防护配置与开关状态 | `Domain` |
| `DescWebDefCcRule` | 2021-06-15 | GET | CC rule details | `Host`, `CurrPage`, `PageSize`, `CCRuleTag`, `CCRuleName`, `Url` |
| `GetWafAllowList` | 2021-06-15 | GET | WAF allowlist rules | `Host`, `CurrPage`, `PageSize`, `AllowRuleName`, `AllowRuleTag` |
| `GetWafBlockList` | 2021-06-15 | GET | WAF blocklist rules | `Host`, `CurrPage`, `PageSize`, `BlockRuleName`, `BlockRuleTag` |
| `DescWebDefBanRegion` | 2021-06-15 | GET | Region-ban configuration | `Host` |

## Attack and event interfaces

| Interface | Version | Request method | Purpose | Main parameters |
|---|---|---|---|---|
| `DescribeAttackEvent` | 2023-03-08 | POST | DDoS attack event details | `InstanceIps[]`, `BeginTime`, `EndTime`, `CurrPage`, `PageSize` |
| `ExportAttackEvents` | 2021-06-15 | POST | Export four-layer events | `InstanceIps`, `BeginTime`, `EndTime` |
| `DescribeEvent` | 2021-06-15 | POST | CCAI event detail query | `EventId` |
| `DescribeTopAttackSrcIp` | 2021-06-15 | GET | Top source IPs | `InstanceIp`, `BeginTime`, `EndTime`, `CurrPage`, `PageSize`, `TimeZone` |
| `DescribeTopAttackSrcArea` | 2021-06-15 | GET | Top source areas | `InstanceIp`, `BeginTime`, `EndTime`, `CurrPage`, `PageSize`, `TimeZone` |
| `DescribeTopAttackSrcInfo` | 2021-06-15 | GET | Top source summary | `InstanceIp`, `BeginTime`, `EndTime`, `CurrPage`, `PageSize`, `TimeZone` |
| `DescribeAttackDistribution` | 2021-06-15 | GET | Attack distribution | `InstanceIp`, `BeginTime`, `EndTime`, `CurrPage`, `PageSize`, `TimeZone` |
| `DescWebAtkOverview` | 2021-06-15 | POST | Web attack overview | host and time-window request fields |
| `DescWebAtkTopSrcIp` | 2021-06-15 | POST | Web top source IPs | host and time-window request fields |
| `DescWebAtkTopUrl` | 2021-06-15 | POST | Web top URLs | host and time-window request fields |

## Traffic interfaces

| Interface | Version | Request method | Purpose | Main parameters |
|---|---|---|---|---|
| `DescribeAttackFlow` | 2021-06-15 | POST | DDoS attack bandwidth and pps | `InstanceIps[]`, `BeginTime`, `EndTime`, `Tab` |
| `DescribeBizFlowAndConnCount` | 2023-03-08 | POST | Business traffic and connection count | `InstanceIps[]`, `BeginTime`, `EndTime` |
| `DescWebBpsFlow` | 2021-06-15 | POST | Web BPS trend | host and time-window request fields |
| `DescWebQpsFlow` | 2021-06-15 | POST | Web QPS trend | host and time-window request fields |
| `DescWebRespCode` | 2021-06-15 | POST | Web response-code distribution | host and time-window request fields |
| `DescWebAtkStatistics` | 2021-06-15 | POST | Web attack and back-to-origin statistics | host and time-window request fields |
| `DescWebDisplayPhase` | 2021-06-15 | GET | Web reporting whitelist state | no additional business parameters |

## Host-to-instance-IP resolution

| Interface | Version | Request method | Purpose | Main parameters |
|---|---|---|---|---|
| `DescHostRules` | 2021-06-15 | GET | Resolve protected host to instance IPs | `Demension`, `Accurate`, `Host` or `Hosts`, `InstanceIp`, `InstanceIps`, `CurrPage`, `PageSize`, `SearchName` |

## CCAI interfaces

| Interface | Request method | Purpose | Main parameters |
|---|---|---|---|
| `ListAssets` | POST | List CCAI assets and AI-defense status for domains | `Domain`, `AiDefenseStatus` |
| `ListEvents` | POST | List CCAI attack / detection events | `PageNumber`, `PageSize`, `Domain`, `Status`, `StartTime`, `EndTime` |
| `DescribeEvent` | POST | Get CCAI event detail | `EventId` |
| `ListRecommendations` | POST | List CCAI defense recommendations | `PageNumber`, `PageSize`, `RecommendationId`, `Domain`, `Status`, `StartTime`, `EndTime` |
| `DescribeRecommendation` | POST | Get CCAI recommendation detail | `RecommendationId` |

## Version note

Use the versions documented in this reference for the interfaces currently covered by this skill.
