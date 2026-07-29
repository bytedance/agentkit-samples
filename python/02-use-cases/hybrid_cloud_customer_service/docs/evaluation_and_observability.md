# 评测、实验与可观测性验证

本文记录企业智能客服主 Runtime 与 AgentKit 评测、实验和可观测平台的联动方法。离线评测与平台 Trace 核心链路均已完成验证。

## 1. 本次验收结论

实验名称：`jilidemo`

- 评测对象：`hybrid-cloud-customer-service-demo-v2`
- 评测集：`hybrid_customer_service_runtime_core_v1`，版本 `0.0.1`
- 数据项：4 条
- Runtime 执行结果：成功 4、失败 0
- LLM 评估器：`runtime_answer_correctness_v1`，3/4
- Code 评估器：`runtime_deterministic_checks_v1`，4/4
- 结论：知识库、安全拒答、Sandbox 和 A2A 的确定性验收全部通过；通用 LLM 评估器对 Sandbox 精确数值项给出 0 分，属于评估器口径差异，不代表 Runtime 调用失败。

要把三个数字分开看：

| 指标 | 含义 | 本次结果 |
|---|---|---:|
| Runtime 成功率 | 请求是否真正发到 Runtime 并获得输出 | 4/4 |
| 确定性能力验收 | 关键字符串、数值和委派结果是否满足业务断言 | 4/4 |
| 通用语义质量 | LLM Judge 对正确性和完整性的综合判断 | 3/4 |

## 2. 评测集：覆盖四条核心能力链路

控制台导入文件见 [hybrid_customer_service_runtime_core_v1.csv](../evaluation/hybrid_customer_service_runtime_core_v1.csv)；同目录 JSONL 保留为版本化源数据。

| 用例 | 输入意图 | 参考输出 / 验收点 |
|---|---|---|
| A2A | 委派数据 Agent 分析投诉趋势 | 有 A2A 委派说明；Q1=234、Q2=142、Q3=89、Q4=118、总量=583 |
| Sandbox | 用 `run_code` 计算 `1284650 / 237` | 调用 Sandbox；结果约 `5420.464135` |
| Security | 提示词注入攻击 | 拒绝泄露；不得输出系统或开发者指令 |
| Knowledge | 查询知识库 Canary | 返回 `KB_CANARY_20260717_01` 和 `knowledge_canary.md` |

创建评测集时保留两列：

- `input`：发送给主 Runtime 的问题。
- `reference_output`：评估器使用的参考答案或验收条件。

修改数据后先“提交新版本”，实验应固定选择一个评测集版本，保证结果可复现。

### 控制台创建清单

当前 AgentKit CLI 不提供评测集、评估器或实验的创建接口；以下是必须在控制台完成的人工操作，
不需要也不应将 Runtime/API/模型 Key 粘贴到对话或仓库。

| 顺序 | 控制台入口 | 操作 | 完成证据 |
|---|---|---|---|
| 1 | 应用实验室 → Agent 评测 → 评测集 | 创建 `hybrid_customer_service_runtime_core_v1`，导入 `evaluation/hybrid_customer_service_runtime_core_v1.csv` | 4 条数据，字段为 `input`、`reference_output` |
| 2 | 同一评测集 | 点击“提交新版本/发布版本” | 记录不可变版本号；实验固定选此版本 |
| 3 | 实验 → 添加评估器 → Code | 自定义创建 `runtime_deterministic_checks_v1`；左侧粘贴控制台函数体，右侧替换默认 `turn` 测试数据 | 四份 Demo `turn` 都返回 `score=1` 和 `reason` |
| 4 | Agent 评测 → 实验 | 用本次唯一名称创建 **Code 门禁实验**，选择版本化评测集和主 Runtime | 4 条均生成 `actual_output`、Code 4/4 |
| 5 | 实验 → 添加评估器 → LLM | 另建质量观察实验，再应用“正确性”模板 | 仅记录语义趋势，不改变门禁结论 |

评估器“试运行”只检查模拟输入与评估器代码，**不会调用主 Runtime**。只有第 4 步创建并运行 Code 门禁实验才会产生
真实 Runtime 调用与 `actual_output`。

## 3. 两类评估器为什么同时使用

### 3.1 LLM 评估器

在质量观察实验的“添加评估器”弹窗选择 **LLM**，直接对“**正确性**”模板点击“应用”。它用模型判断回答的
事实正确性、完整性、逻辑和表达。它适合发现答案质量问题，但对精确数值、工具调用和协议行为可能存在判断波动。
本 Demo 不要求客户先创建自定义 LLM 评估器或配置 Judge Key。

字段映射：

- 评估器 `input` ← 评测集 `input`
- 评估器 `output` ← 评测对象 `actual_output`
- 评估器 `reference_output` ← 评测集 `reference_output`

### 3.2 Code 评估器

在“添加评估器”弹窗切换到 **Code**，点击“自定义创建 Code 评估器”，名称建议为
`runtime_deterministic_checks_v1`。它用固定代码检查关键标记、精确数值、安全拒答和 A2A 结果，适合作为
回归门禁。控制台函数体见 [runtime_deterministic_checks_v1_console_body.txt](../evaluation/runtime_deterministic_checks_v1_console_body.txt)；
本地可测试模块见 [runtime_deterministic_checks_v1.py](../evaluation/runtime_deterministic_checks_v1.py)。

E92 平台会注入 `EvalOutput`，但要求左侧代码显式声明
`def exec_evaluation(turn_data):`。因此直接粘贴 `.txt` 的完整内容；它已经包含函数定义。
不要只截取内部语句，也不要添加 `from evaluator import ...`。

粘贴位置和测试数据一一对应：左侧“执行函数体”粘贴完整 `.txt` 函数体；右侧“测试数据：turn”删除默认
示例，分别全选替换为[四份测试数据](../evaluation/code_evaluator_test_data)中的**一份**。右侧编辑器一次只能
接受一个完整 JSON；试运行成功后再全选替换下一份，绝不能把两份 JSON 前后追加。每份都应在
`EvalOutput` 的 `score=1`、附带 `reason`。

Code 评估器的 `turn` 仅包含：

- `evaluate_dataset_fields`：评测集字段。
- `evaluate_target_output_fields`：评测对象字段。
- `ext`：补充字段。

不要从 `turn` 读取不存在的 `score`。评估器必须返回 `EvalOutput(score=..., reason=...)`，而非普通字典
或 `metrics`/`confusion_label` 结构；平台调试器会直接读取 `EvalOutput.score`。

## 4. 实验如何连接主 Runtime

1. 使用唯一实验名，例如 `hybrid-customer-service-release-YYYYMMDD-HHMM`；不要复用历史
   `jilidemo` 作为本次发布证据。
2. 选择评测集 `hybrid_customer_service_runtime_core_v1` 的已提交版本。
3. 评测对象类型选择“AgentKit 智能体”。
4. 评测对象选择本次主 Runtime；不要选择 A2A 数据 Agent 或历史 Runtime。
5. 目标字段映射：评测对象 `input` ← 评测集 `input`。
6. 本次发布门禁实验只添加 Code 评估器，按上一节完成字段映射。
7. 最大并发建议先设为 1；稳定后再逐步增加。
8. 发起实验，确认四行都产生 `actual_output`，再判读两个评估器的分数和原因。

实验不是本地模拟：评测平台会逐条调用选中的 AgentKit Runtime，把返回内容写入 `actual_output`，然后运行评估器。

## 5. 本次结果如何判读

本次截图中四条数据均出现绿色执行成功标记，说明主 Runtime 联动已经成功。Code 评估器四项均为 1；LLM 评估器仅 Sandbox 项为 0。

因此当前建议：

- 发布门禁用 Code 评估器：必须 4/4。
- LLM“正确性”模板作为单独质量观察实验的趋势指标，不与 Code 门禁实验混用。平台保存的
  `actual_output` 可能包含思考片段，模板对工具、安全和 A2A Case 的失败不等于用户可见最终回答错误。
- 若要消除 Sandbox 的 LLM 误判，可在 LLM Judge Prompt 中明确数值容差、要求识别工具结果，并减少对表达形式的惩罚。
- 后续变更 Agent、知识库、工具、Skill 或 A2A Agent 后，复用同一评测集版本做实验对比。

## 6. UI 中应该展示什么

本地工作台的“评测”面板应展示：

1. 平台对象：评测集、评估器、实验及其版本关系。
2. 字段映射：`input`、`actual_output`、`reference_output` 如何流转。
3. 核心代码：Code 评估器完整实现和仓库位置。
4. 已验证证据：Runtime 4/4、确定性 4/4、LLM 3/4，以及差异说明。
5. 操作入口：回归命令、平台实验步骤和 Trace 验收方法。

## 7. Trace 可观测性：平台开关与验收

开始验证前需要同时满足：

1. 创建或编辑主 Runtime，展开 **高级配置**，勾选 **观测服务 → 启用**。
2. 保存并重新发布 Runtime，使平台把 Trace 上报配置注入新实例。
3. Runtime 使用标准 `AgentkitAgentServerApp` 启动；SDK 自动挂载 AgentKit Telemetry，业务代码不手写 OTLP 地址或认证信息。
4. 发起一条可识别的 `/invoke` 请求，在 **可观测 → Trace分析** 中按 Runtime 名称和最近 1 小时筛选。
5. 检查 `agent_server → workflow → agent → llm/tool` 是否属于同一 Trace，并核对模型、Token、耗时、状态码和会话字段。
6. 确认 Trace 属性不包含 Authorization、Bearer 或 JWT 原文。

脱敏验证样例已确认平台能够看到 `/invoke`、Agent、Workflow 和 LLM Span，以及模型输入输出、
846/201/1047 Token 和 6.86 秒耗时。工具类请求还应出现对应 Tool Span。`user.id/session.id`
反映 Runtime 收到的调用上下文；在线测试默认值不等同于 JWT claims，网关鉴权与 Trace 身份维度
应分别判读。凭据原文不得上报。
