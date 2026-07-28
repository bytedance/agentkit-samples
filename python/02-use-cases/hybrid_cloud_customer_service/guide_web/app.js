const REPOSITORY_ROOT = 'https://github.com/bytedance/agentkit-samples';
const BRANCH = 'main';
const DEMO_PATH = 'python/02-use-cases/hybrid_cloud_customer_service';
const docUrl = path => `${REPOSITORY_ROOT}/blob/${BRANCH}/${DEMO_PATH}/${path}`;
const fileUrl = path => `${REPOSITORY_ROOT}/blob/${BRANCH}/${DEMO_PATH}/${path}`;
const directoryUrl = path => `${REPOSITORY_ROOT}/tree/${BRANCH}/${DEMO_PATH}/${path}`;

const SKILL_BOOTSTRAP = `执行前先完整读取当前目录 AGENTS.md 和 .agents/skills/agentkit-hybrid-cloud-demo/SKILL.md，并把它们作为本次执行规范。
如果当前工具支持 Skill 发现，可以使用 agentkit-hybrid-cloud-demo；不支持时直接按上述文件执行，无需安装 Codex。
如果文件不存在，立即停止并提示我打开完整的 hybrid_cloud_customer_service Demo 目录；不要用其他相近或通用 AgentKit 工作流替代。`;

const CODEX_PROMPTS = {
  deploy: {
    label: '现在建议执行：验收首次部署',
    usage: '只读核对状态、Live 调用和平台 Trace；不会重新部署',
    text: `请按上述项目 Skill，读取 docs/steps/00-runtime.md，验收我刚通过 scripts/deploy_interactive.sh 完成的 Live Runtime。
先只读检查本地 agentkit.yaml 中的非敏感 Runtime Name/ID 绑定，再核对目标 Runtime 的 Ready/RUNNING/Healthy 状态；不要重复创建、删除或默认重新发布。
执行一次 live /invoke，确认返回最终可见回答；再指导我在平台 Trace 中核对 Agent/Workflow/LLM Span、模型名、Token 和耗时。
如果实际状态不完整，定位首个失败环节，并明确区分可自动修复与需要人工完成的控制台操作。
不要输出或写入任何 AK/SK、模型 Key、Runtime Key；遇到 hosts、账号切换、临时凭据等人工步骤时单独列出并等待我完成。
最后记录每一步的通过、失败、人工操作和 README/FAQ 修订。`,
  },
  update: {
    label: '以后有变更时：更新已有 Runtime',
    usage: '修改代码、依赖、模型配置或组件关联后再执行；现在可以跳过',
    text: `请按上述项目 Skill，按 docs/steps/00-runtime.md 和 docs/runtime_deployment.md 更新已有的混合云客服 Runtime。
先检查本地未提交修改和现有 Runtime/关联资源，只更新本次代码涉及的内容，不创建重复资源、不删除任何资源。
运行相关测试和静态检查后，以 linux/amd64 重新构建发布；Runtime 更新或组件关联后必须 release，等待 Ready/Healthy，再执行 live /invoke 回归测试并核对平台 LLM Trace。
不要输出任何密钥或完整 Tool 环境变量；最后列出变更、验证证据、人工操作和回滚注意事项。`,
  },
  knowledge: {
    label: '先执行：创建并发布 Knowledge',
    usage: '完成后只记录 Ready 的 Knowledge ID；此时还不运行联合验证',
    text: `请按上述项目 Skill 执行 docs/steps/01-knowledge.md。
使用 uv run --frozen agentkit knowledge list 调用当前配置的混合云 OpenAPI，只展示 KnowledgeId、Name、Status、ProviderType，并列出全部 Ready Knowledge。
当前 OpenAPI 已指向混合云 Knowledge；AgentKit 0.5.5 的 VIKINGDB_KNOWLEDGE 是公有云 CLI 枚举，不要用它过滤混合云资源。ProviderType 为空在当前混合云 List/Get 响应中是正常表现，不能因此拒绝 Ready Knowledge；有匹配资源则复用并记录 KnowledgeId，没有才按步骤文档引导我在控制台创建。
模型选择、文档上传和发布如果必须人工操作，请逐项告诉我点击位置并等待我的反馈，不要猜模型或资源 ID。
完成后验证知识库状态、检索 knowledge_canary.md 的唯一标记，并把结果和人工步骤记入验证记录。`,
  },
  memory: {
    label: '再执行：创建或复用 Memory',
    usage: 'Knowledge Ready 后再准备 Memory；此时仍不运行联合验证',
    text: `请按上述项目 Skill 执行 docs/steps/02-memory.md。
使用 uv run --frozen agentkit memory list 调用当前配置环境的只读 List API，只展示 MemoryId、Name、Status、ProviderType，并按 Ready + MEM0 过滤；可复用时不要重复创建，也不要仅凭 Runtime 关联信息推断资源是否存在。
如果必须新建，按步骤文档检查会话摘要、语义记忆和用户偏好策略，并明确指出需要我在控制台选择的 Embedding 与 LLM Endpoint/API Key，但不要让我把 Key 发到对话中。跨会话验证还必须在控制台“会话管理（Session）”创建或复用 PostgreSQL 会话管理资源；创建不等于关联，下一步必须到目标 Runtime → 关联组件 → 会话资源完成绑定。当前 CLI 不能自动关联它。
如果 CLI 无法表达平台必填模型配置，停止重试并切换为控制台人工步骤。
完成后记录 MemoryId、状态和仍需在 Runtime 关联后验证的事项。`,
  },
  associate: {
    label: '先执行：关联 Knowledge 与 Memory',
    usage: '两项资源都 Ready 后关联 Runtime，并 release 到 Ready/Healthy',
    text: `请按上述项目 Skill 执行 docs/steps/03-runtime-association.md。
只读确认目标 Runtime、Knowledge、Memory、Sandbox、MCP 工具集和 Skills 空间的真实 ID 与状态；缺少或存在多个候选时先向我说明，不要猜 ID。
优先使用 scripts/bootstrap_platform.py 完成关联，随后必须 runtime release 并等待 Ready/Healthy。
验证平台实际注入了组件配置，但不要输出 Bearer Token、API Key 或完整环境变量。
最后列出关联前后差异、发布结果和下一步验收命令。`,
  },
  verify: {
    label: '关联后执行：验证 Knowledge 与 Memory',
    usage: '仅当两项均已关联、Runtime 已 release 时执行；脚本会隐藏输入 Endpoint/Key',
    text: `请按上述项目 Skill 执行 docs/steps/04-knowledge-memory-validation.md。
开始前只读确认：Knowledge 和 Memory 均已创建且 Ready，两个 ID 均已关联到目标 Runtime；并在目标 Runtime → 关联组件 → 会话资源中确认 PostgreSQL 会话资源不为空；且 Runtime release 后为 Ready/Healthy。
任一前置条件缺失时不要运行验证脚本、不要把预期阻塞写成新的 FAQ；明确指出应返回路线图的哪一个紧邻步骤补齐。
运行 ./scripts/verify_knowledge_memory_interactive.sh；它会隐藏输入 Runtime Endpoint/API Key，仅传给本次验证进程，不要求手动 export，也不读取、打印或写入文件。
脚本会轮询跨 session 召回，分别验证 Knowledge 唯一 Canary 命中、同一 user_id 跨 session 召回，以及不同 user_id 之间无法串读。
同时检查最终可见回答，不能只把 HTTP 200、thought 或 partial 事件当成通过。
失败时输出脱敏诊断和首个失败环节，并更新 README/FAQ；成功时记录三项独立证据。`,
  },
  sandboxMcp: {
    label: '步骤 05：Sandbox 与 MCP',
    text: `请按上述项目 Skill 执行 docs/steps/05-sandbox-mcp.md。
先确认 AIO Sandbox 和平台 MCP 服务/工具集是否已存在且可复用，不要把本地 demo_core 或本地 /mcp 当成平台证据。
能自动完成的资源关联、Runtime release 和状态等待直接执行；控制台创建 MCP 服务、选择认证方式等人工动作逐项说明。
分别触发 run_code 和 mcp_router，核对最终结果以及 Runtime 日志或 Trace 中的真实工具调用 Span。
不要输出 MCP API Key 或 Tool 环境变量；把 Sandbox 与 MCP 的结果分开判定和记录。`,
  },
  skills: {
    label: '步骤 06：Skill 中心',
    text: `请按上述项目 Skill 执行 docs/steps/06-skills.md。
本 Demo 的可发布业务 Skill 在仓库共享目录 ../../../skills/customer-service-compliance/SKILL.md；控制台默认直接上传同目录的 ../../../skills/customer-service-compliance.zip。先执行 agentkit skills validate；只有修改 SKILL.md 后才用 agentkit skills pack 重建 ZIP。不要把 .agents/skills/agentkit-hybrid-cloud-demo 当成平台 Skill。
确认 customer-service-compliance 已发布并位于目标 Skills 空间，SKILL_SPACE_ID 使用空间 ID 而不是 Tool ID；没有明确平台存储配置时不要猜 MinIO Bucket。
先在 Skills Sandbox 配置 AGENTKIT_SKILL_HOST=<top-host> 与 AGENTKIT_TOP_SCHEME=http；再在 Runtime 安全添加 SKILL_SPACE_ID=<ss-...>（使用步骤 03 的 bootstrap_platform.py --skill-space-id，不会显示或覆盖模型 Key），最后在 Runtime 关联组件绑定该 Skills Sandbox。关联提供 Tool ID，不会替代 SKILL_SPACE_ID。
更新并 release Runtime 后，运行 ./scripts/verify_skills_interactive.sh --show-response。它会生成唯一 SKILL_CANARY 确认码，只有返回 customer-service-compliance、needs_confirmation 和该确认码才判定 PASS。
再以 ListSkillsBySpaceId、Successfully loaded skill 和 Skills Sandbox 执行响应作为三段 Trace/日志证据；缺少任一段都标记为部分通过或失败，并记录需要人工完成的控制台操作。`,
  },
  a2a: {
    label: '步骤 07：A2A 外部 Agent',
    text: `请按上述项目 Skill 执行 docs/steps/07-a2a-identity-session.md。
先把 ./scripts/deploy_a2a_interactive.sh 命令交给用户在 Demo 终端手动执行，不要替用户操作交互终端：首次默认创建带 -a2a 后缀的独立数据 Runtime，用户手动填写 Agent 展示名称、AgentCard 能力 ID（skills[].id）和模型配置，脚本自动注入 AGENT_APP_MODE=a2a_data_analyst，不会修改主客服 Runtime 绑定。Registry Token 过期时只指导用户刷新 docker login；用户回复登录成功后仍由用户重新执行脚本。
随后指导用户在 A2A 中心选择空间并注册该 Runtime 的 AgentCard。A2A 中心是可登记多个外部 Agent 的治理与发现入口，不等于一个写死的数据 Agent；本 Demo 默认的 complaint-trend-analysis 只是 AgentCard 能力验收样例。请从所选 Agent 详情复制服务地址，从数据 Runtime 调用页取得它自己的 API Key，再让用户手动执行 ./scripts/configure_a2a_peer_interactive.sh。脚本会读取 AgentCard，自动取得 Agent 名称与 skills[].id；单能力自动选中，多能力才要求选择，然后安全合并到主 Runtime 并自动 release。详情页若未展示 ID，右上角“JSON 文件”可人工查看，但不是必需步骤。
明确说明：A2A 规范虽然把能力数组命名为 skills，但这里不创建或调用 Skills 中心 Skill，不使用 SKILL_SPACE_ID、Skills ZIP 或 Skills Sandbox。
最后让用户运行 ./scripts/verify_a2a_interactive.sh --show-response 并手动输入两端 Endpoint/Key、所选 Agent 和 AgentCard 能力 ID。同一轮 A2A_CANARY 确认码必须同时出现在数据 Agent 直接 message/send 和主 Runtime 委派结果；用脚本输出的 user_id/session_id 找到主 Runtime Trace，确认 execute_tool delegate_complaint_trend_analysis，并在数据 Runtime 日志确认 AgentCard GET 200、POST /a2a 200。三项证据缺一不可，不用 demo fallback 代替真实平台通过。`,
  },
  identity: {
    label: '步骤 07：身份与安全边界',
    text: `请按上述项目 Skill 执行 docs/steps/07-a2a-identity-session.md 的身份部分。
主客服 Runtime 必须保持现有 API Key、Name/ID 和全部组件关联不变；不要把它原地切换为 OAuth。
先让我在 Demo 终端手动运行 ./scripts/deploy_oauth_interactive.sh。该脚本使用独立 agentkit.oauth.yaml，首次只创建 hybrid-cloud-customer-service-oauth；按提示输入认证域名、用户池 ID 和允许的 Client ID，Client Secret 不参与部署。
发布后确认 OAuth Runtime 的可访问用户池正确且 Ready/Healthy，再让我运行 ./scripts/verify_oauth_interactive.sh --show-response，在终端交互输入 OAuth Runtime Endpoint、用户池 ID 与 Client ID，并隐藏输入 Client Secret。脚本从用户池取得短期 Token 后直接以 Bearer Token 调用该 Runtime；HTTP 200 和最终回答就是默认验收，不要另造一套 OAuth 服务测试。只有需要演示拒绝行为时才增加 --negative-checks；Token 和 Client Secret 不得输出或落盘。
首个 OAuth 请求必须无工具，随后在该独立 Runtime 的 Trace 中确认 /invoke → workflow → agent → llm，且没有 Authorization/JWT 原文。明确说明 client_credentials 只证明应用身份；真人用户登录需 Authorization Code + PKCE，网关通过也不等于 sub/自定义 tenant_id 已完成业务映射。
PostgreSQL 会话与跨会话记忆已经在步骤 02–04 验收，本步骤不要重复创建、绑定或验证，也不要把入站 JWT 复用给 Knowledge、MCP、Skills 或 A2A。`,
  },
  quality: {
    label: '步骤 08：评测、Trace 与发布验收',
    text: `请按上述项目 Skill 执行 docs/steps/08-evaluation-observability.md。
不要重复执行已通过的 Knowledge/Memory 或工具功能验收；复用它们的证据和 Trace ID。当前 CLI 没有评测集、评估器和实验创建能力，因此先在控制台创建 Code 门禁实验：导入 evaluation/hybrid_customer_service_runtime_core_v1.csv，确认 input/reference_output 两列和 4 条数据，提交版本；在“添加评估器”弹窗切换到 Code，自定义创建 runtime_deterministic_checks_v1，左侧执行函数体粘贴 evaluation/runtime_deterministic_checks_v1_console_body.txt 完整内容。E92 控制台会注入 EvalOutput，但代码必须显式包含 def exec_evaluation(turn_data):；仓库文件已包含完整入口函数，不要只粘贴内部语句，也不要添加 from evaluator import ...。返回值必须是 EvalOutput(score=..., reason=...)，不能返回 metrics/confusion_label 结构；右侧测试数据 turn 删除默认台湾示例后一次只能保留一份完整 JSON：每次全选替换为 evaluation/code_evaluator_test_data/ 中的一份、试运行中返回 score=1 后再全选替换下一份，绝不能把两份 JSON 追加在一起；完成 input/actual_output/reference_output 映射，使用本次唯一实验名、选择主 Runtime、最大并发 1 后启动实验。
本四条工具/安全/A2A Case 的发布门禁只使用 Code 评估器。LLM“正确性”模板应另建质量观察实验：它读取平台保存的完整流式内容，可能把 thought 片段混入 final answer 而误判；红色模板状态不等于 Runtime 回答错误。明确区分评估器试运行（只测模拟 JSON）与实验执行（真实调用 Runtime）：必须等 4 条均产生 actual_output 且 Code 4/4 才判定通过。再开启观测并 release Runtime，按 Runtime 健康、live 最终回答、评测结果和 Agent/Workflow/LLM/Tool Span 四类证据给出发布结论；只记录非敏感元数据，不导出 Token、Key 或完整环境变量。`,
  },
};

Object.values(CODEX_PROMPTS).forEach(prompt => {
  prompt.text = `${SKILL_BOOTSTRAP}

${prompt.text}`;
});

const STEPS = [
  {
    id: 'runtime',
    number: 'STEP 01',
    badge: '部署后',
    badgeClass: 'required',
    title: '验收 Runtime，按需更新',
    readmeSections: ['步骤 00：Runtime 验收与更新'],
    promptKeys: ['deploy', 'update'],
    summary: 'Live Runtime 已由交互脚本部署。这里不再重复创建：先补齐状态、真实回答和平台 Trace 证据；以后代码或配置发生变化时，再使用更新 Prompt。',
    outcome: '确认当前 Runtime 不只是“创建成功”，而是能稳定返回真实模型回答，并具备后续接入知识、记忆和工具的可靠承载环境。',
    platform: [
      '交互脚本已完成镜像构建、发布、Ready/Healthy 和一次 invoke',
      '现在建议补查平台 LLM Trace，并记录模型、Token 和耗时证据',
      '只有代码、依赖、模型配置或组件关联变化时才重新构建发布',
    ],
    file: 'agent.py · Dockerfile · entrypoint.sh · agentkit.yaml.example',
    links: [
      { label: 'Runtime 部署操作', href: docUrl('docs/runtime_deployment.md'), kind: 'doc' },
      { label: 'Runtime 入口源码', href: fileUrl('agent.py'), kind: 'source' },
    ],
    code: `# 首次部署已经完成，现在不要重复执行\n# 建议：运行“验收首次部署” Prompt\n# 以后有代码或配置变更时，再运行“更新已有 Runtime” Prompt`,
    verification: 'Runtime 状态为 Ready；容器同时支持 /app/entrypoint.sh 与 /opt/application/run.sh；POST /invoke 返回最终可见回答；本地 UI 显示远端 Live，平台 Trace 存在本次 LLM Span、模型名和 Token。',
  },
  {
    id: 'knowledge',
    number: 'STEP 02',
    badge: '先创建',
    badgeClass: 'enhance',
    title: '接入企业知识库',
    readmeSections: ['步骤 01：Knowledge'],
    promptKeys: ['knowledge'],
    summary: '先准备可发布、可检索的企业 Knowledge。这个阶段只完成知识库创建和 Ready 验证，不提前运行 Knowledge/Memory 联合验证。',
    outcome: '“理财产品能否退款”不再依赖模型常识，而是可以在后续关联后检索企业退款政策，并返回来源文件和命中片段。',
    platform: [
      '创建混合云云搜索知识库并上传脱敏规则文档',
      '完成切片和检索检查后发布 Knowledge',
      '确认状态为 Ready，并记录非敏感 Knowledge ID',
    ],
    file: 'platform_knowledge.py · data/knowledge/ · agent.py',
    links: [
      { label: 'Knowledge 步骤文档', href: docUrl('docs/steps/01-knowledge.md'), kind: 'doc' },
      { label: '云搜索适配器源码', href: fileUrl('platform_knowledge.py'), kind: 'source' },
    ],
    code: `knowledge = build_platform_knowledge(app_name)\noptional_features["knowledgebase"] = knowledge\n\n# 创建并发布 Ready；关联与联合验证在后续阶段完成`,
    verification: 'Knowledge 已发布且为 Ready；测试检索能命中唯一 Canary 文档；当前阶段不要求 Runtime 已关联。',
  },
  {
    id: 'memory',
    number: 'STEP 03',
    badge: '再创建',
    badgeClass: 'optional',
    title: '加入会话与记忆',
    readmeSections: ['步骤 02：Memory'],
    promptKeys: ['memory'],
    summary: 'Knowledge Ready 后再创建或复用 MEM0。这个阶段只准备 Memory，不提前关联，也不运行联合验证。',
    outcome: '完成关联和验证后，同一客户可跨会话召回偏好，同时不同客户之间严格隔离。',
    platform: [
      '在会话管理创建 PostgreSQL 资源，并到 Runtime 的会话资源区域完成绑定',
      '创建或复用包含所需策略的 MEM0 Memory',
      '确认状态为 Ready，并记录非敏感 Memory ID',
    ],
    file: 'agent.py · platform_memory.py · platform_capabilities.py',
    links: [
      { label: 'Memory 步骤文档', href: docUrl('docs/steps/02-memory.md'), kind: 'doc' },
      { label: 'MEM0 适配器源码', href: fileUrl('platform_memory.py'), kind: 'source' },
    ],
    code: `short_term_memory = ShortTermMemory(backend="postgresql")\napp = AgentkitAgentServerApp(\n    agent=build_agent(),\n    short_term_memory=short_term_memory,\n)\n\n# 创建 Ready；关联与隔离验证在下一阶段完成`,
    verification: 'Memory 已创建或复用且为 Ready；策略和模型配置完整；当前阶段不运行跨会话或跨用户验证。',
  },
  {
    id: 'actions',
    number: 'STEP 04',
    badge: '先关联',
    badgeClass: 'extend',
    title: '关联并验证知识与记忆',
    readmeSections: ['步骤 03：关联 Runtime', '步骤 04：Knowledge/Memory 验证'],
    promptKeys: ['associate', 'verify'],
    summary: 'Knowledge 和 Memory 都 Ready 后，同时关联 Runtime、release 并完成联合验证。此阶段不创建或验证 Sandbox、Skill、A2A 和身份权限。',
    outcome: '证明客服能检索企业规则、召回同一客户的跨会话偏好，且不会跨用户串读。',
    platform: [
      '把 Knowledge ID 与 Memory ID 同时关联 Runtime，release 至 Ready/Healthy',
      '配置当前终端 Runtime Endpoint/Key，完成 Canary、跨会话和隔离验证',
    ],
    file: 'scripts/bootstrap_platform.py · scripts/verify_knowledge_memory.py · tools/',
    links: [
      { label: 'Runtime 关联步骤', href: docUrl('docs/steps/03-runtime-association.md'), kind: 'doc' },
      { label: 'Knowledge/Memory 验证', href: docUrl('docs/steps/04-knowledge-memory-validation.md'), kind: 'doc' },
      { label: '业务工具源码', href: directoryUrl('tools'), kind: 'source' },
    ],
    code: `# 先关联两项基础资源并 release\nuv run --frozen scripts/bootstrap_platform.py \\\n  --runtime-id <runtime-id> \\\n  --knowledge-id <knowledge-id> \\\n  --memory-id <memory-id>\n\n# 再配置当前终端 Endpoint/Key，运行联合验证\nuv run --frozen scripts/verify_knowledge_memory.py --wait-seconds 15`,
    verification: 'Knowledge Canary、同用户跨会话召回和跨用户隔离三项独立通过。工具、Skill、A2A 与身份验证留给后续阶段。',
  },
  {
    id: 'security',
    number: 'STEP 05',
    badge: '必须',
    badgeClass: 'required',
    title: '建立身份与安全边界',
    readmeSections: ['步骤 07：身份权限'],
    promptKeys: ['identity'],
    summary: '在接入 MCP、Skills 或 A2A 之前，保留主 Runtime 的 API Key 基线，另建 -oauth Runtime 验证用户池 JWT。PostgreSQL 会话与跨会话记忆已在步骤 02–04 验收，不重复执行。',
    outcome: '用完全独立的数据面证明用户池签发 Token、网关验签和拒绝无效凭据，不覆盖已经验收的客服主 Runtime。',
    platform: [
      '运行 deploy_oauth_interactive.sh 创建 hybrid-cloud-customer-service-oauth',
      '绑定允许访问的用户池 Client，主 Runtime 继续保持 API Key',
      '从用户池取得短期 Token，并以 Bearer Token 调用 OAuth Runtime',
      '在 OAuth Runtime Trace 中确认成功链路且无 JWT 原文',
    ],
    file: 'scripts/deploy_oauth_interactive.sh · scripts/verify_oauth_interactive.sh · scripts/verify_oauth.py',
    links: [
      { label: '身份权限步骤文档', href: docUrl('docs/steps/07-a2a-identity-session.md'), kind: 'doc' },
      { label: '独立 OAuth Runtime 部署脚本', href: fileUrl('scripts/deploy_oauth_interactive.sh'), kind: 'source' },
      { label: 'OAuth JWT 验收脚本', href: fileUrl('scripts/verify_oauth_interactive.sh'), kind: 'source' },
      { label: '请求身份上下文源码', href: fileUrl('platform_request_context.py'), kind: 'source' },
    ],
    code: `./scripts/deploy_oauth_interactive.sh\n./scripts/verify_oauth_interactive.sh --show-response\n\n主 Runtime：API Key，保持不变\n身份 Runtime：custom_jwt，独立 -oauth`,
    verification: '短期 Token 获取成功，Bearer 调用 OAuth Runtime 返回 HTTP 200 和最终回答；Trace 中没有凭据原文。401/403 反例仅在显式 --negative-checks 时验收。',
  },
  {
    id: 'extensions',
    number: 'STEP 06',
    badge: '按需扩展',
    badgeClass: 'enhance',
    title: '调用外部能力',
    readmeSections: ['步骤 05：Sandbox/MCP', '步骤 06：Skills 中心', '步骤 07：A2A'],
    promptKeys: ['sandboxMcp', 'skills', 'a2a'],
    summary: '基础知识与记忆闭环通过后，将 MCP、Skills 与 A2A 统一作为外部/托管能力接入。它们共享“关联、release、真实调用、Trace 取证”的方法，但各自独立验收。',
    outcome: '客服可调用平台 MCP 工具、已发布合规 Skill 与远端数据分析 Agent；每一条外部能力链路都有独立请求、结果和 Trace。',
    platform: [
      '创建或复用 AIO Sandbox、MCP 服务/工具集，并分别完成 Runtime 关联',
      '创建 Skills Space、发布 ZIP、配置 Skills Sandbox 与 Runtime 的 SKILL_SPACE_ID',
      '注册 A2A AgentCard、关联远端数据 Agent 并验证 message/send 委派',
      '每项关联后 release 至 Ready/Healthy，再做真实调用和 Trace 取证',
    ],
    file: 'agent.py · a2a_data_agent.py · a2a_client.py · scripts/configure_a2a_peer_interactive.sh',
    links: [
      { label: 'Sandbox/MCP 步骤文档', href: docUrl('docs/steps/05-sandbox-mcp.md'), kind: 'doc' },
      { label: 'Skills 步骤文档', href: docUrl('docs/steps/06-skills.md'), kind: 'doc' },
      { label: 'A2A 步骤文档', href: docUrl('docs/steps/07-a2a-identity-session.md'), kind: 'doc' },
      { label: 'A2A 完整部署与验收', href: docUrl('docs/a2a_agent_validation.md'), kind: 'doc' },
      { label: '数据 Agent（AgentCard / message-send）', href: fileUrl('a2a_data_agent.py'), kind: 'source' },
      { label: '主 Runtime A2A 委派客户端', href: fileUrl('a2a_client.py'), kind: 'source' },
      { label: '安全配置主 Runtime 对端', href: fileUrl('scripts/configure_a2a_peer_interactive.sh'), kind: 'source' },
      { label: 'A2A 确认码验收脚本', href: fileUrl('scripts/verify_a2a_interactive.sh'), kind: 'source' },
      { label: 'Sandbox/Skills 实现', href: fileUrl('agent.py'), kind: 'source' },
    ],
    code: `MCP：mcp_router → MCP 工具集\nSkills：execute_skills → Skill Space + Skills Sandbox\nA2A：delegate → AgentCard → message/send → Artifact\n\n# 每条外部能力链路独立调用并查看 Trace`,
    verification: 'mcp_router、execute_skills、A2A message/send 分别返回真实结果；Skills 验收脚本输出 PASS 和本轮确认码；每项都有独立 Tool/Agent Span。',
  },
  {
    id: 'quality',
    number: 'STEP 07',
    badge: '上线门槛',
    badgeClass: 'quality',
    title: '评测、Trace 与发布验收',
    readmeSections: ['步骤 08：评测与发布验收'],
    promptKeys: ['quality'],
    summary: '复用此前 Runtime、身份与外部能力的通过证据，运行离线评测并以平台 Trace 汇总最终发布结论。',
    outcome: '产品评审看到版本化 Case、评估结果、失败定位和可追踪的线上证据，而不是一次性的演示结果。',
    platform: [
      '导入版本化评测集，创建 LLM 与 Code 评估器',
      '以目标 Runtime 创建实验并保存字段映射',
      '在 Runtime 高级配置中开启观测服务并重新发布',
    ],
    file: 'evaluation/ · docs/evaluation_and_observability.md',
    links: [
      { label: '评测与可观测操作', href: docUrl('docs/evaluation_and_observability.md'), kind: 'doc' },
      { label: '评测代码与数据', href: directoryUrl('evaluation'), kind: 'source' },
    ],
    code: `评测：input + reference_output → actual_output\n评估器：LLM correctness + deterministic checks\n\nTrace：Runtime → Agent → Workflow → Model / Tool`,
    verification: '核心 Case 的确定性评估通过；Trace 可看到模型、Token、耗时、工具和状态，失败 Case 能定位到具体 Span。',
  },
];

const detail = {
  number: document.querySelector('#detail-number'),
  badge: document.querySelector('#detail-badge'),
  title: document.querySelector('#detail-title'),
  summary: document.querySelector('#detail-summary'),
  readmeSections: document.querySelector('#detail-readme-sections'),
  outcome: document.querySelector('#detail-outcome'),
  platform: document.querySelector('#detail-platform'),
  guideLink: document.querySelector('#detail-guide-link'),
  file: document.querySelector('#detail-file'),
  code: document.querySelector('#detail-code'),
  prompts: document.querySelector('#detail-prompts'),
  verification: document.querySelector('#detail-verification'),
  links: document.querySelector('#detail-links'),
  progress: document.querySelector('#progress-text'),
};

let activeIndex = 0;

async function copyPrompt(button, text) {
  try {
    await navigator.clipboard.writeText(text);
  } catch (_) {
    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.setAttribute('readonly', '');
    textarea.style.position = 'fixed';
    textarea.style.opacity = '0';
    document.body.append(textarea);
    textarea.select();
    document.execCommand('copy');
    textarea.remove();
  }
  const previous = button.textContent;
  button.textContent = '已复制';
  button.classList.add('copied');
  window.setTimeout(() => {
    button.textContent = previous;
    button.classList.remove('copied');
  }, 1600);
}

function renderStep(index, updateHash = true) {
  activeIndex = Math.max(0, Math.min(STEPS.length - 1, index));
  const step = STEPS[activeIndex];

  document.querySelectorAll('.step-card').forEach(button => {
    const active = button.dataset.step === step.id;
    button.classList.toggle('active', active);
    button.setAttribute('aria-pressed', String(active));
  });

  detail.number.textContent = step.number;
  detail.badge.textContent = step.badge;
  detail.badge.className = `detail-badge ${step.badgeClass}`;
  detail.title.textContent = step.title;
  detail.summary.textContent = step.summary;
  detail.readmeSections.replaceChildren(...step.readmeSections.map(section => {
    const tag = document.createElement('span');
    tag.textContent = section;
    return tag;
  }));
  detail.outcome.textContent = step.outcome;
  detail.platform.replaceChildren(...step.platform.map(item => {
    const li = document.createElement('li');
    li.textContent = item;
    return li;
  }));
  const primaryGuide = step.links.find(link => link.kind === 'doc');
  detail.guideLink.href = primaryGuide.href;
  detail.guideLink.textContent = `${primaryGuide.label} ↗`;
  detail.guideLink.setAttribute('aria-label', `查看${primaryGuide.label}`);
  detail.file.textContent = step.file;
  detail.code.textContent = step.code;
  detail.prompts.replaceChildren(...step.promptKeys.map(key => {
    const prompt = CODEX_PROMPTS[key];
    const card = document.createElement('details');
    card.className = 'prompt-card';
    const heading = document.createElement('summary');
    const labelGroup = document.createElement('div');
    labelGroup.className = 'prompt-label';
    const label = document.createElement('strong');
    label.textContent = prompt.label;
    labelGroup.append(label);
    if (prompt.usage) {
      const usage = document.createElement('small');
      usage.textContent = prompt.usage;
      labelGroup.append(usage);
    }
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = '复制 Prompt';
    button.setAttribute('aria-label', `复制${prompt.label}`);
    button.addEventListener('click', event => {
      event.preventDefault();
      event.stopPropagation();
      copyPrompt(button, prompt.text);
    });
    heading.append(labelGroup, button);
    const pre = document.createElement('pre');
    pre.textContent = prompt.text;
    card.append(heading, pre);
    return card;
  }));
  detail.verification.textContent = step.verification;
  detail.links.replaceChildren(...step.links.map(link => {
    const anchor = document.createElement('a');
    anchor.href = link.href;
    anchor.target = '_blank';
    anchor.rel = 'noreferrer';
    anchor.className = `resource-link ${link.kind}`;
    anchor.textContent = `${link.label} ↗`;
    return anchor;
  }));
  detail.progress.textContent = `${activeIndex + 1} / ${STEPS.length}`;

  document.querySelector('#previous-step').disabled = activeIndex === 0;
  document.querySelector('#next-step').disabled = activeIndex === STEPS.length - 1;
  if (updateHash) history.replaceState(null, '', `#${step.id}`);
}

document.querySelectorAll('.step-card').forEach(button => {
  button.addEventListener('click', () => {
    const index = STEPS.findIndex(step => step.id === button.dataset.step);
    renderStep(index);
  });
});

document.querySelector('#previous-step').addEventListener('click', () => renderStep(activeIndex - 1));
document.querySelector('#next-step').addEventListener('click', () => renderStep(activeIndex + 1));

const initialIndex = STEPS.findIndex(step => `#${step.id}` === window.location.hash);
renderStep(initialIndex >= 0 ? initialIndex : 0, false);
