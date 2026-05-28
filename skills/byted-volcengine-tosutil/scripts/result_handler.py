from __future__ import annotations

import re

from models import CommandSpec, ErrorAdvice, ExecutionResult, ParsedResult

BUCKET_COUNT_RE = re.compile(r"Bucket number is:\s*(\d+)", re.IGNORECASE)
SUCCESS_COUNT_RE = re.compile(r"Succeed count is:\s*(\d+)", re.IGNORECASE)
FAILED_COUNT_RE = re.compile(r"Failed count is:\s*(\d+)", re.IGNORECASE)
TASK_ID_RE = re.compile(r"Task id is:\s*([A-Za-z0-9-]+)", re.IGNORECASE)
REQUEST_ID_RE = re.compile(r"request id(?:\s*\[|\s+)([A-Za-z0-9-]+)", re.IGNORECASE)


def map_error(command: str, result: ExecutionResult) -> ErrorAdvice | None:
    output = result.combined_output.lower()

    if "http status [403]" in output:
        return ErrorAdvice(
            code="E_PERMISSION_403",
            category="permission_error",
            message="命令执行失败，疑似访问凭证无效或无权限访问目标资源。",
            probable_causes=["AK/SK 配置错误。", "STS Token 已过期。", "目标桶或对象未授予当前身份访问权限。"],
            next_actions=["执行 `tosutil config` 检查当前配置。", "执行 `tosutil ls` 验证基础权限。", "确认目标桶策略、ACL 或 RAM 权限设置。"],
        )

    if "a connection attempt failed" in output:
        return ErrorAdvice(
            code="E_NETWORK_CONNECT",
            category="network_error",
            message="命令执行失败，当前环境无法连通 TOS Endpoint。",
            probable_causes=["网络异常或 DNS 解析失败。", "企业代理、防火墙或安全组限制。", "Endpoint 配置错误。"],
            next_actions=["确认 Endpoint 是否为正确的 TOS 协议域名。", "检查本机网络、代理与 VPN 配置。", "先执行 `tosutil ls` 或网络诊断相关命令定位连通性问题。"],
        )

    if "config file" in output and "not exist" in output:
        return ErrorAdvice(
            code="E_CONFIG_NOT_FOUND",
            category="config_error",
            message="命令执行失败，配置文件不存在或无法读取。",
            probable_causes=["传入的 `-conf` 路径不存在。", "当前用户没有权限访问配置文件。"],
            next_actions=["检查 `-conf` 参数路径是否正确。", "若需要默认配置，可先执行 `tosutil config` 初始化。"],
        )

    if "unknown flag" in output or "invalid argument" in output:
        return ErrorAdvice(
            code="E_INVALID_ARGUMENT",
            category="argument_error",
            message="命令执行失败，参数不合法或当前命令不支持该参数。",
            probable_causes=["命令拼装错误。", "tosutil 版本与参数能力不匹配。"],
            next_actions=["执行 `tosutil help <command>` 查看当前版本支持的参数。", "减少可选参数，先验证最小命令是否可执行。"],
        )

    if result.timed_out:
        return ErrorAdvice(
            code="E_TIMEOUT",
            category="timeout_error",
            message="命令执行超时。",
            probable_causes=["批量任务过大。", "网络波动导致任务执行缓慢。"],
            next_actions=["缩小操作范围后重试。", "针对 `cp`、`du` 等批量任务调整并发与扫描范围。"],
        )

    if result.exit_code != 0:
        return ErrorAdvice(
            code="E_RUNTIME",
            category="runtime_error",
            message=f"`{command}` 执行失败，请结合原始输出进一步排查。",
            probable_causes=["命令参数与资源状态不匹配。", "环境、权限或网络存在异常。"],
            next_actions=["查看 stdout/stderr 原始输出。", "先退回最小只读命令验证环境，例如 `version` 或 `ls`。"],
        )

    return None


def parse_execution_result(spec: CommandSpec, result: ExecutionResult) -> ParsedResult:
    output = result.combined_output
    bucket_count = _search_int(BUCKET_COUNT_RE, output)
    success_count = _search_int(SUCCESS_COUNT_RE, output)
    failed_count = _search_int(FAILED_COUNT_RE, output)
    task_id = _search_text(TASK_ID_RE, output)
    request_id = _search_text(REQUEST_ID_RE, output)
    success = result.exit_code == 0 and not result.timed_out
    advice = None if success else map_error(spec.command, result)

    hints = list(spec.hints)
    if bucket_count is not None:
        hints.append(f"当前列举结果包含 {bucket_count} 个桶。")
    if success_count is not None or failed_count is not None:
        hints.append(f"批量任务统计：成功 {success_count or 0}，失败 {failed_count or 0}。")
    if task_id:
        hints.append(f"任务标识：{task_id}")

    return ParsedResult(
        success=success,
        command=spec.command,
        summary=_build_summary(spec.command, success, bucket_count, success_count, failed_count),
        request_id=request_id,
        task_id=task_id,
        success_count=success_count,
        failed_count=failed_count,
        bucket_count=bucket_count,
        hints=hints,
        advice=advice,
        raw_stdout=result.stdout,
        raw_stderr=result.stderr,
    )


def _search_int(pattern: re.Pattern[str], text: str) -> int | None:
    match = pattern.search(text)
    if not match:
        return None
    return int(match.group(1))


def _search_text(pattern: re.Pattern[str], text: str) -> str | None:
    match = pattern.search(text)
    if not match:
        return None
    return match.group(1)


def _build_summary(
    command: str,
    success: bool,
    bucket_count: int | None,
    success_count: int | None,
    failed_count: int | None,
) -> str:
    if not success:
        return f"`{command}` 执行失败。"
    if command == "ls" and bucket_count is not None:
        return f"`ls` 执行成功，共列举到 {bucket_count} 个桶。"
    if success_count is not None or failed_count is not None:
        return f"`{command}` 执行完成，成功 {success_count or 0} 个，失败 {failed_count or 0} 个。"
    return f"`{command}` 执行成功。"
