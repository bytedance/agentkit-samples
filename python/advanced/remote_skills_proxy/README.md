# RemoteSkills Proxy

本示例演示 Runtime Agent 如何只暴露 RemoteSkill 的名称、描述和输入 Schema，
真实 Skill 实现仍留在远端 AgentKit Skills Sandbox 中，通过统一 A2A 路径执行。

## 核心边界

- Runtime Agent 只加载 `remote_skills.json`，把每个 RemoteSkill 包装成一个工具。
- Agent 看到的是工具描述和参数 Schema，看不到 `SKILL.md`、脚本、依赖和执行流程。
- 工具被调用时，VeADK 组装 `QueryInput`，并复用 `execute_skills()` 走 Skills Sandbox `/a2a`。
- Skills Sandbox 根据 `skill_name` 在远端选择并执行真实 Skill，然后把结果返回给 Agent。

## 目录结构

```text
remote_skills_proxy/
├── README.md
├── agent.py
├── pyproject.toml
├── remote_skills.json
└── tests/
    └── test_remote_skills_proxy.py
```

## 配置 RemoteSkills

`remote_skills.json` 只放 Agent 可见的元数据：

```json
{
  "remote_skills": [
    {
      "name": "pdf",
      "description": "远程处理 PDF 文档，包括文本和表格提取、生成 PDF、合并拆分、表单识别与填写等批量 PDF 任务。",
      "input_schema": {
        "type": "object",
        "properties": {
          "operation": {"type": "string"},
          "input_files": {"type": "array", "items": {"type": "string"}}
        },
        "required": ["operation"]
      }
    }
  ]
}
```

这个 sample 的 manifest 来自 `agentkit-skill` 镜像内置的本地 Skills：
`docx`、`pdf`、`pptx`、`xlsx`、`tos-file-access`、`skill-creator`。
本地 manifest 不保存这些 Skill 的 `SKILL.md`、脚本或依赖。

## 本地检查

本地检查只验证装配，不会真实访问云端 Skills Sandbox：

```bash
cd python/advanced/remote_skills_proxy
uv run --no-sync python -m unittest discover -s tests -v
```

## 真实调用

### 1. 启动 Runtime Agent

```bash
cd python/advanced/remote_skills_proxy
export VOLCENGINE_ACCESS_KEY=<your-volcengine-access-key>
export VOLCENGINE_SECRET_KEY=<your-volcengine-secret-key>
export AGENTKIT_TOOL_ID_SKILLS=<your-skills-sandbox-tool-id>
export REMOTE_SKILLS_MANIFEST=remote_skills.json
uv run python agent.py
```

启动成功后会看到：

```
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### 2. 创建本地 Session

```bash
curl -sS -X POST \
  http://127.0.0.1:8000/apps/remote_skills_proxy_agent/users/u1/sessions/s1 \
  -H 'Content-Type: application/json' \
  -d '{}'
```

成功返回：

```json
{"id":"s1","appName":"remote_skills_proxy_agent","userId":"u1","state":{},"events":[],"lastUpdateTime":...}
```

### 3. 发起 RemoteSkill 调用

下面用 `docx` 这个 RemoteSkill 举例。该请求会让远端 Skills Sandbox 创建一个法律文书风格的文档。

```bash
curl -N -X POST http://127.0.0.1:8000/run_sse \
  -H 'Content-Type: application/json' \
  -d '{
    "appName": "remote_skills_proxy_agent",
    "userId": "u1",
    "sessionId": "s1",
    "newMessage": {
      "role": "user",
      "parts": [
        {
          "text": "用 docx skill 创建一个法律文书风格的文档"
        }
      ]
    },
    "streaming": true
  }'
```

### 预期现象

- 本地 Runtime Agent 会收到 `/run_sse` 请求。
- Agent 根据 `remote_skills.json` 选择 `docx` 工具。
- `remote_skill` 工具内部调用 `execute_skills()`。
- `execute_skills()` 再向远端 Skills Sandbox 的 `/a2a` 发送 `message/send`，并通过 `tasks/get` 轮询结果。

工具内部发送给远端沙箱的 `QueryInput` 形如：

```json
{
  "skill_name": "pdf",
  "query": "提取这份 PDF 的表格，并输出为 Markdown 表格",
  "arguments": {
    "operation": "extract",
    "input_files": ["/home/gem/workspace/report.pdf"],
    "output_requirements": "返回 Markdown 表格和关键结论"
  },
  "request_id": "req_xxx"
}
```

## 设计取舍

这个方案适合需要保护 Skill 实现、依赖和执行流程的场景。它不适合高频低延迟
的小函数调用，因为每次调用都要经过远端 Sandbox 和 A2A 任务轮询。
