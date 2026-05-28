from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class CredentialMode(str, Enum):
    PERMANENT = "permanent"
    STS = "sts"
    ANONYMOUS = "anonymous"


class ResourceKind(str, Enum):
    LOCAL_FILE = "local_file"
    LOCAL_DIR = "local_dir"
    TOS_URI = "tos_uri"
    UNKNOWN = "unknown"


class TransferDirection(str, Enum):
    UPLOAD = "upload"
    DOWNLOAD = "download"
    CLOUD_COPY = "cloud_copy"
    UNKNOWN = "unknown"


class RiskLevel(str, Enum):
    READONLY = "readonly"
    WRITE = "write"
    DESTRUCTIVE = "destructive"


@dataclass
class CommonOptions:
    endpoint: str | None = None
    region: str | None = None
    access_key: str | None = None
    secret_key: str | None = None
    security_token: str | None = None
    conf_path: str | None = None
    bucket_type: str | None = None
    output_dir: str | None = None
    tosutil_binary: str = "tosutil"
    credential_mode: CredentialMode = CredentialMode.PERMANENT
    timeout_seconds: int = 300
    retries: int = 0
    retry_backoff_seconds: float = 0.8

    def to_safe_dict(self) -> dict[str, Any]:
        data = asdict(self)
        for key in ("access_key", "secret_key", "security_token"):
            if data.get(key):
                data[key] = "***"
        return data


@dataclass
class TosResource:
    raw: str
    kind: ResourceKind
    exists: bool = False

    @property
    def is_tos(self) -> bool:
        return self.kind == ResourceKind.TOS_URI


@dataclass
class OperationRequest:
    command: str
    common_options: CommonOptions = field(default_factory=CommonOptions)
    source: str | None = None
    target: str | None = None
    cloud_url: str | None = None
    recursive: bool = False
    force: bool = False
    jobs: int | None = None
    part_concurrency: int | None = None
    threshold: str | None = None
    part_size: str | None = None
    meta: str | None = None
    content_type: str | None = None
    expires: str | None = None
    directory_mode: bool = False
    include_versions: bool = False
    include_multipart: bool = False
    help_command: str | None = None
    extra_args: list[str] = field(default_factory=list)
    assume_yes: bool = False


@dataclass
class CommandSpec:
    command: str
    argv: list[str]
    risk_level: RiskLevel
    summary: str
    requires_confirmation: bool = False
    hints: list[str] = field(default_factory=list)

    def shell_command(self) -> str:
        return " ".join(self.argv)


@dataclass
class ExecutionResult:
    exit_code: int
    stdout: str | bytes
    stderr: str | bytes
    duration_ms: int
    argv: list[str]
    timed_out: bool = False

    @property
    def combined_output(self) -> str:
        return "\n".join(
            _coerce_text(part)
            for part in (self.stdout, self.stderr)
            if part
        )


def _coerce_text(value: str | bytes) -> str:
    if isinstance(value, bytes):
        # 某些超时或底层调用场景仍可能返回 bytes，这里统一兼容处理。
        return value.decode("utf-8", errors="replace")
    return value


@dataclass
class ErrorAdvice:
    code: str
    category: str
    message: str
    probable_causes: list[str] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)


@dataclass
class ParsedResult:
    success: bool
    command: str
    summary: str
    request_id: str | None = None
    task_id: str | None = None
    success_count: int | None = None
    failed_count: int | None = None
    bucket_count: int | None = None
    hints: list[str] = field(default_factory=list)
    advice: ErrorAdvice | None = None
    raw_stdout: str = ""
    raw_stderr: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if self.advice is None:
            data.pop("advice", None)
        return data


@dataclass
class PreflightCheck:
    name: str
    success: bool
    details: str
    hints: list[str] = field(default_factory=list)


@dataclass
class PreflightReport:
    ok: bool
    checks: list[PreflightCheck] = field(default_factory=list)

    def add(self, check: PreflightCheck) -> None:
        self.checks.append(check)
        if not check.success:
            self.ok = False
