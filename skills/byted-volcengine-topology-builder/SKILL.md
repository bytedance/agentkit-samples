---
name: byted-volcengine-topology-builder
description: 从火山引擎账号资产快照中尽量全量拉取当前已接入的资源数据，并沉淀为可复用的基础资产数据与拓扑视图。只要用户在做火山引擎账号资产盘点、资源梳理、依赖关系建模、运维底座建设，或者希望为拓扑分析、影响面评估、自动化运维、故障排查等上层场景准备基础数据时，都应该使用这个 skill；当用户提到“看图”“画图”“导图”“导出拓扑图片”时，也要触发。
---

# 火山引擎基础资产数据与拓扑 Skill

## 能力定位

这个 Skill 的职责是构建一层可复用的基础数据，而不是只服务某一个上层分析场景。

- 采集层：尽量全量拉取当前已接入的火山引擎资源资产
- 建模层：把原始快照整理成结构化资产数据和统一关系表达
- 输出层：落盘为 `json/md/dot/svg/png` 等可复用产物
- 复用层：供拓扑分析、影响面评估、自动化运维、故障排查、资产盘点、依赖梳理等场景继续消费

## 默认产物

默认会在当前工作空间的 `business_topologies/<business_key>/` 下生成：

```text
business_topologies/<business_key>/
  account_assets_snapshot.json
  topology.json
  topology.md
  topology.dot
  topology.svg   # 本地装有 Graphviz 或自动安装成功时生成
  topology.png   # 本地装有 Graphviz 或自动安装成功时生成
```

说明：

- `account_assets_snapshot.json` 是原始资产快照，是后续所有分析和重建的基础输入
- `topology.json` 是结构化关系模型，适合被脚本、agent、分析工具继续消费
- `topology.md` 是给人快速浏览的文本视图
- `topology.dot` 会始终生成，便于后续用 Graphviz 或其他工具继续转换
- `topology.svg/png` 主要用于“看图/导图/给用户展示”

## 一键流水线

1. 准备当前工作空间内的 `.env`：

```env
VOLCENGINE_AK=...
VOLCENGINE_SK=...
```

2. 运行通用入口脚本：

```bash
python3 <byted-volcengine-topology-builder-skill>/scripts/run_topology_pipeline.py \
  --workspace-root "$(pwd)" \
  --env-path ./.env \
  --region cn-shanghai \
  --business default-topology
```

这条流水线默认会依次执行：

- 采集资产快照
- 从快照构建拓扑
- 保存 `topology.json/topology.md`
- 生成 `topology.dot`
- 如果本地可用 `Graphviz`，再继续生成 `topology.svg/topology.png`

如果本地没有 `dot` 命令，脚本会先尝试自动安装 Graphviz；安装失败后再降级为仅输出 `topology.dot`，不会阻塞整个基础数据落盘流程。

## 常用参数

通用入口脚本 `run_topology_pipeline.py` 支持：

- `--business`：业务或资产视图标识
- `--region`：地域
- `--include`：需要采集的资源类型，可重复传入或逗号分隔
- `--entry`：构图时优先使用的入口资源类型，可重复传入或逗号分隔
- `--skip-render-graph`：只生成结构化产物，不额外产图

例如：

```bash
python3 <byted-volcengine-topology-builder-skill>/scripts/run_topology_pipeline.py \
  --workspace-root "$(pwd)" \
  --env-path ./.env \
  --region cn-shanghai \
  --business payment-core \
  --include ecs,eip,clb,alb,natgateway,rds_mysql,redis \
  --entry eip --entry clb
```

## 分层执行

### 1. 采集资产快照

```bash
python3 <byted-volcengine-topology-builder-skill>/scripts/dump_account_assets.py \
  --region cn-shanghai \
  --env-path ./.env \
  --include ecs,eip,clb,alb,natgateway,rds_mysql,redis \
  --output-file ./business_topologies/payment-core/account_assets_snapshot.json
```

这一层的目标是尽量沉淀稳定、可复用、可重建的基础资产数据。

### 2. 从快照构图

```bash
python3 <byted-volcengine-topology-builder-skill>/scripts/build_topology_from_account_assets.py \
  --assets-file ./business_topologies/payment-core/account_assets_snapshot.json \
  --region cn-shanghai \
  --entry eip --entry clb --entry alb --entry natgateway \
  --output-file ./business_topologies/payment-core/topology.json
```

这一层负责把离散资产组织成统一关系模型，方便后续分析和可视化。

### 3. 保存并渲染产物

```bash
python3 <byted-volcengine-topology-builder-skill>/scripts/save_topology.py \
  --business payment-core \
  --root ./business_topologies \
  --topology-file ./business_topologies/payment-core/topology.json
```

如果只想对已有 `topology.json` 单独补画图：

```bash
python3 <byted-volcengine-topology-builder-skill>/scripts/render_topology_graph.py \
  --topology-file ./business_topologies/payment-core/topology.json \
  --output-dir ./business_topologies/payment-core
```

## 关系表达

当前 `topology.json` 使用 `nodes + chains` 的结构：

- `path[].relation`：主链路关系
- `contexts.<node_id>`：路径节点的上下文资源

当前关系语义：

- `attached_to`：A 绑定到 B，例如 `EIP -> CLB`、`ECS -> EBS`
- `has`：A 拥有 B，例如 `CLB -> 后端服务器组`
- `contains`：A 包含 B，例如 `后端服务器组 -> ECS`、`VPC -> 子网`
- `belongs_to`：A 归属 B，例如 `ECS -> VPC/子网/安全组`

展示层默认以资源 `id` 为主，避免实例名称重复导致歧义；`name` 保留在元数据中作为辅助信息。

## 当前覆盖范围

在权限允许且快照字段完整的情况下，当前优先沉淀下面这些基础关系：

- `EIP -> CLB -> 后端服务器组 -> ECS`
- `EIP -> ECS`
- `ECS -> VPC/子网/安全组/EBS`
- `VPC -> 子网`

这意味着它已经能为很多上层场景提供基础输入，但它依然是一个可扩展的底座，不应被理解为“已经完整覆盖所有云资源关系”。

## 常见问题

- `AccessDenied (403)`：账号没有对应产品的只读权限，脚本会尽量降级并保留已成功拉取的资产
- `rds_mysql/redis` 对应 SDK 方法或字段不稳定：说明当前采集适配仍需继续扩展，但不影响已有基础产物落盘
- 本地没有 `dot` 命令：不会阻塞 `topology.json/topology.md` 生成，至少仍会得到 `topology.dot`
- 如果不希望渲染脚本自动安装 Graphviz，可在直接调用渲染脚本时加 `--skip-auto-install-graphviz`
