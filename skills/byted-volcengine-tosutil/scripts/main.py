from __future__ import annotations

import argparse
import json
import sys
import time

from models import CommonOptions, CredentialMode, OperationRequest
from result_handler import parse_execution_result
from tosutil_service import (
    TosutilRunner,
    ValidationError,
    build_command,
    redact_argv,
    run_preflight,
    shell_join,
)


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--endpoint", help="TOS Endpoint（必须是 TOS 协议域名）")
    parser.add_argument("--region", help="Region，例如 cn-beijing")
    parser.add_argument("--access-key", help="Access Key（不会在输出中回显）")
    parser.add_argument("--secret-key", help="Secret Key（不会在输出中回显）")
    parser.add_argument("--security-token", help="STS Token（不会在输出中回显）")
    parser.add_argument("--conf-path", help="配置文件路径（-conf）")
    parser.add_argument("--bucket-type", help="桶类型，fns 或 hns")
    parser.add_argument("--output-dir", help="结果输出目录（-o）")
    parser.add_argument("--tosutil-binary", default="tosutil", help="tosutil 可执行文件路径")
    parser.add_argument(
        "--credential-mode",
        choices=[mode.value for mode in CredentialMode],
        default=CredentialMode.PERMANENT.value,
        help="凭证模式：permanent/sts/anonymous",
    )
    parser.add_argument("--timeout", type=int, default=300, help="单次执行超时秒数（默认 300）")
    parser.add_argument("--retries", type=int, default=0, help="网络/超时错误重试次数（默认 0）")
    parser.add_argument("--retry-backoff", type=float, default=0.8, help="重试退避基准秒数（默认 0.8）")


def _add_execution_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--run", action="store_true", help="是否真的执行（默认只预览命令）")
    parser.add_argument("--preflight", action="store_true", help="执行前进行版本/配置预检查")
    parser.add_argument("--connectivity", action="store_true", help="预检查时额外执行 ls 检查连通性")
    parser.add_argument("--yes", action="store_true", help="对破坏性操作跳过确认（高风险）")


def _build_subcommand_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="byted-volcengine-tosutil：tosutil 命令生成/执行/诊断器")
    sub = parser.add_subparsers(dest="subcommand", required=True)

    common_parent = argparse.ArgumentParser(add_help=False)
    _add_common_args(common_parent)
    execution_parent = argparse.ArgumentParser(add_help=False)
    _add_execution_args(execution_parent)
    parents = [common_parent, execution_parent]

    sub.add_parser("version", help="查看 tosutil 版本", parents=parents)

    p_help = sub.add_parser("help", help="查看 tosutil 帮助", parents=parents)
    p_help.add_argument("--help-command", help="具体命令名，例如 ls/cp/rm")

    sub.add_parser("config", help="查看或更新配置（默认仅查看配置路径）", parents=parents)

    p_ls = sub.add_parser("ls", help="列举桶或对象", parents=parents)
    p_ls.add_argument("--cloud-url", help="可选：tos://bucket 或 tos://bucket/prefix")

    p_mb = sub.add_parser("mb", help="创建桶", parents=parents)
    p_mb.add_argument("--cloud-url", required=True, help="tos://bucket")

    p_cp = sub.add_parser("cp", help="上传/下载/云上复制对象", parents=parents)
    p_cp.add_argument("--source", required=True, help="源路径：本地路径或 tos://")
    p_cp.add_argument("--target", required=True, help="目标路径：本地路径或 tos://")
    p_cp.add_argument("--recursive", action="store_true", help="递归复制目录/前缀")
    p_cp.add_argument("--jobs", type=int, help="批量任务并发数（-j）")
    p_cp.add_argument("--part-concurrency", type=int, help="分片任务并发数（-p）")
    p_cp.add_argument("--threshold", help="分片阈值（-threshold）")
    p_cp.add_argument("--part-size", help="分片大小（-ps）")

    p_rm = sub.add_parser("rm", help="删除桶/对象/前缀（破坏性）", parents=parents)
    p_rm.add_argument("--cloud-url", required=True, help="tos://bucket 或 tos://bucket/prefix")
    p_rm.add_argument("--recursive", action="store_true", help="递归删除（-r）")
    p_rm.add_argument("--force", action="store_true", help="强制删除（-f，跳过交互确认）")
    p_rm.add_argument("--jobs", type=int, help="批量删除并发数（-j）")

    p_du = sub.add_parser("du", help="统计对象/分片大小和数量", parents=parents)
    p_du.add_argument("--cloud-url", required=True, help="tos://bucket 或 tos://bucket/prefix")
    p_du.add_argument("--directory-mode", action="store_true", help="目录模式（-d）")
    p_du.add_argument("--include-versions", action="store_true", help="包含历史版本（-v）")
    p_du.add_argument("--include-multipart", action="store_true", help="包含分片任务（-m）")

    p_setmeta = sub.add_parser("setmeta", help="设置对象元数据", parents=parents)
    p_setmeta.add_argument("--cloud-url", required=True, help="tos://bucket/key 或 tos://bucket/prefix")
    p_setmeta.add_argument("--recursive", action="store_true", help="批量前缀模式（-r）")
    p_setmeta.add_argument("--jobs", type=int, help="批量并发（-j）")
    p_setmeta.add_argument("--meta", help="自定义元数据（-meta，格式 aaa:bbb#ccc:ddd）")
    p_setmeta.add_argument("--content-type", help="Content-Type（-contentType）")
    p_setmeta.add_argument("--expires", help="Expires（-expires，格式 YYYYMMDDHHmmSS）")

    p_stat = sub.add_parser("stat", help="查询桶/对象属性", parents=parents)
    p_stat.add_argument("--cloud-url", required=True, help="tos://bucket 或 tos://bucket/key")

    return parser


def _build_legacy_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="byted-volcengine-tosutil（legacy 模式）")
    _add_common_args(parser)
    parser.add_argument("--command", required=True, help="tosutil 命令名，例如 ls/cp/rm")
    parser.add_argument("--source", help="源路径，本地路径或 tos:// URI")
    parser.add_argument("--target", help="目标路径，本地路径或 tos:// URI")
    parser.add_argument("--cloud-url", help="单资源命令使用的 tos:// URI")
    parser.add_argument("--recursive", action="store_true", help="是否递归执行")
    parser.add_argument("--force", action="store_true", help="是否强制执行")
    parser.add_argument("--jobs", type=int, help="批量任务并发数")
    parser.add_argument("--part-concurrency", type=int, help="分片任务并发数")
    parser.add_argument("--threshold", help="分片阈值")
    parser.add_argument("--part-size", help="分片大小")
    parser.add_argument("--meta", help="自定义元数据")
    parser.add_argument("--content-type", help="Content-Type")
    parser.add_argument("--expires", help="Expires 时间")
    parser.add_argument("--directory-mode", action="store_true", help="du 目录模式")
    parser.add_argument("--include-versions", action="store_true", help="是否统计版本数据")
    parser.add_argument("--include-multipart", action="store_true", help="是否统计分片上传任务")
    parser.add_argument("--help-command", help="help 子命令名称")
    parser.add_argument("--assume-yes", action="store_true", help="跳过删除类命令确认")
    parser.add_argument("--run", action="store_true", help="是否真的执行命令")
    parser.add_argument("--preflight", action="store_true", help="执行前进行版本和配置预检查")
    parser.add_argument("--connectivity", action="store_true", help="预检查时额外执行 ls 检查连通性")
    return parser


def main() -> int:
    started_at = time.time()
    argv = sys.argv[1:]
    use_legacy = "--command" in argv or any(item.startswith("--command=") for item in argv)
    parser = _build_legacy_parser() if use_legacy else _build_subcommand_parser()
    args = parser.parse_args()

    common_options = CommonOptions(
        endpoint=args.endpoint,
        region=args.region,
        access_key=args.access_key,
        secret_key=args.secret_key,
        security_token=args.security_token,
        conf_path=args.conf_path,
        bucket_type=args.bucket_type,
        output_dir=args.output_dir,
        tosutil_binary=args.tosutil_binary,
        credential_mode=CredentialMode(args.credential_mode),
        timeout_seconds=args.timeout,
        retries=args.retries,
        retry_backoff_seconds=args.retry_backoff,
    )
    request = _build_request_from_args(args, common_options, legacy=use_legacy)

    try:
        if args.preflight:
            report = run_preflight(common_options, check_connectivity=args.connectivity)
            _emit_json(
                ok=report.ok,
                code="OK" if report.ok else "E_PREFLIGHT",
                message="预检查通过" if report.ok else "预检查失败",
                data={"preflight": _serialize_preflight(report)},
                started_at=started_at,
            )
            if not report.ok:
                return 2

        spec = build_command(request)
    except ValidationError as exc:
        _emit_json(
            ok=False,
            code="E_VALIDATION",
            message=str(exc),
            data={"input": _safe_input_summary(request)},
            started_at=started_at,
        )
        return 2

    safe_argv = redact_argv(spec.argv)
    preview = {
        "command": spec.command,
        "summary": spec.summary,
        "risk_level": spec.risk_level.value,
        "requires_confirmation": spec.requires_confirmation,
        "argv": safe_argv,
        "shell": shell_join(safe_argv),
        "hints": spec.hints,
    }

    if not args.run:
        _emit_json(ok=True, code="OK", message="已生成命令预览", data={"preview": preview}, started_at=started_at)
        return 0

    assume_yes = getattr(args, "yes", False) or getattr(args, "assume_yes", False)
    if spec.requires_confirmation and not assume_yes:
        _emit_json(
            ok=False,
            code="E_CONFIRM_REQUIRED",
            message="该操作为高风险/破坏性操作，默认不执行。请确认影响范围后重试。",
            data={
                "preview": preview,
                "next_actions": [
                    "先用 `ls` 验证影响范围。",
                    "确认无误后，重新执行并加 `--yes`（或 legacy 模式下加 `--assume-yes`）。",
                ],
            },
            started_at=started_at,
        )
        return 3

    runner = TosutilRunner(
        timeout_seconds=common_options.timeout_seconds,
        retries=common_options.retries,
        retry_backoff_seconds=common_options.retry_backoff_seconds,
    )
    result = runner.run(spec)
    parsed = parse_execution_result(spec, result)
    _emit_json(
        ok=parsed.success,
        code="OK" if parsed.success else parsed.advice.code if parsed.advice else "E_RUNTIME",
        message=parsed.summary,
        data={
            "preview": preview,
            "result": _safe_result_payload(parsed),
            "evidence": {"exit_code": result.exit_code, "duration_ms": result.duration_ms},
        },
        started_at=started_at,
    )
    return 0 if parsed.success else 1


def _serialize_preflight(report: object) -> dict[str, object]:
    checks = getattr(report, "checks", [])
    return {
        "ok": getattr(report, "ok", False),
        "checks": [
            {
                "name": check.name,
                "success": check.success,
                "details": check.details,
                "hints": check.hints,
            }
            for check in checks
        ],
    }


def _build_request_from_args(args: argparse.Namespace, common: CommonOptions, *, legacy: bool) -> OperationRequest:
    if legacy:
        return OperationRequest(
            command=args.command,
            common_options=common,
            source=args.source,
            target=args.target,
            cloud_url=args.cloud_url,
            recursive=args.recursive,
            force=args.force,
            jobs=args.jobs,
            part_concurrency=args.part_concurrency,
            threshold=args.threshold,
            part_size=args.part_size,
            meta=args.meta,
            content_type=args.content_type,
            expires=args.expires,
            directory_mode=args.directory_mode,
            include_versions=args.include_versions,
            include_multipart=args.include_multipart,
            help_command=args.help_command,
            assume_yes=args.assume_yes,
        )

    return OperationRequest(
        command=args.subcommand,
        common_options=common,
        source=getattr(args, "source", None),
        target=getattr(args, "target", None),
        cloud_url=getattr(args, "cloud_url", None),
        recursive=getattr(args, "recursive", False),
        force=getattr(args, "force", False),
        jobs=getattr(args, "jobs", None),
        part_concurrency=getattr(args, "part_concurrency", None),
        threshold=getattr(args, "threshold", None),
        part_size=getattr(args, "part_size", None),
        meta=getattr(args, "meta", None),
        content_type=getattr(args, "content_type", None),
        expires=getattr(args, "expires", None),
        directory_mode=getattr(args, "directory_mode", False),
        include_versions=getattr(args, "include_versions", False),
        include_multipart=getattr(args, "include_multipart", False),
        help_command=getattr(args, "help_command", None),
        assume_yes=False,
    )


def _emit_json(*, ok: bool, code: str, message: str, data: dict[str, object], started_at: float) -> None:
    print(json.dumps({"ok": ok, "code": code, "message": message, "data": data, "ts": int(started_at)}, ensure_ascii=False, indent=2))


def _safe_input_summary(request: OperationRequest) -> dict[str, object]:
    return {
        "command": request.command,
        "source": request.source,
        "target": request.target,
        "cloud_url": request.cloud_url,
        "recursive": request.recursive,
        "force": request.force,
    }


def _truncate(text: str | bytes, max_chars: int = 4000) -> dict[str, object]:
    if isinstance(text, bytes):
        text = text.decode("utf-8", errors="replace")
    if len(text) <= max_chars:
        return {"text": text, "truncated": False, "max_chars": max_chars}
    return {"text": text[:max_chars], "truncated": True, "max_chars": max_chars}


def _safe_result_payload(parsed: object) -> dict[str, object]:
    parsed_dict = getattr(parsed, "to_dict")()
    stdout = parsed_dict.pop("raw_stdout", "")
    stderr = parsed_dict.pop("raw_stderr", "")
    parsed_dict["stdout"] = _truncate(stdout)
    parsed_dict["stderr"] = _truncate(stderr)
    return parsed_dict


if __name__ == "__main__":
    sys.exit(main())
