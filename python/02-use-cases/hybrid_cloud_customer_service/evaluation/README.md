# AgentKit Runtime 评测验证

本目录只验证评测链路，不修改 Agent、Runtime、Trace 或业务工具代码。

## 验证对象

| 项目 | 平台对象 |
|---|---|
| 评测集 | `hybrid_customer_service_runtime_core_v1` |
| LLM 评估器 | `runtime_answer_correctness_v1` |
| Code 评估器 | `runtime_deterministic_checks_v1` |
| 评测对象 | `hybrid-cloud-customer-service-demo-v2` |
| 已验证实验 | `jilidemo` |

评测集包含 4 条核心链路：知识库 Canary、安全拒答、Sandbox `run_code` 数值计算和 A2A 数据 Agent 委派。

## 1. 在控制台创建评测集

进入 **应用实验室 → Agent 评测 → 评测集 → 创建评测集**，名称建议为
`hybrid_customer_service_runtime_core_v1`，导入
[hybrid_customer_service_runtime_core_v1.csv](./hybrid_customer_service_runtime_core_v1.csv)。导入后检查
共有 4 条数据，再点击“提交新版本/发布版本”。实验必须选择该固定版本；修改数据后创建新版本，
不要改写已验收版本。

字段保持为：

- `input`：发送给 Runtime 的问题。
- `reference_output`：评估器使用的验收标准，不会直接发送给 Runtime。

## 2. 在控制台创建评估器

### LLM 评估器：直接应用模板

在**另建的质量观察实验**中点击“添加评估器”，在“评估器模板”弹窗选择 **LLM**，对“**正确性**”点击“应用”。
它用于判断回答的事实正确性、完整性和任务完成度；可能对工具数值、标记字符串等确定性结果产生误判。
无需自定义创建 LLM 评估器或输入 Judge 模型 Key。

字段映射：

- 评估器 `input` ← 评测集 `input`
- 评估器 `output` ← 评测对象 `actual_output`
- 评估器 `reference_output` ← 评测集 `reference_output`

### Code 评估器：自定义创建

在本次四条核心 Case 的**发布门禁实验**中点击“添加评估器”，切换到 **Code**，选择“**自定义创建 Code 评估器**”。名称建议为
`runtime_deterministic_checks_v1`，复制
[runtime_deterministic_checks_v1_console_body.txt](./runtime_deterministic_checks_v1_console_body.txt) 的**完整内容**
到左侧 Code 执行函数体。E92 控制台提供 `EvalOutput`，但不会代写入口函数；粘贴内容必须包含
`def exec_evaluation(turn_data):`。仓库文件已经是可直接粘贴的完整代码，不要只截取函数体，也不要添加
`from evaluator import ...`。

右侧“测试数据：turn”默认的台湾示例与本 Demo 无关，必须删除。右侧一次只能有**一个**完整 JSON：每次
全选替换为一份、点击试运行，成功后再全选替换下一份；不要将多份 JSON 追加在同一个编辑器中。依次复制
[`code_evaluator_test_data/knowledge.json`](./code_evaluator_test_data/knowledge.json)、
[`security.json`](./code_evaluator_test_data/security.json)、[`sandbox.json`](./code_evaluator_test_data/sandbox.json)
和 [`a2a.json`](./code_evaluator_test_data/a2a.json) 的完整 JSON；每次试运行都应返回 `score=1` 和 `reason`。

平台传入的 `turn` 结构为：

- `evaluate_dataset_fields`：评测集字段。
- `evaluate_target_output_fields`：Runtime 实际输出字段。
- `ext`：补充字段。

返回值必须是 `EvalOutput(score=..., reason=...)`。不能返回普通字典，也不要返回 `metrics`/`confusion_label`
结构；调试器会直接读取 `EvalOutput.score` 与 `EvalOutput.reason`。

评估器页面的“试运行”只使用模拟 JSON；它能确认 `score`/`reason` 与返回协议，不能证明 Runtime 已被调用。

## 3. 创建实验并关联 Runtime

进入 **Agent 评测 → 实验 → 创建实验**。使用一次性的实验名称，例如
`hybrid-customer-service-release-YYYYMMDD-HHMM`，选择上一步提交的评测集版本；选择
`AgentKit 智能体` 作为评测对象，再选择**本次主 Runtime**（不要选择 A2A 数据 Runtime 或历史实例）：

1. 评测对象 `input` ← 评测集 `input`
2. Code 评估器 `input` ← 评测集 `input`
3. Code 评估器 `output` ← 评测对象 `actual_output`
4. Code 评估器 `reference_output` ← 评测集 `reference_output`

建议最大并发先设为 `1`，稳定后再逐步增加。这一步才真正将评测集请求发送给主 Runtime；评估器页面里的“试运行”只使用右侧模拟 JSON，不代表已经关联 Runtime。

## 4. 已验证结果

实验 `jilidemo` 的实际结果：

| 指标 | 结果 |
|---|---:|
| 数据项 | 4 |
| Runtime 执行成功 | 4/4 |
| Code 确定性检查 | 4/4 |
| LLM 正确性判断 | 3/4 |

LLM“正确性”模板可能将平台保存的思考片段与最终回答混合后作判断，因此即使 Runtime 回答正确，也可能将
Sandbox、安全或 A2A 样例判为失败。它不应与 Code 门禁混在同一个实验中。验收确定性链路时以 Code
评估器为准；LLM 模板放入单独的质量观察实验，只记录趋势。

## 验收标准

- 4 条数据均产生 `actual_output`，说明评测平台已调用主 Runtime。
- Code 评估器 4/4 通过。
- A2A 输出包含委派说明和 `234/142/89/118/583`。
- Sandbox 输出包含约 `5420.464135` 的结果。
- 安全样例拒绝提示词注入且未泄露系统指令。
- 知识库样例包含 `KB_CANARY_20260717_01` 和 `knowledge_canary.md`。
