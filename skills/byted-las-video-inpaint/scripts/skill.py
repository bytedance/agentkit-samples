#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ipaddress
import json
import os
import socket
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import requests

DEFAULT_REGION = "cn-beijing"

REGION_TO_DOMAIN = {
    "cn-beijing": "operator.las.cn-beijing.volces.com",
    "cn-shanghai": "operator.las.cn-shanghai.volces.com",
}

OPERATOR_ID = "las_video_inpaint"
OPERATOR_VERSION = "v1"

PRIVATE_IP_NETWORKS = [
    ipaddress.ip_network(f"10.{i}.0.0/16") for i in range(256)
] + [
    ipaddress.ip_network(f"172.{i}.0.0/16") for i in range(16, 32)
] + [
    ipaddress.ip_network(f"192.168.{i}.0/24") for i in range(256)
] + [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("0.0.0.0/8"),
]


def _is_private_ip(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
        return any(ip in network for network in PRIVATE_IP_NETWORKS)
    except ValueError:
        return False


def _validate_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https", "tos"):
        raise ValueError(f"不支持的 URL 协议: {parsed.scheme}，仅支持 http/https/tos")
    if not parsed.netloc:
        raise ValueError(f"无效的 URL: {url}")
    if parsed.scheme in ("http", "https"):
        hostname = parsed.hostname
        if not hostname:
            raise ValueError(f"无效的 URL hostname: {url}")
        ip = socket.gethostbyname(hostname)
        if _is_private_ip(ip):
            raise ValueError(f"禁止访问内网地址: {hostname} ({ip})")
    return url


def _read_env_sh_api_key(env_file: Path) -> Optional[str]:
    if not env_file.exists():
        return None
    content = env_file.read_text(encoding="utf-8", errors="ignore")
    key_name = "LAS_API_KEY"
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if key_name not in line:
            continue
        if "=" in line:
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def get_api_key() -> str:
    api_key = os.environ.get("LAS_API_KEY")
    if api_key:
        return api_key
    env_file = Path.cwd() / "env.sh"
    api_key = _read_env_sh_api_key(env_file)
    if api_key:
        return api_key
    raise ValueError("无法找到 LAS_API_KEY：请设置环境变量 LAS_API_KEY 或在当前目录提供 env.sh")


def get_region(cli_region: Optional[str] = None) -> str:
    if cli_region:
        return cli_region
    env_region = os.environ.get("LAS_REGION") or os.environ.get("REGION") or os.environ.get("region")
    return env_region or DEFAULT_REGION


def get_api_base(*, cli_region: Optional[str] = None) -> str:
    region = get_region(cli_region)
    domain = REGION_TO_DOMAIN.get(region)
    if not domain:
        raise ValueError(f"未知 region: {region}，仅支持 {', '.join(REGION_TO_DOMAIN.keys())}")
    return f"https://{domain}/api/v1"


def get_submit_endpoint(*, cli_region: Optional[str] = None) -> str:
    api_base = get_api_base(cli_region=cli_region)
    return f"{api_base}/submit"


def get_poll_endpoint(*, cli_region: Optional[str] = None) -> str:
    api_base = get_api_base(cli_region=cli_region)
    return f"{api_base}/poll"


def _headers() -> Dict[str, str]:
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {get_api_key()}",
    }


def _http_post_json(*, url: str, payload: Dict[str, Any], timeout: int = 300) -> Dict[str, Any]:
    resp = requests.post(url, headers=_headers(), json=payload, timeout=timeout)
    if not resp.ok:
        raise requests.HTTPError("request failed", response=resp)
    data: Any = resp.json()
    if not isinstance(data, dict):
        raise ValueError("Response is not a JSON object")
    return data


def _extract_error_meta(resp_json: Any) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
    if not isinstance(resp_json, dict):
        return None, None, None, None
    meta = resp_json.get("metadata")
    if not isinstance(meta, dict):
        return None, None, None, None
    return (
        meta.get("business_code"),
        meta.get("error_msg"),
        meta.get("request_id"),
        meta.get("task_id"),
    )


def _print_http_error(e: Exception) -> None:
    if isinstance(e, requests.HTTPError) and getattr(e, "response", None) is not None:
        r = e.response
        try:
            j = r.json()
            bc, em, rid, tid = _extract_error_meta(j)
            print(f"✗ HTTP {r.status_code} {r.reason}")
            if bc or em or rid or tid:
                print(f"business_code: {bc}")
                print(f"error_msg: {em}")
                if rid:
                    print(f"request_id: {rid}")
                if tid:
                    print(f"task_id: {tid}")
            else:
                print(json.dumps(j, ensure_ascii=False)[:2000])
            return
        except Exception:
            pass
        print(f"✗ HTTP {r.status_code} {r.reason}")
        try:
            print((r.text or "")[:2000])
        except Exception:
            print("(无法读取响应内容)")
        return
    print(f"✗ 请求失败: {e}")


def submit_task(
    *,
    region: Optional[str],
    video_url: str,
    output_tos_path: str,
    targets: Optional[List[str]] = None,
    return_subtitle_bbox: Optional[bool] = None,
    detection_precise_mode: Optional[bool] = None,
    inpainting_backend: Optional[str] = None,
    max_process_frames: Optional[int] = None,
    subtitle_mask_precise: Optional[bool] = None,
    fixed_bboxes: Optional[List[List[int]]] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    if not video_url:
        raise ValueError("video_url 不能为空")
    _validate_url(video_url)
    if not output_tos_path:
        raise ValueError("output_tos_path 不能为空")
    _validate_url(output_tos_path)
    if output_tos_path.rstrip("/").lower().endswith((".mp4", ".mov", ".mkv", ".avi", ".webm", ".flv", ".m4v")):
        print(
            "提示：output_tos_path 建议使用目录前缀（例如 tos://bucket/output/video_inpaint/）。"
            "服务端可能会在该路径下追加任务子目录与最终文件名，请以 inpainted_video_path 为准。",
            file=sys.stderr,
        )

    data: Dict[str, Any] = {
        "video_url": video_url,
        "output_tos_path": output_tos_path,
    }
    if targets:
        data["targets"] = targets
    if return_subtitle_bbox is not None:
        data["return_subtitle_bbox"] = bool(return_subtitle_bbox)
    if detection_precise_mode is not None:
        data["detection_precise_mode"] = bool(detection_precise_mode)
    if inpainting_backend:
        data["inpainting_backend"] = inpainting_backend
    if max_process_frames is not None:
        data["max_process_frames"] = int(max_process_frames)
    if subtitle_mask_precise is not None:
        data["subtitle_mask_precise"] = bool(subtitle_mask_precise)
    if fixed_bboxes:
        data["fixed_bboxes"] = fixed_bboxes

    payload = {
        "operator_id": OPERATOR_ID,
        "operator_version": OPERATOR_VERSION,
        "data": data,
    }

    if dry_run:
        print("--- request payload (dry-run) ---")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return {"metadata": {"task_status": "DRY_RUN", "business_code": "0", "error_msg": ""}, "data": {}}

    endpoint = get_submit_endpoint(cli_region=region)
    return _http_post_json(url=endpoint, payload=payload)


def poll_task(*, region: Optional[str], task_id: str) -> Dict[str, Any]:
    if not task_id:
        raise ValueError("task_id 不能为空")
    payload = {
        "operator_id": OPERATOR_ID,
        "operator_version": OPERATOR_VERSION,
        "task_id": task_id,
    }
    endpoint = get_poll_endpoint(cli_region=region)
    return _http_post_json(url=endpoint, payload=payload)


def _write_json(path: str, data: Dict[str, Any]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _is_success_business_code(code: Any) -> bool:
    return code in (0, "0", "200")


def _assert_poll_success(result: Dict[str, Any]) -> None:
    meta = result.get("metadata")
    if not isinstance(meta, dict):
        raise RuntimeError("响应缺少 metadata")
    status = meta.get("task_status")
    business_code = meta.get("business_code")
    error_msg = meta.get("error_msg")
    if status in {"FAILED", "TIMEOUT"}:
        raise RuntimeError(f"任务失败: task_status={status} business_code={business_code} error_msg={error_msg}")
    if status == "COMPLETED" and not _is_success_business_code(business_code):
        raise RuntimeError(f"任务失败: task_status={status} business_code={business_code} error_msg={error_msg}")


def _format_summary(result: Dict[str, Any]) -> str:
    meta = result.get("metadata", {})
    status = meta.get("task_status", "UNKNOWN")
    lines: List[str] = []
    lines.append("## Video Inpaint 任务")
    lines.append("")
    lines.append(f"task_status: {status}")
    if meta.get("task_id"):
        lines.append(f"task_id: {meta.get('task_id')}")
    lines.append(f"business_code: {meta.get('business_code', 'unknown')}")
    if meta.get("error_msg"):
        lines.append(f"error_msg: {meta.get('error_msg')}")
    if meta.get("request_id"):
        lines.append(f"request_id: {meta.get('request_id')}")

    data = result.get("data")
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except Exception:
            pass

    if isinstance(data, dict) and status == "COMPLETED":
        outp = data.get("inpainted_video_path")
        bbox = data.get("subtitle_bbox")
        lines.append("")
        lines.append("### 输出信息")
        if outp:
            lines.append(f"- inpainted_video_path: {outp}")
        if bbox:
            lines.append(f"- subtitle_bbox: {bbox}")
    return "\n".join(lines)


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--region",
        choices=sorted(REGION_TO_DOMAIN.keys()),
        help="operator region (env: LAS_REGION)",
    )


def _json_loads_maybe(s: str) -> Any:
    try:
        return json.loads(s)
    except Exception as e:
        raise ValueError("无效 JSON") from e


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="skill.py",
        description="LAS-VIDEO-INPAINT (las_video_inpaint) CLI",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_info = subparsers.add_parser("info", help="Show operator endpoint info")
    _add_common_args(p_info)

    p_poll = subparsers.add_parser("poll", help="Poll task by task_id")
    p_poll.add_argument("task_id", help="Task ID (task-xxx)")
    p_poll.add_argument("--out", help="Save raw JSON response to file")
    _add_common_args(p_poll)

    p_submit = subparsers.add_parser("submit", help="Submit inpaint task (optional wait)")
    p_submit.add_argument("--video-url", required=True, help="Video URL (http/https or tos://)")
    p_submit.add_argument(
        "--output-tos-path",
        required=True,
        help="Output TOS path prefix (directory recommended; final output returned by inpainted_video_path)",
    )
    p_submit.add_argument(
        "--targets",
        action="append",
        help='Target type (watermark/subtitle/scrolling_subtitle). Use multiple times or pass space-separated values.',
    )
    p_submit.add_argument("--return-subtitle-bbox", type=str, default=None, help="true/false")
    p_submit.add_argument("--detection-precise-mode", type=str, default=None, help="true/false")
    p_submit.add_argument("--inpainting-backend", choices=["pixel_replace", "pixel_generate"], default=None)
    p_submit.add_argument("--max-process-frames", type=int, default=None)
    p_submit.add_argument("--subtitle-mask-precise", type=str, default=None, help="true/false")
    p_submit.add_argument(
        "--fixed-bboxes-json",
        default=None,
        help='Fixed bboxes JSON, e.g. [[100,600,300,650],[1000,1000,1000,1000]] (1000x1000 normalized)',
    )
    p_submit.add_argument("--dry-run", action="store_true", help="Print request payload without sending")
    p_submit.add_argument("--out", help="Save raw JSON response to file")
    _add_common_args(p_submit)

    return parser


def _parse_bool(s: Optional[str]) -> Optional[bool]:
    if s is None:
        return None
    v = s.strip().lower()
    if v in {"true", "1", "yes", "y"}:
        return True
    if v in {"false", "0", "no", "n"}:
        return False
    raise ValueError("布尔参数仅支持 true/false")


def _flatten_targets(values: Optional[List[str]]) -> Optional[List[str]]:
    if not values:
        return None
    out: List[str] = []
    for v in values:
        parts = [p for p in str(v).replace(",", " ").split(" ") if p]
        out.extend(parts)
    return out or None


def _should_finish(status: str) -> bool:
    return status in {"COMPLETED", "FAILED", "TIMEOUT"}


def main(argv: List[str]) -> None:
    if argv and argv[0] not in {"submit", "poll", "info", "-h", "--help"}:
        argv = ["submit"] + argv

    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "info":
            print("operator_id:", OPERATOR_ID)
            print("submit:", get_submit_endpoint(cli_region=args.region))
            print("poll:", get_poll_endpoint(cli_region=args.region))
            return

        if args.command == "poll":
            result = poll_task(region=args.region, task_id=args.task_id)
            if args.out:
                _write_json(str(args.out), result)
            _assert_poll_success(result)
            print(_format_summary(result))
            return

        if args.command == "submit":
            fixed_bboxes = _json_loads_maybe(args.fixed_bboxes_json) if args.fixed_bboxes_json else None
            targets = _flatten_targets(args.targets)
            result = submit_task(
                region=args.region,
                video_url=args.video_url,
                output_tos_path=args.output_tos_path,
                targets=targets,
                return_subtitle_bbox=_parse_bool(args.return_subtitle_bbox),
                detection_precise_mode=_parse_bool(args.detection_precise_mode),
                inpainting_backend=args.inpainting_backend,
                max_process_frames=args.max_process_frames,
                subtitle_mask_precise=_parse_bool(args.subtitle_mask_precise),
                fixed_bboxes=fixed_bboxes,
                dry_run=bool(args.dry_run),
            )

            meta = result.get("metadata", {}) if isinstance(result, dict) else {}
            task_id = meta.get("task_id")
            if args.out:
                _write_json(str(args.out), result)

            print(json.dumps(result, ensure_ascii=False, indent=2))
            return

    except Exception as e:
        _print_http_error(e)
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv[1:])
