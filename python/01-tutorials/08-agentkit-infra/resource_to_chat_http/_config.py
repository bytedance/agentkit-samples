"""加载并校验 Harness Infra 示例的 YAML 配置。"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import yaml

from _clients import API_VERSION, ControlConfig

DEFAULT_MODEL_ID = "doubao-seed-evolving"
DEFAULT_MODEL_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
DEFAULT_RUNTIME_ROLE_NAME = "AgentKitDefaultRuntimeAccess"
DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"
EXAMPLE_CONFIG_PATH = DEFAULT_CONFIG_PATH.with_name("config.yaml.example")
LEGACY_CONFIG_PATH = Path(__file__).with_name("config.yaml")
MODEL_KEY_NAME_PATTERN = re.compile(r"[A-Za-z0-9_-]{1,128}")
ENV_REFERENCE_PATTERN = re.compile(r"^\$\{([A-Za-z_][A-Za-z0-9_]*)\}$")
PLACEHOLDER_PATTERN = re.compile(
    r"(^[<[{].*[>\]}]$)|(^your[-_])|(^replace[-_]?me$)|(^change[-_]?me$)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class SessionConfig:
    id: str
    name: str
    endpoint_base_url: str
    title: str
    prompt: str
    expected_substring: str
    verify_sandbox_tools: bool


@dataclass(frozen=True)
class HarnessConfig:
    system_prompt: str
    model_id: str
    model_base_url: str
    model_api_key_name: str
    model_project_name: str
    agent_loop: str
    tools: list[Any]
    skills: list[Any]
    mcp_servers: list[Any]


@dataclass(frozen=True)
class RuntimeTemplateConfig:
    role_name: str
    resources: dict[str, int]
    image_url: str | None
    envs: dict[str, str]
    runtime: dict[str, Any]


@dataclass(frozen=True)
class SessionStoreConfig:
    project_name: str
    vpc_id: str
    subnet_ids: list[str]


@dataclass(frozen=True)
class EnvironmentConfig:
    type: str
    resources: dict[str, int]
    metadata: dict[str, str]
    endpoint_id: str
    env_api_key_id: str
    env_api_key_value: str


@dataclass(frozen=True)
class ExampleConfig:
    """已通过前置校验的 YAML 配置；可能包含待清理的 Environment Key。"""

    control: ControlConfig
    session: SessionConfig
    harness: HarnessConfig
    session_store: SessionStoreConfig
    runtime_template: RuntimeTemplateConfig
    environment: EnvironmentConfig

    @property
    def model_id(self) -> str:
        return self.harness.model_id

    @property
    def model_base_url(self) -> str:
        return self.harness.model_base_url

    @property
    def model_api_key_name(self) -> str:
        return self.harness.model_api_key_name

    @property
    def model_project_name(self) -> str:
        return self.harness.model_project_name

    @property
    def runtime_role_name(self) -> str:
        return self.runtime_template.role_name


def config_path(*fallback_paths: Path) -> Path:
    """显式配置优先，其次共享配置；兼容各示例原目录中的配置。"""
    configured = os.getenv("HARNESS_INFRA_CONFIG", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    for path in (DEFAULT_CONFIG_PATH, *fallback_paths, LEGACY_CONFIG_PATH):
        if path.exists():
            return path.resolve()
    return DEFAULT_CONFIG_PATH.resolve()


def _mapping(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(f"{name} must be a YAML mapping")
    return value


def _list(value: Any, name: str) -> list[Any]:
    if not isinstance(value, list):
        raise TypeError(f"{name} must be a YAML list")
    return value


def _string(value: Any, name: str, *, allow_empty: bool = False) -> str:
    if value is None and allow_empty:
        return ""
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    resolved = value.strip()
    reference = ENV_REFERENCE_PATTERN.fullmatch(resolved)
    if reference:
        resolved = os.getenv(reference.group(1), "").strip()
    if not resolved and not allow_empty:
        raise RuntimeError(f"{name} must be a non-empty string")
    return resolved


def _positive_integer(value: Any, name: str, *, minimum: int = 1) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise RuntimeError(f"{name} must be an integer >= {minimum}")
    return value


def _reject_placeholder(name: str, value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise RuntimeError(f"missing required configuration: {name}")
    if PLACEHOLDER_PATTERN.search(normalized):
        raise RuntimeError(f"{name} still contains an example placeholder")
    if any(character.isspace() for character in normalized):
        raise RuntimeError(f"{name} must not contain whitespace")
    return normalized


def _validate_url(name: str, value: str) -> str:
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise RuntimeError(
            f"{name} must be an HTTPS URL without credentials, query, or fragment"
        )
    return value.rstrip("/")


def _validate_data_url(name: str, value: str) -> str:
    parsed = urlsplit(value)
    is_local_http = parsed.scheme == "http" and parsed.hostname in {
        "127.0.0.1",
        "localhost",
        "::1",
    }
    if (
        (parsed.scheme != "https" and not is_local_http)
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise RuntimeError(
            f"{name} must be an HTTPS URL without credentials, query, or fragment"
        )
    return value.rstrip("/")


def _read_yaml() -> dict[str, Any]:
    path = config_path()
    try:
        parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError:
        raise RuntimeError(
            f"cannot read config file: {path}; copy {EXAMPLE_CONFIG_PATH} "
            "to that path and fill in the required settings"
        ) from None
    except yaml.YAMLError:
        raise RuntimeError(f"cannot parse config file: {path}") from None
    root = _mapping(parsed, "config")
    if root.get("version") != 1:
        raise RuntimeError("config.version must be 1")
    return root


def _first_env(*names: str, default: str = "") -> str:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return default


def _control_config(raw: dict[str, Any], *, require_credentials: bool) -> ControlConfig:
    volcengine = _mapping(raw.get("volcengine"), "volcengine")
    access_key = _string(
        volcengine.get("access_key"), "volcengine.access_key", allow_empty=True
    ) or _first_env(
        "HARNESS_INFRA_ACCESS_KEY",
        "VOLCENGINE_AGENTKIT_ACCESS_KEY",
        "VOLCENGINE_ACCESS_KEY",
    )
    secret_key = _string(
        volcengine.get("secret_key"), "volcengine.secret_key", allow_empty=True
    ) or _first_env(
        "HARNESS_INFRA_SECRET_KEY",
        "VOLCENGINE_AGENTKIT_SECRET_KEY",
        "VOLCENGINE_SECRET_KEY",
    )
    region = _string(
        volcengine.get("region"), "volcengine.region", allow_empty=True
    ) or _first_env(
        "HARNESS_INFRA_REGION",
        "VOLCENGINE_AGENTKIT_REGION",
        "VOLCENGINE_REGION",
        default="cn-beijing",
    )
    if require_credentials:
        access_key = _reject_placeholder("volcengine.access_key", access_key)
        secret_key = _reject_placeholder("volcengine.secret_key", secret_key)
    return ControlConfig(
        access_key=access_key,
        secret_key=secret_key,
        session_token=_first_env(
            "HARNESS_INFRA_SESSION_TOKEN",
            "VOLCENGINE_AGENTKIT_SESSION_TOKEN",
            "VOLCENGINE_SESSION_TOKEN",
        ),
        region=_reject_placeholder("volcengine.region", region),
        service=_first_env(
            "HARNESS_INFRA_SERVICE",
            "VOLCENGINE_AGENTKIT_SERVICE",
            default="agentkit",
        ),
        host=_first_env(
            "HARNESS_INFRA_CONTROL_HOST",
            "VOLCENGINE_AGENTKIT_HOST",
            default="open.volcengineapi.com",
        ),
        scheme=_first_env(
            "HARNESS_INFRA_CONTROL_SCHEME",
            "VOLCENGINE_AGENTKIT_SCHEME",
            default="https",
        ),
        api_version=_first_env(
            "HARNESS_INFRA_API_VERSION",
            "VOLCENGINE_AGENTKIT_API_VERSION",
            default=API_VERSION,
        ),
    )


def _harness_config(
    raw: dict[str, Any],
    *,
    model_id: str,
    model_base_url: str,
    model_api_key_name: str,
    require_model_key_name: bool,
) -> HarnessConfig:
    harness = _mapping(raw.get("harness"), "harness")
    model = _mapping(harness.get("model"), "harness.model")
    resolved_model_id = _reject_placeholder(
        "harness.model.agent_name",
        model_id
        or _string(
            model.get("agent_name"),
            "harness.model.agent_name",
            allow_empty=True,
        )
        or DEFAULT_MODEL_ID,
    )
    resolved_model_url = _validate_url(
        "harness.model.api_base",
        _reject_placeholder(
            "harness.model.api_base",
            model_base_url
            or _string(
                model.get("api_base"),
                "harness.model.api_base",
                allow_empty=True,
            )
            or DEFAULT_MODEL_BASE_URL,
        ),
    )
    key_name = model_api_key_name or _string(
        model.get("api_key_name"),
        "harness.model.api_key_name",
        allow_empty=True,
    )
    if require_model_key_name:
        key_name = _reject_placeholder("harness.model.api_key_name", key_name)
        if MODEL_KEY_NAME_PATTERN.fullmatch(key_name) is None:
            raise RuntimeError(
                "harness.model.api_key_name must match [A-Za-z0-9_-]{1,128}"
            )
    agent_loop = _string(harness.get("agent_loop"), "harness.agent_loop")
    if agent_loop not in {"adk", "codex", "piagent"}:
        raise RuntimeError("harness.agent_loop must be adk, codex, or piagent")
    return HarnessConfig(
        system_prompt=_string(
            harness.get("system_prompt"), "harness.system_prompt", allow_empty=True
        ),
        model_id=resolved_model_id,
        model_base_url=resolved_model_url,
        model_api_key_name=key_name,
        model_project_name=_reject_placeholder(
            "harness.model.project_name",
            _string(
                model.get("project_name", "default"),
                "harness.model.project_name",
            ),
        ),
        agent_loop=agent_loop,
        tools=_list(harness.get("tools", []), "harness.tools"),
        skills=_list(harness.get("skills", []), "harness.skills"),
        mcp_servers=_list(harness.get("mcp_servers", []), "harness.mcp_servers"),
    )


def _session_config(raw: dict[str, Any]) -> SessionConfig:
    session = _mapping(raw.get("session"), "session")
    endpoint_base_url = _string(
        session.get("endpoint_base_url"),
        "session.endpoint_base_url",
        allow_empty=True,
    )
    if endpoint_base_url:
        endpoint_base_url = _validate_data_url(
            "session.endpoint_base_url", endpoint_base_url
        )
    verify_sandbox_tools = session.get("verify_sandbox_tools", False)
    if not isinstance(verify_sandbox_tools, bool):
        raise TypeError("session.verify_sandbox_tools must be a boolean")
    return SessionConfig(
        id=_string(session.get("id"), "session.id", allow_empty=True),
        name=_string(session.get("name"), "session.name", allow_empty=True),
        endpoint_base_url=endpoint_base_url,
        title=_string(session.get("title"), "session.title"),
        prompt=_string(session.get("prompt"), "session.prompt"),
        expected_substring=_string(
            session.get("expected_substring"),
            "session.expected_substring",
            allow_empty=True,
        ),
        verify_sandbox_tools=verify_sandbox_tools,
    )


def _runtime_template_config(raw: dict[str, Any]) -> RuntimeTemplateConfig:
    runtime = _mapping(raw.get("runtime_template"), "runtime_template")
    resources = _mapping(runtime.get("resources"), "runtime_template.resources")
    min_replicas = _positive_integer(
        resources.get("min_replicas"),
        "runtime_template.resources.min_replicas",
        minimum=0,
    )
    max_replicas = _positive_integer(
        resources.get("max_replicas"), "runtime_template.resources.max_replicas"
    )
    if min_replicas > max_replicas:
        raise RuntimeError(
            "runtime_template.resources.min_replicas must not exceed max_replicas"
        )
    image_url = runtime.get("image_url")
    if image_url is not None:
        image_url = _string(image_url, "runtime_template.image_url")
    envs = _mapping(runtime.get("envs", {}), "runtime_template.envs")
    if not all(
        isinstance(key, str) and isinstance(value, str) for key, value in envs.items()
    ):
        raise RuntimeError("runtime_template.envs keys and values must be strings")
    return RuntimeTemplateConfig(
        role_name=_string(runtime.get("role_name"), "runtime_template.role_name"),
        resources={
            "CpuMilli": _positive_integer(
                resources.get("cpu_milli"),
                "runtime_template.resources.cpu_milli",
            ),
            "MemoryMiB": _positive_integer(
                resources.get("memory_mib"),
                "runtime_template.resources.memory_mib",
            ),
            "MinReplicas": min_replicas,
            "MaxReplicas": max_replicas,
        },
        image_url=image_url,
        envs=dict(envs),
        runtime=_mapping(runtime.get("runtime", {}), "runtime_template.runtime"),
    )


def _session_store_config(raw: dict[str, Any]) -> SessionStoreConfig:
    session_store = _mapping(raw.get("session_store", {}), "session_store")
    network = _mapping(session_store.get("network", {}), "session_store.network")
    use_private_network = network.get("use_private_network", False)
    if not isinstance(use_private_network, bool):
        raise TypeError("session_store.network.use_private_network must be a boolean")
    vpc_id = _string(
        network.get("vpc_id"),
        "session_store.network.vpc_id",
        allow_empty=True,
    )
    raw_subnet_ids = _list(
        network.get("subnet_ids", []),
        "session_store.network.subnet_ids",
    )
    if not all(isinstance(item, str) and item.strip() for item in raw_subnet_ids):
        raise RuntimeError(
            "session_store.network.subnet_ids must contain non-empty strings"
        )
    subnet_ids = [item.strip() for item in raw_subnet_ids]
    if use_private_network:
        if not vpc_id or len(subnet_ids) != 1:
            raise RuntimeError(
                "private SessionStore requires vpc_id and exactly one subnet_id"
            )
    elif vpc_id or subnet_ids:
        raise RuntimeError(
            "set session_store.network.use_private_network to use VPC settings"
        )
    return SessionStoreConfig(
        project_name=_string(
            session_store.get("project_name", "default"),
            "session_store.project_name",
        ),
        vpc_id=vpc_id,
        subnet_ids=subnet_ids,
    )


def _environment_config(raw: dict[str, Any]) -> EnvironmentConfig:
    environment = _mapping(raw.get("environment"), "environment")
    resources = _mapping(environment.get("resources"), "environment.resources")
    api_key = _mapping(environment.get("env_api_key"), "environment.env_api_key")
    environment_type = _string(environment.get("type"), "environment.type")
    if environment_type != "Cloud":
        raise RuntimeError("environment.type must be Cloud")
    metadata = _mapping(environment.get("metadata", {}), "environment.metadata")
    if not all(
        isinstance(key, str) and isinstance(value, str)
        for key, value in metadata.items()
    ):
        raise RuntimeError("environment.metadata keys and values must be strings")
    return EnvironmentConfig(
        type=environment_type,
        resources={
            "CpuMilli": _positive_integer(
                resources.get("cpu_milli"), "environment.resources.cpu_milli"
            ),
            "MemoryMb": _positive_integer(
                resources.get("memory_mb"), "environment.resources.memory_mb"
            ),
        },
        metadata=dict(metadata),
        endpoint_id=_string(
            environment.get("endpoint_id"),
            "environment.endpoint_id",
            allow_empty=True,
        ),
        env_api_key_id=_string(
            api_key.get("id"), "environment.env_api_key.id", allow_empty=True
        ),
        env_api_key_value=_string(
            api_key.get("value"),
            "environment.env_api_key.value",
            allow_empty=True,
        ),
    )


def validated_config(
    *,
    model_id: str = "",
    model_base_url: str = "",
    model_api_key_name: str = "",
    require_model_key_name: bool = True,
    require_credentials: bool = True,
) -> ExampleConfig:
    """读取 config.yaml，并让显式 CLI 参数覆盖对应 YAML 字段。"""

    raw = _read_yaml()
    return ExampleConfig(
        control=_control_config(raw, require_credentials=require_credentials),
        session=_session_config(raw),
        harness=_harness_config(
            raw,
            model_id=model_id,
            model_base_url=model_base_url,
            model_api_key_name=model_api_key_name,
            require_model_key_name=require_model_key_name,
        ),
        session_store=_session_store_config(raw),
        runtime_template=_runtime_template_config(raw),
        environment=_environment_config(raw),
    )


def _write_runtime_values(
    *,
    api_key_id: str | None = None,
    api_key_value: str | None = None,
    session_id: str | None = None,
    session_name: str | None = None,
    endpoint_base_url: str | None = None,
) -> None:
    path = config_path()
    raw = _read_yaml()
    if api_key_id is not None or api_key_value is not None:
        environment = _mapping(raw.get("environment"), "environment")
        api_key = _mapping(environment.get("env_api_key"), "environment.env_api_key")
        if api_key_id is not None:
            api_key["id"] = api_key_id
        if api_key_value is not None:
            api_key["value"] = api_key_value
    if (
        session_id is not None
        or session_name is not None
        or endpoint_base_url is not None
    ):
        session = _mapping(raw.get("session"), "session")
        if session_id is not None:
            session["id"] = session_id
        if session_name is not None:
            session["name"] = session_name
        if endpoint_base_url is not None:
            session["endpoint_base_url"] = endpoint_base_url
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        yaml.safe_dump(
            raw,
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
        ),
        encoding="utf-8",
    )
    os.chmod(temporary, 0o600)
    temporary.replace(path)


def persist_environment_api_key(api_key_id: str, value: str) -> None:
    """将 01 创建的 Environment API Key 标识和明文写入 YAML。"""

    if not api_key_id or not value:
        raise RuntimeError("refusing to persist an empty Environment API Key")
    _write_runtime_values(api_key_id=api_key_id, api_key_value=value)


def persist_session(session_id: str, name: str, endpoint_base_url: str) -> None:
    """将 01 创建的 Session 标识及其数据面地址写入 YAML。"""

    if not session_id or not endpoint_base_url:
        raise RuntimeError("refusing to persist incomplete Session data")
    _write_runtime_values(
        session_id=session_id,
        session_name=name,
        endpoint_base_url=endpoint_base_url,
    )


def clear_runtime_values() -> None:
    """清空 YAML 中由 01 写入的运行时凭据和 Session 标识。"""

    _write_runtime_values(
        api_key_id="",
        api_key_value="",
        session_id="",
        session_name="",
        endpoint_base_url="",
    )
