# 步骤 03：关联组件并重新发布 Runtime

## 目标

把确认过的 Knowledge、Memory、Sandbox、MCP 工具集和 Skills 空间关联到目标
Runtime，并让新版本重新达到 `Ready/Healthy`。

Knowledge/Memory 联合验证场景必须先确认步骤 01 的 Knowledge 和步骤 02 的 Memory
都已创建或复用且为 `Ready`，再把两个 ID 一次关联到同一个目标 Runtime。只关联
Memory 或只关联 Knowledge 都不能进入步骤 04。

跨会话 Memory 验证还必须在控制台将已准备的 PostgreSQL **会话管理**资源关联到同一
Runtime。当前 CLI 的 `runtime update` 不提供该组件参数，`scripts/bootstrap_platform.py`
只能自动关联 Knowledge/Memory 等 CLI 支持的资源；完成控制台关联后仍需 release 并等待
`Ready/Healthy`。不要查看、复制或手工填写 Runtime 注入的数据库环境变量。

## 必做的控制台会话绑定

在自动脚本关联 Knowledge/Memory 后，继续在控制台完成以下人工步骤：

1. 进入 **AgentKit → 智能体运行时 → 目标 Runtime → 关联组件**；
2. 下滑到 **会话资源** 区域，点击编辑/绑定；
3. 选择步骤 02 创建或导入的 PostgreSQL 会话资源并保存；
4. 返回关联组件页，确认“会话资源”不再为空，且显示刚选择的资源；
5. 点击“发布”（release），等待 Runtime 回到 `Ready/Healthy`。

会话管理首页的“创建会话”只完成资源准备；不执行上述第 1–5 步，Runtime 不会获得
会话注入，也就不能可靠完成跨会话 Memory 验收。

## 自动执行

先用受限字段只读确认所有资源的真实 ID，不要猜测候选。然后按实际资源执行：

```bash
uv run --frozen scripts/bootstrap_platform.py \
  --runtime-id '<runtime-id>' \
  --knowledge-id '<knowledge-id>' \
  --memory-id '<memory-id>' \
  --tool-id '<sandbox-tool-id>' \
  --mcp-toolset-id '<mcp-toolset-id>' \
  --skill-space-id '<ss-skills-space-id>'
```

只提供当前需要的参数。脚本负责关联、release 和状态等待。提供
`--skill-space-id` 时，脚本只变更 `SKILL_SPACE_ID`：它在内存中保留 Runtime 已有的
模型与平台环境变量，且不会输出、写入文件或通过命令行传递这些值。

Skills 需要分别完成两件事：在 Runtime 的**环境变量/密钥配置**中添加
`SKILL_SPACE_ID=<ss-...>`（可使用上述安全脚本），并在 **关联组件**中绑定 Skills Sandbox。
关联 Sandbox 后平台注入对应 Tool ID；它不会替代 Runtime 的 `SKILL_SPACE_ID`。不要调用
`runtime update --envs-json`，该参数会整体替换环境变量并可能删除模型 Key。

## 安全约束

- 不输出完整 Tool JSON、环境变量、Bearer Token 或 API Key；
- 一个类型存在多个候选时先让用户确认；
- 不创建重复资源，不删除现有资源；
- 关联页面显示成功不等于已发布。

## 通过标准

- 目标关联关系与预期一致；
- Runtime 完成 release 并恢复 `Ready/RUNNING/Healthy`；
- 新请求能触发关联能力；
- Runtime 日志或 Trace 提供实际注入和调用证据。
