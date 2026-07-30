# 步骤 00：环境预检、部署 Runtime 与开始使用

> 已成功执行 `scripts/deploy_interactive.sh` 后，不要立即重复部署。本步骤接下来分为
> 两种用途：现在建议做一次只读验收；只有以后修改代码、依赖、模型配置或组件关联时，
> 才执行 Runtime 更新。

## 目标

构建并发布 `linux/amd64` Live Runtime，验证 `Ready`、`RUNNING`、`Healthy`、
最终回答和平台 LLM Trace，然后用本地 `/chat` 连接该 Runtime。

## 自动执行

在 Demo 根目录执行交互式入口：

```bash
./scripts/deploy_interactive.sh
```

脚本会先检测 AgentKit CLI 的已有目标环境，允许确认复用，或交互输入 OpenAPI
Scheme/Host 与隐藏的 AK/SK；随后显式询问目标 Region。默认方舟仅隐藏输入一次模型
API Key，自定义模型才询问 Model Name、API Base 和 API Key。然后生成临时部署配置、
构建并推送镜像、launch/update Runtime、等待状态并执行 invoke。所有 Key 均不回显；
控制面 AK/SK 按 CLI 标准行为保存到本机全局配置，模型 Key 只进入临时部署配置。
首次部署不要求用户先准备 export 或 Agent Prompt。
更新关联或 Runtime 后必须继续 `runtime release`，不能把 `UnReleased` 当作成功。

如果该 Region 已有同名 Runtime，交互入口会列出 Runtime ID，并让用户确认更新，
或直接输入一个新名称创建独立 Runtime。新名称会先查重。成功后只把非敏感的
Runtime Name/ID 保存到被 Git 忽略的 `agentkit.yaml`，后续 launch 会更新该实例，
不会再次 CreateRuntime。

自动化/CI 已安全注入完整变量时，使用 `scripts/deploy_hybrid.sh`。

## 需要人工完成

- 没有企业 DNS 时配置 hosts；
- 正式环境修复 HTTPS 证书和 Ingress，不能用 `curl -k`；
- 从“访问控制”获取目标环境 AK/SK；
- 通过交互式入口隐藏输入模型 Key，或在自动化环境通过 Secret 注入；
- launch 明确出现 `token expired`、`invalid token claims`、`unauthorized` 或
  `authentication required` 时，重新获取临时登录指令并确认 `Login Succeeded`；
- 在 Runtime 高级配置中启用观测服务并重新发布。

## 部署后调用

从目标 Runtime 的“快速调用/在线测试/调用信息”复制 Endpoint 和 Runtime API Key：

```bash
export RUNTIME_ENDPOINT='<runtime-base-url>'
export RUNTIME_API_KEY='<runtime-api-key>'

curl -sSN -X POST "${RUNTIME_ENDPOINT%/}/invoke" \
  -H "Authorization: Bearer ${RUNTIME_API_KEY}" \
  -H 'Content-Type: application/json' \
  -H 'user_id: post-deploy-proof-user' \
  -H 'session_id: post-deploy-proof-001' \
  -d '{"prompt":"连接验证：请说明当前运行模式。"}'
```

再启动：

```bash
UI_PORT=18000 ./scripts/run_local_ui.sh
```

打开 `/chat`，保存同一组 Endpoint/Key 并发送新消息。“保存并连接”只表示配置进入
本地 BFF；必须出现一次成功调用才能证明连通。

## 通过标准

- Runtime 为 `Ready/RUNNING/Healthy`；
- `/invoke` 返回最终可见回答，而不是只有 thought/partial 事件；
- UI 显示 `远端 Runtime · Live`；
- 平台 Trace 包含 Agent/Workflow/LLM Span、模型、Token 和耗时；
- 使用工具时存在对应 Tool Span。

`远端 Runtime · Demo` 只证明远端路由，不证明模型或平台能力。应用返回的
`trace-...` 不是平台 Trace ID。

完整命令、配置模板和失败排查见[智能体运行时部署](../runtime_deployment.md)。
