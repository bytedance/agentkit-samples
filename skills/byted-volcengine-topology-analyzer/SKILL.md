---
name: byted-volcengine-topology-analyzer
description: 基于已有拓扑数据回答资源影响面、上下游链路、业务归属和变更波及范围。只要用户在问某个节点或资源变更会影响什么应用、入口出口、上下游链路、归属业务，或者想梳理某个 ECS/CLB/EIP/安全组/VPC/子网/EBS 的依赖关系时，都应该使用这个 skill；即使用户没有明确提到 topology，也要主动触发。
---

# 拓扑影响分析 Skill

## 能力定位

这个 Skill 不是负责构建底层数据，而是消费已有拓扑数据，回答与影响面、归属关系、上下游链路和变更波及范围相关的问题。

- 定位目标节点，例如 `sg-xxx`、`eip-xxx`、`clb-xxx`、`i-xxx`、IP、资源名
- 基于结构化拓扑推断直接关联资源、受影响 ECS 和入口链路
- 在用户给出变更描述时，生成基于静态拓扑的风险摘要和校验建议
- 在多候选或多业务场景下，先给出候选排序，再决定是否需要用户确认

## 输入前提

这个 Skill 默认消费由基础资产/拓扑构建流程沉淀出来的业务拓扑数据。

- 默认查找目录：
  - 当前工作空间下的 `business_topologies/`
- 目录结构约定：
···
business_topologies/
  <business-a>/
    topology.json
    topology.md
```

- 结构化拓扑数据：`topology.json`
- 人工可读拓扑摘要：`topology.md`
- 当前图关系语义：
  - `attached_to`：A 绑定到 B
  - `has`：A 拥有 B
  - `contains`：A 包含 B
  - `belongs_to`：A 归属 B

如果用户没有显式指定 `--root`，脚本会优先在这两个默认目录里自动发现业务拓扑数据。

如果用户在问“实时状态”或“当前是否健康”，要明确提醒：这里回答的是基于静态拓扑数据的推断，不是运行时状态。

## 标准流程

### 1. 先提取查询要素

优先识别这些信息：

- 节点标识：资源 ID、IP、名称、关键词
- 业务范围：用户是否已经给出明确业务
- 问题类型：影响面、归属关系、上下游链路、入口出口、直接关联
- 变更动作：例如放开端口、删除规则、切换入口、修改子网

如果用户已经给了业务名，就在查询时带上 `--business`，减少歧义。

### 2. 先跑脚本拿结构化结果

优先使用脚本，不要直接凭肉眼扫 JSON：

```bash
python3 <byted-volcengine-topology-analyzer-skill>/scripts/analyze_topology.py \
  --node "<node-id-or-keyword>" \
  --output json
```

如果已知业务：

```bash
python3 <byted-volcengine-topology-analyzer-skill>/scripts/analyze_topology.py \
  --business "<business>" \
  --node "<node-id-or-keyword>" \
  --output json
```

如果用户给出了变更描述：

```bash
python3 <byted-volcengine-topology-analyzer-skill>/scripts/analyze_topology.py \
  --business "<business>" \
  --node "<node-id-or-keyword>" \
  --change "<change-description>" \
  --output json
```

### 3. 有歧义时先澄清

如果脚本返回多个匹配：

- 优先看 `match_score` 和 `match_reasons`
- 如果是 `id:exact`、`public_ip:exact` 这类高置信命中，可以以第一候选为主回答
- 如果只是 `name:fuzzy` 或 `metadata:fuzzy`，不要擅自选一个，先让用户确认
- 如果多个业务里都有同名节点，要把候选业务、节点类型、得分和命中原因一起列出来

### 4. 需要时再读 `topology.md`

在这些场景下补读对应业务下的 `topology.md`：

- 需要把链路解释得更口语化
- 想确认外部入口链路是否和结构化结果一致
- 用户想看一个更接近人工总结的回答

## 回答原则

### 1. 先分层，再下结论

回答时区分这三层：

- 直接关联：与目标节点 1 跳相连的资源
- 直接影响：能明确推断会受该节点变更影响的 ECS 或入口链路
- 潜在关联：在同一局部拓扑中 2 跳内可达，但不能直接断言一定受影响的资源

### 2. 链路以资源 ID 为主

- 输出链路时默认以资源 `id` 为主，避免实例名称重复导致误判
- 若需要补充人工可读信息，可以附带 `name`，但不要用 `name` 替代 `id`

### 3. 不要凭空虚构应用名

这个数据里未必显式存了“应用名”。因此：

- 如果存在 `EIP -> CLB/ALB -> server_group -> ECS` 这类链路，就表述为“基于拓扑推断出的应用入口链路”
- 不要凭空虚构业务系统名、服务名、域名
- 如果只能定位到 ECS，就明确说“当前只能确认受影响的计算节点，未发现更上层应用名字段”

### 4. 对不同资源类型使用不同推断方式

- `security_group`、`subnet`、`vpc`、`ebs`：
  先找直接归属或挂载到它的 ECS，再继续向上追溯入口链路
- `eip`、`clb`、`alb`、`natgateway`、`server_group`：
  直接向下找 ECS
- `ecs`：
  直接回溯它的上游入口链路，同时列出它所属的 `security_group/subnet/vpc/ebs`

### 5. 变更摘要要明确是启发式推断

如果用户明确在问“做某个变更会怎样”，优先使用脚本返回的 `change_assessment`：

- `risk_level`：作为变更风险等级
- `summary_lines`：作为简洁结论
- `risk_reasons`：作为为什么有风险
- `validation_checklist`：作为变更前后校验项
- `rollback_suggestions`：作为回滚建议

不要把这些启发式风险提示说成“绝对事实”。要明确说这是基于当前静态拓扑和变更关键词的推断。

## 回答结构

优先按这个顺序组织回答：

```markdown
结论：
- 命中的节点是 ...
- 当前可确认直接影响到 ...

关联关系：
- 直接关联资源: ...
- 所属业务: ...
- 候选排序: 如果存在多命中，列出前 2~3 个候选及命中原因

影响链路：
- 链路 1: EIP -> CLB -> server_group -> ECS
- 链路 2: ...

变更风险：
- 风险等级: high / critical / ...
- 风险提示: ...
- 校验建议: ...
- 回滚建议: ...

判断说明：
- 这是基于当前静态拓扑数据的推断
- 如果要做变更前确认，建议继续核对运行时配置和白名单规则
```

## 示例问题

### 示例 1

用户：

```text
安全组 sg-3vai4r386pnuo1w7k94e5s09v 如果放开 80 端口，会影响什么应用？
```

回答重点：

- 命中 `security_group`
- 找到归属这个安全组的 ECS
- 回溯到 `EIP -> CLB -> server_group -> ECS` 或 `EIP -> ECS`
- 明确说明这是“受影响入口链路”而不是“确定业务名”
- 给出风险等级、校验建议和回滚建议

### 示例 2

用户：

```text
14.103.24.61 这个入口 IP 背后挂了哪些资源？
```

回答重点：

- 识别 IP 可能匹配到 `EIP` 或相关资源元数据
- 列出 CLB、后端服务器组、ECS
- 按拓扑顺序描述链路
- 如果存在多候选，要展示候选排序并解释为何优先选第一项

### 示例 3

用户：

```text
i-yek807xukgk36d6jug0q 这个 ECS 属于哪个业务，和哪些网络资源有关？
```

回答重点：

- 返回所属业务
- 列出安全组、子网、VPC、EBS
- 列出对应入口链路

### 示例 4

用户：

```text
帮我全局查一下名为 ECS 的节点，先按最可能的候选排序给我看。
```

回答重点：

- 触发跨业务检索
- 先展示候选排序、命中原因和业务归属
- 如果高分候选不唯一，先请用户确认具体目标节点

## 兜底规则

- 如果脚本查不到节点，要明确说“当前拓扑数据里没有命中该节点”
- 如果能命中节点但没有完整入口链路，不要硬编，直接说明“仅定位到基础设施层”
- 如果用户在问实时状态，而当前数据只是静态拓扑，要提醒这是基于快照/拓扑的分析结果
- 如果用户的问题本质是评估某个变更，但没有明确 node，先追问目标资源，不要泛泛而谈
