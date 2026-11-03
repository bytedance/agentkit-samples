# 按需操作参考

仅在用户需要规范包导入、手动 Evidence 归档、成员协作、预缓存世界诊断、自定义 Environment 或 Schedule 时读取对应章节。
沿用 [主指南](../SKILL.md) 的授权、凭据、Project 与幂等边界；这些能力不是普通发布、执行或诊断的必经步骤。
少量业务文字的 Dataset 草稿、结构化外部结果导入和显式评分见[数据与评分参考](data-and-scoring.md)。

## 准备数据、导入 Evidence 与项目协作

先检查已安装 CLI 的命令帮助，旧版二进制可能缺少以下能力。创建导入、上传文件、
发布版本、提交／中止 Evidence 或添加成员前，必须确认 Project 和目标写入范围。
已有明确授权可以覆盖有界工作流，无需对范围内每一步重复询问。这些操作均不代表
用户已授权启动 Run 或执行评分。

```bash
agent-eval datasets adapters list --format json
agent-eval datasets adapters get <adapter-key> --format json
agent-eval datasets imports create --project-id <project_id> --input <request.json> --file <dataset.tar.zst> --format json
agent-eval datasets imports upload --project-id <project_id> --input <reservation.json> --file <dataset.tar.zst> --format json
agent-eval datasets imports complete-upload <import-id> --project-id <project_id> --upload-id <upload-id> --wait --format json
agent-eval datasets draft update <dataset-id> --project-id <project_id> --input <request.json> --file <dataset.tar.zst> --format json
agent-eval datasets versions create <dataset-id> --project-id <project_id> --input <request.json> --format json
agent-eval models spec --input <model-spec.json> --format json
agent-eval models list --agent-type <agent_type> --format json
agent-eval models validate --input <model-spec.json> --format json
agent-eval projects member add --project-id <project_id> --user-id <platform-user-id> --format json
```

本节 Dataset 上传路径要求准备好规范归档包；少量文本可走 `datasets draft create/edit`，不必先打包。
CLI 不负责打包题目、安装 Harbor 或推导
题目内容摘要。用户希望复用时，优先选择其有权访问的精确 DatasetVersion。
归档包的 SHA-256 和大小由 CLI 计算；Draft 的 `content_digest` 和 `task_count`
必须来自真实包元数据。返回的上传计划应保持私密。URL 过期后，只有原请求仍获授权且输入、文件和幂等键均可精确恢复时，
才能原样重放 create/update；否则先停止并说明结果未确认。PUT 结果不确定时，先执行 imports get；
complete-upload 会校验文件内容。PUT 返回 409/412 不能证明成功，应保留回执并使用
相同 ID 执行 complete-upload 验证。Draft update 使用相同的上传／完成流程，
且绝不自动发布；创建版本时必须绑定精确的 Draft revision/digest，并在已有版本派生时
绑定已确认的基础版本；手工新建且从未发布的草稿首次发布使用 `base_dataset_version_id: null`。

```bash
agent-eval evidence uploads create --project-id <project_id> --input <request.json> --format json
agent-eval evidence uploads files add <upload-id> --project-id <project_id> --evidence-class c2 --file <trajectory.json> --format json
agent-eval evidence uploads preview <upload-id> --project-id <project_id> --format json
agent-eval evidence uploads get <upload-id> --project-id <project_id> --format json
agent-eval evidence uploads commit <upload-id> --project-id <project_id> \
  --expected-upload-content-digest <preview_upload_content_digest> --format json
```

导入外部 Evidence 需要 `client_token`，以及数据集题目或任务描述。应根据真实材料
选择 c1-c4，不能猜测系统角色；对外不开放 c5 和内部 Run/Trial 血缘。Preview
是只读操作；材料不足不等于 API 失败。`unclassified` 表示已存储但未匹配模板。
首次 commit 及原请求重放都必须绑定已确认 preview 返回的 `upload_content_digest`，
格式为 `sha256:` 加 64 位小写十六进制；不能使用单文件摘要或归档后的 manifest digest。
服务提示 `UPLOAD_CONTENT_CHANGED` 时，重新 preview 并核对变更，不自动替换摘要后提交。
如果任一文件被拒绝或响应丢失，应先查询 Session 再重试，因为部分文件可能已经存在。
不得为了恢复而自动 commit、abort 或删除文件。`archived`／`duplicate` 回执和
`regrade_ready` 都不能证明 Assessment 已存在。

详细请求样例和恢复说明通过 `agent-eval examples asset-imports.md` 获取。
添加成员时，让待加入成员使用自己的已鉴权身份查询：

```bash
agent-eval whoami --format json
```

将返回的平台 `user_id` 提供给项目管理员，再由管理员执行 `projects member add`。
不能把管理员自己的 ID、邮箱或 TOP `account_id`／`user_id` 当作待加入成员 ID；成员命令不接受
`--account-id`。身份查询不是每次评测的额外前置步骤。
`models list/spec/validate` 只查询或校验配置，不执行模型，也不需要 Ark Key；
所选模型及 Owner 返回的参数 Schema 是权威事实。

## 预缓存世界是否已构建并可运行

Environment 策略 `resolution_mode=benchmark_precache` 下，每道题目运行在自己的
"世界"（world）里：服务从自己的对象存储直接提供的一个 OCI 镜像。用户在选择数据集、
诊断 `WORLD_INCOMPLETE`／`PRECACHE_ITEM_UNRESOLVED`／`WORLD_RECORD_MISSING`，
或询问"这个世界构建好了吗、能跑吗"时，使用以下只读命令，不要凭镜像列表或他人口述推断。

```bash
agent-eval worlds check --dataset <dataset@version> --item <task_name> --format json
agent-eval worlds list  --dataset <dataset@version> --verify 10 [--limit 50] --format json
```

`check` 回答一道题，并对该题镜像的每个 blob 在**本部署自己的 bucket** 中逐个 HEAD（约 3–4 秒）。
`list` 汇总运行时会读取的那份 manifest 中的每道题：仅凭 manifest 就能判定 `base_only` 与
`unbound`；是否真的在库需要逐镜像 HEAD，因此只校验前 `--verify` 个不同镜像（≤50，
约每镜像 0.5 秒），其余命名了世界但未校验的题目记为 `bound`。数据集整体只有在**全部**
不同镜像都校验通过时才是 `ready`。二者都在服务端按 Run 使用的同一套规则作答：选取运行时
会选取的 manifest；`built` 类题目必须带 `world: built`（Dockerfile 的产物，而不是 FROM
基础镜像）。答案携带 `checked_bucket`、`checked_prefix`、`service_revision` 和
`checked_at`，表明是哪一个部署在哪一刻作答。命令不会构建、复制、签名或启动任何东西。

退出码：`0` ready；`1` 未能确立就绪（明确阻塞，或数据集仅为 `bound`）；`3` `state=unknown`
（存储读取失败，既非存在也非缺失）。即使非零退出，JSON 仍会打印，应读取其中的 `state`
与 `reason` 而不是只看退出码。准备跑少量题目时，对每道题各执行一次 `check`。

按 `state` 解读与升级：

| state | 含义 | 下一步 |
|---|---|---|
| `ready` | 运行时会解析到这个世界，且它的每个 blob 都在本存储中 | 无。这不证明 Provider 能启动或评测会成功 |
| `bound`（仅 `list`） | 题目命名了一个世界，但本次未校验它的 blob 是否在库 | 提高 `--verify`，或对将要运行的题目逐个 `check` |
| `base_only` | 存储里只有该题的 FROM 基础镜像，Dockerfile 从未执行；运行时会以 `WORLD_INCOMPLETE` 拒绝 | 请预缓存负责人离线构建该题世界并重写 manifest；`manifest_digest` 是已缓存的基础镜像 |
| `missing_blobs` / `missing_image_record` | manifest 声称的镜像在本 bucket 中不完整；通常是从另一个 bucket 复制 manifest 时没有带上 blob | 请负责人把该镜像的完整闭包复制到本部署的存储；`blobs.missing[].key` 列出缺失对象 |
| `blob_mismatch` | 对象存在但大小与镜像记录不符 | 请负责人用校验过的字节修复该对象 |
| `unbound` | manifest 列出该题但没有镜像摘要：扫描时什么也没缓存到 | 请负责人缓存／构建后重写 manifest；`note` 可能给出原因 |
| `not_in_manifest` | 运行时会读取的那份 manifest 不含该题（另一份 manifest 含有也不算） | 核对题目名；请负责人发布覆盖该题的 manifest |
| `dataset_unknown` | 本存储没有该数据集的任何 manifest | 核对 `dataset@version` 拼写，或该数据集尚未预缓存到本部署 |
| `invalid_record` | 镜像记录没有层或描述符缺摘要 | 生产方修复记录；不要盲目触发构建 |
| `unknown` | 存储不可读（403、超时等） | 有限次重试；持续失败则报告部署运维，**不要**称之为"缺失" |

`list` 的 `state` 取值为 `ready`／`bound`／`mixed`／`empty`／`dataset_unknown`／`unknown`；
`verified_images` 与 `distinct_images` 说明校验覆盖了多少镜像，`counts` 始终完整，
`items` 每个状态最多列出 `--limit` 个题目键。

不得得出的结论：

- "镜像已缓存" 不等于 "世界已就绪"：`built` 题目缓存的往往只是基础镜像。
- 在一个部署（bucket）中 ready，不等于在另一个部署中 ready；必须对目标部署再查一次。
- 手工找到一份包含该题的 manifest，不等于运行时会读取它；以 `manifest_key` 为准。
- Plan 已编译、Snapshot 已发布，不证明世界就绪；`ready` 也不证明 Provider 资源、
  沙箱镜像或评分链路可用。
- 离线预缓存工具的退出码 0 不是本部署的就绪证明。

升级时提供 JSON 中的安全事实：`checked_bucket`、`service_revision`、`dataset`／`item_key`、
`state`／`reason`、`manifest_key`、`manifest_digest`、`blobs.missing` 与 `checked_at`。
不要粘贴签名 URL 或凭据（这些命令也不会返回它们）。

## Environment 与 Provider

Environment 模块负责创建、校验和发布 Environment 版本，并暴露负责物化它们的
Provider。选择 Provider 前先读取对应 Provider 记录：`--provider` 在创建时绑定，
之后不可修改。

```bash
agent-eval provider list --format json
agent-eval provider get vefaas --format json
```

在 Provider 键下使用供应商定义的原始字段名；Provider 配置没有简写参数：

```bash
agent-eval environment create --project-id <project_id> --name <name> --type container_workspace \
  --provider vefaas --from image:<registry>/<image>@sha256:<digest> \
  --set vefaas.CreateFunction.CpuMilli=4000 --set vefaas.CreateFunction.MemoryMB=8192 \
  --set vefaas.CreateSandbox.Timeout=60 --format json
agent-eval environment validate <name> --project-id <project_id> --format json   # 会创建探测实例，不是只读操作
agent-eval environment get <name> --project-id <project_id> --format json
agent-eval environment publish <name> --project-id <project_id> --revision <head_revision> --message "<note>" --format json
```

需要遵循以下规则：

- `validate` 会在探测实例上依次执行 Setup、Healthcheck、Reset、Collect 和 Cleanup；
  只执行 `--phases` 子集的结果不能用于发布。
- 没有最新、完整且可解析的报告时，`publish` 会拒绝执行，且没有强制发布参数。
  使用 `environment get` 返回的 `publish_blockers` 查看原因。
- 对已发布版本执行 `update` 会派生新的 Draft。`update` 和 `publish` 前读取
  `environment get` 返回的 `environment.revision`，显式传入 `--revision` 作为并发校验值。
  同一请求重放保持 revision、请求内容和幂等键不变；发生版本冲突时重新读取并核对差异，
  不得自动换成最新 revision 覆盖他人修改。
- `update` 的数组必须通过 `--file` 或 `--set 'path=[...]'` 整体替换，并保留仍需使用的旧元素；
  不支持 `[]`／`[n]` 局部路径。`create` 仍可使用数组追加和索引。
  `--file` 与 `--from` 同用时，后者替换完整的 `base_source`，不会继承旧来源的 digest；
  显式 `--set*` 最后生效。
- Environment spec 与 instance env 中严禁写入任何凭据（明文或引用都不行）；
  `secretref://` 已移除，含该写法的 spec 会以 `SECRET_REF_UNSUPPORTED` 被拒绝。

执行 Project 范围的 Environment 操作时，list/get/create/update/validate/publish
及后续 Operation 查询必须使用同一个已确认的 Project ID。可以显式传
`--project-id`，或在开发者本地 Shell 中通过 `projects use` 保存当前 Profile 默认值；
不得自动选择任意 Project。Get 回读和校验轮询也必须携带该 Project。

使用 `agent-eval operation get <id> --project-id <project_id> --wait --timeout 15m` 轮询异步操作。
Operation 完成与校验通过分别判断。Provider Validate 不是普通评测的前置步骤；若创建与读取的
作用域／鉴权不一致，应记录 Operation ID、稳定错误码和 Request ID 并交由服务负责人处理，
不得切换 Project、补猜测凭据或绕过 CLI 来掩盖服务问题。

## 定时评测（Schedule）

用户明确需要定时执行时才进入；只运行一次或只发布方案不自动创建 Schedule。
先检查 `schedules --help`，已安装 CLI 或目标服务不支持时说明对应缺口，
不自行用后台循环、cron 或宿主自动化模拟平台调度。

### 创建与授权

```bash
agent-eval examples schedule-create.json
agent-eval schedules list --project-id <project_id> --format json
agent-eval schedules create --input <schedule.json> --idempotency-key <request_key> --format json
agent-eval schedules get <schedule_id> --format json
agent-eval schedules history <schedule_id> --format json
```

创建前回读精确 Plan / Comparison Snapshot，核对 Project、摘要、就绪状态和单次执行规模。
当前 Schedule 只接收服务支持的 VeFaaS 主动评测运行时；Comparison 的每个成员都必须满足准入。
MA 尚无无人值守凭据合同，服务返回 `SCHEDULE_MA_CREDENTIALS_UNAVAILABLE`；其他运行时返回
`SCHEDULE_RUNTIME_UNSUPPORTED`，非主动评测返回 `SCHEDULE_ACTIVE_EVALUATION_ONLY`。
手动 MA 评测仍按主指南使用调用方 Ark 身份，不因定时能力受限而更换 Target。
不能把 `ARK_API_KEY` 写入 Schedule／Snapshot，也不能用平台凭据或后台循环绕过准入。
未来指定时刻只执行一次用 `once`；按天／周重复用 `daily`／`weekly`，不接受 cron 表达式或任意间隔。
用户授权须覆盖对应的单次或周期执行、时区及资源／费用范围；一次 Run 的授权不能推定为持续授权。
创建成功即为 `enabled`，不是仅保存草稿。周期规则没有次数／预算上限或结束日期字段；
用户要求这些硬限制而服务不能表达时先说明，不承诺届时自动停止，也不创建无界计划替代。
按主指南展示单次执行预期，并说明周期会重复消耗资源；配置频率是计划，不保证每轮都实际执行，
跳过的轮次不会自动积压补跑。不能以高频 Schedule 绕过容量限制，也不承诺周期费用硬上限。
时刻表示计划触发，不是完成或收到报告的时间；当前空闲不能保证未来资源可用，也不靠遍历现有 Run／Schedule
预测未来空闲。结合用户要求一次说明关键影响，不逐轮索要风险确认：上一轮执行或资源释放未结束时，
同一 Schedule 的后续轮次可能跳过；延长单轮预算可能增加跳过机会。多个 Schedule 仍可能争用同一连接／项目容量，
同一 Schedule 的跳过保护不是跨 Schedule 的全局串行。只有频率／完成要求确实冲突时才建议调整，不能暗改。
“每天 9 点收到完整报告”包含完成时间和通知两个要求，不能直接换成 9 点触发；
无法保证硬期限或没有已验证的通知能力时说明缺口，按用户意图确认替代方案，不承诺自动送达。
执行身份由服务绑定创建者 `execution_user_id`，修改或恢复不会改成操作者身份；每次触发重新校验
该用户及 Project 的执行权限，不依赖创建时的权限快照，也不把凭据放入请求。

| 输入 | 说明 |
|---|---|
| `project_id` | 创建请求中的正整数，样例的 0 必须替换；不是 `create` 的独立 flag |
| `snapshot_type`、`snapshot_id`、`snapshot_digest` | `plan` 或 `comparison` 与精确发布身份，不能使用 Draft 或 latest |
| `timezone` | 用户确认的 IANA 时区；示例 `Asia/Shanghai` 不是替用户选择的默认时区 |
| `time_rule` | `once`：`kind=once` 加带时区偏移、精确到分钟的未来 `at`；`daily`：`kind=daily` 加 HH:mm 的 `local_time`；`weekly`：`kind=weekly`、`local_time` 加不重复的 `weekdays`，周一 0 到周日 6。各类不混填其他时间字段 |

创建后保存 `schedule_id`、`revision`、`status` 和 `next_trigger_at`；后者由服务以 UTC 返回，
转为已确认时区展示首个触发时刻，不仅复述用户输入。`once.at` 的偏移决定实际时刻，不把无偏移时间当作本地时间；
使用夏令时地区时，daily/weekly 的不存在时刻会跳过，重复时刻只选第一次，不承诺每个自然日都触发。
同时返回 `schedules get/history` 查询入口；启用成功、实际触发、评测完成和报告送达分别说明，
不为等待首轮完成而延迟交接，也不隐含持续监控或自动补跑。

定时执行始终复用绑定的 Snapshot，不提供“自动更新代码／数据并发布最新 Draft”的工作流；
更换配置需按主流程发布新 Snapshot，再显式更新 Schedule。远程 MCP 或可变 Git 引用等外部依赖不会
因此被锁定，可复现性边界见[方案配置参考](configuration.md)。

### 修改、停用与恢复

```bash
agent-eval schedules update <schedule_id> --input <updated-schedule.json> --idempotency-key <update_key> --format json
agent-eval schedules pause <schedule_id> --revision <current_revision> --idempotency-key <pause_key> --format json
agent-eval schedules resume <schedule_id> --revision <current_revision> --idempotency-key <resume_key> --format json
```

更新前 get 回读，输入保留完整的 `name`、Snapshot 绑定、`timezone`、`time_rule` 并携带当前 `revision`；
不要将 get 的 `status`、`project_id`、时间戳等只读字段原样塞进 update。暂停／恢复也绑定当前 revision，
同一请求重放保持输入、revision 和幂等键不变；冲突时先核对变化，不盲重试。
update 保留 enabled／paused／blocked；finished 更新后变为 paused，不等于重新启用。
更换时间或 Snapshot 不改变已经冻结的触发记录；若用户要求停止旧配置尚未创建的执行，先按授权 pause，
核对 history 后再 update。pause 阻止后续触发及尚未创建的执行，不取消已经创建的 Run；
取消某轮 Run 也不会停用 Schedule。停用定时计划使用 pause，不猜测 delete/cancel 命令。
需连同当前轮次停止时，从 history 取精确执行 ID，再按主指南取消；reconciling 仍表示创建结果待核对。
恢复须仍在对应授权内，并使用 get 回读的最新 revision；恢复只安排未来时间，不补跑暂停期间的轮次。
已过时的 once 需要先获授权更新到未来时间，再显式 resume。变更后 get 核对状态和下次触发时刻。

### 查询与未按预期触发

list / history 按 `next_cursor` 续传 `--cursor`，以返回的 `has_more` 核对完整性。
Schedule 的 `finished` 仅表示没有下次触发，不表示评测完成；history 的 `created` 仅表示已经创建 Run／Comparison。
通过该条历史的 `run_id` / `comparison_start_id` 进入主指南查询状态与报告，不用当前 Schedule 绑定解释旧轮次。
`pending`／`processing`／`reconciling` 不是失败证明；先有界查询，不另起一轮来消除不确定性。

| 现象／原因码 | 解释与处理 |
|---|---|
| `skipped / MISSED_WINDOW` | 当前服务错过超过 5 分钟的触发窗口会跳过，不回放积压；不能承诺故障恢复后补齐 |
| `skipped / PREVIOUS_EXECUTION_ACTIVE` | 同一 Schedule 的上一轮未结束或创建结果未确定，本轮跳过；不是排队等待上一轮完成 |
| `skipped / PREVIOUS_RESOURCE_RELEASE_PENDING` | 上一轮虽已终态但仍有资源占用，本轮跳过；报告可读不等于资源已释放，不另建 Schedule 绕过 |
| `blocked / EXECUTION_PERMISSION_DENIED` | 核对绑定创建者和 Project 的当前权限；修复权限后仍需显式授权 resume，不能换凭据冒认执行人 |
| 其他 `blocked`／`failed`，或已到时却无 history | 保留 `schedule_id`、触发时间、revision、`blocked_reason`／`reason_code` 和 Request ID，交由服务负责人核对；命令可用、创建成功均不能证明调度 Worker 已正常运行 |

上述为当前调度规则；以目标服务实际响应为准，未经真实触发验证不声称 BOE 调度已通过。
需要补跑必须重新确认精确 Snapshot 和执行范围，不自行 resume、重建 Schedule 或发起 Run。
