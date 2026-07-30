# 步骤 06：Skills 中心

## 目标

验证“Skills 中心发布 → Runtime 加载元数据 → Skills Sandbox 隔离执行”完整链路。

## 操作

本 Demo 引用仓库共享目录中的一个可直接发布的自定义 Skill：

```text
../../../skills/byted-customer-service-compliance/
└── SKILL.md
../../../skills/byted-customer-service-compliance.zip  # 控制台直接上传此文件
```

先在本地确认它的格式；这一步不访问平台也不包含凭据：

```bash
uv run --frozen agentkit skills validate \
  --path ../../../skills/byted-customer-service-compliance
```

然后在控制台完成以下人工操作：

1. 进入 **AgentKit → Skills 中心**，创建或选择一个唯一的目标 Skills 空间，记录
   `ss-...` Space ID。
2. 在该空间选择“创建新 Skill → 上传压缩包”，直接上传仓库提供的
   `../../../skills/byted-customer-service-compliance.zip` 并发布。该包解压后仅含一个名为
   `byted-customer-service-compliance` 的目录，且 `SKILL.md` 位于目录根，符合控制台约束。
3. 只有修改了 `SKILL.md` 后，才重新在本地打包并替换 ZIP：

   ```bash
   uv run --frozen agentkit skills pack \
     --path ../../../skills/byted-customer-service-compliance \
     --out ../../../skills/byted-customer-service-compliance.zip
   ```

   不要把项目内的 `.agents/skills/agentkit-hybrid-cloud-demo` 当作平台
   Skill；它是给编码 Agent 使用的项目执行规范，不能替代本步骤的业务 Skill。
4. 等待该 Skill 发布完成，并在空间内确认能看到名称
   `byted-customer-service-compliance`。
5. 创建或编辑用于隔离执行的 **Skills Sandbox**（不要用普通 AIO Sandbox 代替），在它的
   环境变量中填写目标 TOP 的非敏感访问配置：

   ```text
   AGENTKIT_SKILL_HOST=<top-host-with-port-if-required>
   AGENTKIT_TOP_SCHEME=http
   ```

   `AGENTKIT_SKILL_HOST` 填当前混合云 TOP 的主机地址，不带 `http://` 前缀；如环境实际
   使用 HTTPS，按目标环境填写 `https`。不要填写或猜测 `MINIO_*`、Bucket、TOS 路径或长期
   凭据。
6. 在目标 Runtime 的**环境变量/密钥配置**中添加
   `SKILL_SPACE_ID=<ss-...>`。推荐通过步骤 03 的
   `scripts/bootstrap_platform.py --skill-space-id '<ss-...>'` 安全更新：脚本会保留已有
   模型变量，且不显示它们。不要使用部分 `--envs-json`。
7. 在目标 Runtime → **关联组件**中绑定该 **Skills Sandbox**，保存后 release 并等待
   `Ready/Healthy`。该关联提供执行用的 Tool ID；Runtime 的 `SKILL_SPACE_ID` 负责加载
   Skill 元数据，两者缺一不可。
8. 使用交互式验收脚本发起真实 Runtime 调用。Endpoint/API Key 仅作本次子进程的隐藏输入，
   不写入文件或对话：

   ```bash
   ./scripts/verify_skills_interactive.sh --show-response
   ```

   脚本会生成本轮唯一的 `SKILL_CANARY_<id>` 确认码。只有可见响应同时包含
   `byted-customer-service-compliance`、`needs_confirmation` 与该确认码时才会输出 PASS；否则输出
   FAIL 和脱敏的响应摘要。确认码可用于按 user/session 在 Trace 中定位本轮请求。
9. 如需手工复现，明确要求 Agent 调用 `execute_skills`：

```text
请明确调用 execute_skills：按已发布的 byted-customer-service-compliance Skill
检查理财产品退款是否需要人工确认；返回 Skill 名称、合规结论和执行摘要。
```

`SKILL_SPACE_ID` 是空间 ID，不是 Tool ID。平台通过 `AGENTKIT_TOOL_ID` 指向执行
Sandbox。Runtime 会把 Skills Space、TOP 地址与调用范围的临时上下文转交给隔离 Sandbox。
无需手填 `MINIO_*`、Bucket 或 `TOS_SKILLS_DIR`。若控制台的上传流程明确要求对象存储配置，
使用平台管理员提供的配置；不要猜测 Bucket 或向对话发送凭据。
如果此前已被旧版本脚本覆盖模型变量，无法从样例恢复密钥；请在控制台 Secret/密钥配置中
重新设置模型 API Key 后再 release。恢复后使用安全脚本或控制台的“新增/编辑单个变量”方式
添加 `SKILL_SPACE_ID`，不要整体覆盖环境变量。

## 通过标准

- `verify_skills_interactive.sh` 输出 `PASS` 及本轮确认码；

日志或 Trace 同时包含：

- `ListSkillsBySpaceId`；
- `Successfully loaded skill ...`；
- `Invoke run sandbox agent response` 或等价隔离执行证据。

缺少任一段都标记为部分通过。动态创建并上传 Skill 需要平台明确配置可写对象存储，
不属于当前默认验收项，不能猜 Bucket。
