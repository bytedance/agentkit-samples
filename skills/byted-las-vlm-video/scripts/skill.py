#!/usr/bin/env python3
"""LAS-VLM-VIDEO Skill (las_vlm_video)

封装文档中的同步调用流程：
- POST https://operator.las.cn-beijing.volces.com/api/v1/process
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
import socket
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import requests

DEFAULT_REGION = "cn-beijing"

REGION_TO_DOMAIN = {
    "cn-beijing": "operator.las.cn-beijing.volces.com",
    "cn-shanghai": "operator.las.cn-shanghai.volces.com",
}

OPERATOR_ID = "las_vlm_video"
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
        try:
            ip = socket.gethostbyname(hostname)
            if _is_private_ip(ip):
                raise ValueError(f"禁止访问内网地址: {hostname} ({ip})")
        except socket.gaierror as e:
            raise ValueError(f"无法解析域名: {hostname}") from e
    return url


def _extract_error_meta(resp_json: Any) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    if not isinstance(resp_json, dict):
        return None, None, None
    meta = resp_json.get("metadata")
    if not isinstance(meta, dict):
        return None, None, None
    return (
        meta.get("business_code"),
        meta.get("error_msg"),
        meta.get("request_id"),
    )


def _print_http_error(e: Exception) -> None:
    if isinstance(e, requests.HTTPError) and getattr(e, "response", None) is not None:
        r = e.response
        try:
            j = r.json()
            bc, em, rid = _extract_error_meta(j)
            print(f"✗ HTTP {r.status_code} {r.reason}")
            if bc or em or rid:
                print(f"business_code: {bc}")
                print(f"error_msg: {em}")
                if rid:
                    print(f"request_id: {rid}")
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


def get_endpoint(*, cli_region: Optional[str] = None) -> str:
    api_base = get_api_base(cli_region=cli_region)
    return f"{api_base}/process"


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


def _headers() -> Dict[str, str]:
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {get_api_key()}",
    }


def _build_messages(*, video_url: str, text: str) -> List[Dict[str, Any]]:
    return [
        {
            "role": "user",
            "content": [
                {"type": "video_url", "video_url": {"url": video_url}},
                {"type": "text", "text": text},
            ],
        }
    ]


def process_task(
    *,
    region: Optional[str] = None,
    video_url: str,
    text: str,
    model_name: Optional[str] = None,
    min_resolution_height: Optional[int] = None,
    compress_fps: Optional[float] = None,
    max_tokens: Optional[int] = None,
    max_completion_tokens: Optional[int] = None,
    temperature: Optional[float] = None,
    top_p: Optional[float] = None,
    stop: Optional[List[str]] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    if not video_url:
        raise ValueError("video_url 不能为空")
    _validate_url(video_url)
    if not text:
        raise ValueError("text 不能为空")

    data: Dict[str, Any] = {
        "messages": _build_messages(video_url=video_url, text=text),
    }
    if model_name:
        data["model_name"] = model_name
    if min_resolution_height is not None:
        data["min_resolution_height"] = min_resolution_height
    if compress_fps is not None:
        data["compress_fps"] = compress_fps
    if max_tokens is not None:
        data["max_tokens"] = max_tokens
    if max_completion_tokens is not None:
        data["max_completion_tokens"] = max_completion_tokens
    if temperature is not None:
        data["temperature"] = temperature
    if top_p is not None:
        data["top_p"] = top_p
    if stop:
        data["stop"] = stop

    payload = {
        "operator_id": OPERATOR_ID,
        "operator_version": OPERATOR_VERSION,
        "data": data,
    }

    if dry_run:
        print("--- request payload (dry-run) ---")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return {"metadata": {"task_status": "DRY_RUN", "business_code": "0", "error_msg": ""}, "data": {}}

    endpoint = get_endpoint(cli_region=region)
    resp = requests.post(endpoint, headers=_headers(), json=payload, timeout=300)
    if not resp.ok:
        raise requests.HTTPError("request failed", response=resp)
    resp_json: Any = resp.json()
    if isinstance(resp_json, dict):
        return resp_json
    raise ValueError("Response is not a JSON object")


def _write_json(path: str, data: Dict[str, Any]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _extract_vlm_text(data: Any) -> Optional[str]:
    if not isinstance(data, dict):
        return None
    vlm_result = data.get("vlm_result")
    if isinstance(vlm_result, list) and vlm_result:
        vlm_result = vlm_result[0]
    if not isinstance(vlm_result, dict):
        return None
    choices = vlm_result.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    msg = choices[0].get("message")
    if not isinstance(msg, dict):
        return None
    content = msg.get("content")
    if isinstance(content, str):
        return content
    return None


def _format_summary(result: Dict[str, Any]) -> str:
    meta = result.get("metadata", {})
    status = meta.get("task_status", "UNKNOWN")
    lines: List[str] = []
    lines.append("## VLM Video 任务")
    lines.append("")
    lines.append(f"task_status: {status}")
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

    vlm_text = _extract_vlm_text(data)
    if vlm_text:
        lines.append("")
        lines.append("### 模型输出")
        lines.append(vlm_text)

    if isinstance(data, dict):
        compress = data.get("compress_result")
        if isinstance(compress, list) and compress:
            lines.append("")
            lines.append(f"### 压缩结果 ({len(compress)})")
            for item in compress[:3]:
                if not isinstance(item, dict):
                    continue
                vurl = item.get("video_url")
                if vurl:
                    lines.append(f"- video_url: {vurl}")

    return "\n".join(lines)


def _is_success_business_code(code: Any) -> bool:
    return code in (0, "0", 200, "200")


def _assert_success(result: Dict[str, Any]) -> None:
    meta = result.get("metadata")
    if not isinstance(meta, dict):
        raise RuntimeError("响应缺少 metadata")
    status = meta.get("task_status")
    business_code = meta.get("business_code")
    error_msg = meta.get("error_msg")
    if status != "COMPLETED" or not _is_success_business_code(business_code):
        raise RuntimeError(f"模型请求失败: task_status={status} business_code={business_code} error_msg={error_msg}")


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--region",
        choices=sorted(REGION_TO_DOMAIN.keys()),
        help="operator region (env: LAS_REGION)",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="skill.py",
        description="LAS-VLM-VIDEO (las_vlm_video) CLI",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_info = subparsers.add_parser("info", help="Show operator endpoint info")
    _add_common_args(p_info)

    p_process = subparsers.add_parser("process", help="Execute video understanding")
    p_process.add_argument("--video-url", required=True, help="Video URL (http/https or tos://bucket/key)")
    p_process.add_argument("--text", required=True, help="Prompt text for video understanding")
    p_process.add_argument("--model-name", default=None, help="Doubao model name (e.g. doubao-seed-1.6-vision)")
    p_process.add_argument("--min-resolution-height", type=int, default=None, help="Min vertical resolution (default 360)")
    p_process.add_argument("--compress-fps", type=float, default=None, help="Compressed FPS (default 5.0)")
    p_process.add_argument("--max-tokens", type=int, default=None, help="Max output tokens")
    p_process.add_argument("--max-completion-tokens", type=int, default=None, help="Max completion tokens (mutual exclusive with max_tokens on server)")
    p_process.add_argument("--temperature", type=float, default=None, help="Sampling temperature (0~2)")
    p_process.add_argument("--top-p", type=float, default=None, help="Top-p (0~1)")
    p_process.add_argument("--stop", action="append", help="Stop string (can use multiple times)")
    p_process.add_argument("--dry-run", action="store_true", help="Print request payload without sending")
    p_process.add_argument("--out", help="Save raw JSON response to file")
    _add_common_args(p_process)

    return parser


def main(argv: List[str]) -> None:
    if argv and argv[0] not in {"process", "info", "-h", "--help"}:
        argv = ["process"] + argv

    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "info":
            print("operator_id:", OPERATOR_ID)
            print("endpoint:", get_endpoint(cli_region=args.region))
            return

        if args.command == "process":
            print("Processing task...")
            result = process_task(
                region=args.region,
                video_url=args.video_url,
                text=args.text,
                model_name=args.model_name,
                min_resolution_height=args.min_resolution_height,
                compress_fps=args.compress_fps,
                max_tokens=args.max_tokens,
                max_completion_tokens=args.max_completion_tokens,
                temperature=args.temperature,
                top_p=args.top_p,
                stop=args.stop,
                dry_run=args.dry_run,
            )

            if args.out:
                _write_json(str(args.out), result)

            if not args.dry_run:
                _assert_success(result)

            print(_format_summary(result))
            return

    except Exception as e:
        _print_http_error(e)
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv[1:])
