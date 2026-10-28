"""Local resource console. Cloud credentials never leave the Python process."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import sys
import tempfile
import threading
from pathlib import Path
from urllib.parse import quote, urlsplit

import requests
import yaml

SAMPLE = Path(__file__).resolve().parent.parent / "resource_to_chat_http"
sys.path.insert(0, str(SAMPLE))
# Shared sample modules are importable only after adding the sibling directory.
from _clients import (  # noqa: E402
    DataPlaneClient,
    HarnessInfraError,
    TopClient,
    _decode_json,
    sign_headers,
)
from _config import (  # noqa: E402
    _control_config,
    _environment_config,
    _harness_config,
    _runtime_template_config,
    _session_store_config,
)

CATALOG = {
    "endpoints": {
        "label": "Endpoint",
        "id": "EndpointId",
        "create": "CreateEndpoint",
        "list": "ListEndpoints",
        "get": None,
        "delete": None,
        "filters": [],
    },
    "harnesses": {
        "label": "Harness",
        "id": "HarnessId",
        "create": "CreateHarness",
        "list": "ListHarnesses",
        "get": "GetHarness",
        "archive": "ArchiveHarness",
        "delete": None,
        "delete_unavailable_reason": "当前 akx 契约未提供 Harness 删除接口；删除不会调用归档接口。",
        "filters": ["IncludeArchived", "Status"],
    },
    "stores": {
        "label": "SessionStore",
        "id": "SessionStoreId",
        "create": "CreateSessionStore",
        "list": "ListSessionStores",
        "get": "GetSessionStore",
        "delete": "DeleteSessionStore",
        "filters": ["ProjectName", "Filters", "CreateTimeAfter", "CreateTimeBefore"],
    },
    "templates": {
        "label": "RuntimeTemplate",
        "id": "RuntimeTemplateId",
        "create": "CreateRuntimeTemplate",
        "list": "ListRuntimeTemplates",
        "get": "GetRuntimeTemplate",
        "delete": "DeleteRuntimeTemplate",
        "filters": ["Status", "NamePrefix"],
    },
    "environments": {
        "label": "Environment",
        "id": "EnvironmentId",
        "create": "CreateEnvironment",
        "list": "ListEnvironments",
        "get": "GetEnvironment",
        "delete": "DeleteEnvironment",
        "filters": ["IncludeArchived"],
    },
    "keys": {
        "label": "Environment API Key",
        "id": "ApiKeyId",
        "create": "CreateAPIKey",
        "list": "ListAPIKeys",
        "get": "GetAPIKey",
        "delete": "DeleteAPIKey",
        "filters": ["EnvironmentId", "EndpointId"],
    },
    "resources": {
        "label": "EnvironmentResource",
        "id": "ResourceId",
        "create": "CreateEnvironmentResource",
        "list": "ListEnvironmentResources",
        "get": "GetEnvironmentResource",
        "delete": "DeleteEnvironmentResource",
        "filters": ["EnvironmentId", "Status", "TargetType", "IncludeDeleted"],
    },
    "sessions": {
        "label": "Session",
        "id": "id",
        "create": "POST /v1/sessions",
        "list": "GET /v1/sessions",
        "get": "GET /v1/sessions/{id}",
        "delete": "Archive + DELETE",
        "filters": [
            "environment_id",
            "agent_id",
            "runtime_template_id",
            "statuses",
            "include_archived",
        ],
    },
}
SECRET_FIELDS = {
    "key",
    "apikey",
    "environmentkey",
    "accesskey",
    "secretkey",
    "sessiontoken",
    "authorization",
    "password",
    "token",
    "secret",
    "envs",
    "envvars",
    "headers",
}


def redact(value, secrets=()):
    if isinstance(value, dict):
        return {
            k: (
                "••••••••"
                if re.sub(r"[^a-z]", "", k.lower()) in SECRET_FIELDS and v
                else redact(v, secrets)
            )
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [redact(v, secrets) for v in value]
    if isinstance(value, str):
        for secret in sorted((s for s in secrets if s), key=len, reverse=True):
            value = value.replace(secret, "••••••••")
    return value


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,256}", value):
        raise ValueError(
            "资源 ID 不能为空，且只能包含字母、数字、下划线、点、冒号和连字符"
        )
    return value


def validate_url(value):
    parsed = urlsplit(value)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("网关地址必须为不含凭据、查询参数或 fragment 的 HTTP(S) URL")
    return value.rstrip("/")


class Console:
    def __init__(self, config_path: Path, state_path: Path | None = None):
        self.path = config_path.resolve()
        try:
            raw = yaml.safe_load(self.path.read_text())
        except (OSError, yaml.YAMLError):
            raise ValueError(f"无法读取 YAML 配置：{self.path}") from None
        if not isinstance(raw, dict) or raw.get("version") != 1:
            raise ValueError("配置须为 version: 1 的 YAML 对象")
        self.raw = raw
        self.control = TopClient(_control_config(raw, require_credentials=True))
        # A timeout must not silently repeat a non-idempotent CreateEndpoint.
        self.control.retries = 0
        scope = self.control.scope + self.control.config.access_key + str(self.path)
        digest = hashlib.sha256(scope.encode()).hexdigest()[:20]
        self.state_path = (
            state_path or Path(__file__).parent / ".local" / f"keys-{digest}.json"
        )
        self.lock = threading.RLock()
        self.keys = {}
        if self.state_path.exists():
            try:
                self.keys = json.loads(self.state_path.read_text())
                if not isinstance(self.keys, dict):
                    raise TypeError()
            except (OSError, ValueError, TypeError):
                raise ValueError(
                    "本地密钥文件损坏，请检查 .local 中的文件；为避免丢失密钥，服务未覆盖它"
                ) from None
            self.state_path.chmod(0o600)
        self.config_key = raw.get("environment", {}).get("env_api_key", {})
        self.config_key = {k: self.resolve(v) for k, v in self.config_key.items()}
        self.runtime_session_id = raw.get("session", {}).get("id", "")
        self.revoked_config_keys = set()
        options = raw.get("console", {})
        self.rest_base = (
            validate_url(options["control_rest_base_url"])
            if options.get("control_rest_base_url")
            else ""
        )
        self.presets = self.make_presets(raw)

    @staticmethod
    def resolve(value):
        if isinstance(value, str) and re.fullmatch(
            r"\$\{[A-Za-z_][A-Za-z0-9_]*\}", value
        ):
            return os.getenv(value[2:-1], "")
        return value

    def secrets(self):
        with self.lock:
            return [
                self.control.config.access_key,
                self.control.config.secret_key,
                self.control.config.session_token,
                self.config_key.get("value", ""),
                *(v["value"] for v in self.keys.values()),
            ]

    def refresh_runtime_config(self):
        """Refresh tutorial-written runtime references, without changing account scope."""
        with self.lock:
            try:
                raw = yaml.safe_load(self.path.read_text())
                if not isinstance(raw, dict) or raw.get("version") != 1:
                    return "config.yaml 格式不正确，未刷新会话凭据"
                if raw.get("volcengine") != self.raw.get("volcengine"):
                    return "控制面账号或地域配置已变更，请重启 server 后再连接数据面"
                environment = raw.get("environment", {})
                session = raw.get("session", {})
                key = environment.get("env_api_key", {})
                if not isinstance(key, dict) or not isinstance(session, dict):
                    return "config.yaml 的 Session / 环境密钥配置格式不正确"
                values = {
                    name: self.resolve(key.get(name) or "") for name in ("id", "value")
                }
                session_id = session.get("id") or ""
                if not all(isinstance(v, str) for v in [*values.values(), session_id]):
                    return "config.yaml 的 Session ID 和环境密钥须为字符串"
                self.config_key = (
                    {} if values["id"] in self.revoked_config_keys else values
                )
                self.runtime_session_id = session_id
                return ""
            except (OSError, yaml.YAMLError, AttributeError):
                return "暂时无法读取 config.yaml，请确认文件已保存后刷新"

    def safe(self, value):
        return redact(value, self.secrets())

    def make_presets(self, raw):
        # Reuse the tutorial's field translation and validation, without requiring a model key for listing.
        h = _harness_config(
            raw,
            model_id="",
            model_base_url="",
            model_api_key_name="",
            require_model_key_name=False,
        )
        store = _session_store_config(raw)
        t = _runtime_template_config(raw)
        e = _environment_config(raw)
        env = {"Type": e.type, "Resources": e.resources}
        raw_env = raw["environment"]
        if raw_env.get("image_url") not in (None, "", "null"):
            env["ImageUrl"] = raw_env["image_url"]
        if raw_env.get("envs"):
            env["EnvVars"] = raw_env["envs"]
        packages = {
            k.capitalize(): v for k, v in (raw_env.get("package") or {}).items() if v
        }
        if packages:
            env["Packages"] = packages
        network = raw_env.get("network", {})
        if network.get("use_private_network"):
            env["AgentKit"] = {
                "Networking": {
                    "EnablePrivateNetwork": True,
                    "VpcConfiguration": {
                        "VpcId": network["vpc_id"],
                        "SubnetIds": [network["subnet_id"]],
                        "SecurityGroupIds": network["security_group_ids"],
                    },
                }
            }
        store_preset = {
            "Name": "console-session-store",
            "ProjectName": store.project_name,
            "Description": "Harness Console session storage",
            "ProviderType": "SERVERLESS_PG",
        }
        if store.vpc_id:
            store_preset["VpcConfig"] = {
                "VpcId": store.vpc_id,
                "SubnetIds": store.subnet_ids,
            }
        template = {
            "SessionStoreId": "",
            "Name": "console-runtime",
            "RoleName": t.role_name,
            "Resources": t.resources,
        }
        for k, v in (
            ("ImageUrl", t.image_url),
            ("Envs", t.envs),
            ("Runtime", t.runtime),
        ):
            if v:
                template[k] = v
        return {
            "endpoints": {},
            "harnesses": {
                "Name": "console-harness",
                "Description": "",
                "Model": {"Id": h.model_id, "BaseUrl": h.model_base_url},
                "AgentLoop": h.agent_loop,
                "System": h.system_prompt,
                "Tools": h.tools,
                "Skills": h.skills,
                "McpServers": h.mcp_servers,
            },
            "stores": store_preset,
            "templates": template,
            "environments": {
                "Name": "console-environment",
                "Description": "",
                "Config": env,
                "Metadata": e.metadata,
            },
            "keys": {
                "Name": "console-key",
                "EnvironmentId": "",
                "EndpointId": e.endpoint_id,
            },
            "resources": {
                "Name": "console-resource",
                "Region": self.control.config.region,
                "Target": {"Type": "AgentKit", "EnvironmentId": ""},
            },
            "sessions": {
                "title": raw.get("session", {}).get("title", "Console chat"),
                "agent": {"type": "agent", "id": ""},
                "environment_id": "",
                "runtime_template_id": "",
                "runtime_type": "agentkit_runtime",
                "initial_events": [],
            },
        }

    def bootstrap(self):
        config_refresh_error = self.refresh_runtime_config()
        catalog = copy.deepcopy(CATALOG)
        catalog["endpoints"]["delete"] = (
            "DELETE /v1/endpoint/{id}" if self.rest_base else None
        )
        presets = copy.deepcopy(self.presets)
        presets["templates"].pop("Envs", None)
        presets["environments"]["Config"].pop("EnvVars", None)
        return self.safe(
            {
                "catalog": catalog,
                "config_path": str(self.path),
                "region": self.control.config.region,
                "control_host": self.control.config.host,
                "presets": presets,
                "model_key_name": self.resolve(
                    self.raw.get("harness", {}).get("model", {}).get("api_key_name", "")
                ),
                "local_keys": self.key_metadata(),
                "default_session": self.runtime_session_id,
                "config_refresh_error": config_refresh_error,
                "endpoint_delete_note": "Endpoint 详情从完整列表匹配。删除使用控制面 REST 网关，需配置 console.control_rest_base_url。",
            }
        )

    def key_metadata(self):
        with self.lock:
            items = [
                {
                    "id": k,
                    "environment_id": v.get("environment_id", ""),
                    "endpoint_id": v.get("endpoint_id", ""),
                    "source": "本地保存",
                }
                for k, v in self.keys.items()
            ]
            if (
                self.config_key.get("id")
                and self.config_key.get("value")
                and self.config_key["id"] not in self.keys
            ):
                items.append({"id": self.config_key["id"], "source": "config.yaml"})
            return items

    def save_keys(self):
        self.state_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd, temp = tempfile.mkstemp(dir=self.state_path.parent, prefix=".keys-")
        try:
            with os.fdopen(fd, "w") as file:
                json.dump(self.keys, file)
                file.flush()
                os.fsync(file.fileno())
            os.replace(temp, self.state_path)
        finally:
            if os.path.exists(temp):
                os.unlink(temp)

    def store_key(self, key_id, value, metadata):
        identifier(key_id)
        if not isinstance(value, str) or not value.strip():
            raise ValueError("环境 API Key 明文不能为空")
        with self.lock:
            self.keys[key_id] = {
                "value": value.strip(),
                "environment_id": metadata.get("EnvironmentId", ""),
                "endpoint_id": metadata.get("EndpointId", ""),
            }
            self.save_keys()

    def import_key(self, body):
        key_id = identifier(body.get("id"))
        metadata = self.control.call("GetAPIKey", {"ApiKeyId": key_id})
        self.store_key(key_id, body.get("value"), metadata)
        return {"local_keys": self.key_metadata()}

    def data_client(self, context):
        config_error = self.refresh_runtime_config()
        if config_error:
            raise ValueError(config_error)
        key_id = identifier(context.get("key_id"))
        endpoint_id = identifier(context.get("endpoint_id"))
        # Resolve binding and URL from the control plane; never send keys to a browser-provided URL.
        key = self.control.call("GetAPIKey", {"ApiKeyId": key_id})
        if key.get("EndpointId") != endpoint_id:
            raise ValueError("所选 Endpoint 与 API Key 绑定不一致")
        endpoint = self.get("endpoints", endpoint_id)
        with self.lock:
            secret = self.keys.get(key_id, {}).get("value")
            if not secret and self.config_key.get("id") == key_id:
                secret = self.config_key.get("value")
        if not secret:
            raise ValueError(
                "该 Key 的明文尚未保存在本地；请导入已有密钥，或创建一个新的环境 API Key"
            )
        return DataPlaneClient(validate_url(endpoint["BaseUrl"]), secret), key.get(
            "EnvironmentId"
        )

    def list(self, kind, filters=None, cursor="", context=None):
        spec = CATALOG[kind]
        filters = filters or {}
        allowed = set(spec["filters"])
        if set(filters) - allowed:
            raise ValueError("列表包含不支持的筛选字段")
        if kind == "sessions":
            data, environment = self.data_client(context or {})
            if (
                filters.get("environment_id")
                and filters["environment_id"] != environment
            ):
                raise ValueError("Session 筛选环境与所选 API Key 不一致")
            params = {
                "limit": 100,
                "order": "desc",
                **filters,
                "environment_id": environment,
            }
            if cursor:
                params["page"] = cursor
            params = {
                k: str(v).lower() if isinstance(v, bool) else v
                for k, v in params.items()
            }
            result = data.call("GET", "/v1/sessions", params=params)
            items, next_cursor = result.get("data"), result.get("next_page")
        else:
            body = {"MaxResults": 100, **filters}
            if cursor:
                body["NextToken"] = cursor
            result = self.control.call(spec["list"], body)
            items, next_cursor = (
                result.get("SessionStores" if kind == "stores" else "Items"),
                result.get("NextToken"),
            )
        if not isinstance(items, list):
            raise TypeError(
                "上游列表响应缺少 Items/SessionStores/data 数组，请确认服务端协议版本"
            )
        if next_cursor and next_cursor == cursor:
            raise ValueError("上游重复返回分页游标，已停止翻页")
        return {"items": items, "next_cursor": next_cursor or ""}

    def all_items(self, kind):
        items, cursor, seen = [], "", set()
        for _ in range(500):
            page = self.list(kind, cursor=cursor)
            items.extend(page["items"])
            cursor = page["next_cursor"]
            if not cursor:
                return items
            if cursor in seen:
                raise ValueError("分页游标循环")
            seen.add(cursor)
        raise ValueError("列表超过 500 页，请使用筛选")

    def get(self, kind, resource_id, context=None):
        identifier(resource_id)
        if kind == "endpoints":
            for item in self.all_items(kind):
                if item.get("EndpointId") == resource_id:
                    return item
            raise HarnessInfraError(
                "GetEndpoint",
                "NotFound",
                "Endpoint 不在当前账号列表中",
                status_code=404,
            )
        if kind == "sessions":
            data, _ = self.data_client(context or {})
            return data.call("GET", f"/v1/sessions/{quote(resource_id, safe='')}")
        spec = CATALOG[kind]
        return self.control.call(spec["get"], {spec["id"]: resource_id})

    def restore_preset(self, value, original):
        """Round-trip redacted default credentials without sending mask text upstream."""
        safe_original = self.safe(original)
        if value == safe_original and safe_original != original:
            return copy.deepcopy(original)
        if isinstance(value, dict) and isinstance(original, dict):
            return {
                k: self.restore_preset(v, original.get(k)) for k, v in value.items()
            }
        if isinstance(value, list) and isinstance(original, list):
            return [
                self.restore_preset(v, original[i] if i < len(original) else None)
                for i, v in enumerate(value)
            ]
        return copy.deepcopy(value)

    def create(self, kind, body, context=None, model_key_name="", token=""):
        if not isinstance(body, dict):
            raise TypeError("创建参数须为 JSON 对象")
        body = self.restore_preset(body, self.presets[kind])
        if kind == "environments":
            config = body.get("Config", {})
            packages = config.get("Packages")
            # Older open forms may still submit an empty Packages object.
            if isinstance(packages, dict) and all(
                value == [] for value in packages.values()
            ):
                config.pop("Packages")
        # Secrets omitted from editable presets stay server-side; explicit replacements are respected.
        if (
            kind == "templates"
            and "Envs" not in body
            and self.presets[kind].get("Envs")
        ):
            body["Envs"] = self.presets[kind]["Envs"]
        if (
            kind == "environments"
            and "EnvVars" not in body.get("Config", {})
            and self.presets[kind]["Config"].get("EnvVars")
        ):
            body.setdefault("Config", {})["EnvVars"] = self.presets[kind]["Config"][
                "EnvVars"
            ]
        if kind == "sessions":
            data, environment = self.data_client(context or {})
            if body.get("environment_id") != environment:
                raise ValueError("Session Environment 必须与所选 API Key 绑定一致")
            model_key_name = model_key_name or self.resolve(
                self.raw.get("harness", {}).get("model", {}).get("api_key_name", "")
            )
            if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", model_key_name or ""):
                raise ValueError("请输入方舟模型 API Key Name（不是密钥明文）")
            return data.call(
                "POST",
                "/v1/sessions",
                body=body,
                headers={
                    "x-ark-key-name": model_key_name,
                    "Idempotency-Key": identifier(token),
                },
            )
        if kind == "stores":
            if body.get("ProviderType") != "SERVERLESS_PG":
                raise ValueError("控制台仅创建 SERVERLESS_PG SessionStore")
            vpc = body.get("VpcConfig", {})
            if not isinstance(vpc, dict):
                raise ValueError("VpcConfig 必须为对象")
            try:
                _session_store_config(
                    {
                        "session_store": {
                            "project_name": body.get("ProjectName", "default"),
                            "network": {
                                "use_private_network": bool(vpc),
                                "vpc_id": vpc.get("VpcId", ""),
                                "subnet_ids": vpc.get("SubnetIds", []),
                            },
                        }
                    }
                )
            except (RuntimeError, TypeError, ValueError) as error:
                raise ValueError(
                    "SessionStore 配置不正确；私网模式需 VpcId 和一个 SubnetId"
                ) from error
            # This API has no ClientToken contract, unlike Harness/RuntimeTemplate.
            body.pop("ClientToken", None)
            if not vpc:
                body.pop("VpcConfig", None)
        if kind == "templates":
            store_id = body.get("SessionStoreId")
            if not store_id:
                raise ValueError(
                    "创建 RuntimeTemplate 必须选择 Ready 的 SERVERLESS_PG SessionStore"
                )
            store = self.get("stores", store_id)
            if (
                store.get("SessionStoreId") != store_id
                or store.get("Status") != "Ready"
                or store.get("ProviderType") != "SERVERLESS_PG"
            ):
                raise ValueError(
                    "所选 SessionStore 尚未 Ready 或不是 SERVERLESS_PG，请刷新后重试"
                )
        if kind not in {"endpoints", "stores"}:
            body.setdefault("ClientToken", identifier(token))
        result = self.control.call(CATALOG[kind]["create"], body)
        if kind == "keys" and result.get("Key"):
            self.store_key(result["ApiKeyId"], result["Key"], {**body, **result})
        if kind == "keys":
            result["local_key_available"] = any(
                k["id"] == result.get("ApiKeyId") for k in self.key_metadata()
            )
        return result

    def archive(self, kind, resource_id, token=""):
        spec = CATALOG[kind]
        if not spec.get("archive"):
            raise ValueError("该资源未提供独立归档操作")
        result = self.control.call(
            spec["archive"],
            {spec["id"]: identifier(resource_id), "ClientToken": identifier(token)},
        )
        return {
            "accepted": True,
            "message": "Harness 已归档，历史版本保留",
            "result": result,
        }

    def delete(self, kind, resource_id, context=None, token="", reason=""):
        identifier(resource_id)
        if kind == "sessions":
            data, _ = self.data_client(context or {})
            path = f"/v1/sessions/{resource_id}"
            data.call("POST", path + "/archive")
            result = data.call("DELETE", path)
            return {
                "accepted": True,
                "message": "已受理异步删除；刷新并查询至 404 才表示删除完成",
                "result": result,
            }
        if kind == "endpoints":
            if not self.rest_base:
                raise ValueError(
                    "公开 TOP 没有 DeleteEndpoint；请配置 console.control_rest_base_url 为支持该 REST 路由的可信控制面网关"
                )
            self.get(kind, resource_id)
            parsed = urlsplit(self.rest_base)
            path = parsed.path.rstrip("/") + f"/v1/endpoint/{resource_id}"
            headers = sign_headers(
                "DELETE", parsed.netloc, {}, b"", config=self.control.config, path=path
            )
            try:
                response = requests.delete(
                    self.rest_base + f"/v1/endpoint/{resource_id}",
                    headers=headers,
                    timeout=self.control.timeout,
                    allow_redirects=False,
                )
            except requests.RequestException:
                raise ValueError(
                    "Endpoint 删除请求网络异常，请先查询状态再决定是否重试"
                ) from None
            return _decode_json("DeleteEndpoint", response, top_envelope=False)
        spec = CATALOG[kind]
        if not spec.get("delete"):
            raise ValueError(
                spec.get("delete_unavailable_reason", "该资源未提供删除操作")
            )
        body = {spec["id"]: resource_id}
        if kind != "stores":
            body["ClientToken"] = identifier(token)
        if kind == "templates":
            if (
                not isinstance(reason, str)
                or not 1 <= len(reason.strip().encode("utf-8")) <= 1024
            ):
                raise ValueError(
                    "删除 RuntimeTemplate 必须填写原因（去除首尾空白后 1–1024 UTF-8 字节）"
                )
            body["Reason"] = reason.strip()
        result = self.control.call(spec["delete"], body)
        if kind == "keys":
            with self.lock:
                self.keys.pop(resource_id, None)
                if self.config_key.get("id") == resource_id:
                    self.revoked_config_keys.add(resource_id)
                    self.config_key = {}
                self.save_keys()
        return {
            "accepted": True,
            "message": "删除请求已受理，请刷新资源状态",
            "result": result,
        }

    def events(self, resource_id, context, after=0):
        data, _ = self.data_client(context)
        result = data.call(
            "GET",
            f"/v1/sessions/{identifier(resource_id)}/events",
            params={"after_sequence": int(after), "order": "asc", "limit": 100},
        )
        if not isinstance(result.get("data"), list):
            raise TypeError("事件响应缺少 data 数组")
        return result

    def send(self, resource_id, context, prompt, event_id):
        if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 100000:
            raise ValueError("请输入 1–100000 字的问题")
        data, _ = self.data_client(context)
        return data.call(
            "POST",
            f"/v1/sessions/{identifier(resource_id)}/events",
            body={
                "events": [
                    {
                        "id": identifier(event_id),
                        "type": "user.message",
                        "content": [{"type": "text", "text": prompt}],
                    }
                ]
            },
        )
