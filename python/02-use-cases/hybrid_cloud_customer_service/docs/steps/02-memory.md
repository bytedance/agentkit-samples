# 步骤 02：创建或复用 Memory

## 目标

准备一个托管 MEM0 Memory 和 Runtime 会话管理 PostgreSQL，用于可靠地跨会话召回，
并保持 tenant/user 隔离。

## 操作

1. 先通过 CLI 调用已配置环境的只读 List API：

   ```bash
   uv run --frozen agentkit memory list \
     --region '<region>' --all --status Ready --provider-type MEM0 \
     --fields MemoryId,Name,Status,ProviderType --no-color
   ```

   该查询只返回非敏感字段；不得读取 Memory 连接信息或 API Key。
2. 可复用时不要重复创建；记录 Memory ID 和状态。
3. 新建时配置会话摘要、语义记忆和用户偏好策略。
4. 按平台要求人工选择 Embedding、LLM Endpoint/API Key。
5. 在 **AgentKit → 会话管理（Session）** 点击“创建会话”，创建或导入关系型
   PostgreSQL 会话资源；它保存完整的 user/session 事件，供长期记忆保存回调读取。
   只填写平台页面要求的连接配置，不读取 Runtime 或 Memory 自动注入的环境变量。
6. 创建完成只代表会话资源已准备，**尚未关联到 Runtime**。记下非敏感的会话资源名称，
   等待它可用后进入步骤 03 完成绑定。

若 CLI 无法表达平台必填模型配置，应停止重试并使用控制台；不要猜模型或把 Key
写入对话、README、脚本和仓库。

## 通过标准

本步骤只证明资源准备完成。真正通过还需要在[步骤 04](04-knowledge-memory-validation.md)
验证：

- 同一 `user_id`、不同 `session_id` 可召回；
- 不同 `user_id` 无法串读；
- Runtime Trace 存在真实 `load_memory` 调用。

`agentkit runtime update` 当前没有会话管理关联参数，因此 PostgreSQL 必须在控制台的
目标 Runtime“关联组件”页面的**会话资源**区域人工绑定；关联后 release 并等待
`Ready/Healthy`。不要读取或填写应用实际注入的数据库连接信息。
