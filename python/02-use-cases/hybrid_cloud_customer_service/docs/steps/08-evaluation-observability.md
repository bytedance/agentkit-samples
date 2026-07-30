# 步骤 08：评测、Trace 与发布验收

## 目标

以版本化 Case、平台实验、确定性检查和平台 Trace 证明 Runtime 可以发布。

本步骤需要在控制台创建 **评测集 → 两个评估器 → 实验**。当前 AgentKit CLI 没有这三类
资源的创建命令，不能把本地的 CSV、JSONL 或 Python 文件误认为已经导入平台。

## 操作

### 0. 前置检查

确认目标主 Runtime 为 `Ready / RUNNING / Healthy`，并记录其非敏感 Runtime 名称/ID。若此前
已通过 Knowledge、Memory、Sandbox/MCP、Skills、A2A 或身份验收，**复用其证据，不在本步骤
重复创建资源或重复远程执行**。

### 1. 创建评测集

1. 进入 **应用实验室 → Agent 评测 → 评测集**，点击“创建评测集”。
2. 名称建议为 `hybrid_customer_service_runtime_core_v1`；导入
   [`evaluation/hybrid_customer_service_runtime_core_v1.csv`](../../evaluation/hybrid_customer_service_runtime_core_v1.csv)。
3. 导入后检查共有 4 条数据，且字段为 `input`、`reference_output`；后者只给评估器，不发送给
   Runtime。
4. 点击“提交新版本/发布版本”，记下版本号。后续实验必须选择这个固定版本；若修改数据，创建新版本，
   不覆盖已用于验收的版本。

### 2. 创建两个评估器

1. 在创建实验的“添加评估器”弹窗中，选择 **LLM** 类型，找到“**正确性**”模板并点击“应用”。
   这就是本 Demo 的 LLM 语义质量评估器；无需先创建名为 `runtime_answer_correctness_v1` 的自定义
   LLM 评估器，也不需要填写模型 Key。
2. 再次“添加评估器”，切换到 **Code** 类型，点击“**自定义创建 Code 评估器**”；名称建议为
   `runtime_deterministic_checks_v1`，将
   [`evaluation/runtime_deterministic_checks_v1_console_body.txt`](../../evaluation/runtime_deterministic_checks_v1_console_body.txt)
   的**完整内容**粘贴到左侧“执行函数体（Python）”后保存。E92 控制台会注入 `EvalOutput`，
   但要求代码显式定义 `def exec_evaluation(turn_data):`；仓库文件已包含这个完整函数，不要只粘贴
   函数内部代码，也不要添加 `from evaluator import ...`。
3. 在右侧“测试数据：turn”中，删除默认的台湾示例。**该编辑器一次只能保留一份完整 JSON：每次先全选并替换为一份，再点“试运行”；成功后再全选替换为下一份，绝不能在第一份 JSON 后追加第二份。** 依次测试
   [`knowledge.json`](../../evaluation/code_evaluator_test_data/knowledge.json)、
   [`security.json`](../../evaluation/code_evaluator_test_data/security.json)、
   [`sandbox.json`](../../evaluation/code_evaluator_test_data/sandbox.json) 和
   [`a2a.json`](../../evaluation/code_evaluator_test_data/a2a.json)。每份均应返回 `score=1` 和可读的
   `reason`。任一份失败或显示“系统错误”时，先核对返回 `EvalOutput(score=..., reason=...)` 的协议，
   不要保存为发布门禁评估器。
4. 在实验的字段映射中为 Code 评估器配置：`input ← input`、`output ← actual_output`、
   `reference_output ← reference_output`。评估器页面的“试运行”仅检查评估器本身，不能当成 Runtime
   通过证据。
5. 若实验数据项显示绿色成功，但 Code 评估器得分显示“—”，控制台实际可能是在展示
   `score=0`，并不表示评估器未执行。打开数据项详情查看 `reason`；安全 Case 应使用仓库最新
   评估器版本，它兼容中英文及多种英文拒答表达，同时仍会拦截明确的提示词泄露。修改评估器后必须
   “提交新版本”，并让新实验显式选择该版本；历史实验不会自动换用新代码。

### 3. 创建并执行实验

1. 在 **Agent 评测 → 实验** 点击“创建实验”，使用本次唯一名称，例如
   `hybrid-customer-service-release-YYYYMMDD-HHMM`；不要复用历史 `jilidemo` 作为本次发布证据。
2. 选择第 1 步提交的评测集版本；评测对象类型选择 **AgentKit 智能体**，目标选择本次主 Runtime。
3. 将评测对象 `input` 映射到评测集 `input`；本次四条核心能力的**发布门禁实验只添加 Code
   评估器**，并配置 `input ← input`、`output ← actual_output`、`reference_output ← reference_output`。
   LLM“正确性”模板另建为质量观察实验，不能与 Code 门禁混在同一个成功/失败结论中。
4. 首次执行最大并发设为 `1`，创建并启动实验。确认 4 条数据均生成 `actual_output`，再查看两个评估器
   的分数和原因。

### 4. Trace 与发布结论

1. 在 Runtime 高级配置开启“观测服务”，保存并 release；等待 Runtime 回到 `Ready / Healthy`。
2. 从本次实验或一次新的可识别 `/invoke` 取得 Trace，确认同一链路有
   `agent_server → workflow → agent → llm/tool`，并记录非敏感 Trace ID、模型、Token、耗时和状态。
3. 发布门禁：4 条 Runtime 调用成功、Code 评估器 4/4、每个失败项能定位到具体 Span。LLM“正确性”
   模板用于质量趋势；它会读取平台保存的完整流式内容，可能把思考片段当作最终回答并误判，因此不得把
   其红色状态并入本四条工具/安全/A2A 能力门禁。

## 最小证据集

- Runtime `Ready/RUNNING/Healthy`；
- live `/invoke` 返回最终回答；
- Knowledge 有来源；
- Memory 同用户召回且跨用户隔离；
- 写操作参数校验、人工确认和幂等生效；
- Prompt Injection、凭据索取和越权请求被拒绝；
- 评测通过，失败 Case 可定位到具体 Span；
- Trace 可见模型、Token、耗时和真实工具调用。

完整平台操作见[评测与可观测](../evaluation_and_observability.md)和
[评测验证](../evaluation_validation.md)。
