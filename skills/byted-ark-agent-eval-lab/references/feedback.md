# 用户反馈

通过 `agent-eval feedback` 保存问题、体验与建议；不创建评测、不修改方案、不代表已派单或已解决。
沿用[主指南](../SKILL.md)的凭据和授权边界。只通过正式 CLI，不直连 API 或数据库。

## 何时进入、是否需要确认

| 场景 | 行动 |
|---|---|
| 用户明确说“帮我上报／提交反馈” | 已授权提交当前问题的最小必要信息；先简述拟提交内容，不重复索要相同授权 |
| 同一目标连续两次失败，且已有允许的诊断仍未解决 | 说明当前阻断，询问是否整理并上报；不为了达到次数阈值多执行一次 |
| 用户表达不满、明显受阻或单次已确认的服务硬阻断 | 先回应具体问题，再询问是否上报；不要求用户先重复失败 |
| 用户只要诊断／方法建议、正常低分、CLI 等待到期但任务仍在运行 | 正常处理原请求，不自动触发上报 |

同一问题本会话只主动提示一次；用户拒绝后停止提示，只有用户再次主动提出才继续。
如果已提交，优先提供原 `feedback_id`；没有新的事实不重复创建。会话内去重是引导规则，
不是后台监控或跨会话自动搜集协议。反馈提交失败不触发“反馈该失败”的递归上报。

## 整理最小信息

用已有上下文写清：用户想完成什么、实际现象、影响、已经做过的有限尝试。
未知原因明确为未知，不能把推断写成已确认根因；不要要求用户逐字段填表。

| 信息 | 来源与边界 |
|---|---|
| `summary`；可选 `expected`、`actual`、`impact`、`attempt_summary` | 简短事实摘要，不粘贴整段聊天、原始日志、代码或业务题目内容。summary 最多 256 字，其余单字段最多 8000 字；请求总计 64 KiB |
| `category`／`trigger_reason` | problem／experience／suggestion；explicit／repeated_failure／dissatisfaction／blocker，按实际场景填写 |
| 一个主资源和可选 Project | 从当前已确认对象选择 Plan、PlanSnapshot、Run、Comparison、ComparisonSnapshot 或 Comparison execution；不要猜 ID，不填所有关联 ID，也不继承 Profile 默认项目 |
| CLI 与运行环境 | CLI 自动补 CLI 版本、edition、环境、OS／架构；Agent 名称、Skill 版本或 digest 仅在已知时填入 `client_context`。不把 CLI 版本当作已安装 Skill 版本或服务部署版本 |
| 安全诊断标识 | `diagnostics` 只填 command（如 `runs.get`，不是带参数的命令行）、error_code、request_id、error_id、phase 和带时区的 observed_at；未知则省略 |

服务按主资源校验权限、反查权威 Project，并记录该 Run／execution 的精确历史 Snapshot 绑定；
不会读取“最新 Snapshot”替换历史事实。Draft revision/digest 是收集时观察值，不代表失败时版本。
服务端返回的 `resolved_context` 与用户提供的 `submitted_payload` 分开保存；没有部署版本证据就标为未知，
不为补齐信息读取源码、环境变量全集、配置文件或隐藏会话。安装／鉴权阶段失败可不关联任何资源。

凭据、Authorization／Cookie、签名 URL、完整 Snapshot／Plan spec、题目内容、轨迹和原始日志均不上传。
CLI 和服务会做有限脱敏，但这不是任意秘密的检测保证：提交前仍须检查摘要，只保留最小必要信息。

## 使用已有命令

先检查已安装版本是否提供反馈能力；帮助存在不证明目标服务已部署：

```bash
agent-eval feedback --help
agent-eval feedback submit --help
agent-eval examples feedback-submit.json
```

简单反馈在已获授权后可直接提交；无关联资源时省略 `--run-id`：

```bash
agent-eval feedback submit --run-id <run-id> --message "查询评测结果持续失败，阻断验收" --format json
```

需要更多上下文时，根据内置样例在新的本地私有文件 `feedback.json` 中填写安全摘要。
先本地检查；目标环境沿用当前已确认环境，不改 Profile。
以下输出文件须不存在；不要覆盖已有反馈文件：

```bash
agent-eval feedback submit --input feedback.json --dry-run --output prepared-feedback.json --format json
```

`--dry-run` 不鉴权、不访问网络，也能在无配置或配置损坏时使用；输出仅代表本地准备完成，**不是上报成功**。
生成的私有重放文件包含脱敏后的固定请求及幂等键。用户已有上报授权时可直接继续；
如果只有排查／预览授权，展示安全摘要、目标环境与关联对象后询问是否提交：

```bash
agent-eval feedback submit --input prepared-feedback.json --format json
agent-eval feedback get <feedback-id> --format json
agent-eval feedback list --format json
```

仅以服务返回 `status=saved` 与 `feedback_id` 认定保存成功，向用户返回 ID 和简短摘要；
不承诺处理时限。普通用户只能读取本人反馈；关联项目时还需要当前项目读取权限。
`list --scope all` 仅供平台管理员分诊；默认 `mine` 不包含其他用户反馈。

## 失败、重放与不可用

- 网络超时／响应丢失时，服务可能已经保存。CLI 错误会提供 `replay_file`，在原环境、原身份下用
  `feedback submit --input <replay-file>` 原样重放；同键同请求返回原反馈。不得重新生成 key、
  修改 prepared 文件或自动循环提交。需要更改反馈内容时创建新的原始请求，并使用新 key。
- 认证失败或资源权限失败时先修复对应问题，不换身份、不删资源关联来绕过鉴权；无凭据时保留本地摘要，
  不尝试匿名上报。没有资源的普通反馈不强制选择项目，但在线提交仍需要有效身份。
- 未提供 `--output` 的直接提交在发送前自动保存私有重放文件，确认成功后清理；提交失败时保留。
  用户指定的输出／输入文件不会自动删除。文件可能含用户摘要，妥善保管，用完按用户意愿清理。
- CLI 缺少命令、网关拒绝 Action 或服务不可用时，说明实际版本和错误，保留本地脱敏材料；
  无法使用 dry-run 就只整理对话中的安全摘要。不得绕过 CLI、宣称已上报，或以反馈能力替代服务修复。

服务当前不设置自动到期或 90 天清理；只收集必要信息，保存不代表公开分享或任何自动处理承诺。
