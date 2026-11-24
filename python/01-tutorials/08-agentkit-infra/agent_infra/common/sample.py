"""三个模式共用的命令入口、配置隔离和控制面步骤。"""

import argparse
import json
import os
import subprocess
import sys
import uuid
from dataclasses import replace
from pathlib import Path
from tempfile import NamedTemporaryFile

ROOT = Path(__file__).resolve().parents[1]
INFRA = ROOT.parent
sys.path.insert(0, str(INFRA / "resource_to_chat_http"))

from _clients import HarnessInfraError, TopClient  # noqa: E402
from _common import load_state, new_state, run, save_state, state_path  # noqa: E402
from _config import validated_config  # noqa: E402
from _workflow import (  # noqa: E402
    _create_session_store,
    _not_found,
    _prepare_endpoint,
    cleanup_resources,
    create_environment,
    create_environment_api_key,
    create_harness,
    create_queue_session,
    create_runtime_template,
)

from .stream import HarnessApp, run_queue_sse  # noqa: E402


def configure_paths(mode):
    """三个模式读取 agent_infra 根配置，分别保存运行状态与 Dispatcher 记录。"""
    folder = ROOT / ".local" / mode
    path = ROOT / "config.yaml"
    os.environ.update(
        HARNESS_INFRA_CONFIG=str(path),
        HARNESS_INFRA_STATE=str(folder / "resources.json"),
        HARNESS_INFRA_BACKEND_STATE=str(folder / "dispatcher.json"),
    )
    return path


def key_path():
    """返回当前模式的私有凭据文件；它不是用户配置。"""
    return state_path().with_name("environment-key.json")


def save_environment_key(key_id, key):
    """以 0600 原子写入本轮签发的密钥，不修改共享 YAML。"""
    path = key_path()
    with NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, delete=False
    ) as file:
        temporary = Path(file.name)
        try:
            json.dump({"id": key_id, "value": key}, file)
            file.close()
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)


def restore_run_config(config, client, state):
    """从本轮状态恢复默认 Workspace，只加载 ID 匹配的环境密钥。"""
    workspace = state.get("workspace_id")
    if workspace and not config.control.workspace_id:
        client.config = replace(client.config, workspace_id=workspace)
        config = replace(config, control=client.config)
    if state.get("control_scope") != client.scope:
        raise RuntimeError("本轮状态与共享配置中的控制面地址或 Workspace 不一致")
    key_id = state["resources"].get("api_key", {}).get("id")
    key = ""
    if key_id and key_path().is_file():
        private = json.loads(key_path().read_text(encoding="utf-8"))
        if isinstance(private, dict) and private.get("id") == key_id:
            value = private.get("value")
            if isinstance(value, str):
                key = value
    return replace(
        config,
        environment=replace(
            config.environment,
            env_api_key_id=key_id if key else "",
            env_api_key_value=key,
        ),
    )


def initialize_sample(client, config, mode):
    """初始化本轮资源状态；后续命令复用同一组 ID 和幂等 token。"""
    state = new_state(
        client,
        prefix=mode,
        model_id=config.model_id,
        model_base_url=config.model_base_url,
        role_name=config.runtime_role_name,
        agent_loop="adk" if mode == "direct" else config.harness.agent_loop,
        environment_type=config.environment.type,
    )
    state["sample_mode"] = mode
    save_state(state)
    return state


def resource_steps(environment_type, direct):
    """列出各模式支持的控制面步骤及 dry-run 计划。"""
    steps = {
        "create-route": "ListEndpoints → 按需 CreateRoute",
        "create-environment": f"CreateEnvironment（{environment_type}）→ 等待 Active",
        "create-session-store": "CreateSessionStore（SERVERLESS_PG）→ 等待 Ready",
        "create-runtime-template": "准备 IAM 执行角色 → CreateRuntimeTemplate → GetRuntime Ready",
    }
    if environment_type == "Cloud":
        steps["create-environment"] += " → 等待 Sandbox Ready"
    if not direct:
        steps.update(
            {
                "create-harness": "CreateHarness → 保存 HarnessId",
                "create-api-key": "CreateAPIKey → 保存 Environment Key",
            }
        )
    return steps


def require_resource(resources, key, status, step):
    """下游步骤只使用本轮已登记且就绪的资源。"""
    resource = resources.get(key, {})
    if resource.get("status") != status or not resource.get("id"):
        raise RuntimeError(f"请先执行 {step}")
    return resource


def create_resource_step(client, config, state, command, *, direct):
    """逐步执行控制面调用；仅 Direct Runtime 绑定 Sandbox ToolId。"""
    resources = state["resources"]
    if command == "create-route":
        _prepare_endpoint(
            client,
            state,
            endpoint_id=config.environment.endpoint_id,
            apig_gateway_id=config.environment.apig_gateway_id,
            json_output=False,
        )
    elif command == "create-environment":
        create_environment(client, state, config, write_workspace=False)
        if direct and not resources["environment_resource"].get("tool_id"):
            raise RuntimeError("Cloud Sandbox Ready，但尚未返回 ToolId")
    elif command == "create-session-store":
        _create_session_store(client, state, config, json_output=False)
    elif command == "create-harness":
        require_resource(resources, "environment", "Active", "create-environment")
        create_harness(client, state, config)
    elif command == "create-runtime-template":
        tool_id = ""
        if direct:
            sandbox = require_resource(
                resources, "environment_resource", "Ready", "create-environment"
            )
            tool_id = sandbox.get("tool_id")
            if not tool_id:
                raise RuntimeError("请先执行 create-environment，取得 Sandbox ToolId")
        store = require_resource(
            resources, "session_store", "Ready", "create-session-store"
        )
        create_runtime_template(client, state, config, store["id"], tool_id=tool_id)
        if direct:
            state["status"] = "control_plane_ready"
            save_state(state)
    elif command == "create-api-key":
        require_resource(resources, "endpoint", "ready", "create-route")
        environment = require_resource(
            resources, "environment", "Active", "create-environment"
        )
        if config.environment.type == "Cloud":
            require_resource(
                resources, "environment_resource", "Ready", "create-environment"
            )
        require_resource(resources, "harness", "Active", "create-harness")
        require_resource(resources, "runtime", "Ready", "create-runtime-template")
        create_environment_api_key(
            client, state, config, environment["id"], save_key=save_environment_key
        )
        if state["status"] != "resources_ready":
            state["status"] = "control_plane_ready"
            save_state(state)


def direct_session(client, state, command, prompt):
    """保存会话身份用于重试与续聊；Runtime Key 仅在进程中使用。"""
    runtime_id = state["resources"].get("runtime", {}).get("id")
    session = state.get("direct_session")
    if command == "cleanup" and (not session or session.get("deleted")):
        return
    if not runtime_id:
        raise RuntimeError("没有 RuntimeId，请先执行 create-runtime-template")
    try:
        runtime = client.call("GetRuntime", {"RuntimeId": runtime_id})
    except HarnessInfraError as exc:
        if command != "cleanup" or not _not_found(exc):
            raise
        # Runtime 已被外部删除，无法调用其中的会话 API；下一步删除其 SessionStore。
        print("Runtime 已不存在，将继续回收 SessionStore。")
        return
    app = HarnessApp(runtime)
    if command == "create-session":
        if not session:
            session = {
                "id": str(uuid.uuid4()),
                "user_id": "agent-infra-sample",
                "app_name": "harness_agent",
            }
            state["direct_session"] = session
            save_state(state)
        if session.get("deleted"):
            raise RuntimeError("会话已删除，请完成 cleanup 后重建")
        app.create_session(session)
        session["ready"] = True
        save_state(state)
        print(f"Harness App SessionId: {session['id']}")
    elif command == "cleanup":
        with app.call("DELETE", app.session_path(session), allowed=(404,)):
            pass
        session["deleted"] = True
        save_state(state)
    else:
        if not session or not session.get("ready") or session.get("deleted"):
            raise RuntimeError("请先执行 create-session")
        app.run_sse(session, prompt)


def dispatcher(config, state):
    """用当前环境的连接参数启动自托管样例，避免读到其他环境的参数。"""
    env = {
        **os.environ,
        "ANTHROPIC_BASE_URL": state["resources"]["endpoint"]["base_url"],
        "ANTHROPIC_ENVIRONMENT_ID": state["resources"]["environment"]["id"],
        "ANTHROPIC_ENVIRONMENT_KEY": config.environment.env_api_key_value,
    }
    if config.control.workspace_id:
        env["HARNESS_INFRA_WORKSPACE_ID"] = config.control.workspace_id
    script = INFRA / "self_host/agentkit_sandbox_mode/02_create_dispatcher.py"
    if subprocess.run([sys.executable, str(script)], env=env, check=False).returncode:
        raise RuntimeError("Dispatcher 部署失败，请检查上方输出")


def execute(mode):
    """按资源、会话、流式对话、清理四阶段执行；dry-run 无副作用。"""
    direct = mode == "direct"
    selfhost = mode == "queue-selfhost"
    environment_type = "SelfHosted" if selfhost else "Cloud"
    steps = resource_steps(environment_type, direct)
    plans = {
        **steps,
        "create-session": (
            "Runtime GET /list-apps → POST /apps/{app}/users/{user}/sessions/{id}"
            if direct
            else "APIG POST /v1/sessions"
        ),
        "run-sse": (
            "Runtime POST /run_sse"
            if direct
            else "APIG POST /v1/sessions/{id}/events → GET /v1/sessions/{id}/events/stream"
        ),
        "cleanup": (
            "删除 Harness App Session → DeleteRuntime → DeleteSessionStore → "
            "DeleteEnvironmentResource → DeleteEnvironment；保留 Route / IAM 角色"
            if direct
            else "删除 APIG Session → DeleteAPIKey → DeleteRuntime → DeleteSessionStore → "
            + ("回收 Cloud Sandbox → " if not selfhost else "")
            + "DeleteEnvironment → ArchiveHarness；保留 Route / IAM 角色"
        ),
    }
    if selfhost:
        plans["dispatcher"] = "复用自托管样例：CreateTool → CreateRuntime → 等待 Ready"
    cli = argparse.ArgumentParser(description=f"AgentKit Infra / {mode}")
    cli.add_argument("command", choices=plans)
    cli.add_argument(
        "--dry-run", action="store_true", help="预览，不读取配置、不访问网络"
    )
    cli.add_argument("--prompt", default="请只回复 AGENT_INFRA_OK")
    args = cli.parse_args()
    path = configure_paths(mode)
    if args.dry_run:
        print(f"{mode}: {plans[args.command]}\n配置：{path}")
        return
    if not path.is_file():
        raise RuntimeError(f"缺少 {path}，请从 {ROOT / 'config.yaml.example'} 复制")
    config = validated_config(
        environment_type=environment_type,
        require_model_key_name=not direct and args.command == "create-session",
    )
    if args.command == "run-sse" and not args.prompt.strip():
        raise RuntimeError("--prompt 不能为空")
    client = TopClient(config.control)
    state = load_state() if state_path().exists() else None
    if state and state.get("sample_mode") != mode:
        raise RuntimeError("当前状态不属于本模式")
    if state and not state.get("cleaned"):
        config = restore_run_config(config, client, state)
    if not state or state.get("cleaned"):
        if args.command == "cleanup":
            key_path().unlink(missing_ok=True)
            print("没有待清理的本轮资源。")
            return
        if args.command not in {
            "create-route",
            "create-environment",
            "create-session-store",
        }:
            raise RuntimeError("请先执行 create-environment 创建本轮资源")
        key_path().unlink(missing_ok=True)
        state = initialize_sample(client, config, mode)
    if args.command == "cleanup":
        state["cleanup_started"] = True
        save_state(state)
        if direct:
            direct_session(client, state, "cleanup", "")
        cleanup_resources(
            client, state, environment_api_key=config.environment.env_api_key_value
        )
        key_path().unlink(missing_ok=True)
        return
    if state.get("cleanup_started"):
        raise RuntimeError("本轮已开始清理，请先执行 cleanup 完成回收")
    if args.command in steps:
        create_resource_step(client, config, state, args.command, direct=direct)
        return
    if state.get("status") not in {"control_plane_ready", "resources_ready"}:
        step = "create-runtime-template" if direct else "create-api-key"
        raise RuntimeError(f"控制面资源未就绪，请先检查 {step} 的结果")
    if direct:
        direct_session(client, state, args.command, args.prompt)
        return
    api_key = state["resources"].get("api_key", {})
    if (
        not api_key.get("id")
        or api_key["id"] != config.environment.env_api_key_id
        or not config.environment.env_api_key_value
    ):
        raise RuntimeError("本轮 Environment API Key 不可用，请检查本地配置")
    if args.command == "dispatcher":
        dispatcher(config, state)
        return
    session = state["resources"].get("session", {})
    key = config.environment.env_api_key_value
    if args.command == "create-session":
        session_id = session.get("id") or create_queue_session(
            state, config, key, write_session=False
        )
        print(f"AgentKit SessionId: {session_id}")
    elif not session.get("id"):
        raise RuntimeError("请先执行 create-session")
    else:
        run_queue_sse(
            state["resources"]["endpoint"]["base_url"], key, session["id"], args.prompt
        )


def main(mode):
    """将共享错误处理应用到各目录的独立脚本。"""
    run(lambda: execute(mode))
