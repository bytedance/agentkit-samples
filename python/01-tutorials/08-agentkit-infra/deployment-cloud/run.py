#!/usr/bin/env python3
"""独立的 Cloud Deployment sample：创建、触发、只读验收、第二轮及清理。"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
from importlib.metadata import version as package_version
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid
from typing import Any
from urllib.parse import urlsplit

import requests
import yaml

from clients import APIError, CREDENTIAL_FIELDS, RuntimeClient, TopClient

ROOT = Path(__file__).resolve().parent
DEFAULT_STATE = ROOT / ".agentkit" / "state.json"
REPORT_ROOT = (
    Path(os.getenv("XDG_STATE_HOME", str(Path.home() / ".local" / "state")))
    / "agentkit-samples"
    / "deployment-cloud"
    / "reports"
)


class Pending(RuntimeError):
    """事件尚未完整，调用者可以继续只读轮询。"""


def has_error(value: Any) -> bool:
    """递归检查工具返回的显式错误；不把普通文本中的 error 字样当失败。"""
    if isinstance(value, dict):
        if value.get("is_error") is True or value.get("isError") is True:
            return True
        if value.get("error") or value.get("errorCode") or value.get("error_code"):
            return True
        if isinstance(value.get("exit_code"), int) and value["exit_code"] != 0:
            return True
        return any(has_error(item) for item in value.values())
    return isinstance(value, list) and any(has_error(item) for item in value)


def verify_events(events: list[dict[str, Any]], *, marker: str) -> dict[str, Any]:
    """验证用户输入、最终模型文本和 bash 调用，严格要求一调用一结果。

    输入：单轮 ADK 持久化事件切片，按 Session 保存顺序排列。
    输出：不含凭据的验收摘要。未完成抛 Pending，确定失败抛 RuntimeError。
    ADK 的非 partial 模型文本且无 functionCall 表示本轮最终回答；
    不要求 AKX 专用的 session.status_idle。
    """
    calls: dict[str, dict[str, Any]] = {}
    results: dict[str, list[dict[str, Any]]] = {}
    final_index = -1
    answer = ""
    user_seen = False
    for index, event in enumerate(events):
        if any(event.get(key) for key in ("error", "errorCode", "error_code")):
            raise RuntimeError("ADK Session 包含执行错误")
        content = event.get("content") or {}
        if not isinstance(content, dict):
            raise RuntimeError("ADK content 必须是对象")
        parts = content.get("parts") or []
        if not isinstance(parts, list) or any(
            not isinstance(part, dict) for part in parts
        ):
            raise RuntimeError("ADK parts 必须是对象列表")
        role = content.get("role")
        user_seen |= event.get("author") == "user" and any(
            part.get("text") for part in parts
        )
        for part in parts:
            call = part.get("functionCall")
            result = part.get("functionResponse")
            if isinstance(call, dict) and not event.get("partial"):
                reference = call.get("id")
                if not reference:
                    raise RuntimeError("工具调用缺少 functionCall.id")
                if reference in calls:
                    raise RuntimeError("工具调用 ID 重复")
                calls[reference] = {**call, "_index": index}
            if isinstance(result, dict):
                reference = result.get("id")
                if not reference:
                    raise RuntimeError("工具结果缺少 functionResponse.id")
                results.setdefault(reference, []).append({**result, "_index": index})
        text = "".join(
            str(part.get("text") or "") for part in parts if not part.get("thought")
        )
        if (
            role == "model"
            and not event.get("partial")
            and text
            and not any(
                part.get("functionCall") or part.get("functionResponse")
                for part in parts
            )
        ):
            answer, final_index = text, index
    if not user_seen or not answer:
        raise Pending("尚未看到用户消息和完整的模型回答")
    for reference, call in calls.items():
        paired = results.get(reference, [])
        if not paired:
            if final_index > call["_index"]:
                raise RuntimeError("最终回答已出现，但工具调用缺少结果")
            raise Pending("工具结果尚未保存")
        if len(paired) != 1:
            raise RuntimeError("一个工具调用必须恰有一个结果")
        result = paired[0]
        if (
            result.get("name") != call.get("name")
            or not call["_index"] < result["_index"] < final_index
        ):
            raise RuntimeError("工具结果名称或事件顺序不正确")
        if has_error(result.get("response")):
            raise RuntimeError("工具执行失败")
    if set(results) - set(calls):
        raise RuntimeError("工具结果缺少对应调用")
    # 当前统一 Runtime 镜像通过 Sandbox 工具后端把 shell 工具导出为 Execute；
    # 原生 agent_toolset 则使用 bash。两者都要求真实 command 参数和配对结果。
    bash_ids = [
        ref
        for ref, call in calls.items()
        if call.get("name") in {"bash", "Execute"}
        and isinstance(call.get("args"), dict)
        and isinstance(call["args"].get("command"), str)
        and call["args"]["command"].strip()
    ]
    if not bash_ids:
        raise RuntimeError("最终回答已出现，但没有真实 shell 工具调用（bash/Execute）")
    if marker not in answer:
        raise RuntimeError(f"最终回答未包含预期值 {marker}")
    if not any(
        marker in json.dumps(results[ref][0].get("response"), ensure_ascii=False)
        for ref in bash_ids
    ):
        raise RuntimeError("bash 工具实际结果未包含预期值")
    return {
        "answer": answer,
        "event_count": len(events),
        "tool_calls": len(calls),
        "tool_results": sum(map(len, results.values())),
        "tool_names": sorted({call["name"] for call in calls.values()}),
        "shell_tool_names": sorted({calls[ref]["name"] for ref in bash_ids}),
        "tool_executions": [
            {
                "call_id": reference,
                "result_id": results[reference][0]["id"],
                "name": call["name"],
                "successful": True,
                "call_event_index": call["_index"],
                "result_event_index": results[reference][0]["_index"],
                "response_sha256": hashlib.sha256(
                    json.dumps(
                        results[reference][0].get("response"),
                        sort_keys=True,
                        ensure_ascii=False,
                    ).encode()
                ).hexdigest(),
            }
            for reference, call in calls.items()
        ],
        "completion": "adk_final_model_message",
        "expected_marker": marker,
    }


def save(path: Path, value: dict[str, Any]) -> None:
    """以 0600 权限原子保存非敏感状态，避免中断留下半份 JSON。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    with os.fdopen(
        os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w"
    ) as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
    temp.replace(path)


def load_config(path: Path, command: str = "all") -> dict[str, Any]:
    """按当前命令检查必填配置；凭据支持环境变量覆盖，不读取相邻项目。"""
    if not path.exists():
        raise RuntimeError(f"请先复制 config.yaml.example 为 {path}")
    cfg = yaml.safe_load(path.read_text())
    if not isinstance(cfg, dict):
        raise ValueError("配置必须是 YAML 对象")
    control = cfg["control"]
    for key in CREDENTIAL_FIELDS:
        env = "VOLCENGINE_" + key.upper()
        control[key] = os.getenv(env) or control.get(key, "")
    for key in (
        "access_key",
        "secret_key",
        "host",
        "region",
    ):
        if not control.get(key):
            raise ValueError(f"缺少 control.{key}")
    model_commands = {
        "all",
        "prepare",
        "create-runtime",
        "create-harness",
        "create-deployment",
    }
    if command in model_commands:
        required = (
            ("ark_api_key_name",)
            if command == "create-deployment"
            else ("id", "base_url", "ark_api_key_name")
        )
        for key in required:
            if not cfg["model"].get(key):
                raise ValueError(f"{command} 必填：model.{key}")
    if (
        command in {"all", "prepare", "create-runtime"}
        and not cfg["runtime"].get("id")
        and not cfg["runtime"].get("role_name")
    ):
        raise ValueError(
            f"{command} 必填：runtime.role_name（新建 Runtime 时需要预先配置的执行角色）"
        )
    if cfg["runtime"].get("app_name") != "harness_agent":
        raise ValueError("当前 Cloud Deployment 执行器固定使用 harness_agent")
    prompt_fields = []
    if command in {"create-deployment", "prepare", "all"}:
        prompt_fields.append(("deployment", "user_prompt"))
    if command in {
        "invoke-session",
        "second-round",
        "all",
    }:
        prompt_fields.append(("verification", "second_round_prompt"))
    for section, key in prompt_fields:
        value = cfg.get(section, {}).get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"{command} 必填：{section}.{key}；请参考 config.yaml.example 填写用户提示词"
            )
    for key in ("timeout_seconds", "poll_seconds", "dispatch_settle_seconds"):
        value = cfg["verification"].get(key)
        if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
            raise ValueError(f"verification.{key} 必须为正数")
    return cfg


def wait(fetch, ready, cfg: dict[str, Any], title: str):
    """有界轮询只读状态，每三十秒输出进度，失败不重发执行请求。"""
    deadline = time.monotonic() + cfg["verification"]["timeout_seconds"]
    next_log = 0.0
    while True:
        result = fetch()
        if ready(result):
            return result
        now = time.monotonic()
        if now >= deadline:
            raise TimeoutError(f"{title} 超时；保留状态，使用原 ID 继续验收")
        if now >= next_log:
            print(f"等待 {title}...", flush=True)
            next_log = now + 30
        time.sleep(min(cfg["verification"]["poll_seconds"], deadline - now))


class Sample:
    """编排控制面生命周期，状态仅保存 ID、token、验收摘要和资源归属。"""

    def __init__(self, cfg: dict[str, Any], state_path: Path):
        self.cfg, self.state_path = cfg, state_path
        self.top = TopClient(cfg["control"])
        self.state = (
            json.loads(state_path.read_text())
            if state_path.exists()
            else {
                "version": 1,
                "suffix": uuid.uuid4().hex[:12],
                "tokens": {},
                "resources": {},
                "runs": [],
            }
        )
        scope = {
            key: cfg["control"].get(key, "")
            for key in ("host", "region", "workspace_id", "access_key")
        }
        scope_hash = hashlib.sha256(
            json.dumps(scope, sort_keys=True).encode()
        ).hexdigest()
        if self.state.get("scope_hash", scope_hash) != scope_hash:
            raise RuntimeError("状态与控制面账号/Workspace 不匹配；请使用另一状态文件")
        self.state["scope_hash"] = scope_hash
        cfg["runtime"]["user_id"] = cfg["runtime"].get("user_id") or self.state.get(
            "deployment_user_id", ""
        )
        self.persist()

    def persist(self) -> None:
        """保存当前可恢复状态；所有 Key 仅停留在客户端内存。"""
        save(self.state_path, self.state)

    def token(self, operation: str) -> str:
        """请求前持久化 ClientToken，恢复时复用同一 token。"""
        if operation not in self.state["tokens"]:
            self.state["tokens"][operation] = str(uuid.uuid4())
            self.persist()
        return self.state["tokens"][operation]

    def create(
        self,
        kind: str,
        action: str,
        body: dict[str, Any],
        id_field: str,
        *,
        with_token: bool = True,
    ) -> str:
        """独立创建并立即登记归属；已登记资源不重复创建。"""
        recorded = self.state["resources"].get(kind)
        if recorded:
            if recorded.get("deleted"):
                raise RuntimeError("本次状态已清理；新建测试请使用另一 --state 路径")
            return recorded["id"]
        if with_token:
            body = {**body, "ClientToken": self.token(action)}
        result = self.top.call(action, body)
        resource_id = result.get(id_field)
        if not isinstance(resource_id, str) or not resource_id:
            raise RuntimeError(f"{action} 缺少 {id_field}")
        self.state["resources"][kind] = {"id": resource_id, "owned": True}
        self.persist()
        print(f"{action}: {resource_id}", flush=True)
        return resource_id

    def require(self, kind: str, command: str) -> dict[str, Any]:
        """返回已登记资源；缺少前置资源时给出可直接执行的命令。"""
        resource = self.state["resources"].get(kind)
        if not resource or resource.get("deleted"):
            raise ValueError(f"缺少可用 {kind}；请先执行 python run.py {command}")
        return resource

    def create_route(self) -> dict[str, Any]:
        """复用 Ready Endpoint；不存在时按 route.apig_gateway_id 创建账号路由。"""
        recorded = self.state["resources"].get("endpoint")
        if recorded:
            return recorded
        items = []
        token = ""
        seen = set()
        while True:
            body = {"MaxResults": 100}
            if token:
                body["NextToken"] = token
            value = self.top.call("ListEndpoints", body)
            page = value.get("Items")
            if not isinstance(page, list):
                raise RuntimeError("ListEndpoints 缺少 Items[]")
            items.extend(page)
            token = value.get("NextToken") or ""
            if not token:
                break
            if token in seen:
                raise RuntimeError("ListEndpoints 分页 token 重复")
            seen.add(token)
        cfg = self.cfg.get("route", {})
        selected = cfg.get("endpoint_id") or self.cfg.get("cleanup", {}).get(
            "endpoint_id"
        )
        if selected:
            matches = [item for item in items if item.get("EndpointId") == selected]
            if len(matches) != 1:
                raise ValueError("route.endpoint_id 必须是当前账号可见的 Endpoint")
            endpoint, owned = matches[0], False
        elif len(items) == 1:
            endpoint, owned = items[0], False
        elif items:
            raise ValueError(
                "存在多个 Endpoint；必填 route.endpoint_id，明确指定复用哪一个"
            )
        else:
            gateway = cfg.get("apig_gateway_id")
            if not gateway:
                raise ValueError(
                    "账号没有 Endpoint；创建路由必填 route.apig_gateway_id"
                )
            endpoint = self.top.call(
                "CreateRoute",
                {
                    "ApigGatewayId": gateway,
                },
            )
            owned = True
        if (
            str(endpoint.get("Status", "")).lower() != "ready"
            or not endpoint.get("EndpointId")
            or not endpoint.get("BaseUrl")
        ):
            raise RuntimeError("Endpoint 必须 Ready 且包含 EndpointId/BaseUrl")
        recorded = {
            "id": endpoint["EndpointId"],
            "base_url": endpoint["BaseUrl"],
            "owned": owned,
        }
        self.state["resources"]["endpoint"] = recorded
        self.persist()
        print(f"Endpoint Ready: {recorded['id']}", flush=True)
        return recorded

    def create_session_store(self) -> None:
        """创建或复用 SERVERLESS_PG SessionStore，等待 Ready 后供 Runtime 引用。"""
        cfg = self.cfg.get("session_store", {})
        resources = self.state["resources"]
        existing = cfg.get("id") or self.cfg["runtime"].get("session_store_id")
        if "session_store" not in resources and existing:
            resources["session_store"] = {"id": existing, "owned": False}
            self.persist()
        if "session_store" not in resources:
            if self.state.get("session_store_creation_pending"):
                raise RuntimeError(
                    "SessionStore 创建结果未知；请先核对账号资源，将真实 ID 填入 session_store.id 后恢复"
                )
            self.state["session_store_creation_pending"] = True
            self.persist()
            self.create(
                "session_store",
                "CreateSessionStore",
                {
                    "Name": self.cfg["deployment"]["name_prefix"]
                    + "-"
                    + self.state["suffix"]
                    + "-store",
                    "ProjectName": cfg.get("project_name", "default"),
                    "Description": "Cloud Deployment SessionStore",
                    "ProviderType": "SERVERLESS_PG",
                },
                "SessionStoreId",
                with_token=False,
            )
            self.state.pop("session_store_creation_pending", None)
            self.persist()
        store_id = self.require("session_store", "create-session-store")["id"]

        def ready(value):
            """拒绝失败/删除终态和非托管 PG 类型。"""
            if value.get("Status") in {"Failed", "Deleting", "Deleted"}:
                raise RuntimeError("SessionStore 不可用")
            if (
                value.get("Status") == "Ready"
                and value.get("ProviderType") != "SERVERLESS_PG"
            ):
                raise RuntimeError("本 sample 要求 SERVERLESS_PG SessionStore")
            return value.get("Status") == "Ready"

        value = wait(
            lambda: self.top.call("GetSessionStore", {"SessionStoreId": store_id}),
            ready,
            self.cfg,
            "SessionStore Ready",
        )
        if value.get("SessionStoreId") != store_id:
            raise RuntimeError("SessionStore 响应 ID 不匹配")
        resources["session_store"]["status"] = "Ready"
        self.persist()
        print(f"SessionStore Ready: {store_id}", flush=True)

    def create_environment(self) -> None:
        """只准备 Cloud Environment 和自动 Sandbox，不创建其他资源。"""
        cfg, resources = self.cfg, self.state["resources"]
        prefix = cfg["deployment"]["name_prefix"] + "-" + self.state["suffix"]
        env_cfg = cfg["environment"]
        if "environment" not in resources and env_cfg.get("id"):
            resources["environment"] = {"id": env_cfg["id"], "owned": False}
            self.persist()
        env_id = self.create(
            "environment",
            "CreateEnvironment",
            {
                "Name": prefix + "-env",
                "Description": "独立 Cloud Deployment sample",
                "Config": {"Type": "Cloud", "Resources": env_cfg["resources"]},
            },
            "EnvironmentId",
        )

        def environment_ready(value):
            """拒绝类型不符或归档的 Environment。"""
            if (
                (value.get("Config") or {}).get("Type") != "Cloud"
                or value.get("ArchivedAt")
                or value.get("Status") == "Archived"
            ):
                raise RuntimeError("Environment 必须为未归档的 Cloud 类型")
            return value.get("Status") == "Active"

        wait(
            lambda: self.top.call("GetEnvironment", {"EnvironmentId": env_id}),
            environment_ready,
            cfg,
            "Cloud Environment Active",
        )

        def sandbox():
            """读取自动创建的 Cloud 工具资源；明确拒绝多资源选择歧义。"""
            result = self.top.call(
                "ListEnvironmentResources", {"EnvironmentId": env_id, "MaxResults": 100}
            )
            items = result.get("Items")
            if not isinstance(items, list) or result.get("NextToken"):
                raise RuntimeError("Cloud 工具资源列表不完整")
            active = [item for item in items if item.get("Status") != "Deleted"]
            if len(active) > 1:
                raise RuntimeError("Cloud Environment 包含多个工具资源，无法自动选择")
            if not active:
                return {}
            value = active[0]
            if value.get("Status") in {"Failed", "DeleteFailed"} or value.get(
                "ErrorCode"
            ):
                raise RuntimeError("Cloud 工具资源创建失败")
            return value

        tool = wait(
            sandbox,
            lambda value: value.get("Status") == "Ready"
            and bool(value.get("ToolId"))
            and value.get("DesiredGeneration") == value.get("ObservedGeneration"),
            cfg,
            "Cloud Sandbox Ready",
        )
        resources["sandbox"] = {
            "id": tool["ResourceId"],
            "tool_id": tool["ToolId"],
            "owned": resources["environment"]["owned"],
        }
        self.persist()
        print(f"Cloud Sandbox Ready: {tool['ToolId']}", flush=True)

    def create_runtime(self) -> None:
        """只创建或复用 Runtime，使用先前准备的 Cloud Sandbox 和 SessionStore。"""
        cfg, resources = self.cfg, self.state["resources"]
        prefix = cfg["deployment"]["name_prefix"] + "-" + self.state["suffix"]
        self.require("environment", "create-environment")
        tool = self.require("sandbox", "create-environment")
        runtime_cfg = cfg["runtime"]
        if "runtime" not in resources and runtime_cfg.get("id"):
            resources["runtime"] = {"id": runtime_cfg["id"], "owned": False}
            self.persist()
        if "runtime" not in resources:
            store = self.require("session_store", "create-session-store")
            if store.get("status") != "Ready":
                raise ValueError(
                    "SessionStore 尚未就绪；请先执行 python run.py create-session-store"
                )
            body = {
                "Name": prefix + "-runtime",
                "SessionStoreId": store["id"],
                "RoleName": runtime_cfg["role_name"],
                "Resources": runtime_cfg["resources"],
                "Envs": {
                    **runtime_cfg.get("envs", {}),
                    "HARNESS_APP_ENABLED": "true",
                    "STUDIO_ENABLED": "false",
                    "HARNESS_SANDBOX_TOOL_ID": tool["tool_id"],
                    "MODEL_NAME": cfg["model"]["id"],
                    "MODEL_AGENT_NAME": cfg["model"]["id"],
                    "MODEL_API_BASE": cfg["model"]["base_url"],
                    "MODEL_AGENT_API_BASE": cfg["model"]["base_url"],
                    "MODEL_AGENT_API_KEY_NAME": cfg["model"]["ark_api_key_name"],
                    "SYSTEM_PROMPT": "必须使用真实 bash 工具执行用户要求，基于结果回答。",
                    "RUNTIME": "adk",
                },
            }
            if runtime_cfg.get("settings"):
                body["Runtime"] = runtime_cfg["settings"]
            if runtime_cfg.get("image_url"):
                body["ImageUrl"] = runtime_cfg["image_url"]
            self.create("runtime", "CreateRuntimeTemplate", body, "RuntimeId")
        runtime_id = resources["runtime"]["id"]

        def runtime_ready(value):
            """Runtime 终态错误立即失败，Creating 才继续等待。"""
            if value.get("Status") in {"Error", "Aborted", "Deleting", "Deleted"}:
                raise RuntimeError(f"Runtime 不可用：{value['Status']}")
            return value.get("Status") == "Ready"

        runtime = wait(
            lambda: self.top.call("GetRuntime", {"RuntimeId": runtime_id}),
            runtime_ready,
            cfg,
            "Runtime Ready",
        )
        app = RuntimeClient(runtime)
        apps = app.json("GET", "/list-apps")
        if not isinstance(apps, list) or runtime_cfg["app_name"] not in apps:
            raise RuntimeError("Runtime /list-apps 不包含配置的 app_name")
        self.state["runtime_provenance"] = {
            key: runtime.get(key)
            for key in (
                "RuntimeId",
                "ArtifactUrl",
                "CurrentVersionNumber",
                "SessionStoreId",
                "Status",
            )
        }
        resources["runtime"]["status"] = "Ready"
        self.persist()
        print(f"Runtime Ready: {runtime_id}", flush=True)

    def create_harness(self) -> None:
        """只创建 Harness，绑定已有 Environment/Runtime 并记录版本和触发者。"""
        cfg, resources = self.cfg, self.state["resources"]
        prefix = cfg["deployment"]["name_prefix"] + "-" + self.state["suffix"]
        env_id = self.require("environment", "create-environment")["id"]
        runtime_id = self.require("runtime", "create-runtime")["id"]
        runtime_cfg = cfg["runtime"]
        harness_id = self.create(
            "harness",
            "CreateHarness",
            {
                "Name": prefix + "-harness",
                "Description": "Cloud Deployment 两轮 bash 验收",
                "Model": {
                    "Id": cfg["model"]["id"],
                    "BaseUrl": cfg["model"]["base_url"],
                },
                "AgentLoop": "adk",
                "System": "必须调用真实工具完成任务，不得猜测工具结果。保留同一 Session 的上下文。",
                "Tools": [
                    {
                        "Type": "agent_toolset_20260401",
                        "DefaultConfig": {
                            "Enabled": False,
                            "PermissionPolicy": {"Type": "always_allow"},
                        },
                        "Configs": [
                            {
                                "Type": "bash",
                                "Enabled": True,
                                "PermissionPolicy": {"Type": "always_allow"},
                            }
                        ],
                    }
                ],
                "EnvironmentId": env_id,
                "RuntimeId": runtime_id,
            },
            "HarnessId",
        )
        harness = self.top.call("GetHarness", {"HarnessId": harness_id})
        user_id = runtime_cfg.get("user_id") or (harness.get("Metadata") or {}).get(
            "sys:agentkit:creator"
        )
        if not user_id:
            raise ValueError("Harness 未返回触发者标识，请显式填写 runtime.user_id")
        runtime_cfg["user_id"] = str(user_id)
        self.state["deployment_user_id"] = str(user_id)
        version = harness.get("HarnessVersion") or harness.get("Version")
        if not isinstance(version, int) or version <= 0:
            raise RuntimeError("Harness 响应缺少有效版本")
        resources["harness"]["version"] = version
        self.persist()
        print(f"Harness Version: {version}", flush=True)

    def create_deployment(self) -> None:
        """只创建 Deployment，固定现有 Harness 版本及目标 Environment/Runtime。"""
        cfg = self.cfg
        prefix = cfg["deployment"]["name_prefix"] + "-" + self.state["suffix"]
        harness = self.require("harness", "create-harness")
        harness_id, version = harness["id"], harness.get("version")
        if not version:
            raise ValueError("缺少 Harness 版本；请先执行 python run.py create-harness")
        env_id = self.require("environment", "create-environment")["id"]
        runtime_id = self.require("runtime", "create-runtime")["id"]
        nonce = self.state["suffix"]
        marker = f"DEPLOYMENT_CLOUD_OK_{nonce}"
        # 仅替换约定占位符，保留用户提示词中的 JSON、shell 等其他花括号。
        prompt = (
            cfg["deployment"]["user_prompt"]
            .replace("{nonce}", nonce)
            .replace("{marker}", marker)
        )
        body = {
            "Name": prefix,
            "HarnessId": harness_id,
            "HarnessVersion": version,
            "EnvironmentId": env_id,
            "RuntimeId": runtime_id,
            "ArkApiKeyName": cfg["model"]["ark_api_key_name"],
            "InitialEvents": [
                {"type": "user.message", "content": [{"type": "text", "text": prompt}]}
            ],
        }
        if cfg["deployment"].get("cron"):
            body["Schedule"] = {
                "Type": "cron",
                "Expression": cfg["deployment"]["cron"],
                "Timezone": cfg["deployment"]["timezone"],
            }
        self.create("deployment", "CreateDeployment", body, "DeploymentId")
        self.persist()

    def prepare(self) -> None:
        """按资源依赖顺序准备路由、Environment、SessionStore、Runtime、Harness 和 Deployment。"""
        self.create_route()
        self.create_environment()
        if not self.cfg["runtime"].get("id"):
            self.create_session_store()
        self.create_runtime()
        self.create_harness()
        self.create_deployment()

    def trigger(self, *, new_run: bool = False) -> None:
        """提交一次 Run；默认恢复最近一次，--new-run 才创建另一个测试 Run。"""
        if self.state["runs"] and not new_run:
            print("复用最近一次 DeploymentRun，未重复触发", flush=True)
            return
        deployment_id = self.require("deployment", "create-deployment")["id"]
        index = len(self.state["runs"])
        result = self.top.call(
            "RunDeployment",
            {
                "DeploymentId": deployment_id,
                "ClientToken": self.token(f"RunDeployment-{index}"),
            },
        )
        run_id = result.get("DeploymentRunId")
        if not isinstance(run_id, str) or not run_id:
            raise RuntimeError("RunDeployment 缺少 DeploymentRunId")
        self.state["runs"].append({"id": run_id, "deployment_id": deployment_id})
        self.persist()
        self.check_run()
        print(f"RunDeployment: {run_id}", flush=True)

    def create_session(self, *, new_run: bool = False) -> None:
        """通过 RunDeployment 创建首轮 Session，等待并展示其 ID，不另建空 Session。"""
        self.trigger(new_run=new_run)
        value = wait(
            self.check_run,
            lambda item: bool(item.get("SessionId")),
            self.cfg,
            "Deployment SessionId",
        )
        print(f"SessionId: {value['SessionId']}", flush=True)

    def get_session(self) -> None:
        """只读展示当前 Deployment Session 的身份和事件数量，不打印模型思考。"""
        if not self.state["runs"]:
            raise ValueError(
                "缺少 Run；手动任务先 create-session，定时任务先 list-deployment-runs，再 get-session --run-id <RunId>"
            )
        wait(
            self.check_run,
            lambda item: bool(item.get("SessionId")),
            self.cfg,
            "Deployment SessionId",
        )
        value = self.snapshot(self.app())
        print(
            json.dumps(
                {
                    "run_id": self.state["runs"][-1]["id"],
                    "session_id": value["id"],
                    "app_name": self.state["runs"][-1]["app_name"],
                    "user_id": self.state["runs"][-1]["user_id"],
                    "event_count": len(value["events"]),
                },
                ensure_ascii=False,
            ),
            flush=True,
        )

    def list_deployment_runs(self) -> None:
        """分页展示 Deployment 的运行 ID、SessionId、触发上下文和错误类型。"""
        deployment_id = self.require("deployment", "create-deployment")["id"]
        items = [
            {
                "run_id": item.get("DeploymentRunId"),
                "session_id": item.get("SessionId"),
                "created_at": item.get("CreatedAt"),
                "trigger_context": item.get("TriggerContext"),
                "error_type": (item.get("Error") or {}).get("Type"),
            }
            for item in self.deployment_runs()
        ]
        print(
            json.dumps(
                {"deployment_id": deployment_id, "runs": items}, ensure_ascii=False
            ),
            flush=True,
        )

    def deployment_runs(self) -> list[dict[str, Any]]:
        """完整读取当前 Deployment 的 Run 历史，不触发任务或选择 Session。"""
        deployment_id = self.require("deployment", "create-deployment")["id"]
        token = ""
        seen = set()
        items = []
        while True:
            body = {"DeploymentId": deployment_id, "MaxResults": 100}
            if token:
                body["NextToken"] = token
            value = self.top.call("ListDeploymentRuns", body)
            page = value.get("Items")
            if not isinstance(page, list):
                raise RuntimeError("ListDeploymentRuns 缺少 Items[]")
            for item in page:
                if (
                    not isinstance(item, dict)
                    or item.get("DeploymentId") != deployment_id
                ):
                    raise RuntimeError("ListDeploymentRuns 的 Run 归属不匹配")
                items.append(item)
            token = value.get("NextToken") or ""
            if not token:
                break
            if token in seen:
                raise RuntimeError("ListDeploymentRuns 分页 token 重复")
            seen.add(token)
        return items

    def select_run(self, run_id: str) -> None:
        """只读解析指定 Run 并保存当前选择；归属验证通过后才更新本地状态。"""
        deployment_id = self.require("deployment", "create-deployment")["id"]
        recorded = next(
            (run for run in self.state["runs"] if run["id"] == run_id), None
        )
        if recorded is None:
            recorded = {"id": run_id, "deployment_id": deployment_id}
        if recorded["deployment_id"] != deployment_id:
            raise RuntimeError("Run 不属于当前 Deployment")
        self.check_run(recorded)
        self.state["runs"] = [
            run for run in self.state["runs"] if run["id"] != run_id
        ] + [recorded]
        self.persist()
        print(f"当前 Run: {run_id}", flush=True)

    def check_run(
        self, recorded: dict[str, Any] | None = None, *, check_error: bool = True
    ) -> dict[str, Any]:
        """读取并检查 Run.Error 和 Deployment 归属，SessionId 不代表完成。"""
        if recorded is None:
            if not self.state["runs"]:
                raise ValueError(
                    "缺少 Run；手动任务先 create-session，定时任务先 list-deployment-runs，再 verify-session --run-id <RunId>"
                )
            recorded = self.state["runs"][-1]
        value = self.top.call("GetDeploymentRun", {"DeploymentRunId": recorded["id"]})
        if (
            value.get("DeploymentRunId") != recorded["id"]
            or value.get("DeploymentId") != recorded["deployment_id"]
        ):
            raise RuntimeError("Run 的 Deployment/Run ID 不匹配")
        if check_error and value.get("Error"):
            error = value["Error"]
            kind = (
                error.get("Type", "unknown") if isinstance(error, dict) else "unknown"
            )
            raise RuntimeError(f"DeploymentRun 失败：{kind}")
        session_id = value.get("SessionId")
        if recorded.get("session_id") and session_id != recorded["session_id"]:
            raise RuntimeError("Run 的 SessionId 发生变化")
        if session_id:
            if not self.cfg["runtime"].get("user_id"):
                raise ValueError(
                    "缺少 Runtime Session 用户标识；请先 prepare 或填写 runtime.user_id"
                )
            recorded["session_id"] = session_id
            recorded["app_name"] = self.cfg["runtime"]["app_name"]
            recorded["user_id"] = self.cfg["runtime"]["user_id"]
            self.persist()
        return value

    def app(self) -> RuntimeClient:
        """每次从 GetRuntime 获取访问凭据，不落盘、不使用 Environment Key。"""
        return RuntimeClient(
            self.top.call(
                "GetRuntime", {"RuntimeId": self.state["resources"]["runtime"]["id"]}
            )
        )

    def snapshot(self, app: RuntimeClient) -> dict[str, Any]:
        """只读获取本次 Run 对应的 Harness App Session。"""
        run = self.state["runs"][-1]
        value = app.json(
            "GET", app.path(run["app_name"], run["user_id"], run["session_id"])
        )
        if not isinstance(value, dict) or value.get("id") != run["session_id"]:
            raise RuntimeError("Runtime Session 响应 ID 不匹配")
        events = value.get("events")
        if not isinstance(events, list) or any(
            not isinstance(event, dict) for event in events
        ):
            raise RuntimeError("Runtime Session 响应缺少 events[]")
        return value

    def history(self) -> None:
        """按 NextToken 完整分页，确认当前 Run 出现在当前 Deployment 的历史中。"""
        run = self.state["runs"][-1]
        token = ""
        seen = set()
        found = False
        while True:
            body = {"DeploymentId": run["deployment_id"], "MaxResults": 100}
            if token:
                body["NextToken"] = token
            result = self.top.call("ListDeploymentRuns", body)
            items = result.get("Items")
            if not isinstance(items, list):
                raise RuntimeError("ListDeploymentRuns 缺少 Items[]")
            found |= any(
                item.get("DeploymentRunId") == run["id"]
                and item.get("DeploymentId") == run["deployment_id"]
                for item in items
            )
            token = result.get("NextToken") or ""
            if not token:
                break
            if token in seen:
                raise RuntimeError("ListDeploymentRuns 重复分页 token")
            seen.add(token)
        if not found:
            raise RuntimeError("本次 Run 不在 Deployment 历史中")
        run["history_verified"] = True
        self.persist()

    def verify(self) -> None:
        """首轮完全只读验收，期间持续检查可能晚写入的 dispatch_error。"""
        if not self.state["runs"]:
            raise RuntimeError(
                "缺少 Run；手动任务先 create-session，定时任务使用 verify-session --run-id <RunId>"
            )
        wait(
            self.check_run,
            lambda value: bool(value.get("SessionId")),
            self.cfg,
            "Run SessionId",
        )
        app = self.app()
        marker = f"DEPLOYMENT_CLOUD_OK_{self.state['suffix']}"
        run = self.state["runs"][-1]

        def fetch():
            """Session 创建可能滞后，仅 404 可继续等待。"""
            self.check_run()
            try:
                session = self.snapshot(app)
            except APIError as exc:
                if exc.status == 404:
                    return None
                raise
            # 第二轮之后重验首轮仍只检查首轮保存的事件范围。
            events = session["events"][
                : run.get("first_event_count", len(session["events"]))
            ]
            try:
                summary = verify_events(events, marker=marker)
            except Pending:
                return None
            return summary, len(events)

        summary, count = wait(
            fetch,
            lambda value: value is not None,
            self.cfg,
            "Deployment 首轮真实工具结果",
        )
        self.settle()
        self.history()
        run["first_round"] = {**summary, "read_only": True}
        run["first_event_count"] = count
        self.persist()
        print(
            json.dumps(
                {
                    "run_id": run["id"],
                    "session_id": run["session_id"],
                    "first_round": run["first_round"],
                },
                ensure_ascii=False,
            ),
            flush=True,
        )

    def settle(self) -> None:
        """完整回答后继续观察 Run.Error，覆盖服务端异步派发收尾窗口。"""
        deadline = (
            time.monotonic() + self.cfg["verification"]["dispatch_settle_seconds"]
        )
        while True:
            self.check_run()
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return
            time.sleep(min(self.cfg["verification"]["poll_seconds"], remaining))

    def second_round(self) -> None:
        """同一 Session 第二轮；发送前记账，结果未知时只读恢复，绝不盲目重发。"""
        self.verify()
        run = self.state["runs"][-1]
        app = self.app()
        if run.get("second_round"):
            events = self.snapshot(app)["events"][run["second_event_offset"] :]
            summary = verify_events(events, marker=f"CONTEXT_OK_{self.state['suffix']}")
            run["second_round"] = {
                **summary,
                "same_session": True,
                "nonce_repeated_in_prompt": False,
            }
            self.persist()
            print("第二轮已经通过，未重复发送", flush=True)
            return
        if "second_round_started" not in run:
            session = self.snapshot(app)
            run["second_event_offset"] = len(session["events"])
            run["second_round_started"] = dt.datetime.now(dt.UTC).isoformat()
            self.persist()
            app.run(
                run["app_name"],
                run["user_id"],
                run["session_id"],
                self.cfg["verification"]["second_round_prompt"],
            )
        marker = f"CONTEXT_OK_{self.state['suffix']}"

        def fetch():
            """只验收第二轮新增持久化事件，不以 SSE HTTP 200 作为成功。"""
            self.check_run()
            events = self.snapshot(app)["events"][run["second_event_offset"] :]
            try:
                return verify_events(events, marker=marker)
            except Pending:
                return None

        summary = wait(
            fetch, lambda value: value is not None, self.cfg, "第二轮上下文与 bash"
        )
        self.settle()
        run["second_round"] = {
            **summary,
            "same_session": True,
            "nonce_repeated_in_prompt": False,
        }
        self.persist()
        print(
            json.dumps({"second_round": run["second_round"]}, ensure_ascii=False),
            flush=True,
        )

    def report(self) -> Path:
        """输出脱敏验收证据，记录源码内容哈希及实际 Runtime 镜像版本。"""
        files = sorted(ROOT.glob("*.py")) + [
            ROOT / "pyproject.toml",
            ROOT / "config.yaml.example",
        ]
        hashes = {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in files
        }
        revision = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True
        )
        state_id = hashlib.sha256(str(self.state_path.resolve()).encode()).hexdigest()[
            :12
        ]
        path = REPORT_ROOT / state_id / "acceptance.json"
        save(
            path,
            {
                "recorded_at": dt.datetime.now(dt.UTC).isoformat(),
                "control_host": self.cfg["control"]["host"],
                "workspace_id": self.cfg["control"].get("workspace_id", ""),
                "source_commit": revision.stdout.strip(),
                "source_sha256": hashes,
                "python_version": sys.version,
                "runtime": self.state.get("runtime_provenance"),
                "dependency_versions": {
                    name: package_version(name) for name in ("requests", "PyYAML")
                },
                "resources": self.state["resources"],
                "runs": self.state["runs"],
                "request_audit": self.top.audit,
                "passed": bool(
                    self.state["runs"]
                    and self.state["runs"][-1].get("first_round")
                    and self.state["runs"][-1].get("second_round")
                    and self.state["runs"][-1].get("history_verified")
                ),
                "image_digest": None,
                "image_digest_note": "GetRuntime 未返回镜像 digest；仅记录实际 ArtifactUrl 和 Runtime 版本，不把 tag 当作 digest。",
            },
        )
        return path

    def delete_logical_sessions(self) -> None:
        """通过 Environment Key 删除 AKX 逻辑记录，释放 Cloud 资源引用。

        Cloud 的执行事件仍只从 Runtime 验收。这个 APIG 调用只用于清理
        Run 创建的 AKX 逻辑 Session；临时 Key 仅在内存中读取，随后撤销。
        """
        runs = [
            run
            for run in self.state["runs"]
            if run.get("session_id") and not run.get("logical_session_deleted")
        ]
        if not runs:
            return
        resources = self.state["resources"]
        if resources.get("cleanup_key", {}).get("deleted"):
            self.state.setdefault("revoked_cleanup_keys", []).append(
                resources.pop("cleanup_key")["id"]
            )
            self.state["tokens"].pop("CreateAPIKey", None)
            self.state["tokens"].pop("DeleteCleanupAPIKey", None)
            self.persist()
        endpoint = self.create_route()
        base = endpoint["base_url"]
        url = urlsplit(base)
        if (
            url.scheme != "https"
            or not url.hostname
            or url.username
            or url.query
            or url.fragment
        ):
            raise RuntimeError("清理 Endpoint 不是合法 HTTPS 地址")
        key_id = self.create(
            "cleanup_key",
            "CreateAPIKey",
            {
                "Name": "cloud-cleanup-" + self.state["suffix"],
                "EnvironmentId": resources["environment"]["id"],
                "EndpointId": endpoint["id"],
            },
            "ApiKeyId",
        )
        key = self.top.call("GetAPIKey", {"ApiKeyId": key_id}).get("Key")
        if not key:
            raise RuntimeError("GetAPIKey 未返回清理 Key")
        try:
            for run in runs:
                target = base.rstrip("/") + "/v1/sessions/" + run["session_id"]
                for method in ("DELETE", "GET"):
                    with requests.request(
                        method,
                        target,
                        headers={"x-api-key": key},
                        allow_redirects=False,
                        timeout=(10, 90),
                    ) as response:
                        if method == "GET" and response.status_code != 404:
                            raise RuntimeError("逻辑 Session 删除后仍能读取")
                        if method == "DELETE" and not (
                            200 <= response.status_code < 300
                            or response.status_code == 404
                        ):
                            raise APIError(
                                "删除 AKX 逻辑 Session", response.status_code
                            )
                run["logical_session_deleted"] = True
                self.persist()
        finally:
            self.top.call(
                "DeleteAPIKey",
                {"ApiKeyId": key_id, "ClientToken": self.token("DeleteCleanupAPIKey")},
            )
            resources["cleanup_key"]["deleted"] = True
            self.persist()

    def cleanup(self) -> None:
        """暂停/归档自建 Deployment、删除自建 Session/Harness/Environment/Runtime。"""
        resources = self.state["resources"]
        if resources.get("environment", {}).get("owned") and "sandbox" not in resources:
            result = self.top.call(
                "ListEnvironmentResources",
                {"EnvironmentId": resources["environment"]["id"], "MaxResults": 100},
            )
            active = [
                item
                for item in result.get("Items", [])
                if item.get("Status") != "Deleted"
            ]
            if len(active) > 1 or result.get("NextToken"):
                raise RuntimeError("清理前无法唯一定位 Cloud 工具资源")
            if active:
                resources["sandbox"] = {"id": active[0]["ResourceId"], "owned": True}
                self.persist()
        deployment = resources.get("deployment")
        if deployment and deployment["owned"] and not deployment.get("deleted"):
            try:
                self.top.call(
                    "PauseDeployment",
                    {
                        "DeploymentId": deployment["id"],
                        "ClientToken": self.token("PauseDeployment"),
                    },
                )
                # 定时调度可能生成尚未被用户选择的 Session；暂停后完整登记，
                # 失败 Run 也可能留下 Session，因此清理不以 Run.Error 阻止登记。
                for item in self.deployment_runs():
                    recorded = next(
                        (
                            run
                            for run in self.state["runs"]
                            if run["id"] == item["DeploymentRunId"]
                        ),
                        None,
                    )
                    if recorded is None:
                        recorded = {
                            "id": item["DeploymentRunId"],
                            "deployment_id": deployment["id"],
                        }
                        self.state["runs"].append(recorded)
                        self.persist()
                    wait(
                        lambda: self.check_run(recorded, check_error=False),
                        lambda value: bool(
                            value.get("SessionId") or value.get("Error")
                        ),
                        self.cfg,
                        "清理前等待 Run SessionId",
                    )
                self.top.call(
                    "ArchiveDeployment",
                    {
                        "DeploymentId": deployment["id"],
                        "ClientToken": self.token("ArchiveDeployment"),
                    },
                )
            except APIError as exc:
                if exc.status != 404:
                    raise
            deployment["deleted"] = True
            self.persist()
        if any(
            run.get("session_id") and not run.get("session_deleted")
            for run in self.state["runs"]
        ):
            app = self.app()
            for run in self.state["runs"]:
                if run.get("session_id") and not run.get("session_deleted"):
                    path = app.path(run["app_name"], run["user_id"], run["session_id"])
                    with app.request("DELETE", path, allowed=(404,)):
                        pass
                    with app.request("GET", path, allowed=(404,)) as response:
                        if response.status_code != 404:
                            raise RuntimeError("Session 删除后仍能读取")
                    run["session_deleted"] = True
                    self.persist()
        self.delete_logical_sessions()
        for kind, action, field in (
            ("harness", "ArchiveHarness", "HarnessId"),
            ("runtime", "DeleteRuntime", "RuntimeId"),
            ("session_store", "DeleteSessionStore", "SessionStoreId"),
            ("sandbox", "DeleteEnvironmentResource", "ResourceId"),
            ("environment", "DeleteEnvironment", "EnvironmentId"),
        ):
            value = resources.get(kind)
            if value and value["owned"] and not value.get("deleted"):
                try:
                    body = {field: value["id"]}
                    if kind != "session_store":
                        body["ClientToken"] = self.token(action)
                    self.top.call(action, body)
                except APIError as exc:
                    if exc.status != 404:
                        raise
                if kind != "harness":
                    get_action = {
                        "runtime": "GetRuntime",
                        "session_store": "GetSessionStore",
                        "sandbox": "GetEnvironmentResource",
                        "environment": "GetEnvironment",
                    }[kind]

                    def deleted():
                        """删除操作受理后继续查询，直到资源消失或进入 Deleted。"""
                        try:
                            return self.top.call(get_action, {field: value["id"]})
                        except APIError as exc:
                            if exc.status == 404:
                                return {"Status": "Deleted"}
                            raise

                    wait(
                        deleted,
                        lambda result: result.get("Status") == "Deleted",
                        self.cfg,
                        f"{kind} 删除完成",
                    )
                value["deleted"] = True
                self.persist()
        print("清理完成；账号 Endpoint、执行角色和复用的资源保留", flush=True)


def main() -> None:
    """提供一键验收与可恢复的分阶段命令；状态路径不受当前工作目录影响。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=[
            "create-route",
            "create-environment",
            "create-session-store",
            "create-runtime",
            "create-harness",
            "create-deployment",
            "run-deployment",
            "create-session",
            "get-session",
            "verify-session",
            "invoke-session",
            "list-deployment-runs",
            "prepare",
            "run",
            "verify",
            "second-round",
            "all",
            "cleanup",
        ],
    )
    parser.add_argument("--config", type=Path, default=ROOT / "config.yaml")
    parser.add_argument(
        "--state",
        type=Path,
        default=DEFAULT_STATE,
        help="状态文件，默认使用当前项目的 .agentkit/state.json",
    )
    parser.add_argument(
        "--new-run", action="store_true", help="显式新建一次 Run；默认恢复最近一次"
    )
    parser.add_argument(
        "--run-id",
        help="get-session / verify-session 选择已有 Run，适用于定时任务；不会触发新 Run",
    )
    args = parser.parse_args()
    if args.run_id is not None and args.command not in {
        "get-session",
        "verify-session",
        "verify",
    }:
        parser.error("--run-id 仅用于 get-session / verify-session / verify")
    sample = Sample(load_config(args.config, args.command), args.state)
    try:
        if args.run_id is not None:
            sample.select_run(args.run_id)
        commands = {
            "create-route": sample.create_route,
            "create-environment": sample.create_environment,
            "create-session-store": sample.create_session_store,
            "create-runtime": sample.create_runtime,
            "create-harness": sample.create_harness,
            "create-deployment": sample.create_deployment,
            "get-session": sample.get_session,
            "list-deployment-runs": sample.list_deployment_runs,
        }
        if args.command in commands:
            commands[args.command]()
        if args.command == "create-session":
            sample.create_session(new_run=args.new_run)
        if args.command in {"prepare", "all"}:
            sample.prepare()
        if args.command in {"run", "run-deployment", "all"}:
            sample.trigger(new_run=args.new_run)
        if args.command in {"verify", "verify-session"}:
            sample.verify()
        if args.command in {
            "second-round",
            "invoke-session",
            "all",
        }:
            sample.second_round()
        if args.command == "cleanup":
            sample.cleanup()
    finally:
        print(f"验收报告：{sample.report()}", flush=True)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError, TimeoutError, KeyError) as exc:
        print(f"失败：{exc}", file=sys.stderr)
        sys.exit(1)
