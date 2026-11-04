"""加载并校验 RuntimeTemplate HTTP 示例的 YAML 配置。"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG_PATH = Path(__file__).with_name("config.yaml")
EXAMPLE_CONFIG_PATH = DEFAULT_CONFIG_PATH.with_name("config.yaml.example")
PLACEHOLDER_PATTERN = re.compile(
    r"(^[<[{].*[>\]}]$)|(^your[-_])|(^replace[-_]?me$)|(^change[-_]?me$)",
    re.IGNORECASE,
)
START_COMMANDS = {
    "bash /app/run-runtime.sh",
    "python /app/examples/16_self_host_sandbox/agentkit_runtime.py",
    "bash /app/examples/16_self_host_sandbox/run-runtime.sh",
}


@dataclass(frozen=True)
class ControlConfig:
    access_key: str
    secret_key: str
    region: str
    workspace_id: str = ""


@dataclass(frozen=True)
class RuntimeTemplateConfig:
    id: str
    status: str
    endpoint: str
    name_prefix: str
    description: str | None
    role_name: str
    cpu_milli: int
    memory_mib: int
    min_replicas: int
    max_replicas: int
    image_url: str | None
    envs: dict[str, str]
    meta: dict[str, str]
    port: int | None
    start_command: str | None
    session_store_id: str = ""
    workspace_id: str = ""

    def generated_name(self) -> str:
        """生成账号内唯一且便于定位来源的模板名称。"""
        suffix = time.strftime("%Y%m%d%H%M%S", time.gmtime())
        return f"{self.name_prefix}-{suffix}-{uuid.uuid4().hex[:8]}".lower()


@dataclass(frozen=True)
class ExampleConfig:
    path: Path
    control: ControlConfig
    runtime_template: RuntimeTemplateConfig


def config_path(argv: list[str] | None = None) -> Path:
    """按 CLI、环境变量、默认路径的优先级选择配置文件。"""
    pre_parser = argparse.ArgumentParser(add_help=False)
    pre_parser.add_argument("--config")
    args, _ = pre_parser.parse_known_args(sys.argv[1:] if argv is None else argv)
    configured = (
        args.config or os.getenv("AGENTKIT_RUNTIME_TEMPLATE_CONFIG", "").strip()
    )
    return (
        Path(configured).expanduser().resolve()
        if configured
        else DEFAULT_CONFIG_PATH.resolve()
    )


def _mapping(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(f"{name} must be a YAML mapping")
    return value


def _string(value: Any, name: str, *, allow_empty: bool = False) -> str:
    if value is None and allow_empty:
        return ""
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    result = value.strip()
    if not result and not allow_empty:
        raise RuntimeError(f"{name} must be a non-empty string")
    return result


def _positive_integer(value: Any, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise RuntimeError(f"{name} must be an integer >= 1")
    return value


def _string_map(value: Any, name: str) -> dict[str, str]:
    result = _mapping(value, name)
    if not all(
        isinstance(key, str) and key.strip() and isinstance(item, str)
        for key, item in result.items()
    ):
        raise RuntimeError(f"{name} keys and values must be strings")
    return dict(result)


def _optional_string(value: Any, name: str) -> str | None:
    if value is None:
        return None
    return _string(value, name)


def _runtime_config(raw: dict[str, Any]) -> RuntimeTemplateConfig:
    runtime = _mapping(raw.get("runtime_template"), "runtime_template")
    resources = _mapping(runtime.get("resources"), "runtime_template.resources")
    runtime_process = _mapping(
        runtime.get("runtime", {}),
        "runtime_template.runtime",
    )
    min_replicas = _positive_integer(
        resources.get("min_replicas"),
        "runtime_template.resources.min_replicas",
    )
    max_replicas = _positive_integer(
        resources.get("max_replicas"),
        "runtime_template.resources.max_replicas",
    )
    if min_replicas > max_replicas:
        raise RuntimeError(
            "runtime_template.resources.min_replicas must not exceed max_replicas"
        )
    port = runtime_process.get("port")
    if port is not None:
        port = _positive_integer(port, "runtime_template.runtime.port")
    start_command = _optional_string(
        runtime_process.get("start_command"),
        "runtime_template.runtime.start_command",
    )
    if (port is None) != (start_command is None):
        raise RuntimeError(
            "runtime_template.runtime.port and start_command must be "
            "configured together"
        )
    if start_command is not None and start_command not in START_COMMANDS:
        raise RuntimeError(
            "runtime_template.runtime.start_command is not in the supported allowlist"
        )
    return RuntimeTemplateConfig(
        workspace_id=_string(
            runtime.get("workspace_id", ""),
            "runtime_template.workspace_id",
            allow_empty=True,
        ),
        session_store_id=_string(
            runtime.get("session_store_id", ""),
            "runtime_template.session_store_id",
            allow_empty=True,
        ),
        id=_string(
            runtime.get("id"),
            "runtime_template.id",
            allow_empty=True,
        ),
        status=_string(
            runtime.get("status"),
            "runtime_template.status",
            allow_empty=True,
        ),
        endpoint=_string(
            runtime.get("endpoint"),
            "runtime_template.endpoint",
            allow_empty=True,
        ),
        name_prefix=_string(
            runtime.get("name_prefix"),
            "runtime_template.name_prefix",
        ),
        description=_optional_string(
            runtime.get("description"),
            "runtime_template.description",
        ),
        role_name=_string(
            runtime.get("role_name"),
            "runtime_template.role_name",
            allow_empty=True,
        ),
        cpu_milli=_positive_integer(
            resources.get("cpu_milli"),
            "runtime_template.resources.cpu_milli",
        ),
        memory_mib=_positive_integer(
            resources.get("memory_mib"),
            "runtime_template.resources.memory_mib",
        ),
        min_replicas=min_replicas,
        max_replicas=max_replicas,
        image_url=_optional_string(
            runtime.get("image_url"),
            "runtime_template.image_url",
        ),
        envs=_string_map(runtime.get("envs", {}), "runtime_template.envs"),
        meta=_string_map(runtime.get("meta", {}), "runtime_template.meta"),
        port=port,
        start_command=start_command,
    )


def _read_yaml(path: Path) -> dict[str, Any]:
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


def load_config(argv: list[str] | None = None) -> ExampleConfig:
    """读取配置；凭据占位符延迟到真实网络请求前校验。"""
    path = config_path(argv)
    root = _read_yaml(path)
    volcengine = _mapping(root.get("volcengine"), "volcengine")
    return ExampleConfig(
        path=path,
        control=ControlConfig(
            workspace_id=_string(
                root.get("workspace_id", ""), "workspace_id", allow_empty=True
            ),
            access_key=_string(
                volcengine.get("access_key"),
                "volcengine.access_key",
                allow_empty=True,
            ),
            secret_key=_string(
                volcengine.get("secret_key"),
                "volcengine.secret_key",
                allow_empty=True,
            ),
            region=_string(volcengine.get("region"), "volcengine.region"),
        ),
        runtime_template=_runtime_config(root),
    )


def _write_yaml(path: Path, root: dict[str, Any]) -> None:
    """原子更新包含凭据的配置文件，并固定权限为 0600。"""
    temporary = path.with_suffix(path.suffix + ".tmp")
    content = yaml.safe_dump(
        root,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    )
    descriptor = os.open(
        temporary,
        os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
        0o600,
    )
    os.fchmod(descriptor, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        stream.write(content)
    temporary.replace(path)


def persist_runtime_state(
    runtime_template_id: str,
    status: str,
    endpoint: str,
    workspace_id: str | None = None,
) -> Path:
    """将服务端返回的最小运行时状态写回 config.yaml。"""
    path = config_path()
    root = _read_yaml(path)
    if workspace_id:
        root["workspace_id"] = workspace_id
        _mapping(root.get("runtime_template"), "runtime_template")["workspace_id"] = (
            workspace_id
        )
    runtime = _mapping(root.get("runtime_template"), "runtime_template")
    runtime["id"] = runtime_template_id
    runtime["status"] = status
    runtime["endpoint"] = endpoint
    _write_yaml(path, root)
    return path


def clear_runtime_state(runtime_template_id: str) -> Path:
    """仅在 ID 匹配时清空 config.yaml 中的运行时状态。"""
    path = config_path()
    root = _read_yaml(path)
    runtime = _mapping(root.get("runtime_template"), "runtime_template")
    if runtime.get("id") == runtime_template_id:
        runtime["id"] = ""
        runtime["status"] = ""
        runtime["endpoint"] = ""
        _write_yaml(path, root)
    return path


def activate_control(config: ExampleConfig, *, require_credentials: bool) -> None:
    """将 YAML 控制面配置注入现有 HTTP/IAM 客户端的环境接口。"""
    control = config.control
    pre_parser = argparse.ArgumentParser(add_help=False)
    pre_parser.add_argument("--workspace-id")
    selected, _ = pre_parser.parse_known_args()
    workspace = selected.workspace_id
    if workspace is None:
        workspace = os.getenv(
            "HARNESS_INFRA_WORKSPACE_ID",
            os.getenv("AGENTKIT_WORKSPACE_ID", control.workspace_id),
        )
    os.environ["HARNESS_INFRA_WORKSPACE_ID"] = workspace.strip()
    if (
        config.runtime_template.id
        and config.runtime_template.workspace_id
        and workspace.strip() != config.runtime_template.workspace_id
    ):
        raise RuntimeError(
            "runtime state belongs to another Workspace; use a separate configuration"
        )
    provider = os.getenv("AGENTKIT_CLOUD_PROVIDER", "volcengine").strip().lower()
    if require_credentials and provider == "volcengine":
        for name, value in (
            ("volcengine.access_key", control.access_key),
            ("volcengine.secret_key", control.secret_key),
        ):
            if not value:
                raise RuntimeError(f"missing required configuration: {name}")
            if PLACEHOLDER_PATTERN.search(value):
                raise RuntimeError(f"{name} still contains an example placeholder")
            if any(character.isspace() for character in value):
                raise RuntimeError(f"{name} must not contain whitespace")
    os.environ.setdefault("AGENTKIT_CLOUD_PROVIDER", "volcengine")
    if provider == "volcengine":
        os.environ["VOLCENGINE_AGENTKIT_ACCESS_KEY"] = control.access_key
        os.environ["VOLCENGINE_AGENTKIT_SECRET_KEY"] = control.secret_key
        os.environ["VOLCENGINE_ACCESS_KEY"] = control.access_key
        os.environ["VOLCENGINE_SECRET_KEY"] = control.secret_key
        os.environ["VOLCENGINE_AGENTKIT_REGION"] = control.region
