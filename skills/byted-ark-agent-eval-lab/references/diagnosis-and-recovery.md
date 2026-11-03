# 诊断与修正参考

用户询问为什么失败、为什么超时、旧 Snapshot 为何不可运行、修改为何未生效，或希望据此调整方案时读取。
沿用[主指南](../SKILL.md)的查询、授权、凭据与结果解释边界；只查状态或已有报告时不必执行整套诊断。
本参考提供取证和行动选择，不复制服务端错误分类器，也不把诊断自动升级为修复或重新执行。

## 先确定事实与修改必要性

从实际失败操作开始，只读取相关对象。Preview／Validate 失败从对应 Draft 和诊断起步，不创建 Run 取证。
启动明确被拒绝且尚无 Run 时，从失败请求的精确 Snapshot ID／摘要、环境、Project 与返回诊断起步，
不要求不存在的 Run ID；响应丢失／超时则先按主指南查询受理结果，不能当成明确拒绝再次启动。
下列入口用于普通主动 Run；`mode=rescore` 或独立 Evidence／Assessment 的异常按
[数据与评分参考](data-and-scoring.md)使用专属查询，不套用普通 Run 的逐题结构。

```bash
agent-eval runs get <run_id> --format json
agent-eval plans snapshots get <snapshot_id> --format json
agent-eval runs items <run_id> --page-size 100 --format json
```

已有 Run 时 Snapshot ID 来自源 Run，不取最新版本；分页与 Comparison 批次定位沿用主指南。
按实际 Item／repetition／Attempt 血缘读取 Evidence、轨迹与 Assessment／报告；
失败 Attempt 的证据用于解释异常，最终评分仍以服务选定的结果绑定为准。
仅在需要检查 Draft 或提出配置修正时再 `plans get`，历史查询不要求重建方案。

| 需要保留的证据 | 用途 |
|---|---|
| CLI 版本、目标环境、Project、精确 Run／Snapshot ID 与摘要 | 防止把别的版本或批次当作本次事实；部署版本不可取得时标为未知 |
| 实际返回的诊断 `code`、`field_path`、`owner`，或 Attempt 的 `error.code`、`error.phase`、`error.owner` | 定位拒绝的配置或失败阶段；字段缺失／未知就说明，不能自行补一个根因 |
| 安全的 Request ID、`error_id`、`cause_ref` 与关联证据 ID | 供对应服务负责人继续排查；不回显凭据、签名链接或原始敏感日志 |
| `result_class`、评分可读状态、Evidence 完整性及 cleanup 状态 | 区分质量结论、执行／评分缺口和资源清理；终态或取得报告不证明资源已释放 |

面向用户说明“已确认现象与证据 → 已确认原因／仍待确认的部分 → 下一步及停止点”。
错误码或失败阶段只用于缩小范围：例如 `agent_execution` 不能单独证明模型慢，
`verification` 也不能单独证明评分规则写错。服务故障或证据不足时，不给出猜测性的配置修改。

## 执行准备失败

先区分平台身份、模型访问和业务登录，业务配置见[执行准备参考](execution-preparation.md)。
仅当 Snapshot 显式包含 preparation 时按绑定的精确资产／鉴权版本检查；普通 Run 不默认要求补鉴权。
Skill 上传可能在 input_transfer 阶段失败，不能仅因没有进入 execution_preparation 就排除产物准备问题。
根据实际异常区分上传／解包、CLI 安装／版本校验、登录初始化和业务调用；登录失败也不必然是密钥错误。
核对资产可用状态、精确引用、Attempt error_id、Evidence 和 cleanup；未知根因如实保留。
安装／鉴权准备失败保持未评分，不改为质量零分，不反复重跑或绕过权限、网关及归档保护。

## 原生重评分诊断

先回读 ID 的 mode／来源，区分原始 active Run 与本次 rescore Run；原始 Run 成功或旧 reward 存在，
不证明重评分已经创建或成功。诊断按实际失败阶段选择，不为定位问题再次 start：

| 阶段 | 查询与下一步 |
|---|---|
| 创建请求明确被拒绝 | 保留本次请求的精确来源、评分 DatasetVersion／Environment 绑定、外层错误码、Request ID 和安全诊断。尚无重评分 ID 时不描述为 verifier 已执行失败；响应丢失／超时则先查询，不等同明确拒绝 |
| 已创建，准备或评分失败／不可评分 | 用 `runs rescore get/items`；Comparison 先 get，再查全部成员。按服务选定执行及实际证据解释材料、兼容性或运行依赖问题，保留不可评分状态，不补零、不拿旧评分顶替 |
| 已有评分，报告异常 | 分开查询评分事实与报告生成／发布状态，返回可读评分及报告缺口，不为修报告重新评分 |

服务端可在 `data.details[].diagnostics[]` 返回受控原因；CLI JSON 显示在 `error.details[]`，
按其中 `code`／`owner` 结合实际资产解释，不依赖未透出的内部 message。旧服务无 diagnostics 或原因未知时，
外层 `REGRADE_ENVIRONMENT_REFUSED` 只能证明评分准备被拒绝，不能自行补一个确定根因。

- `REGRADE_SINGLE_STEP_SEPARATE_REQUIRED`：检查本次评分版本是否为单步骤且具有独立 separate 评分声明；
  这是组合前提，不单凭此码认定 shared。已确认只有 shared 时按[评分版本准备](data-and-scoring.md#评分版本不兼容时)引导，
  有兼容已发布版本则复用；不修改原 Run 或放宽校验。
- `REGRADE_GRADING_BUILD_UNSUPPORTED`／`REGRADE_GRADING_IMAGE_MISMATCH`：分别核对真实评分镜像是否已声明、
  评分要求与所选精确 Environment 镜像是否匹配；资源不足／运行时不支持按对应诊断处理，不一律要求发布新 Dataset。
  公开 requirements 会过滤 `docker_image`，不能仅凭该字段未展示认定镜像缺失。
- `publishable=false` 本身不等于已发布 Environment 不可执行，非阻塞警告也不等于拒绝原因；
  必须结合发布状态、实际阻断项与本次诊断，不能凭网络／目录警告建议换项目、放宽安全配置或重复提交。

请求结果未知时保留原请求和幂等键，恢复规则见[提交一次与恢复](data-and-scoring.md#提交一次与恢复)。
不能取得原失败请求／评分版本时，明确区分“当前配置可复现的阻断”和“原请求根因已确认”。

## 哪些问题适合修改方案

| 已有证据指向的问题 | 先核对什么 | 可采取的动作与边界 |
|---|---|---|
| Preview／Validate 拒绝某个输入字段 | `field_path`、对应 Target／Model Spec 或[配置参考](configuration.md)中的输入形状 | 在授权范围内修正相应 Draft 分区；不支持的 RunPolicy 覆盖项属于能力限制，不能换字段试探 |
| 环境或题目世界未就绪 | 精确 Snapshot 的 readiness、Dataset 版本与 requirements；预缓存世界用 `worlds check`，细节见[高级操作参考](advanced-operations.md) | 缺少资产时交由对应负责人准备，或按已有授权准备；准备完成后按既有刷新流程发布新 Snapshot，不改旧 Snapshot，也不自动换 Provider／数据集 |
| Target 参数、模型、MCP／Skill 或题目依赖与用户目标不符 | 当前 Draft、原 Snapshot、服务返回的支持范围及实际异常证据 | 明确是哪项配置需变、为何能解决已确认问题，再修改对应分区或绑定新的不可变资产版本；保留用户未要求修改的参数及 MA 身份／凭据边界 |
| 鉴权、模型服务、网络、存储、归档或平台依赖故障 | 当前身份与作用域、稳定诊断和实际失败依赖；鉴权按主指南处理 | 区分用户凭据问题和部署侧问题；不是一律改 Plan，也不换 Key、模型或环境掩盖故障。持续阻断返回诊断交给相应负责人 |
| 缺少评分、评分异常或轨迹不完整 | 源 Attempt／Evidence／Assessment 绑定、可读状态与缺失原因 | 未评分不补零，不因缺报告而重跑；评分规则确需变更时，按[数据与评分参考](data-and-scoring.md)选择原生重评分或独立 Assessment，不默认重新跑 Agent |

有效低分不自动等于配置错误。用户希望提高效果时，先讨论有证据支持的模型／Skill／Tool 调整，
不承诺修改后必然涨分；需要比较效果时保留基线、题目、评分口径与可比条件。

## 等待与资源占用怎么解释

先查同一 Run 的状态、稳定诊断及必要的逐题进度，不凭等待时长定位故障，也不创建新 Run 试探。

| 已有事实 | 解释与处理 |
|---|---|
| `CAPACITY_UNAVAILABLE` 或尚在排队 | 容量可能受环境、模型、Project、Run 等约束，不直接断言平台模型排队；按实际诊断解释，未知原因保持未知，有限观察后交回查询入口 |
| `CAPACITY_POLICY_UNAVAILABLE` 或依赖读取失败 | 属于容量策略／依赖不可用，不等于用户并发设置错误；保留 Request ID 和原因码交给服务负责人，不擅自降低并发、换 Key 或换模型 |
| 429 或模型调用受限 | 核对返回的错误码、Owner 和相关连接／模型证据；不能一律归因于共享 Key，也不承诺个人 Key 能解决环境或平台瓶颈 |
| 取消已受理、Run 已终态或报告已生成 | 均不能单独证明资源已释放；按实际清理／容量证据说明，未知就标明未知，不发起新一轮来验证释放 |

只有证据指向用户可调整配置且获得授权时才修改；是否继续等待、取消或更换资源按用户意图处理，不自动执行。

## 超时先分清是哪一层

| 现象 | 核对与解释 | 下一步 |
|---|---|---|
| CLI `watch`／`--wait` 到期 | 查同一个 Run 的当前状态；客户端停止观察不等于服务端超时或取消 | 按用户需要继续有限查询；不改 Plan、不重放启动请求 |
| 服务返回 `ITEM_TIMEOUT` 或 `RUN_TIMEOUT` | 回读该 Snapshot 的 `content.run_policy`，结合实际返回的失败阶段与证据；整轮预算含创建后的排队时间 | 已冻结 Run／Snapshot 不可原地改预算；证据支持且用户授权时，按[配置参考](configuration.md)修改 Draft 的可配字段并重新发布，新 Run 另需执行授权；不默认加时、增加 repetitions、拆循环 Run 或把失败记为质量零分 |
| 在单题总预算之前出现阶段超时 | 看实际阶段诊断、可读取的 Trial 证据及冻结执行合同，不能按耗时数字猜阶段 | 先确认是阶段上限、外层预算还是依赖中断；原因未确认不提出加时／改模型结论 |
| 模型、工具或环境依赖调用超时 | 看实际 `owner`、错误码和关联证据，不与单题预算耗尽混为一谈 | 可由用户修正的配置才按上表处理；依赖故障交由对应负责人，是否重跑另按资格和授权判断 |

历史 Snapshot 还需检查 `content.runtime.executor_contract_version`：
`ael-trial-executor.v1` 保留题包／Harbor 的阶段时限；`ael-trial-executor.v2` 将冻结的单题预算映射为阶段上限；
`ael-trial-executor.v3` 为环境启动等待设置最多 1 小时的上限，仍计入单题预算，其他预算解释见[配置参考](configuration.md#冻结结果怎么读)。
外层仍约束整题总时长，不是环境准备、Agent、Verifier 各自获得一份完整预算。
这里的执行合同版本不是 Snapshot 外层 `schema_version`；不要与环境 pending 的 Snapshot v2 混淆。
旧版本本身不是故障或强制升级理由。证据确认旧语义影响用户目标时，按下节选择受支持的修正路径，
不手改 `content.runtime`，也不承诺重新发布必然解决问题。

## Snapshot 不兼容时如何恢复

Snapshot 冻结配置与编译结果，不保证后续服务永远支持执行。只在实际拒绝、已确认的兼容性问题，
或用户询问时进入本节；正常执行不额外刷新。区分 Snapshot 外层 schema、冻结环境协议与
`content.runtime.executor_contract_version`，不能仅凭版本数字大小推定失效或升级方向。

| 已确认事实 | 处理路径 |
|---|---|
| `PLAN_SNAPSHOT_RETIRED`／`DATASET_VERSION_RETIRED`，或精确资源回读明确为 `availability=RETIRED` | 核对实际退役对象、可读的退役原因和本次操作诊断；这是运行准入限制，不是环境 pending 或协议过旧。停止被拒绝的新发布／执行路径；原因不明或没有适用替代时联系资源负责人，不自动 refresh、重新发布、Copy 或换版本绕过退役 |
| `SNAPSHOT_VERSION_UNSUPPORTED` 且诊断明确指向已发布环境协议不支持，并要求刷新环境重新发布 | 核对当前 Draft 后，复用 `agent-eval examples README.md` 的“环境待就绪后重新发布”流程；当前服务仍须支持所需编译结果 |
| 冻结环境为 pending，其依赖已准备完成 | 沿用同一环境刷新流程；旧 Snapshot 不会随依赖就绪自动变化 |
| 输入协议确需迁移，如旧 Skill 绑定在 preparation 中 | 按[执行准备参考](execution-preparation.md)修改必要输入后重新发布；纯环境 refresh 不替代配置迁移，不自动升级资产版本或改变业务身份 |
| 只有 `SNAPSHOT_EXECUTION_CONTRACT_INVALID`、`SNAPSHOT_DIGEST_MISMATCH` 等汇总错误，或未知诊断 | 保留错误码、阶段、Owner 和安全请求标识继续定位；这些错误不足以证明旧版本不兼容，不据此改 Plan 或反复发布 |
| 权限、容量、网络、存储或运行时部署不匹配 | 按对应依赖／部署问题处理；不能让用户通过更换配置掩盖服务故障。缺少兼容能力时交给服务负责人 |

退役不抹除历史事实：有权限时仍可查询原 Snapshot、Run、Evidence 和报告，不要求先修复或迁移。
历史重评分按本次操作的服务端准入判断，不因源 DatasetVersion 退役就一概判为不能重评分。
用户授权已覆盖明确的替代方案，且替代资源经正常查询／准入确认可用时，按原流程处理，不增加负责人审批；
不自动替用户选择替代版本，也不修改旧 Snapshot 或历史结果。

**先确认基线，再选择恢复动作。** 回读原 Snapshot 与当前 Draft；若 Snapshot 详情本身也被拒绝，
保留原请求／Run 中已有的精确绑定和诊断，明确哪些冻结内容无法核对，不以最新 Snapshot 代替。
当前 Draft 不等于历史输入；存在他人改动或无法确认原意时，先展示差异／缺项并确认本次发布范围，
不能声称原配置已完整保留，也不能从编译结果反造 Draft。

**复用已有刷新或修改流程。** 环境刷新只使用 `agent-eval examples plan-refresh-environment.json`，
携带最新 Draft revision/digest；其操作为 `refresh /spec/environment`，不携带 value、不修改用户配置。
它推进 revision，使后续发布重新编译，不是通用协议迁移，不能改为 `refresh /spec/runtime`，
也不通过改名称或同值 replace 制造升级。需要修改输入时沿用下节最小修改和级联恢复规则。
Comparison 使用全体成员的 `batch-patch-members` 同步父级绑定，再重新 Preview／Validate／Publish；
不逐个修改成员后继续使用旧父级绑定，不为通过校验放宽控制变量条件。
首次使用先核对 CLI 帮助和包内样例；不支持、校验拒绝或原因仍未知时停止该路径，说明缺口。

**发布后验证范围，不自动运行。** 按下节回读新 Snapshot 的精确绑定、相关环境／执行合同与未变配置；
同一 Draft revision 再次 Publish 只返回原 Snapshot，`runs rerun` 也仍消费原冻结合同。
新 Snapshot 不自动替换历史 Run、已有 ComparisonSnapshot 或 Schedule 的绑定；更新定时任务须另有相应授权。
用户只要求发布时到此结束，返回“新配置已发布，运行效果待验证”。已获运行授权时，从新 Snapshot
按主指南启动一次约定范围的执行；单 Target 可建议选题验证，Comparison 不臆造选题参数或静默全量运行。
实际阶段、Evidence 与评分事实才证明该范围的恢复；执行语义变化会影响历史可比性，不能直接归因为 Agent 效果变化。

## 从已确认问题到最小修改

1. **核对基线和范围。** 用户指的是某次历史评测时，读取原 Snapshot，再读当前 Draft，展示相关差异。
   当前 Draft 已被他人修改时不能静默夹带其变化；无法恢复所需用户输入就说明缺项，不能把编译后的 Snapshot 反写为 Draft。
2. **只修改必要配置。** 展示修改字段、保留项、计划执行量和停止阶段；原授权覆盖时直接继续，不逐步重复确认。
   仅改重复次数使用 `agent-eval examples plan-patch-run-policy.json`；完整填写方法读取
   `agent-eval examples README.md` 的“修改已有方案”。其他分区沿用现有级联恢复规则，不用模板重置未改字段。
   Comparison 使用全体成员的原子更新并重新校验可比性；共享 RunPolicy 不能只改一侧，也不能为通过校验静默改变对比类型。
3. **按授权回读并停止。** 只保存：回读 Draft 的新绑定、修改值和未变配置后结束；
   需要发布：以新绑定 Preview／Validate，通过后发布并回读精确 Snapshot；需要执行：再核对执行授权，启动一次新 Run。
   任何一步出现新阻断就返回已完成事实和下一步，不循环修改／发布／重跑尝试碰运气。

发布后核对的不只是 ID 是否变化，还包括用户要求的配置是否进入 `content.run_policy` 等对应冻结分区，
以及 Target、精确 Dataset／题目范围、Environment、执行合同与其他条件是否仍符合约定。
输入形状和 Owner 编译输出不必逐字相同；以服务返回的绑定和语义核对，不在 Skill 重写编译规则。
新 Snapshot 配置正确只证明配置已冻结，不证明运行故障已消除。若用户授权验证，提前说明要观察的具体结果，
用新 Run 的实际阶段、Evidence 和评分事实判断；无法验证时保留“配置已更新，运行效果待验证”。

## 仍然受阻或用户希望反馈

先说明已确认现象、证据和阻断，不以“已上报”代替诊断或承诺问题已解决。
用户明确要求上报，或同一目标连续失败／表达不满时，读取[用户反馈参考](feedback.md)。
未明确要求上报时先询问；同一问题本会话仅提示一次，拒绝后不再提示或上传。
只用已有安全证据，不为收集反馈新增 Run、重评分、发布或反复重试。
