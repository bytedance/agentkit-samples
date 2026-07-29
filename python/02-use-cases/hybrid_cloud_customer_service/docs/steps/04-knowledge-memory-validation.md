# 步骤 04：验证 Knowledge、Memory 与隔离

## 目标

用三个独立 Case 验证 Knowledge、同用户跨会话记忆和不同用户隔离。

## 前置条件

以下条件必须全部满足，缺一项就返回对应步骤补齐，不启动验证脚本：

1. 步骤 01 的 Knowledge 已创建、发布且为 `Ready`；
2. 步骤 02 的 Memory 已创建或复用且为 `Ready`；
3. 步骤 03 已把 Knowledge ID 和 Memory ID 同时关联到目标 Runtime；
4. 已在控制台的目标 Runtime → 关联组件 → **会话资源** 中绑定 PostgreSQL 会话资源，
   且该区域不再为空；
5. Runtime 已 release，并恢复 `Ready/Healthy`；
6. 已从目标 Runtime 的“快速调用/在线测试/调用信息”页取得 Endpoint 和 API Key。

发现 `KnowledgeId` 或 `MemoryId` 为空属于前置步骤未完成，不应作为验证脚本的新缺陷
写入 FAQ。补齐关联并 release 后再回来验证。

## 执行

使用交互式入口输入 Runtime Endpoint 和 API Key。API Key 为隐藏输入，只传给本次
验证进程，不写入文件，也不要求手动 `export`：

```bash
./scripts/verify_knowledge_memory_interactive.sh --wait-seconds 60
```

需要脱敏诊断时：

```bash
./scripts/verify_knowledge_memory_interactive.sh \
  --wait-seconds 60 \
  --show-responses
```

脚本会：

1. 使用独立验证用户查询唯一 Knowledge Canary，避免该普通对话被写入待验证用户的长期记忆；
2. 让用户 A 在会话 1 写入偏好，并在会话 2 召回；
3. 用用户 B 查询同一偏好，确认不能读到用户 A 数据。

Memory 写入由 Runtime 启动时注入的 `DATABASE_MEM0_BASE_URL` 与
`DATABASE_MEM0_API_KEY` 启用。VeADK 在请求结束后从会话服务读取完整会话；同一用户
切到新 session 时会强制保存上一 session，再调用 MEM0 写入接口。MEM0 默认异步入库，
因此脚本会在超时范围内轮询召回，而不是只等待一次后作出结论。召回 Case 要求最终
可见回答只包含本轮生成的 `MEM_CANARY_...`；仅在回答里提及该值（例如“未找到该值”）
不会误判为通过。

若最终失败，在 Runtime 日志中只检索以下无敏感关键词：`Short-term session backend:
AgentKit managed PostgreSQL`、`Short-term session backend: local fallback`、`MEM0
long-term memory is enabled`、`MEM0 write accepted`、`MEM0 search completed`、
`Long-term memory is disabled` 或 `Unexpected error while saving session`。不要查看或
导出完整环境变量。

若日志显示 `load_memory` 已返回记忆事件，但最终回答仍为“无记录/未存储”，说明 Memory
关联与检索正常，故障位于模型未使用 Tool 结果。确认使用本样例最新镜像（系统指令要求
有结果时据实回答）后重新发布；并在 Trace 中核对该次 `load_memory` Tool Span 的输出，
无需查看任何凭据。

## 通过标准

- 三项分别通过，不能用 HTTP 200 代替业务结果；
- 最终回答位于非 `thought=true`、非 partial 的文本事件；
- Knowledge 返回可核验来源；
- 同用户跨会话召回成功；
- 不同用户无串读；
- Trace 中可见 Knowledge/Memory Tool Span。

已知 metadata 兼容错误和处理方式见[常见问题](../troubleshooting.md)。
