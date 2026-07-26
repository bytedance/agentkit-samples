# 步骤 01：创建或复用 Knowledge

## 目标

准备一个已发布且 `Ready` 的云搜索 Knowledge，并用唯一 Canary 证明真实检索。

## 操作

1. 使用 AgentKit 权限账号进入 **AgentKit → 知识库**。
2. 先通过 CLI 调用已配置环境的只读 List API，列出所有 `Ready` 资源：

   ```bash
   uv run --frozen agentkit knowledge list \
     --region '<region>' --all --status Ready \
     --fields KnowledgeId,Name,Status,ProviderType --no-color
   ```

   当前 CLI 已通过环境配置连接混合云 OpenAPI，因此该 API 返回的 `Ready`
   Knowledge 就是可复用候选。只返回上述非敏感字段，不读取连接信息。
3. 若没有，创建云搜索 Knowledge，按环境要求选择模型，上传脱敏文档并发布。
4. 等待状态为 `Ready`，记录 Knowledge ID，不记录凭据。
5. 上传/确认 `data/knowledge/knowledge_canary.md`，检索其中的唯一标记。

模型选择、文档上传和发布通常需要人工控制台操作。不要猜测模型、资源 ID 或把
本地 `data/knowledge` 的回答当成平台 Knowledge 证据。

AgentKit 0.5.5 的 `knowledge provider-types` 只列出公有云
`VIKINGDB_KNOWLEDGE`，但混合云 List/Get API 可能正常返回空的 `ProviderType` 和
`ProviderKnowledgeId`。这不是类型错误：不要使用 `--provider-type
VIKINGDB_KNOWLEDGE` 过滤混合云资源，也不要因为该字段为空而拒绝一个 `Ready`
Knowledge。混合云知识后端的正确性最终通过 Canary 检索、Runtime 引用和 Trace
验证。

## 通过标准

- Knowledge 已发布且 `Ready`；
- 唯一 Canary 可被真实检索；
- 后续 Runtime 调用返回知识来源或引用；
- Trace 中存在 `load_knowledgebase`/Knowledge Tool Span。

创建完成后进入[步骤 02：Memory](02-memory.md)，或在不需要长期记忆时直接进入
[步骤 03：Runtime 关联](03-runtime-association.md)。
