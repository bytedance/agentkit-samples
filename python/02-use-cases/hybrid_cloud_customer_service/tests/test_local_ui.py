from __future__ import annotations

import csv
import os
import re
import subprocess
from pathlib import Path

import local_ui
import pytest
from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class FakeResponse:
    headers = {"content-type": "text/event-stream"}

    def raise_for_status(self) -> None:
        return None

    def iter_lines(self, decode_unicode: bool = False):
        assert decode_unicode is True
        return iter(
            [
                'data: {"content":{"parts":[{"text":"internal", "thought":true}]}}',
                'data: {"content":{"parts":[{"text":"最终回答"}]}}',
            ]
        )


class FakeJsonResponse:
    headers = {"content-type": "application/json; charset=utf-8"}

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return {
            "answer": "根据已发布规则，申请后按客户确认的方式到账。",
            "session_id": "runtime-session",
            "trace_id": "runtime-trace",
            "mode": "demo",
            "citations": [{"title": "退款规则"}],
            "events": [{"name": "knowledge.search", "status": "succeeded"}],
        }


class CloseTrackingResponse(FakeResponse):
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class FailingCloseTrackingResponse(CloseTrackingResponse):
    def raise_for_status(self) -> None:
        raise local_ui.requests.ConnectionError("Runtime unavailable")


def test_remote_ui_closes_response_after_success(monkeypatch) -> None:
    monkeypatch.setenv("RUNTIME_ENDPOINT", "https://runtime.example/")
    monkeypatch.setenv("RUNTIME_API_KEY", "test-key")
    response = CloseTrackingResponse()
    monkeypatch.setattr(local_ui.requests, "post", lambda *args, **kwargs: response)

    local_ui.chat(local_ui.LocalChatRequest(message="测试"))

    assert response.closed is True


def test_remote_ui_closes_response_after_http_error(monkeypatch) -> None:
    monkeypatch.setenv("RUNTIME_ENDPOINT", "https://runtime.example/")
    monkeypatch.setenv("RUNTIME_API_KEY", "test-key")
    response = FailingCloseTrackingResponse()
    monkeypatch.setattr(local_ui.requests, "post", lambda *args, **kwargs: response)

    with pytest.raises(local_ui.HTTPException) as exc_info:
        local_ui.chat(local_ui.LocalChatRequest(message="测试"))

    assert exc_info.value.status_code == 502
    assert response.closed is True


def test_remote_ui_omits_model_thought(monkeypatch) -> None:
    monkeypatch.setenv("RUNTIME_ENDPOINT", "https://runtime.example/")
    monkeypatch.setenv("RUNTIME_API_KEY", "test-key")
    monkeypatch.setattr(local_ui.requests, "post", lambda *args, **kwargs: FakeResponse())

    result = local_ui.chat(local_ui.LocalChatRequest(message="测试"))

    assert result["answer"] == "最终回答"
    assert result["thoughts"] == ["internal"]
    assert result["transport"] == "remote"
    assert result["runtime_endpoint"] == "https://runtime.example"


def test_remote_ui_accepts_runtime_json_response(monkeypatch) -> None:
    monkeypatch.setenv("RUNTIME_ENDPOINT", "https://runtime.example/")
    monkeypatch.setenv("RUNTIME_API_KEY", "test-key")
    monkeypatch.setattr(local_ui.requests, "post", lambda *args, **kwargs: FakeJsonResponse())

    result = local_ui.chat(local_ui.LocalChatRequest(message="退款多久到账？"))
    response = TestClient(local_ui.app).post("/ui/chat/stream", json={"message": "退款多久到账？"})

    assert result["answer"] == "根据已发布规则，申请后按客户确认的方式到账。"
    assert result["trace_id"] == "runtime-trace"
    assert result["citations"] == [{"title": "退款规则"}]
    assert result["transport"] == "remote"
    assert result["runtime_endpoint"] == "https://runtime.example"
    assert response.status_code == 200
    assert "event: answer" in response.text
    assert "根据已发布规则" in response.text
    assert "event: done" in response.text
    assert '"transport": "remote"' in response.text
    assert "Runtime 未返回可展示的文本" not in response.text


def test_remote_ui_forwards_incremental_sse(monkeypatch) -> None:
    monkeypatch.setenv("RUNTIME_ENDPOINT", "https://runtime.example/")
    monkeypatch.setenv("RUNTIME_API_KEY", "test-key")
    monkeypatch.setattr(local_ui.requests, "post", lambda *args, **kwargs: FakeResponse())

    response = TestClient(local_ui.app).post("/ui/chat/stream", json={"message": "测试"})

    assert response.status_code == 200
    assert "event: thought" in response.text
    assert "event: answer" in response.text
    assert "event: done" in response.text


def test_remote_ui_requires_api_key(monkeypatch) -> None:
    monkeypatch.setenv("RUNTIME_ENDPOINT", "https://runtime.example/")
    monkeypatch.delenv("RUNTIME_API_KEY", raising=False)

    response = TestClient(local_ui.app).post("/ui/chat/stream", json={"message": "测试"})

    assert response.status_code == 200
    assert "RUNTIME_API_KEY is missing" in response.text


def test_local_demo_is_explicitly_marked_as_local_transport(monkeypatch) -> None:
    monkeypatch.delenv("RUNTIME_ENDPOINT", raising=False)
    monkeypatch.delenv("RUNTIME_API_KEY", raising=False)

    result = local_ui.chat(local_ui.LocalChatRequest(message="你是谁"))

    assert result["mode"] == "demo"
    assert result["transport"] == "local"
    assert "runtime_endpoint" not in result


def test_runtime_config_is_process_local_and_never_returns_key(monkeypatch) -> None:
    monkeypatch.delenv("RUNTIME_ENDPOINT", raising=False)
    monkeypatch.delenv("RUNTIME_API_KEY", raising=False)
    client = TestClient(local_ui.app)

    response = client.post(
        "/ui/runtime-config",
        json={"endpoint": "https://runtime.example/invoke", "api_key": "secret-key"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "remote": True,
        "endpoint": "https://runtime.example",
        "api_key_configured": True,
        "source": "ui-session",
    }
    assert "secret-key" not in client.get("/ui/config").text
    client.delete("/ui/runtime-config")


def test_chat_keeps_only_sessions_connection_and_conversation_ui() -> None:
    client = TestClient(local_ui.app)

    index = client.get("/chat")
    app_js = client.get("/web/app.js")

    assert index.status_code == 200
    assert 'aria-label="本地会话"' in index.text
    assert 'id="new-session"' in index.text
    assert 'id="runtime-config-open"' in index.text
    assert 'id="messages"' in index.text
    assert 'id="composer"' in index.text
    assert 'id="message"' in index.text
    assert 'id="send"' in index.text
    assert "nav-item" not in index.text
    assert 'class="inspector"' not in index.text
    assert 'class="prompt-strip"' not in index.text
    assert 'id="a2ui-mode"' not in index.text
    assert 'id="module-dialog"' not in index.text
    assert 'id="trace-dialog"' not in index.text
    assert "agentkit-chat-sessions-v3" in app_js.text


def test_chat_does_not_render_deployment_modules() -> None:
    client = TestClient(local_ui.app)
    index_text = client.get("/chat").text

    assert not re.findall(r'data-module="([a-z0-9_]+)"', index_text)
    assert "能力调用链" not in index_text
    assert "知识引用" not in index_text
    assert "离线评测" not in index_text


def test_public_guides_use_hybrid_cloud_backends_and_sanitized_trace_data() -> None:
    readme = (PROJECT_ROOT / "README.md").read_text()
    app_js = (PROJECT_ROOT / "web/app.js").read_text()
    bootstrap = (PROJECT_ROOT / "scripts/bootstrap_platform.py").read_text()

    assert "云搜索" in readme
    assert "MEM0" in readme
    assert "provider-knowledge-id" not in bootstrap
    assert '"runtime",\n        "release",' in bootstrap
    assert "--tool-id" in bootstrap
    assert "--mcp-toolset-id" in bootstrap
    assert "--skill-space-id" in bootstrap
    assert "merge_runtime_envs" in bootstrap
    assert '"--envs-json",' not in bootstrap
    assert 'status == "Ready"' in bootstrap
    assert '"--provider-type",\n            "MEM0",' in bootstrap
    assert '"--status",\n            "Ready",' in bootstrap
    assert "Trace ID：<platform-trace-id>" in app_js
    assert "openai/<model-endpoint>" in app_js


def test_runtime_deployment_guide_uses_environment_specific_openapi_host() -> None:
    client = TestClient(local_ui.app)
    index = client.get("/").text
    app_js = client.get("/guide/app.js").text
    readme = (PROJECT_ROOT / "README.md").read_text()
    deployment = (PROJECT_ROOT / "docs/runtime_deployment.md").read_text()
    configure_script = (PROJECT_ROOT / "scripts/configure_agentkit_cli.sh.example").read_text()
    deploy_script = (PROJECT_ROOT / "scripts/deploy_hybrid.sh").read_text()
    interactive_deploy = (PROJECT_ROOT / "scripts/deploy_interactive.sh").read_text()
    a2a_deploy = (PROJECT_ROOT / "scripts/deploy_a2a_interactive.sh").read_text()
    a2a_peer_deploy = (PROJECT_ROOT / "scripts/configure_a2a_peer_interactive.sh").read_text()
    a2a_verify = (PROJECT_ROOT / "scripts/verify_a2a_interactive.sh").read_text()
    oauth_deploy = (PROJECT_ROOT / "scripts/deploy_oauth_interactive.sh").read_text()
    oauth_verify = (PROJECT_ROOT / "scripts/verify_oauth_interactive.sh").read_text()
    oauth_verify_py = (PROJECT_ROOT / "scripts/verify_oauth.py").read_text()
    oauth_cli_compat = (PROJECT_ROOT / "scripts/agentkit_cli_poc.py").read_text()
    agentkit_config = (PROJECT_ROOT / "agentkit.yaml.example").read_text()
    dockerfile = (PROJECT_ROOT / "Dockerfile").read_text()
    requirements_lock = (PROJECT_ROOT / "requirements.lock").read_text()

    assert 'data-step="runtime"' in index
    assert "id: 'runtime'" in app_js
    assert "首次部署已经完成，现在不要重复执行" in app_js
    assert "智能体运行时部署" in readme
    assert "https://astral.sh/uv/install.sh" in readme
    assert "uv run --frozen --extra dev pytest -q" in readme
    assert "python -m venv .venv" not in readme
    assert "pip install -r requirements.txt" not in readme
    assert "${AGENTKIT_OPENAPI_SCHEME}://${AGENTKIT_OPENAPI_HOST}/ping" in deployment
    assert 'COMMON_HOST="${AGENTKIT_OPENAPI_HOST:?' in configure_script
    assert 'COMMON_SCHEME="${AGENTKIT_OPENAPI_SCHEME:-http}"' in configure_script
    assert 'set_config "services.agentkit.scheme" "${COMMON_SCHEME}"' in configure_script
    assert "agentkit launch" in deploy_script
    assert "scripts/deploy_interactive.sh" in readme
    assert "scripts/deploy_a2a_interactive.sh" in readme
    assert "read -r -s -p" in interactive_deploy
    assert "OpenAPI 协议 [http]" in interactive_deploy
    assert (
        "OpenAPI 域名（通常为 openapi.<environment-domain>，不含协议和路径）" in interactive_deploy
    )
    assert "目标环境 Access Key（输入不可见）" in interactive_deploy
    assert "目标环境 Secret Key（输入不可见）" in interactive_deploy
    assert "Access Key / Secret Key：平台右上角用户账号 → 访问控制 → 密钥管理" in interactive_deploy
    assert "运维端 → 账户 → 关于 → 查看地域" in interactive_deploy
    assert "平台已创建 Runtime 的环境变量 REGION" in interactive_deploy
    assert "模型配置说明" in interactive_deploy
    assert "复用已有 CLI 配置" in interactive_deploy
    assert "仅供参考，不会自动采用" in interactive_deploy
    assert "MODEL_AGENT_API_KEY" in interactive_deploy
    assert 'exec bash "${PROJECT_ROOT}/scripts/deploy_hybrid.sh"' in interactive_deploy
    assert "AGENT_APP_MODE" in a2a_deploy
    assert "a2a_data_analyst" in a2a_deploy
    assert "hybrid-cloud-customer-service-a2a" in a2a_deploy
    assert "AGENTKIT_MODEL_REQUIRED=1" in a2a_deploy
    assert "A2A_AGENT_NAME" in a2a_deploy
    assert "A2A_AGENT_SKILL_ID" in a2a_deploy
    assert "AgentCard 能力 ID" in a2a_deploy
    assert "AGENTKIT_POST_DEPLOY_INVOKE=0" in a2a_deploy
    assert "configure_a2a_peer.py" in a2a_peer_deploy
    assert "discover_a2a_card.py" in a2a_peer_deploy
    assert "AgentCard 能力 ID" in a2a_peer_deploy
    assert "--capability-id" in a2a_peer_deploy
    assert "要委派的 Skill ID" not in a2a_peer_deploy
    assert 'read -r -s -p "数据 Agent Runtime API Key' in a2a_peer_deploy
    assert "确认继续 [y/N]" in a2a_peer_deploy
    assert "verify_a2a.py" in a2a_verify
    assert "Data Runtime API Key" in a2a_verify
    assert "AgentCard 能力 ID" in a2a_verify
    assert "hybrid-cloud-customer-service-oauth" in oauth_deploy
    assert 'runtime_auth_type"] = "custom_jwt"' in oauth_deploy
    assert "runtime_jwt_discovery_url" in oauth_deploy
    assert "runtime_jwt_allowed_clients" in oauth_deploy
    assert "oauth_runtime_id == primary_runtime_id" in oauth_deploy
    assert "AGENTKIT_POST_DEPLOY_INVOKE=0" in oauth_deploy
    assert "Client Secret 不属于部署配置" in oauth_deploy
    assert "AGENTKIT_ALLOW_HTTP_OIDC=1" in oauth_deploy
    assert "正式环境必须使用 HTTPS" in oauth_deploy
    assert "HybridStrategyConfig" in oauth_cli_compat
    assert 'rule["pattern"] = r"^https?://.+"' in oauth_cli_compat
    assert "AGENTKIT_ALLOW_HTTP_OIDC" in deploy_script
    assert "run_project_agentkit launch" in deploy_script
    assert "项目 Runtime Region 写入失败" in deploy_script
    assert (
        '"${configured_scheme}://${configured_host}/ping" >"${PING_RESPONSE_FILE}"' in deploy_script
    )
    assert 'grep --quiet \'"pong"\' "${PING_RESPONSE_FILE}"' in deploy_script
    assert "read -r -s -p" in oauth_verify
    assert "OAUTH_CLIENT_SECRET" in oauth_verify
    assert "--negative-checks" in oauth_verify_py
    assert "OAuth Runtime invoke" in oauth_verify_py
    assert "invalid credential" in oauth_verify_py
    assert "missing credential" in oauth_verify_py
    assert "uv sync --frozen --extra dev" in deploy_script
    assert "export AGENTKIT_OPENAPI_HOST" not in app_js
    assert "--platform linux/amd64" in deploy_script
    assert "--preflight-mode skip" in deploy_script
    assert "agentkit invoke" in deploy_script
    assert "AGENTKIT_POST_DEPLOY_INVOKE" in deploy_script
    assert "AGENTKIT_MODEL_REQUIRED" in deploy_script
    assert "退款多久到账？" in deploy_script
    assert "docker.from_env()" in deploy_script
    assert 'PROJECT_REGION="${VOLCENGINE_REGION:-}"' in deploy_script
    assert "不会静默用于本次 Runtime 部署" in deploy_script
    assert "token expired" in deploy_script
    assert "Login Succeeded" in deploy_script
    assert "agentkit runtime list" in deploy_script
    assert "AGENTKIT_RUNTIME_ID" in deploy_script
    assert "InvalidParameter[.]DuplicateName" in deploy_script
    assert 'hybrid["runtime_id"] = runtime_id' in deploy_script
    assert 'hybrid["runtime_name"] = runtime_name' in deploy_script
    assert "输入新名称并创建独立 Runtime" in deploy_script
    assert "1–63 位小写字母、数字或连字符" in deploy_script
    assert "名称查重失败" in deploy_script
    assert 'AGENTKIT_EXISTING_RUNTIME_ACTION="prompt"' in interactive_deploy
    assert '"region"' in deploy_script
    assert '--region "${PROJECT_REGION}"' in deploy_script
    assert "AGENTKIT_CR_REGISTRY" not in deploy_script
    assert "common:" in agentkit_config
    assert "launch_types:" in agentkit_config
    assert "cr_instance_name: cr-basic" in agentkit_config
    assert "DEMO_MODE: live" in agentkit_config
    assert "MODEL_AGENT_API_KEY" not in agentkit_config
    assert 'DEPLOY_MODE="${AGENTKIT_DEPLOY_MODE:-live}"' in deploy_script
    assert "missing_model_vars" in deploy_script
    assert "deepseek-v4-pro-260425" in deploy_script
    assert 'runtime_envs["MODEL_AGENT_API_BASE"]' in deploy_script
    assert "Checking AgentKit control-plane credentials" in deploy_script
    assert 'run_project_agentkit runtime list >"${AUTH_CHECK_FILE}" 2>&1' in deploy_script
    assert "控制面 AK/SK 鉴权失败" in deploy_script
    assert "未进入镜像构建或 Runtime 创建阶段" in deploy_script
    assert "TOP 详细错误（凭证与签名值已脱敏）" in deploy_script
    assert "RequestId" in deploy_script
    assert "凭证与签名值已脱敏" in deploy_script
    assert '[[ "${1:-}" = "launch"' in deploy_script
    assert "AGENTKIT_VERBOSE_DOCKER_LOGS=1 PYTHONUNBUFFERED=1" in deploy_script
    assert "live lines are prefixed with [docker]" in deploy_script
    assert "mktemp" in deploy_script
    assert "AGENTKIT_DEPLOY_MODE=demo" in deploy_script
    assert ".agentkit-deploy.*" in (PROJECT_ROOT / ".dockerignore").read_text()
    assert "COPY requirements.lock ./" in dockerfile
    assert "ARG RUNTIME_PLATFORM=linux/amd64" in dockerfile
    assert (
        "FROM --platform=${RUNTIME_PLATFORM} python:3.12-slim@sha256:"
        "cab2dbf575e971934a81e4622f5aba17aa7929719bd7e31033a3a83b97fd0464" in dockerfile
    )
    assert "pip install --no-cache-dir -r requirements.lock" in dockerfile
    assert "`[docker]`" in deployment
    assert "pip install --no-cache-dir -r requirements.txt" not in dockerfile
    assert "agentkit-sdk-python==0.8.1" in requirements_lock
    assert "google-adk==2.2.0" in requirements_lock
    assert "veadk-python==1.0.10" in requirements_lock
    assert "uv export --frozen --no-hashes --no-dev --no-emit-project" in requirements_lock
    assert "requirements.lock" not in (PROJECT_ROOT / ".dockerignore").read_text()
    assert "临时访问指令" in deployment
    assert "Login Succeeded" in deployment
    assert "人工刷新不是违规操作，而是必要恢复路径" in deployment
    assert "直接输入新名称" in deployment
    assert "--fields ToolId,Name,ToolType,Status" in deployment
    assert "curl -k" in deployment
    assert "不能作为用户部署方案" in deployment
    assert "VAE" not in readme
    assert "VAE" not in deployment
    fixed_demo_host = "top." + "vestack.cloud"
    assert fixed_demo_host not in app_js + readme + deployment + configure_script


def test_compact_chat_keeps_streaming_support_without_preset_prompts() -> None:
    client = TestClient(local_ui.app)

    index = client.get("/chat")
    app_js = client.get("/web/app.js")

    assert index.status_code == 200
    assert ">身份自检</button>" not in index.text
    assert "data-prompt=" not in index.text
    assert "你好，有什么可以帮助你？" in app_js.text
    assert "远端 SSE 会被解析为最终回答" in index.text
    assert "核对 Trace 与 Claim 边界" in app_js.text
    identity_panel = app_js.text.split("  identity: {", 1)[1].split("  session: {", 1)[0]
    knowledge_panel = app_js.text.split("  knowledge: {", 1)[1].split("  memory: {", 1)[0]
    assert "请求范围内传递 Bearer 凭据" not in identity_panel
    assert "供知识库适配器调用" not in identity_panel
    assert "deploy_oauth_interactive.sh" in identity_panel
    assert "verify_oauth_interactive.sh --show-response" in identity_panel
    assert "RUNTIME_API_KEY" not in identity_panel
    assert "hybrid-cloud-customer-service-oauth" in identity_panel
    assert "Backend 从当前请求读取 Bearer 凭据" in knowledge_panel


def test_observability_guidance_is_not_rendered_in_compact_chat() -> None:
    client = TestClient(local_ui.app)

    index = client.get("/chat")
    app_js = client.get("/web/app.js")

    assert 'data-module="observability"' not in index.text
    assert "查看本次本地 UI 会话收集的 Trace 历史" not in index.text
    assert "observability: {" in app_js.text
    assert "traceBadge.addEventListener('click', openTrace)" not in app_js.text


def test_default_route_is_the_step_by_step_deployment_guide() -> None:
    client = TestClient(local_ui.app)

    index = client.get("/")
    app_js = client.get("/guide/app.js")
    styles = client.get("/guide/styles.css")

    assert index.status_code == 200
    assert app_js.status_code == 200
    assert styles.status_code == 200
    assert "一个客服智能体的建设路径" in index.text
    assert 'data-step="runtime"' in index.text
    assert 'data-step="memory"' in index.text
    assert "下一步 →" in index.text
    assert "textarea" not in index.text


def test_roadmap_summaries_align_to_readme_and_offer_copyable_codex_prompts() -> None:
    client = TestClient(local_ui.app)
    index = client.get("/").text
    app_js = client.get("/guide/app.js").text

    assert index.count('class="step-card') == 7
    assert 'id="detail-readme-sections"' in index
    assert 'id="detail-prompts"' in index
    assert "7 个阶段按安全优先顺序展开" in index
    assert "首次部署不用 Prompt，后续步骤交给项目 Skill" in index
    assert "任何能读取仓库和执行终端命令的智能编码 Agent" in index
    assert "交给智能编码 Agent" in index
    assert "复制 Prompt" in app_js
    assert "navigator.clipboard.writeText" in app_js
    for label in (
        "现在建议执行：验收首次部署",
        "以后有变更时：更新已有 Runtime",
        "先执行：创建并发布 Knowledge",
        "再执行：创建或复用 Memory",
        "先执行：关联 Knowledge 与 Memory",
        "关联后执行：验证 Knowledge 与 Memory",
        "步骤 05：Sandbox 与 MCP",
        "步骤 06：Skill 中心",
        "步骤 07：A2A 外部 Agent",
        "步骤 07：身份与安全边界",
        "步骤 08：评测、Trace 与发布验收",
    ):
        assert label in app_js
    assert "不要输出或写入任何 AK/SK" in app_js
    assert "不要猜 ID" in app_js
    assert "不要猜 MinIO Bucket" in app_js
    assert "不要用其他相近或通用 AgentKit 工作流替代" in app_js
    assert "无需安装 Codex" in app_js
    assert "AGENTS.md" in app_js
    assert ".agents/skills/agentkit-hybrid-cloud-demo/SKILL.md" in app_js
    assert "提示我打开完整的 hybrid_cloud_customer_service Demo 目录" in app_js
    assert "不会重新部署" in app_js
    assert "现在可以跳过" in app_js
    assert "验收 Runtime，按需更新" in index
    assert index.index('data-step="knowledge"') < index.index('data-step="memory"')
    assert index.index('data-step="memory"') < index.index('data-step="actions"')
    assert app_js.index("id: 'knowledge'") < app_js.index("id: 'memory'")
    assert "promptKeys: ['knowledge']" in app_js
    assert "promptKeys: ['memory']" in app_js
    assert "promptKeys: ['associate', 'verify']" in app_js
    assert "promptKeys: ['identity']" in app_js
    assert "deploy_oauth_interactive.sh" in app_js
    assert "verify_oauth_interactive.sh --show-response" in app_js
    assert "hybrid-cloud-customer-service-oauth" in app_js
    assert "Bearer Token 调用" in app_js
    assert "--negative-checks" in app_js
    assert "promptKeys: ['sandboxMcp', 'skills', 'a2a']" in app_js
    assert "A2A 完整部署与验收" in app_js
    assert "数据 Agent（AgentCard / message-send）" in app_js
    assert "主 Runtime A2A 委派客户端" in app_js
    assert "安全配置主 Runtime 对端" in app_js
    assert "verify_a2a_interactive.sh --show-response" in app_js
    assert "A2A_CANARY" in app_js
    assert "promptKeys: ['quality']" in app_js
    assert "Knowledge 和 Memory 均已创建且 Ready" in app_js
    assert "不要把预期阻塞写成新的 FAQ" in app_js
    assert "verify_knowledge_memory_interactive.sh" in app_js
    assert "当前 OpenAPI 已指向混合云 Knowledge" in app_js
    assert "不要用它过滤混合云资源" in app_js
    assert "ProviderType 为空" in app_js
    assert "Ready + MEM0" in app_js
    assert "PostgreSQL 会话管理" in app_js
    assert "目标 Runtime → 关联组件 → 会话资源" in app_js
    assert "../../../skills/byted-customer-service-compliance/SKILL.md" in app_js
    assert "../../../skills/byted-customer-service-compliance.zip" in app_js
    assert "agentkit skills pack" in app_js
    assert "AGENTKIT_SKILL_HOST=<top-host>" in app_js
    assert "bootstrap_platform.py --skill-space-id" in app_js
    assert "verify_skills_interactive.sh" in app_js


def test_deployed_agent_chat_is_preserved_at_chat_route() -> None:
    client = TestClient(local_ui.app)

    chat = client.get("/chat")

    assert chat.status_code == 200
    assert "AgentKit Chat" in chat.text
    assert 'aria-label="本地会话"' in chat.text
    assert "连接配置" in chat.text
    assert "能力调用链" not in chat.text
    assert client.get("/web/app.js").status_code == 200
    assert client.get("/guide/not-allowed.js").status_code == 404
    assert "尚未调用验证" in chat.text
    assert "Runtime Ready" not in chat.text


def test_chat_distinguishes_remote_transport_from_runtime_data_mode() -> None:
    client = TestClient(local_ui.app)
    index = client.get("/chat").text
    app_js = client.get("/web/app.js").text
    readme = (PROJECT_ROOT / "README.md").read_text()
    deployment = (PROJECT_ROOT / "docs/runtime_deployment.md").read_text()
    runtime_step = (PROJECT_ROOT / "docs/steps/00-runtime.md").read_text()

    assert "保存只表示配置进入 BFF" in index
    assert "远端 Runtime · Demo" in app_js
    assert "远端 Runtime · Live" in app_js
    assert "data.transport === 'remote'" in app_js
    assert "startConnectionSession('远端连接验证')" in app_js
    assert "不调用模型，也不会产生平台 LLM Span" in app_js
    assert "尚未产生调用证据" not in index
    assert "<summary><strong>部署后连接 Chat</strong></summary>" in readme
    assert "`远端 Runtime · Demo`" in readme
    assert "`远端 Runtime · Demo` 只证明远端路由" in runtime_step
    assert "Agent/Workflow/LLM Span、模型、Token 和耗时" in runtime_step
    assert "快速调用" in deployment
    assert "保存连接配置只表示 Endpoint/Key 已进入本地 BFF 内存" in deployment
    assert "响应中的 `trace-...` 是应用演示 ID，不是平台 Trace ID" in deployment


def test_readme_starts_with_interactive_deploy_then_routes_to_skill_prompts() -> None:
    readme = (PROJECT_ROOT / "README.md").read_text()
    app_js = (PROJECT_ROOT / "guide_web/app.js").read_text()
    skill = (PROJECT_ROOT / ".agents/skills/agentkit-hybrid-cloud-demo/SKILL.md").read_text()

    agents = (PROJECT_ROOT / "AGENTS.md").read_text()

    assert readme.index("## 第一步：交互部署 Live Runtime") < readme.index(
        "## 第二步：打开智能体建设路线图"
    )
    assert readme.index("## 第二步：打开智能体建设路线图") < readme.index(
        "## 第三步：用项目 Skill 执行路线图 Prompt"
    )
    assert len(readme.splitlines()) < 260
    assert "旧任务不会刷新 Skill 列表" in readme
    assert "agentkit-veadk-codex-runtime" not in readme
    assert "首次部署不需要 Prompt" in readme
    assert "不要求提前 `export`" in readme
    assert readme.count("./scripts/deploy_interactive.sh") == 1
    assert "<details>" in readme
    assert "<summary><strong>自动化 / CI：非交互变量方式</strong></summary>" in readme
    assert ".agents/skills/agentkit-hybrid-cloud-demo/SKILL.md" in agents
    assert "Do not substitute another similarly named" in agents
    assert "./scripts/install_codex_skill.sh" in readme
    assert "./scripts/install_codex_skill.sh --update" in readme
    step_documents = (
        "00-runtime.md",
        "01-knowledge.md",
        "02-memory.md",
        "03-runtime-association.md",
        "04-knowledge-memory-validation.md",
        "05-sandbox-mcp.md",
        "06-skills.md",
        "07-a2a-identity-session.md",
        "08-evaluation-observability.md",
    )
    for document in step_documents:
        assert f"docs/steps/{document}" in readme
        assert (PROJECT_ROOT / "docs/steps" / document).is_file()
        assert f"docs/steps/{document}" in skill
    assert app_js.count("请按上述项目 Skill 执行 docs/steps/") == 9
    assert "scripts/deploy_hybrid.sh" in skill
    assert "scripts/deploy_a2a_interactive.sh" in skill
    assert "scripts/configure_a2a_peer_interactive.sh" in skill
    assert "scripts/deploy_oauth_interactive.sh" in skill
    assert "scripts/verify_oauth_interactive.sh" in skill
    assert "scripts/bootstrap_platform.py" in skill
    assert "scripts/verify_knowledge_memory_interactive.sh" in skill
    assert "Never write or print AK/SK" in skill


def test_evaluation_customer_flow_uses_csv_and_actual_template_choices() -> None:
    dataset = PROJECT_ROOT / "evaluation/hybrid_customer_service_runtime_core_v1.csv"
    with dataset.open(newline="") as stream:
        rows = list(csv.DictReader(stream))

    assert len(rows) == 4
    assert set(rows[0]) == {"input", "reference_output"}

    step = (PROJECT_ROOT / "docs/steps/08-evaluation-observability.md").read_text()
    app_js = (PROJECT_ROOT / "guide_web/app.js").read_text()
    assert "**正确性**”模板" in step
    assert "自定义创建 Code 评估器" in step
    assert "不需要填写模型 Key" in step
    assert "hybrid_customer_service_runtime_core_v1.csv" in app_js
    assert "Code 门禁实验" in app_js
    assert "默认台湾示例" in app_js
    assert "一次只能保留一份完整 JSON" in app_js
    assert "绝不能在第一份 JSON 后追加第二份" in step


def test_codex_skill_installer_is_safe_and_update_is_explicit(tmp_path: Path) -> None:
    installer = PROJECT_ROOT / "scripts/install_codex_skill.sh"
    codex_home = tmp_path / "codex"
    environment = os.environ | {"CODEX_HOME": str(codex_home)}

    installed = subprocess.run(
        [str(installer)],
        cwd=PROJECT_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    destination = codex_home / "skills/agentkit-hybrid-cloud-demo"

    assert installed.returncode == 0
    assert (destination / "SKILL.md").is_file()
    assert "Start a new Codex task" in installed.stdout

    current = subprocess.run(
        [str(installer)],
        cwd=PROJECT_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert current.returncode == 0
    assert "already up to date" in current.stdout

    (destination / "SKILL.md").write_text("different installed version\n")
    guarded = subprocess.run(
        [str(installer)],
        cwd=PROJECT_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert guarded.returncode == 2
    assert "--update" in guarded.stderr

    updated = subprocess.run(
        [str(installer), "--update"],
        cwd=PROJECT_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert updated.returncode == 0
    assert (destination / "SKILL.md").read_text().startswith("---\nname:")
    assert list((codex_home / "skill-backups").glob("agentkit-hybrid-cloud-demo.*"))
    assert not list((codex_home / "skills").glob("agentkit-hybrid-cloud-demo.backup.*"))
