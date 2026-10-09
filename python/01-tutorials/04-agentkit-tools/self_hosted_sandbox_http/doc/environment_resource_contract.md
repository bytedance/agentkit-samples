# EnvironmentResource 示例接口核对记录

本文汇总 **2026-10-09 本次验证记录**：MR 契约核对、离线测试、真实只读请求、本机 01～05 完整生命周期、配置读回和清理检查。记录来自本次执行输出及保存的日志/快照；整理本文时没有重新提交云端操作。

本机通过真实 Volcengine TOP + Ark 跑通创建、查询、列表、元数据更新、Sandbox 规格更新和删除，共 11 次脚本执行，退出码均为 0。最终测试资源为 `deleted/completed`，两代共四个组件记录均为 `deleted`，活动列表为空。

## 1. 验证环境与契约依据

| 项目 | 本次使用值 |
| --- | --- |
| 日期 / 时区 | 2026-10-09 / Asia/Shanghai |
| 本地系统 | macOS，zsh |
| 示例目录 | `/Users/bytedance/work/wm_project/ak-s/volcengine-agentkit-samples/python/01-tutorials/04-agentkit-tools/self_hosted_sandbox_http` |
| Python | 3.13.7，`/tmp/self-hosted-sandbox-http-venv/bin/python` |
| 依赖 | requests 2.34.2；目录要求 `requests>=2.31,<3` |
| 静态检查 | Ruff 0.11.12，`/tmp/self-hosted-sandbox-http-venv/bin/ruff` |
| 资源 API | `POST https://open.volcengineapi.com/?Action=<Action>&Version=2025-10-30` |
| 签名配置 | Volcengine AK/SK，region=`cn-beijing`，service=`agentkit` |
| IAM API | `GET https://open.volcengineapi.com/?Action=<IAMAction>&Version=2018-01-01`，签名 service=`iam` |
| 目标类型 / 模式 | `ark` / `runtime_and_sandbox` |
| Sandbox profile | `ark_skills` |
| 目标 Environment | `$AGENTKIT_ENVIRONMENT_ID` |
| Environment Base URL | `https://ark.cn-beijing.volces.com/api/v3` |
| Sandbox 镜像 | `enterprise-public-cn-beijing.cr.volces.com/vefaas-public/agentkit-selfhostsandbox:tool-ark-skills-0.0.2` |
| Runtime 镜像 | `enterprise-public-cn-beijing.cr.volces.com/vefaas-public/agentkit-selfhostsandbox:runtime-ark-skills-0.0.2` |

验证使用上述独立虚拟环境。真实调用前在当前 shell 加载本目录 `.env`，仅核对配置是否存在，没有打印 AK/SK 或 Environment Key。脚本本身不自动读取 `.env`：

```bash
set -a
source .env
set +a
```

## 2. 离线测试与静态检查

在示例目录使用以下命令执行：

```bash
/tmp/self-hosted-sandbox-http-venv/bin/python -m unittest discover -s tests -v
/tmp/self-hosted-sandbox-http-venv/bin/ruff check .
/tmp/self-hosted-sandbox-http-venv/bin/ruff format --check .
git diff --check
```

测试使用本机模拟 HTTP 服务及测试凭据，不访问真实云资源。HTTP 方法、路径、请求体、签名头/摘要和响应处理的检查不等同于云端鉴权与供应验证。

| 检查项 | 结果 | 耗时 | 保存的日志 |
| --- | --- | --- | --- |
| 离线测试 | 35 tests，OK | 33.401 秒 | `/tmp/self-hosted-list-after.log` |
| Ruff check / format --check | 通过 | 未单独记录 | 本次执行输出 |
| git diff --check | 通过 | 未单独记录 | 本次执行输出；文档整理后再次检查 |

最终 35 项测试均位于 `tests/test_examples.py` 的 `ProtocolTests`，覆盖如下。表中“通过”指测试断言通过，包括预期失败时返回非零退出码的场景。

| 测试名 | 核对内容 | 结果 |
| --- | --- | --- |
| `test_direct_lifecycle_and_explicit_revision_replay` | 五接口生命周期、直连认证头、Ark 请求、显式旧 revision 原样重放、null/空对象清空、缓存脱敏 | 通过 |
| `test_top_envelope_signing_and_byteplus_configuration` | TOP 包装、Volcengine/BytePlus 入口和签名配置 | 通过 |
| `test_top_accepts_plain_resource_and_list_responses` | TOP 直接透传资源对象和 data 列表 | 通过 |
| `test_top_pascal_list_and_mixed_response_pagination` | PascalCase 列表、混合格式分页、空列表、自定义字典原样保留、List 不写状态 | 通过 |
| `test_pascal_resource_responses_support_lifecycle_and_state` | PascalCase Create/Get/Update/Delete 终态及状态文件 | 通过 |
| `test_pascal_rolled_back_operation_is_still_a_failure` | PascalCase FailedClean 不能被 ready 掩盖 | 通过 |
| `test_malformed_pascal_list_is_not_treated_as_empty_success` | 异常列表/ID/游标拒绝，保留诊断字段 | 通过 |
| `test_malformed_success_responses_do_not_update_state` | 非法 HTTP 成功响应不得污染缓存 | 通过 |
| `test_all_dry_runs_without_credentials_or_state_writes` | 五脚本 dry-run、默认镜像、自动 token、不发请求或写状态 | 通过 |
| `test_agentkit_mode_omits_ark_fields` | AgentKit 模式不发送 Ark runtime/key 字段 | 通过 |
| `test_list_filters_pagination_and_empty_body` | 筛选、游标续页、无参数空请求体 | 通过 |
| `test_repeated_cursor_fails` | 重复 next_page 终止并报错 | 通过 |
| `test_rolled_back_ready_is_not_success` | ready + failed_clean 回滚状态正确失败 | 通过 |
| `test_generation_mismatch_times_out_without_success` | 期望/观察代次不一致时超时，不误报完成 | 通过 |
| `test_metadata_completion_does_not_require_a_new_generation` | metadata 操作完成不要求新代次 | 通过 |
| `test_operation_change_is_not_our_success` | operation_id 被其他操作替换时不误报成功 | 通过 |
| `test_errors_and_automatic_retry_keep_the_same_body` | 503 原请求体重试、RevisionConflict 和 API Error 处理 | 通过 |
| `test_invalid_cli_inputs_do_not_send_requests` | 非法 token、limit、空更新、非字符串 env_vars 在请求前失败 | 通过 |
| `test_state_cannot_silently_cross_endpoints` | 状态文件不能跨入口复用 | 通过 |
| `test_mutations_use_cached_id_and_latest_revision` | Update/Delete 从缓存读取同一资源 ID 和最新 revision | 通过 |
| `test_human_submission_does_not_claim_async_success` | 摘要区分已受理/成功，输出 token、进度及继续等待提示 | 通过 |
| `test_mutations_reject_missing_invalid_or_mismatched_state` | 缓存缺失、版本非法、ID 不一致时提前失败 | 通过 |
| `test_explicit_mutation_parameters_override_cached_values` | 显式 ID/revision 参数覆盖缓存 | 通过 |
| `test_explicit_runtime_role_is_only_validated_and_replayed` | 显式角色只 GetRole，IAM GET 签名/STS/摘要，创建重放保持角色和请求体 | 通过 |
| `test_runtime_role_reuse_follows_role_and_policy_pages` | 按角色及策略 Total 分页并选择可复用角色 | 通过 |
| `test_policy_response_without_total_is_not_paged` | 策略缺省/null Total 时不继续查询重复页 | 通过 |
| `test_role_response_without_total_is_not_paged` | 角色列表缺少 Total 时不继续分页 | 通过 |
| `test_auto_runtime_role_creation_and_trust_policy` | 角色命名、普通/stg 信任策略及默认 System 策略绑定 | 通过 |
| `test_iam_failures_stop_before_resource_creation` | 角色缺失、权限拒绝、角色不匹配时不提交资源创建 | 通过 |
| `test_malformed_or_repeated_iam_pages_fail_closed` | 异常 IAM 页及显式 Total 下的重复页中止 | 通过 |
| `test_attach_conflict_requires_confirmed_policy` | Attach 冲突只有在重新查询确认绑定后才接受 | 通过 |
| `test_other_transports_pass_role_without_calling_volcengine_iam` | BytePlus/直连透传角色，不访问 Volcengine IAM | 通过 |
| `test_role_dry_run_and_agentkit_mode_never_call_iam` | dry-run 不访问 IAM，AgentKit 模式拒绝角色参数 | 通过 |
| `test_http_errors_include_status_business_code_and_request_id` | HTTP status、reason、bizCode、RequestId 来源优先级及脱敏 | 通过 |
| `test_failed_mutations_exit_nonzero_without_wait` | Create/Update/Delete 未传 wait 时也保存失败状态并非零退出 | 通过 |

## 3. 完整生命周期之前的真实只读核对

### 3.1 TOP 响应结构

同一真实 Volcengine TOP 入口的只读请求观察到以下响应形式。

| Action / 请求体 | 实际响应形式 | 解析结果 |
| --- | --- | --- |
| List / `{}` | `ResponseMetadata` + `Result.EnvironmentResources[]`；资源字段及枚举为 PascalCase | 可列出 ready 资源并正确显示状态 |
| List / `{"environment_id":"env-20260924080657-r58tb"}` | 顶层 `data`、`next_page`、`RequestId` | 可解析 |
| Get / `{"resource_id":"er_db46oikh1ves72u09jjg"}` | 顶层 snake_case 资源对象 | 可解析，满足 ready 完成判定 |
| Get / `{"ResourceId":"er_db46oikh1ves72u09jjg"}` | Result 包装的 PascalCase 资源对象 | 归一化后满足同一 ready 完成判定 |

这里核对的是用户已有资源 `er_db46oikh1ves72u09jjg`，最初为 ready、revision=1；它不是后续完整生命周期中新建的测试资源。该阶段未提交 Create/Update/Delete 或 IAM 写操作。

### 3.2 既有资源与分页检查

以下三条实际脚本命令使用独立缓存 `/tmp/self-hosted-sandbox-live-20261009/existing-resource.json`，均退出 0：

```bash
python 02_get_environment_resource.py \
  --resource-id er_db46oikh1ves72u09jjg --wait deleted
python 03_list_environment_resources.py
python 03_list_environment_resources.py \
  --environment-id "$AGENTKIT_ENVIRONMENT_ID" \
  --include-deleted --limit 1 --all
```

此时用户已有资源已被用户删除；Get 读到 `deleted/completed`、revision=3。无参数 List 返回 0 条活动资源；分页查询返回四页，每页一条，均为 deleted：

| 资源 ID | revision | 状态 |
| --- | --- | --- |
| `er_db46oikh1ves72u09jjg` | 3 | deleted |
| `er_db3foou3j93c711iblag` | 2 | deleted |
| `er_daqdrc7pifjc72o6eqrg` | 2 | deleted |
| `er_daqdkqgo8ijs72phmpe0` | 2 | deleted |

保存的日志为该临时目录内的 `02-existing.log`、`03-default.log`、`03-filtered.log`。该阶段仅查询已有资源，没有更新或删除这些历史资源。

## 4. 本机真实执行 01～05

### 4.1 本轮资源、状态与操作标识

本轮日志目录：

```text
/var/folders/47/6n4ywn557tbfqwk__rlk9mt00000gn/T/self-hosted-sandbox-live-20261009-q1vlk0bm
```

下文以 `RUN_DIR` 指代该目录。执行包装器 `run_step.py` 使用 `/tmp/self-hosted-sandbox-http-venv/bin/python` 启动实际示例脚本、保存合并输出和退出码，并做了以下环境设置：删除继承的 `AGENTKIT_RESOURCE_ID`，设置 `AGENTKIT_RESOURCE_STATE=$RUN_DIR/resource.json`、`PYTHONUNBUFFERED=1`。所有 Update/Delete 都使用本轮缓存，未使用用户默认状态文件。

| 项目 | 记录 |
| --- | --- |
| 资源 ID | `er_db474osh1ves72u09r1g` |
| 创建名称 | `sandbox-http-e2e-1009124935` |
| 创建描述 | `Temporary resource for local 01-05 lifecycle verification` |
| 更新名称 | `sandbox-http-e2e-updated` |
| 更新描述 | `Updated during local 01-05 lifecycle verification` |
| IAM 角色 | 自动复用 `AgentKit_Runtime_Default_ServiceRole_k3e1t95` |
| 自定义环境变量更新 | `SAMPLE_LIFECYCLE_TEST=local-01-to-05`，这是本轮专用测试值 |
| 初始 Skill Space / 自定义 env_vars | 未配置 |
| API 记录的创建时间 | 2026-10-09 12:49:39.621205 +08:00 |
| API 记录的删除时间 | 2026-10-09 12:52:37.475869 +08:00 |

创建没有显式传 `--role-name`，验证了自动查询与复用分支；没有新建角色、绑定策略或修改已有角色。两个镜像参数也未在此次命令行显式传入，实际请求与 spec 读回均使用第 1 节列出的默认 `0.0.2` 镜像。

以下 client_token 是请求去重标识，不是鉴权凭据。表格保存本次历史操作的对应关系；再次独立验证应使用新的资源名称、状态文件和 token，不能将历史记录当作新操作参数复用。

| 操作 | client_token | operation_id |
| --- | --- | --- |
| Create | `734177f64b3d4834b77eed12ba327330` | `op_db474osh1ves72u09r20` |
| Update 元数据 | `0c09a43d67264fc3a99fc2e93757ab1a` | `op_db475cefhjfs72to5r30` |
| Update 规格 | `c7015a7f67bf4dcc8c7a0eeca89cc9b8` | `op_db475fmfhjfs72to5r70` |
| Delete | `5c75e84bf61e44ccb0bda53a6345c2b2` | `op_db4761ogb69s72oejlp0` |

### 4.2 实际命令与全部执行结果

下面是去掉日志包装器后的等效脚本命令。表中 `CREATE_TOKEN`、`METADATA_TOKEN`、`SPEC_TOKEN`、`DELETE_TOKEN` 分别对应上一表的 token；`AGENTKIT_ENVIRONMENT_ID` 来自已加载的 `.env`。序号按业务执行顺序排列，创建中的 List 在 01 等待期间单独执行，因此其完成记录早于 01。

| 序号 | 实际脚本及参数（命令均以 `python` 启动） | 结果 | 退出码 | 耗时 / 秒 | 日志文件 |
| --- | --- | --- | --- | --- | --- |
| 1 | `01_create_environment_resource.py --target-type ark --name sandbox-http-e2e-1009124935 --description 'Temporary resource for local 01-05 lifecycle verification' --client-token "$CREATE_TOKEN" --wait` | creating → ready/completed；revision=1 | 0 | 63.09 | `01-create.log` |
| 2 | `03_list_environment_resources.py`，在创建期间执行 | 1 条 creating 资源，ID 为本轮资源 | 0 | 0.44 | `03-creating.log` |
| 3 | `02_get_environment_resource.py --wait ready` | ready/completed；revision=1 | 0 | 0.51 | `02-ready.log` |
| 4 | `03_list_environment_resources.py` | 1 条 ready 资源 | 0 | 0.42 | `03-default.log` |
| 5 | `03_list_environment_resources.py --environment-id "$AGENTKIT_ENVIRONMENT_ID" --include-deleted --limit 1 --all` | 5 页，每页 1 条；本轮 ready + 历史 deleted 4 条 | 0 | 1.89 | `03-paginated.log` |
| 6 | `04_update_environment_resource.py --name sandbox-http-e2e-updated --description 'Updated during local 01-05 lifecycle verification' --client-token "$METADATA_TOKEN" --wait` | metadata 同步完成；revision=2 | 0 | 0.44 | `04-metadata.log` |
| 7 | `04_update_environment_resource.py --sandbox-env-vars '{"SAMPLE_LIFECYCLE_TEST":"local-01-to-05"}' --client-token "$SPEC_TOKEN" --wait` | updating → ready/completed；revision=3、代次=2 | 0 | 64.72 | `04-spec.log` |
| 8 | `05_delete_environment_resource.py --client-token "$DELETE_TOKEN" --wait` | deleting → deleted/completed；revision=4 | 0 | 16.50 | `05-delete.log` |
| 9 | `02_get_environment_resource.py --wait deleted` | deleted/completed；revision=4 | 0 | 0.42 | `02-deleted.log` |
| 10 | `03_list_environment_resources.py` | 0 条活动资源 | 0 | 0.45 | `03-after-delete.log` |
| 11 | `03_list_environment_resources.py --environment-id "$AGENTKIT_ENVIRONMENT_ID" --status deleted --include-deleted --limit 1 --all` | 5 页，每页 1 条，全部 deleted | 0 | 1.84 | `03-tombstones.log` |

耗时由包装器在启动每个脚本前后使用单调时钟记录，包含本地启动、HTTP 请求和轮询等待；不是后端各组件的纯供应耗时。11 条执行结果保存在 `results.jsonl`。

### 4.3 状态、配置读回与操作完成判定

每个主要操作之后另用 `EnvironmentResourceHttpClient` 发送真实 Get/List，并对结果执行断言；这些辅助读取不计入上表的 11 次脚本执行。检查通过后保存脱敏快照。

| 检查点 | status | revision | desired / observed generation | last_operation.status / step | 读回与断言 |
| --- | --- | --- | --- | --- | --- |
| 创建完成 | ready | 1 | 1 / 1 | completed / provision | 名称与描述符合创建输入，目标 Environment 正确，Tool/Runtime ID 非空；ready 筛选列表包含本轮资源 |
| 元数据更新完成 | ready | 2 | 1 / 1 | completed / metadata | 新名称/描述逐项相等，Tool/Runtime ID 保持不变 |
| 规格更新完成 | ready | 3 | 2 / 2 | completed / retire | `spec.sandbox.env_vars` 与测试输入相等，名称保留，新 Tool/Runtime ID 均不同于创建时，旧组件记录 deleted |
| 删除完成 | deleted | 4 | 2 / 2 | completed / delete | operation_completed(..., 'deleted') 成立，历史组件恰好 4 个且全部 deleted；目标环境活动列表为空、没有下一页 |

创建中间快照记录 `desired_generation=1`、`observed_generation=0`，Sandbox 已 ready 而 Runtime 仍 creating。规格更新中间快照记录 `desired_generation=2`、`observed_generation=1`，第 2 代正在创建、第 1 代仍 ready。脚本均继续等待，没有将中间状态或 HTTP 200 当作最终成功。

主要快照与 RequestId 如下；RequestId 对应操作后的 Get 读回请求，不是 Create/Update/Delete 提交请求的 ID：

| 快照 | 对应状态 | Get RequestId |
| --- | --- | --- |
| `created.json` | 创建完成 | `20261009125056677FD65CE306F1E99227` |
| `metadata-updated.json` | 元数据更新完成 | `2026100912511037CF674DD7EE1B1315E6` |
| `spec-updated.json` | 规格更新完成 | `202610091252223575C6E7446A2AB0C6E1` |
| `deleted.json` | 删除完成 | `2026100912525683CA6A49FE90929146F1` |

### 4.4 两代组件与清理结果

| 代次 | 组件 | ID | 规格更新完成后 | 最终删除后 |
| --- | --- | --- | --- | --- |
| 1 | Sandbox Tool | `t-yewuuhmry8ebbiac6miz` | deleted | deleted |
| 1 | Runtime | `r-yewuuij30gebbiacatkj` | deleted | deleted |
| 2 | Sandbox Tool | `t-yewuul6lmo7htd7g1jss` | ready | deleted |
| 2 | Runtime | `r-yewuum03k07htd7g4stp` | ready | deleted |

四条历史组件记录均为 `ownership=owned`、`error_code=null`。最终当前 Runtime/Sandbox 组件状态也均为 deleted。无参数 List 和目标 Environment 的活动列表均为空；包含 deleted 的查询仍能看到本轮资源及之前四条历史墓碑。

只删除了本轮资源 `er_db474osh1ves72u09r1g`；没有对第 3 节的历史资源提交更新或删除，没有提交删除目标 Environment 或 IAM 角色的请求。清理确认来自 EnvironmentResource Get/List 及其组件历史，未再独立调用下游 Tool/Runtime 查询接口。

## 5. 输出、凭据与文档检查

- 真实运行期间使用独立状态文件；最终保存 resource_id、revision=4、status=deleted、operation_id、代次和入口，不保存 Environment Key、AK/SK、请求体或自定义 env_vars。
- 保存的完整资源快照经过 `redact()`，环境变量值显示为 `<redacted>`；配置相等性在脱敏保存之前检查。上述专用测试值可公开记录，不包含业务密钥。
- 删除阶段检查了当时已保存的 16 个 `.json`、`.jsonl`、`.log` 文件：将运行环境中名称匹配 KEY/SECRET/TOKEN/PASSWORD 且长度至少为 8 的非空值与文件内容逐项比较，命中为 0。后续 Get/List 快照也走同一脱敏函数；该扫描仅证明这些配置值未原样出现，不是通用敏感信息审计。
- 中英文 README 已同步真实验证结果及 `.env` 的 shell 加载命令；核对 Markdown 代码块成对闭合、两种语言均包含加载命令及约 63/65/17 秒的结果摘要，`git diff --check` 通过。
- 本文整理后再次核对：35 个测试名与源码及最终成功日志完全对应，11 条脚本记录的退出码/耗时与 `results.jsonl` 一致，四份主要快照中的资源/操作/RequestId/组件标识和本轮 token 均已收录。Markdown 代码块闭合检查通过，对本文执行上述配置值扫描命中为 0。
- 本次整理仅补充本文，不重新运行云生命周期；没有因整理文档而新建或删除其他资源。

## 6. 证据文件索引与验证范围

本文已保存关键输入、全部脚本运行结果及状态证据，不依赖临时目录长期存在。原始日志可在本机以下位置进一步核对；系统清理临时目录后这些路径可能失效。

| 位置 | 文件 | 内容 |
| --- | --- | --- |
| `/tmp` | `self-hosted-list-after.log` | 第 2 节的 35 项离线测试通过记录 |
| `/tmp/self-hosted-sandbox-live-20261009` | `02-existing.log`、`03-default.log`、`03-filtered.log`、`existing-resource.json` | 完整运行前的既有资源墓碑、空列表和四页查询 |
| `RUN_DIR` | 第 4.2 节列出的 11 份日志 | 真实脚本 stdout/stderr |
| `RUN_DIR` | `run.json`、`run_step.py`、`results.jsonl` | 本轮名称/token、执行包装器、退出码和耗时 |
| `RUN_DIR` | `create-progress.json`、`update-progress.json` | 创建和规格更新的中间状态 |
| `RUN_DIR` | `created.json`、`metadata-updated.json`、`spec-updated.json`、`deleted.json` | 四个主要状态的脱敏 Get 快照 |
| `RUN_DIR` | `resource.json`、`report.md` | 最终独立缓存、运行摘要 |

本次线上成功覆盖 **当前账号、cn-beijing、Volcengine TOP、Ark 目标、上述镜像、已有 IAM 角色复用** 的资源管理生命周期。以下项目不能据此视为已经在线通过：

- IAM 新角色创建、策略绑定、冲突确认、显式角色和 stg 信任关系分支；它们有离线测试，真实运行只经过自动复用。
- BytePlus 发布可用性、AgentKit 目标、直连 HTTP 部署；仅离线检查相应客户端行为。
- Skill Space 挂载、实际 Session/Work 创建与执行、模型推理或工具调用。
- 云端异常恢复、进程重启后相同 token 恢复、网络故障、并发修改、失败回滚、ResourceInUse/drain；部分客户端保护有模拟测试，未在线制造这些故障。
- 修改 Sandbox 镜像、resources、networking 等全部规格字段的云端行为；本轮实际规格更新为一个自定义环境变量。
- 独立下游组件 API 查询、跨账号/跨区域兼容性和性能基准；组件清理按资源接口记录确认，耗时仅为本次观测值。
