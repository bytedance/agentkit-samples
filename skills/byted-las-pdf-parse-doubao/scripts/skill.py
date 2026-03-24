"""LAS-AI PDF 解析 Skill（las_pdf_parse_doubao）

封装 LAS 异步算子调用流程：submit -> poll/wait。

- submit: POST https://operator.las.<region>.volces.com/api/v1/submit
- poll:   POST https://operator.las.<region>.volces.com/api/v1/poll

API Key 读取优先级：
1) 环境变量 `LAS_API_KEY`
2) 当前目录 `env.sh`（兼容 `export LAS_API_KEY="..."` / `LAS_API_KEY=...`）

用法示例：
- 提交（不等待）: `python3 scripts/skill.py submit --url "https://...pdf" --no-wait`
- 等待并输出 Markdown: `python3 scripts/skill.py wait <task_id> --format markdown`
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
import socket
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlparse

import requests


DEFAULT_REGION = "cn-beijing"
REGION_TO_DOMAIN = {
    "cn-beijing": "operator.las.cn-beijing.volces.com",
    "cn-shanghai": "operator.las.cn-shanghai.volces.com",
}

OPERATOR_ID = "las_pdf_parse_doubao"
OPERATOR_VERSION = "v1"

PARSE_MODE_ALIASES = {
    "normal": "normal",
    "detail": "detail",
    "fast": "normal",
    "标准": "normal",
    "简单": "normal",
    "详细": "detail",
    "精细": "detail",
}

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
    """尽量把服务端错误信息打印出来，避免只看到 400/401。"""

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
    return (
        os.environ.get("LAS_REGION")
        or os.environ.get("REGION")
        or os.environ.get("region")
        or DEFAULT_REGION
    )


def get_api_base(*, cli_region: Optional[str] = None) -> str:
    region = get_region(cli_region)
    domain = REGION_TO_DOMAIN.get(region)
    if not domain:
        raise ValueError(f"未知 region: {region}，仅支持 {', '.join(REGION_TO_DOMAIN.keys())}")
    return f"https://{domain}/api/v1"


def get_endpoints(*, cli_region: Optional[str] = None) -> Tuple[str, str]:
    api_base = get_api_base(cli_region=cli_region)
    return f"{api_base}/submit", f"{api_base}/poll"


def _read_env_sh_api_key(env_file: Path) -> Optional[str]:
    if not env_file.exists():
        return None

    content = env_file.read_text(encoding="utf-8", errors="ignore")
    key_name = "".join(["LAS", "_", "API", "_", "KEY"])
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if key_name not in line:
            continue

        if '"' in line:
            parts = line.split('"')
            if len(parts) >= 2 and parts[1].strip():
                return parts[1].strip()
        if "'" in line:
            parts = line.split("'")
            if len(parts) >= 2 and parts[1].strip():
                return parts[1].strip()
        if "=" in line:
            v = line.split("=", 1)[1].strip().strip('"').strip("'")
            if v:
                return v

    return None


def get_api_key() -> str:
    key_name = "".join(["LAS", "_", "API", "_", "KEY"])
    api_key = os.environ.get(key_name)
    if api_key:
        return api_key

    env_file = Path.cwd() / "env.sh"
    api_key = _read_env_sh_api_key(env_file)
    if api_key:
        return api_key

    raise ValueError(f"无法找到 {key_name}：请设置环境变量 {key_name} 或在当前目录提供 env.sh")


def _get_auth_mode() -> str:
    return "bearer"


def _headers() -> Dict[str, str]:
    api_key = get_api_key()
    auth_mode = _get_auth_mode()
    h = {"Content-Type": "application/json"}
    if auth_mode == "bearer":
        h["Authorization"] = f"Bearer {api_key}"
        return h
    raise ValueError(f"未知 auth_mode: {auth_mode}（支持 bearer）")


def _is_retryable_http_status(code: int) -> bool:
    return code in (408, 425, 429, 500, 502, 503, 504)


def _is_retryable_business_code(resp_json: Any) -> bool:
    if not isinstance(resp_json, dict):
        return False
    meta = resp_json.get("metadata")
    if not isinstance(meta, dict):
        return False
    bc = meta.get("business_code")
    if bc is None:
        return False
    bc_str = str(bc)
    # 文档常见：2002 TIMEOUT_ERROR / 2003 SERVER_BUSY
    return bc_str in {"2002", "2003"}


def _post_json_with_retry(
    *,
    url: str,
    payload: Dict[str, Any],
    timeout_s: int,
    max_attempts: int = 3,
    backoff_s: float = 1.0,
) -> Dict[str, Any]:
    last_err: Optional[Exception] = None
    for attempt in range(1, max_attempts + 1):
        try:
            r = requests.post(url, headers=_headers(), json=payload, timeout=timeout_s)
            if not r.ok:
                if _is_retryable_http_status(r.status_code) and attempt < max_attempts:
                    time.sleep(backoff_s * (2 ** (attempt - 1)))
                    continue
                raise requests.HTTPError("request failed", response=r)

            j: Any = r.json()
            if not isinstance(j, dict):
                raise ValueError("返回不是 JSON object")

            if _is_retryable_business_code(j) and attempt < max_attempts:
                time.sleep(backoff_s * (2 ** (attempt - 1)))
                continue

            return j
        except Exception as e:
            last_err = e
            if attempt < max_attempts:
                time.sleep(backoff_s * (2 ** (attempt - 1)))
                continue
            raise

    raise RuntimeError(f"请求失败: {last_err}")


def _normalize_parse_mode(v: Optional[str]) -> Optional[str]:
    if v is None:
        return None
    v = v.strip()
    if not v:
        return None
    return PARSE_MODE_ALIASES.get(v, v)


def submit_task(
    *,
    region: Optional[str],
    url: str,
    parse_mode: Optional[str] = None,
    start_page: int = 1,
    num_pages: Optional[int] = None,
    timeout_s: int = 60,
    dry_run: bool = False,
) -> Dict[str, Any]:
    if not url:
        raise ValueError("url 不能为空")
    _validate_url(url)

    submit_url, _ = get_endpoints(cli_region=region)
    data: Dict[str, Any] = {
        "url": url,
        "start_page": start_page,
    }

    pm = _normalize_parse_mode(parse_mode)
    if pm:
        data["parse_mode"] = pm
    if num_pages is not None:
        data["num_pages"] = num_pages

    payload = {
        "operator_id": OPERATOR_ID,
        "operator_version": OPERATOR_VERSION,
        "data": data,
    }

    if dry_run:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return {"metadata": {"task_id": "DRY_RUN"}, "data": {}}

    return _post_json_with_retry(url=submit_url, payload=payload, timeout_s=timeout_s)


def poll_task(
    *,
    region: Optional[str],
    task_id: str,
    timeout_s: int = 60,
) -> Dict[str, Any]:
    if not task_id:
        raise ValueError("task_id 不能为空")

    _, poll_url = get_endpoints(cli_region=region)
    payload = {
        "operator_id": OPERATOR_ID,
        "operator_version": OPERATOR_VERSION,
        "task_id": task_id,
    }
    return _post_json_with_retry(url=poll_url, payload=payload, timeout_s=timeout_s)


def wait_for_completion(
    *,
    region: Optional[str],
    task_id: str,
    timeout_s: int,
    interval_s: int,
) -> Dict[str, Any]:
    start = time.time()
    while True:
        res = poll_task(region=region, task_id=task_id)
        meta = res.get("metadata") if isinstance(res, dict) else None
        meta = meta if isinstance(meta, dict) else {}
        status = meta.get("task_status")

        if status == "COMPLETED":
            return res
        if status in ("FAILED", "TIMEOUT"):
            bc, em, rid = _extract_error_meta(res)
            raise RuntimeError(
                "任务失败: "
                + json.dumps(
                    {
                        "task_id": task_id,
                        "task_status": status,
                        "business_code": bc,
                        "error_msg": em,
                        "request_id": rid,
                    },
                    ensure_ascii=False,
                )
            )
        if time.time() - start > timeout_s:
            raise TimeoutError(f"等待超时: timeout={timeout_s}s, last_status={status}")
        time.sleep(interval_s)


def _get_markdown(res: Dict[str, Any]) -> str:
    data = res.get("data")
    if not isinstance(data, dict):
        return ""
    md = data.get("markdown")
    return md if isinstance(md, str) else ""


def _write_text(path: str, content: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="skill.py", description="LAS-AI PDF 解析（las_pdf_parse_doubao）")
    sp = p.add_subparsers(dest="cmd")

    parent = argparse.ArgumentParser(add_help=False)
    parent.add_argument("--region", choices=sorted(REGION_TO_DOMAIN.keys()))

    sp.add_parser("info", parents=[parent], help="打印 endpoint")

    p_submit = sp.add_parser("submit", parents=[parent], help="提交任务")
    p_submit.add_argument("--url", required=True)
    p_submit.add_argument(
        "--parse-mode",
        default="normal",
        help="解析模式：normal（默认，不进行深度思考，速度更快）/ detail（开启深度思考，更细致但耗时更长）",
    )
    p_submit.add_argument("--start-page", type=int, default=1)
    p_submit.add_argument("--num-pages", type=int)
    p_submit.add_argument("--dry-run", action="store_true")
    p_submit.add_argument("--no-wait", action="store_true")
    p_submit.add_argument("--wait-timeout", type=int, default=1800)
    p_submit.add_argument("--interval", type=int, default=5)
    p_submit.add_argument("--format", choices=["markdown", "json"], default="markdown")
    p_submit.add_argument("--out-markdown")
    p_submit.add_argument("--out-json")

    p_poll = sp.add_parser("poll", parents=[parent], help="查询任务")
    p_poll.add_argument("task_id")
    p_poll.add_argument("--out-json")

    p_wait = sp.add_parser("wait", parents=[parent], help="等待任务完成")
    p_wait.add_argument("task_id")
    p_wait.add_argument("--timeout", type=int, default=1800)
    p_wait.add_argument("--interval", type=int, default=5)
    p_wait.add_argument("--format", choices=["markdown", "json"], default="markdown")
    p_wait.add_argument("--out-markdown")
    p_wait.add_argument("--out-json")

    return p


def main(argv: list[str]) -> None:
    # 兼容：用户直接传入 URL 时，默认做 submit --url <URL> --no-wait
    known_cmds = {"info", "submit", "poll", "wait"}
    if argv and argv[0] not in known_cmds and not argv[0].startswith("-"):
        argv = ["submit", "--url", argv[0], "--no-wait"] + argv[1:]

    parser = build_parser()
    if not argv:
        parser.print_help()
        return

    args = parser.parse_args(argv)
    if not args.cmd:
        parser.print_help()
        return

    if args.cmd == "info":
        submit_url, poll_url = get_endpoints(cli_region=args.region)
        print("operator_id:", OPERATOR_ID)
        print("operator_version:", OPERATOR_VERSION)
        print("region:", get_region(args.region))
        print("api_base:", get_api_base(cli_region=args.region))
        print("submit:", submit_url)
        print("poll:", poll_url)
        return

    if args.cmd == "submit":
        try:
            res = submit_task(
                region=args.region,
                url=args.url,
                parse_mode=args.parse_mode,
                start_page=args.start_page,
                num_pages=args.num_pages,
                dry_run=args.dry_run,
            )
            meta = res.get("metadata") if isinstance(res, dict) else None
            meta = meta if isinstance(meta, dict) else {}
            task_id = meta.get("task_id")
            if not task_id:
                print(json.dumps(res, ensure_ascii=False, indent=2)[:2000])
                raise ValueError("submit 返回缺少 metadata.task_id")

            if args.no_wait or args.dry_run:
                print(task_id)
                return

            final = wait_for_completion(
                region=args.region,
                task_id=task_id,
                timeout_s=args.wait_timeout,
                interval_s=args.interval,
            )
            if args.out_json:
                _write_text(args.out_json, json.dumps(final, ensure_ascii=False, indent=2))
            if args.format == "json":
                print(json.dumps(final, ensure_ascii=False, indent=2))
                return
            md = _get_markdown(final)
            if args.out_markdown:
                _write_text(args.out_markdown, md)
            print(md)
            return
        except Exception as e:
            _print_http_error(e)
            sys.exit(1)

    if args.cmd == "poll":
        try:
            res = poll_task(region=args.region, task_id=args.task_id)
            if args.out_json:
                _write_text(args.out_json, json.dumps(res, ensure_ascii=False, indent=2))
            print(json.dumps(res, ensure_ascii=False, indent=2))
            return
        except Exception as e:
            _print_http_error(e)
            sys.exit(1)

    if args.cmd == "wait":
        try:
            res = wait_for_completion(
                region=args.region,
                task_id=args.task_id,
                timeout_s=args.timeout,
                interval_s=args.interval,
            )
            if args.out_json:
                _write_text(args.out_json, json.dumps(res, ensure_ascii=False, indent=2))
            if args.format == "json":
                print(json.dumps(res, ensure_ascii=False, indent=2))
                return
            md = _get_markdown(res)
            if args.out_markdown:
                _write_text(args.out_markdown, md)
            print(md)
            return
        except Exception as e:
            _print_http_error(e)
            sys.exit(1)

    parser.print_help()


if __name__ == "__main__":
    main(sys.argv[1:])
