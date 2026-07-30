# 常见问题与排障

## Skill

- **新任务找不到 `$agentkit-hybrid-cloud-demo`**：在 Demo 根目录运行
  `./scripts/install_codex_skill.sh`，然后新建任务。旧任务不会刷新 Skill 列表。
- **已安装版本与仓库不同**：查看 Skill diff 后执行
  `./scripts/install_codex_skill.sh --update`；脚本会保留备份。

## OpenAPI 与鉴权

- **正式 HTTPS 证书不受信任或域名不匹配**：修复 TLS Secret/Ingress；不能用
  `curl -k` 作为客户方案。
- **显示 `Kubernetes Ingress Controller Fake Certificate`**：Ingress 没有绑定
  匹配域名的正式证书。
- **`/ping` 成功但 `runtime list` 返回 `InvalidAccessKey`**：网络已通，AK/SK
  无效、过期或属于其他环境；从目标环境重新获取并轮换已暴露 Key。

## Docker、镜像与 Registry

- **CLI 的 `docker info` 正常但 AgentKit 报 Docker 不可用**：可能是 nerdctl
  包装；AgentKit 需要真实 Docker daemon/socket。
- **Apple Silicon 架构不匹配**：必须构建和发布 `linux/amd64`。
- **`meta.db`/`containerdmeta.db` I/O error**：先确认容器可中断，再重启或诊断
  Docker Desktop，不要直接删除数据。
- **Registry token expired / unauthorized**：正常情况下不预先登录；但 launch
  已明确出现 `token expired`、`invalid token claims`、`unauthorized` 或
  `authentication required` 时，应从目标镜像仓库重新获取临时 `docker login`
  指令，确认 `Login Succeeded` 后重跑。不要把令牌粘贴到 Prompt 或文档。
- **CreateRuntime `InvalidRegion`**：不要静默复用 CLI 全局 Region。运行
  `scripts/deploy_interactive.sh` 显式输入本次目标 Region，或在自动化环境设置
  `VOLCENGINE_REGION`。
- **CreateRuntime `InvalidParameter.DuplicateName`**：新目录没有已有 Runtime 的
  本地 ID 绑定，CLI 因而尝试重复创建。不要删除现有实例；重新运行
  `scripts/deploy_interactive.sh`，核对显示的同名 Runtime ID 后选择更新。成功后
  脚本会把非敏感 Name/ID 保存到本地 `agentkit.yaml`。若确实需要独立实例，选择
  “输入新名称并创建”，接受建议名称或输入自定义名称；脚本会先查重。

## Runtime 与组件

- **update 成功但关联未生效**：继续执行 release 并等待 `Ready/Healthy`。
- **Tool 列表输出密钥**：只查询受限字段；若密钥进入日志或录屏，立即轮换。
- **UI 显示 `远端 Runtime · Demo`**：请求已到远端，但没有调用真实模型；按默认
  live 配置重新发布。
- **`/invoke 200` 但 Trace 为空**：确认 live 模式、观测服务已启用且修改后已重新发布。
- **Runtime 为 `Ready/Healthy`，但 Knowledge/Memory 验证首次 `/invoke` 返回
  HTTP 500**：先用 `agentkit invoke --config-file agentkit.yaml "只回答 OK"`
  复现基础调用。若同样为 500，故障发生在业务 Case 和最终回答之前；不要继续重跑
  Canary/跨会话验证，也不要把它记录为 Knowledge 或 Memory 未命中。到目标 Runtime
  日志按失败时间查第一个异常，优先核对 `Short-term session backend:`、
  `AgentKitKnowledgeBackend`、`AgentKitMem0Backend`、`ListSkillsBySpaceId` 和异常类型；
  只摘录脱敏错误，不导出完整日志或环境变量。修复首个异常、release 并恢复
  `Ready/Healthy` 后，先确认最小 invoke 返回最终可见回答，再重跑三项验证。
- **关联 Skills 后 `MODEL_AGENT_API_KEY` 消失、release 启动失败**：旧版关联脚本将
  `--envs-json` 当作增量更新，实际该 API 会整体替换 Runtime 环境变量。先在控制台
  Secret/密钥配置恢复模型 Key 并 release；以后使用
  `scripts/bootstrap_platform.py --skill-space-id '<ss-...>'`，或在控制台只新增/编辑
  `SKILL_SPACE_ID`，不要用 `--envs-json`。
- **Skills 为空、没有 `ListSkillsBySpaceId` 或 Sandbox 无法下载已发布 Skill**：确认三层
  配置都已完成：Runtime 有 `SKILL_SPACE_ID=<ss-...>`；Runtime 已关联 **Skills Sandbox**；
  Skills Sandbox 环境变量有 `AGENTKIT_SKILL_HOST=<top-host>` 和
  `AGENTKIT_TOP_SCHEME=http`。Space ID 不是 Tool ID；不要用 AIO Sandbox 或手填 MinIO
  配置代替。
- **A2A 直接 `message/send` 成功，但主 Runtime 委派出现模型连接错误**：先运行
  `scripts/verify_a2a_interactive.sh`。数据 Runtime 的 `/health` 必须显示模型三项配置已存在，
  主 Runtime 也必须保留自己的 Model Name/API Base/API Key。重新运行
  `scripts/deploy_a2a_interactive.sh` 会交互收集数据 Runtime 的独立模型配置；不要把主、数据
  Runtime 的 API Key 或模型 Key 混用。A2A 中心只负责 AgentCard 治理与发现，不会替两个
  Runtime 注入模型配置。
- **Code 评估器提示 `required function not found`**：E92 左侧执行体必须显式包含
  `def exec_evaluation(turn_data):`。全量替换为
  `evaluation/runtime_deterministic_checks_v1_console_body.txt`，不要只复制函数内部语句；
  右侧每次只放一份完整测试 JSON。平台注入 `EvalOutput`，代码仍需自行定义入口函数。
- **实验数据项成功，但 Code 评估器得分为“—”**：数据项绿色只说明 Runtime 调用完成；
  “—”在当前控制台也可能代表评估器返回 `score=0`。打开详情查看 `reason`，全量替换为最新
  `evaluation/runtime_deterministic_checks_v1_console_body.txt`，依次试运行四份 JSON，
  提交新的评估器版本，并在新实验中明确选择新版本。历史实验继续绑定旧版本，不会自动更新。

## Knowledge 与 Memory

- **`unhashable type: 'AgentKitKnowledgeBackend'`**：使用最新版样例重新构建，
  其中已把 Tool metadata 规范化为 JSON-safe 类名。
- **`unhashable type: 'AgentKitMem0Backend'`**：使用包含 Memory metadata 和
  `search_memory(user_id, query, top_k)` 修复的新镜像重新发布。
- **Memory 检索页有记录，Runtime `load_memory` 也返回事件，但最终回答“无记录”**：
  Memory 资源和关联已生效；这是模型没有消费 Tool 结果。更新到包含 Memory Tool 结果
  约束的样例镜像、release 后重试，并在 Trace 只核对 `load_memory` Span 输出，切勿导出
  环境变量或任何 Key。
- **验证脚本显示跨会话 Memory 通过，但调试回答说“工具结果不包含 Canary”**：旧版本仅用
  marker 字符串是否出现判断通过，模型复述“未找到 marker”会造成假阳性；此外 Knowledge
  查询与 Memory Case 复用同一用户会污染语义检索。更新到最新脚本后重试：它会隔离
  Knowledge 验证用户，并只接受“完整回答为本轮 Canary”的结果。
- **Runtime 的“会话资源”为空**：会话管理首页“创建会话”只创建/导入 PostgreSQL
  资源，不会自动绑定 Runtime。进入目标 Runtime → 关联组件 → 会话资源完成绑定，再
  发布并等待 `Ready/Healthy`，详见[步骤 03](steps/03-runtime-association.md)。
- **`database_session_service` 报 `password authentication failed`，随后 `/invoke`
  返回 HTTP 500**：会话资源已经注入 Runtime，但 PostgreSQL 拒绝了平台为该 Session
  生成并注入的专用用户。资源显示“正常”和 Runtime `Healthy` 都不能替代实际数据库
  鉴权。当前混合云控制台未提供 Session 的连接测试入口，因此不要要求用户寻找该按钮。
  原始 PostgreSQL 密码正确，也不能证明平台生成的 `user_ss_...` 专用用户及其注入
  Secret 仍然同步。先在目标 Runtime 的“关联组件 → 会话资源”核对所关联资源的名称/ID
  与当前查看“集成代码”的 Session 是否相同；不要将某个 Session 的集成代码或环境变量
  当成另一个已关联资源的凭据证明。若不一致，改为关联目标资源后发布；若一致仍失败，优先
  使用控制台已提供的凭据刷新/重新导入能力。没有该能力时，创建一个新的 PostgreSQL
  Session 资源（验证成功前保留旧资源），等待可用后把目标 Runtime 的“关联组件 → 会话
  资源”切换到新资源，发布并等待 `Ready/Healthy`。不要反复修改应用或手填
  `DATABASE_POSTGRESQL_*`。若新资源仍出现相同错误，携带脱敏的 Runtime ID、Session
  ID、时间和异常类型交给平台管理员检查专用数据库用户与 Secret 同步，不提供任何密码。
  先用最小 invoke 确认最终可见回答，再重跑 Knowledge/Memory 联合验证。

## 本地环境

- **`uv sync` 长时间回溯**：保留 `uv.lock`，使用
  `uv sync --frozen --extra dev`。
- **本地 UI 端口占用**：不要停止未知服务，改用
  `UI_PORT=18000 ./scripts/run_local_ui.sh`。

更多 Runtime 级问题见[智能体运行时部署](runtime_deployment.md)。
