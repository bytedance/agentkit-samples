from __future__ import annotations

"""
集中放置 tosutil skill 的“服务层”逻辑：
- 命令构建
- 资源识别和公共参数校验
- 子进程执行与重试
- 预检查
- 输出脱敏与命令串拼接
"""

import os
import re
import shlex
import subprocess
import time
from pathlib import Path
from typing import Callable

from models import (
    CommandSpec,
    CommonOptions,
    ExecutionResult,
    OperationRequest,
    PreflightCheck,
    PreflightReport,
    ResourceKind,
    RiskLevel,
    TosResource,
    TransferDirection,
)

TOS_URI_PREFIX = "tos://"
_S3_ENDPOINT_HINT_RE = re.compile(r"(^|\.)(s3|tos-s3)(\.|$)", re.IGNORECASE)
_RETRYABLE_NETWORK_SNIPPET = "a connection attempt failed"


class ValidationError(ValueError):
    pass


# ----------------------------
# Resource detection
# ----------------------------
def is_tos_uri(value: str | None) -> bool:
    return bool(value) and value.startswith(TOS_URI_PREFIX)


def detect_resource(path_or_uri: str | None) -> TosResource:
    if not path_or_uri:
        return TosResource(raw="", kind=ResourceKind.UNKNOWN, exists=False)

    if is_tos_uri(path_or_uri):
        return TosResource(raw=path_or_uri, kind=ResourceKind.TOS_URI, exists=True)

    path = Path(path_or_uri).expanduser()
    if path.exists() and path.is_dir():
        return TosResource(raw=path_or_uri, kind=ResourceKind.LOCAL_DIR, exists=True)
    if path.exists() and path.is_file():
        return TosResource(raw=path_or_uri, kind=ResourceKind.LOCAL_FILE, exists=True)
    if path_or_uri.endswith(("/", os.sep)):
        return TosResource(raw=path_or_uri, kind=ResourceKind.LOCAL_DIR, exists=False)
    return TosResource(raw=path_or_uri, kind=ResourceKind.LOCAL_FILE, exists=False)


# ----------------------------
# Common validation & CLI helpers
# ----------------------------
def validate_tos_endpoint(endpoint: str | None) -> None:
    if endpoint and _S3_ENDPOINT_HINT_RE.search(endpoint):
        raise ValidationError("检测到疑似 S3 协议域名，请改用 TOS 协议 Endpoint。")


def validate_common_options(options: CommonOptions) -> list[str]:
    hints: list[str] = []
    validate_tos_endpoint(options.endpoint)

    if options.conf_path and not Path(options.conf_path).expanduser().exists():
        raise ValidationError("`-conf` 指向的配置文件不存在。")

    mode = options.credential_mode.value
    if mode == "anonymous":
        if options.access_key or options.secret_key or options.security_token:
            raise ValidationError("匿名访问模式下，不应再传入 AK/SK/Token。")
        hints.append("当前为匿名访问模式，仅适用于公共读或公共写场景。")
        return hints

    if mode == "sts" and not options.security_token:
        raise ValidationError("STS 模式缺少 security token。")

    return hints


def normalize_command_name(command: str) -> str:
    normalized = command.strip().lower()
    if not normalized:
        raise ValidationError("命令名不能为空。")
    return normalized


def ensure_required(value: str | None, field_name: str) -> str:
    if value:
        return value
    raise ValidationError(f"缺少必填参数：{field_name}")


def append_flag(argv: list[str], flag: str, enabled: bool) -> None:
    if enabled:
        argv.append(flag)


def append_option(argv: list[str], flag: str, value: str | int | None) -> None:
    if value is None or value == "":
        return
    argv.append(f"{flag}={value}")


def shell_join(argv: list[str]) -> str:
    join_fn = getattr(shlex, "join", None)
    if join_fn:
        return join_fn(argv)
    return " ".join(shlex.quote(arg) for arg in argv)


def redact_argv(argv: list[str]) -> list[str]:
    return [mask_sensitive_text(item) for item in argv]


def mask_sensitive_text(value: str) -> str:
    masked = value
    for pattern, replacement in (
        (r"(-i=)(\S+)", r"\1***"),
        (r"(-k=)(\S+)", r"\1***"),
        (r"(-t=)(\S+)", r"\1***"),
    ):
        masked = re.sub(pattern, replacement, masked)
    return masked


# ----------------------------
# Command building (public)
# ----------------------------
def build_command(request: OperationRequest) -> CommandSpec:
    command = normalize_command_name(request.command)
    hints = validate_common_options(request.common_options)

    builders: dict[str, Callable[[OperationRequest, list[str]], CommandSpec]] = {
        "version": _build_version,
        "help": _build_help,
        "config": _build_config,
        "ls": _build_ls,
        "mb": _build_mb,
        "cp": _build_cp,
        "rm": _build_rm,
        "du": _build_du,
        "setmeta": _build_setmeta,
        "stat": _build_stat,
    }

    builder = builders.get(command)
    if not builder:
        raise ValidationError(f"暂未实现命令：{command}")
    return builder(request, hints)


def _build_version(request: OperationRequest, hints: list[str]) -> CommandSpec:
    return CommandSpec(
        command="version",
        argv=[request.common_options.tosutil_binary, "version"],
        risk_level=RiskLevel.READONLY,
        summary="查看 tosutil 版本信息",
        hints=hints,
    )


def _build_help(request: OperationRequest, hints: list[str]) -> CommandSpec:
    argv = [request.common_options.tosutil_binary, "help"]
    if request.help_command:
        argv.append(request.help_command)
    _append_common_options(argv, request.common_options)
    return CommandSpec(command="help", argv=argv, risk_level=RiskLevel.READONLY, summary="查看 tosutil 帮助文档", hints=hints)


def _build_config(request: OperationRequest, hints: list[str]) -> CommandSpec:
    argv = [request.common_options.tosutil_binary, "config"]
    _append_common_options(argv, request.common_options, include_output=False)
    return CommandSpec(command="config", argv=argv, risk_level=RiskLevel.WRITE, summary="初始化或更新 tosutil 配置", hints=hints)


def _build_ls(request: OperationRequest, hints: list[str]) -> CommandSpec:
    argv = [request.common_options.tosutil_binary, "ls"]
    if request.cloud_url:
        argv.append(request.cloud_url)
    _append_common_options(argv, request.common_options)
    return CommandSpec(command="ls", argv=argv, risk_level=RiskLevel.READONLY, summary="列举桶或对象", hints=hints)


def _build_mb(request: OperationRequest, hints: list[str]) -> CommandSpec:
    cloud_url = ensure_required(request.cloud_url, "cloud_url")
    _ensure_tos_resource(cloud_url, "mb")
    argv = [request.common_options.tosutil_binary, "mb", cloud_url]
    _append_common_options(argv, request.common_options, include_output=False)
    return CommandSpec(command="mb", argv=argv, risk_level=RiskLevel.WRITE, summary="创建新桶", hints=hints)


def _build_cp(request: OperationRequest, hints: list[str]) -> CommandSpec:
    source = ensure_required(request.source, "source")
    target = ensure_required(request.target, "target")
    src_resource = detect_resource(source)
    dst_resource = detect_resource(target)
    direction = _detect_transfer_direction(src_resource, dst_resource)
    if direction == TransferDirection.UNKNOWN:
        raise ValidationError("无法识别 `cp` 的传输方向，请检查源和目标路径。")

    argv = [request.common_options.tosutil_binary, "cp", source, target]
    append_flag(argv, "-r", request.recursive or src_resource.kind == ResourceKind.LOCAL_DIR)
    append_option(argv, "-j", request.jobs)
    append_option(argv, "-p", request.part_concurrency)
    append_option(argv, "-threshold", request.threshold)
    append_option(argv, "-ps", request.part_size)
    _append_common_options(argv, request.common_options)

    summary_by_direction = {
        TransferDirection.UPLOAD: "上传本地文件或目录到 TOS",
        TransferDirection.DOWNLOAD: "从 TOS 下载对象到本地",
        TransferDirection.CLOUD_COPY: "在 TOS 内部复制对象",
    }
    return CommandSpec(
        command="cp",
        argv=argv,
        risk_level=RiskLevel.WRITE,
        summary=summary_by_direction[direction],
        hints=hints + _build_cp_hints(direction, request),
    )


def _build_rm(request: OperationRequest, hints: list[str]) -> CommandSpec:
    cloud_url = ensure_required(request.cloud_url, "cloud_url")
    _ensure_tos_resource(cloud_url, "rm")
    argv = [request.common_options.tosutil_binary, "rm", cloud_url]
    append_flag(argv, "-r", request.recursive)
    append_flag(argv, "-f", request.force or request.assume_yes)
    append_option(argv, "-j", request.jobs)
    _append_common_options(argv, request.common_options)
    return CommandSpec(
        command="rm",
        argv=argv,
        risk_level=RiskLevel.DESTRUCTIVE,
        summary="删除桶、对象或对象前缀",
        requires_confirmation=not (request.force or request.assume_yes),
        hints=hints + _build_rm_hints(request),
    )


def _build_du(request: OperationRequest, hints: list[str]) -> CommandSpec:
    cloud_url = ensure_required(request.cloud_url, "cloud_url")
    _ensure_tos_resource(cloud_url, "du")
    argv = [request.common_options.tosutil_binary, "du", cloud_url]
    append_flag(argv, "-d", request.directory_mode)
    append_flag(argv, "-v", request.include_versions)
    append_flag(argv, "-m", request.include_multipart)
    _append_common_options(argv, request.common_options, include_output=False)
    if not request.directory_mode:
        hints.append("如果对象规模较大，建议按目录拆分统计，避免一次性全量扫描。")
    return CommandSpec(command="du", argv=argv, risk_level=RiskLevel.READONLY, summary="统计对象与分片大小和数量", hints=hints)


def _build_setmeta(request: OperationRequest, hints: list[str]) -> CommandSpec:
    cloud_url = ensure_required(request.cloud_url, "cloud_url")
    _ensure_tos_resource(cloud_url, "setmeta")
    argv = [request.common_options.tosutil_binary, "setmeta", cloud_url]
    append_flag(argv, "-r", request.recursive)
    append_option(argv, "-j", request.jobs)
    append_option(argv, "-meta", request.meta)
    append_option(argv, "-contentType", request.content_type)
    append_option(argv, "-expires", request.expires)
    _append_common_options(argv, request.common_options)
    if request.recursive and request.jobs is None:
        hints.append("批量设置元数据时建议显式设置 `-j`，避免默认并发不可控。")
    return CommandSpec(command="setmeta", argv=argv, risk_level=RiskLevel.WRITE, summary="设置对象元数据", hints=hints)


def _build_stat(request: OperationRequest, hints: list[str]) -> CommandSpec:
    cloud_url = ensure_required(request.cloud_url, "cloud_url")
    _ensure_tos_resource(cloud_url, "stat")
    argv = [request.common_options.tosutil_binary, "stat", cloud_url]
    _append_common_options(argv, request.common_options, include_output=False)
    return CommandSpec(command="stat", argv=argv, risk_level=RiskLevel.READONLY, summary="查询桶或对象属性", hints=hints)


def _append_common_options(argv: list[str], options: CommonOptions, *, include_output: bool = True) -> None:
    append_option(argv, "-e", options.endpoint)
    append_option(argv, "-re", options.region)
    if options.credential_mode.value == "anonymous":
        argv.extend(["-i=", "-k=", "-t="])
    else:
        append_option(argv, "-i", options.access_key)
        append_option(argv, "-k", options.secret_key)
        append_option(argv, "-t", options.security_token)
    append_option(argv, "-conf", options.conf_path)
    append_option(argv, "-bt", options.bucket_type)
    if include_output:
        append_option(argv, "-o", options.output_dir)


def _detect_transfer_direction(source: TosResource, target: TosResource) -> TransferDirection:
    if source.is_tos and target.is_tos:
        return TransferDirection.CLOUD_COPY
    if source.is_tos and target.kind in (ResourceKind.LOCAL_DIR, ResourceKind.LOCAL_FILE):
        return TransferDirection.DOWNLOAD
    if target.is_tos and source.kind in (ResourceKind.LOCAL_DIR, ResourceKind.LOCAL_FILE):
        return TransferDirection.UPLOAD
    return TransferDirection.UNKNOWN


def _ensure_tos_resource(cloud_url: str, command: str) -> None:
    resource = detect_resource(cloud_url)
    if resource.kind != ResourceKind.TOS_URI:
        raise ValidationError(f"`{command}` 需要传入 `tos://` 资源地址。")


def _build_cp_hints(direction: TransferDirection, request: OperationRequest) -> list[str]:
    hints: list[str] = []
    if direction == TransferDirection.UPLOAD:
        hints.append("上传大文件时，建议结合 `-threshold`、`-p` 调整分片策略。")
    if direction == TransferDirection.DOWNLOAD:
        hints.append("下载目录或前缀时，请确认目标本地路径具备写权限。")
    if request.jobs and request.jobs > 50:
        hints.append("当前并发较高，建议根据机器资源和带宽情况评估是否下调。")
    return hints


def _build_rm_hints(request: OperationRequest) -> list[str]:
    hints = ["删除前建议先用 `ls` 检查影响范围。"]
    if request.recursive:
        hints.append("当前为递归删除，请确认前缀范围是否准确。")
    if request.force:
        hints.append("当前使用强制删除，命令将跳过交互确认。")
    return hints


# ----------------------------
# Runner
# ----------------------------
class TosutilRunner:
    def __init__(self, *, timeout_seconds: int = 300, retries: int = 0, retry_backoff_seconds: float = 0.8) -> None:
        self.timeout_seconds = timeout_seconds
        self.retries = max(0, retries)
        self.retry_backoff_seconds = max(0.0, retry_backoff_seconds)

    def run(self, spec: CommandSpec) -> ExecutionResult:
        last_result: ExecutionResult | None = None
        attempts = 1 + self.retries
        for attempt in range(1, attempts + 1):
            result = self._run_once(spec)
            last_result = result
            if result.exit_code == 0 and not result.timed_out:
                return result
            if attempt >= attempts or not self._is_retryable(result):
                return result
            # 指数退避：瞬时网络抖动下更稳定。
            time.sleep(self.retry_backoff_seconds * (2 ** (attempt - 1)))
        return last_result or self._run_once(spec)

    def _run_once(self, spec: CommandSpec) -> ExecutionResult:
        started_at = time.perf_counter()
        try:
            completed = subprocess.run(
                spec.argv,
                capture_output=True,
                text=True,
                check=False,
                timeout=self.timeout_seconds,
            )
            return ExecutionResult(
                exit_code=completed.returncode,
                stdout=completed.stdout,
                stderr=completed.stderr,
                duration_ms=int((time.perf_counter() - started_at) * 1000),
                argv=spec.argv,
                timed_out=False,
            )
        except subprocess.TimeoutExpired as exc:
            return ExecutionResult(
                exit_code=124,
                stdout=exc.stdout or "",
                stderr=exc.stderr or "",
                duration_ms=int((time.perf_counter() - started_at) * 1000),
                argv=spec.argv,
                timed_out=True,
            )

    def _is_retryable(self, result: ExecutionResult) -> bool:
        if result.timed_out:
            return True
        return _RETRYABLE_NETWORK_SNIPPET in result.combined_output.lower()


# ----------------------------
# Preflight
# ----------------------------
def run_preflight(common_options: CommonOptions, *, check_connectivity: bool = False) -> PreflightReport:
    runner = TosutilRunner(timeout_seconds=min(common_options.timeout_seconds, 30), retries=0)
    report = PreflightReport(ok=True)

    binary_check = _check_binary(common_options.tosutil_binary)
    report.add(binary_check)
    if not binary_check.success:
        return report

    report.add(_check_conf_path(common_options))
    report.add(_run_preflight_command(runner, OperationRequest(command="version", common_options=common_options)))
    if check_connectivity:
        report.add(_run_preflight_command(runner, OperationRequest(command="ls", common_options=common_options)))
    return report


def _run_preflight_command(runner: TosutilRunner, request: OperationRequest) -> PreflightCheck:
    spec = build_command(request)
    result = runner.run(spec)
    success = result.exit_code == 0 and not result.timed_out
    details = f"`{request.command}` 检查通过" if success else f"`{request.command}` 检查失败"
    hints: list[str] = []
    snippet = _compact_output(result.combined_output)
    if snippet and not success:
        hints.append(f"输出摘要：{snippet}")
    return PreflightCheck(name=request.command, success=success, details=details, hints=hints)


def _compact_output(text: str, max_chars: int = 200) -> str:
    cleaned = " ".join(text.split())
    if not cleaned:
        return ""
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[:max_chars] + "..."


def _check_binary(binary_path: str) -> PreflightCheck:
    path = Path(binary_path).expanduser()
    if path.exists() and path.is_file() and os.access(str(path), os.X_OK):
        return PreflightCheck(name="binary", success=True, details=f"已找到可执行文件：{path}")
    return PreflightCheck(
        name="binary",
        success=False,
        details=f"未找到 tosutil 可执行文件：{binary_path}",
        hints=["请确认 `tosutil` 已下载并具备执行权限，例如 `chmod +x tosutil`。"],
    )


def _check_conf_path(common_options: CommonOptions) -> PreflightCheck:
    if not common_options.conf_path:
        return PreflightCheck(name="config_path", success=True, details="未显式指定 `-conf`，将使用默认配置文件路径。")
    conf_path = Path(common_options.conf_path).expanduser()
    if conf_path.exists():
        return PreflightCheck(name="config_path", success=True, details=f"配置文件存在：{conf_path}")
    return PreflightCheck(
        name="config_path",
        success=False,
        details=f"配置文件不存在：{conf_path}",
        hints=["请先创建配置文件，或移除 `-conf` 使用默认配置路径。"],
    )
