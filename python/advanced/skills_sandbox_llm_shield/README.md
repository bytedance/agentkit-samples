# Skills Sandbox + LLM Shield

本示例展示如何在 AgentKit Runtime 中同时接入 Skills Sandbox，并用环境变量开启大模型防火墙（LLM Shield）。

默认配置是安全的：`execute_skills` 不会暴露给 Agent，LLM Shield 也不会启用。完成 Runtime 组件绑定并确认要真实调用后，再显式打开开关。

## 能力边界

- `SKILL_SPACE_ID` 指向 AgentKit Skills 空间，用于加载已发布 Skill 的元数据。
- `AGENTKIT_TOOL_ID` 指向 Runtime 关联的 Skills Sandbox Tool，用于执行 `execute_skills`。
- `AGENTKIT_TOOL_ID_SKILLS` 只作为兼容别名；新样例优先使用 `AGENTKIT_TOOL_ID`。
- `ENABLE_SKILL_SANDBOX=true` 且 `EXPOSE_SKILL_SANDBOX_TO_AGENT=true` 时，才会把 `execute_skills` 加入 Agent tools。
- `ENABLE_LLM_SHIELD=true` 时，需要设置 `TOOL_LLM_SHIELD_APP_ID`，Agent 才会注册 `content_safety.before_model_callback`。

## 本地运行

```bash
cd python/advanced/skills_sandbox_llm_shield
python3 -m unittest discover -s tests -v
uv sync
uv run python agent.py
```

本地只做装配和配置检查时，可以不设置真实云资源。要真实调用 Skills Sandbox，需要先配置：

```bash
export ENABLE_SKILL_SANDBOX=true
export EXPOSE_SKILL_SANDBOX_TO_AGENT=true
export AGENTKIT_TOOL_ID=<your-skills-sandbox-tool-id>
export SKILL_SPACE_ID=<your-skill-space-id>
```

要开启大模型防火墙：

```bash
export ENABLE_LLM_SHIELD=true
export TOOL_LLM_SHIELD_APP_ID=<your-llm-shield-app-id>
```

如果你的运行环境要求额外的 LLM Shield API Key，请通过 AgentKit 控制台、凭证托管或部署时密钥注入提供，不要写入源码或 README。

## AgentKit 部署

`agentkit.yaml` 中只包含占位符和默认关闭的开关。部署前通过 AgentKit 控制台或 CLI 完成两类绑定：

1. 在 Runtime 关联 Skills Sandbox Tool，得到 `AGENTKIT_TOOL_ID`。
2. 在 Runtime 环境变量中设置 `SKILL_SPACE_ID`。
3. 如需 LLM Shield，在 Runtime 关联或配置防火墙应用，并设置 `ENABLE_LLM_SHIELD=true` 与 `TOOL_LLM_SHIELD_APP_ID`。
4. 确认真实调用后，再设置 `ENABLE_SKILL_SANDBOX=true` 与 `EXPOSE_SKILL_SANDBOX_TO_AGENT=true`。

建议先部署默认关闭版本，调用 `check_skill_sandbox` 和 `check_llm_shield` 查看配置状态，再打开真实执行能力。
