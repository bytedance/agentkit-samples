#!/usr/bin/env python3
"""LAS-AUDIO-CONVERT Skill (las_audio_convert)

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
import requests
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from urllib.parse import urlparse

DEFAULT_REGION = "cn-beijing"

# 常见 region -> domain 映射
REGION_TO_DOMAIN = {
    "cn-beijing": "operator.las.cn-beijing.volces.com",
    "cn-shanghai": "operator.las.cn-shanghai.volces.com",
}

OPERATOR_ID = "las_audio_convert"
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
        for network in PRIVATE_IP_NETWORKS:
            if ip in network:
                return True
        return False
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


def process_task(
    *,
    region: Optional[str] = None,
    input_path: str,
    output_path: str,
    output_format: str = "wav",
    extra_params: Optional[List[str]] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    if not input_path:
        raise ValueError("input_path 不能为空")
    _validate_url(input_path)
    if not output_path:
        raise ValueError("output_path 不能为空")
    # output_path 也应该是 TOS 路径，简单校验下
    _validate_url(output_path)

    data: Dict[str, Any] = {
        "input_path": input_path,
        "output_path": output_path,
        "output_format": output_format,
    }

    if extra_params:
        data["extra_params"] = extra_params

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
    
    try:
        resp_json: Any = resp.json()
    except Exception:
        resp_json = None
        
    if not resp.ok:
        bc, em, rid = _extract_error_meta(resp_json)
        raise requests.HTTPError(
            f"HTTP {resp.status_code} request failed; business_code={bc}; error_msg={em}; request_id={rid}",
            response=resp,
        )
    if isinstance(resp_json, dict):
        return resp_json
    raise ValueError("Response is not a JSON object")


def _write_json(path: str, data: Dict[str, Any]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _format_summary(result: Dict[str, Any]) -> str:
    meta = result.get("metadata", {})
    status = meta.get("task_status", "UNKNOWN")
    lines: List[str] = []
    lines.append("## Audio Convert 任务")
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
            
    if isinstance(data, dict):
        audios = data.get("audios")
        if audios and isinstance(audios, list):
            lines.append("")
            lines.append(f"### Converted Audios ({len(audios)})")
            for audio in audios:
                if isinstance(audio, dict):
                    status = audio.get("status", "unknown")
                    duration = audio.get("duration")
                    inp = audio.get("input_path")
                    out = audio.get("output_path")
                    
                    lines.append(f"- Status: {status}")
                    if duration is not None:
                        lines.append(f"  Duration: {duration}s")
                    if inp:
                        lines.append(f"  Input:  {inp}")
                    if out:
                        lines.append(f"  Output: {out}")
                    lines.append("")

    return "\n".join(lines)


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--region",
        choices=sorted(REGION_TO_DOMAIN.keys()),
        help="operator region (env: LAS_REGION)",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="skill.py",
        description="LAS-AUDIO-CONVERT (las_audio_convert) CLI",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_info = subparsers.add_parser("info", help="Show operator endpoint info")
    _add_common_args(p_info)

    p_process = subparsers.add_parser("process", help="Execute audio conversion")
    p_process.add_argument("--input-path", required=True, help="Input TOS path (e.g. tos://bucket/input.mp3)")
    p_process.add_argument("--output-path", required=True, help="Output TOS path (e.g. tos://bucket/output.wav)")
    p_process.add_argument("--output-format", default="wav", choices=["wav", "mp3", "flac"], help="Output format")
    p_process.add_argument("--extra-params", action="append", help="Extra FFmpeg parameters (can use multiple times)")
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
                input_path=args.input_path,
                output_path=args.output_path,
                output_format=args.output_format,
                extra_params=args.extra_params,
                dry_run=args.dry_run,
            )
            
            if args.out:
                _write_json(str(args.out), result)
            
            print(_format_summary(result))
            return

    except Exception as e:
        _print_http_error(e)
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv[1:])
