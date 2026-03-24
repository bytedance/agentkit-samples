"""LAS 视频智能剪辑 Skill（las_video_edit，scripts/skill.py）

封装火山引擎文档中的异步调用流程：
- submit: POST https://operator.las.cn-beijing.volces.com/api/v1/submit
- poll:   POST https://operator.las.cn-beijing.volces.com/api/v1/poll

优先从环境变量读取 LAS_API_KEY；也支持从当前目录 env.sh 读取。
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
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import requests


DEFAULT_REGION = "cn-beijing"

# 常见 region -> domain 映射（按需可扩展）
REGION_TO_DOMAIN = {
    "cn-beijing": "operator.las.cn-beijing.volces.com",
    "cn-shanghai": "operator.las.cn-shanghai.volces.com",
}

OPERATOR_ID = "las_video_edit"
OPERATOR_VERSION = "v1"


# 注意：线上接口的 mode 可选值以服务端返回为准。
# 当前已验证可用：simple / detail。
MODE_ALIASES = {
    # 英文别名
    "simple": "simple",
    "detail": "detail",
    "fine": "detail",
    "normal": "simple",
    "standard": "simple",
    "简单": "simple",
    "精细": "detail",
    "标准": "detail",
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


def _validate_urls(urls: List[str]) -> None:
    for url in urls:
        _validate_url(url)


def _json_loads_maybe(s: str) -> Any:
    try:
        return json.loads(s)
    except Exception as e:
        raise ValueError(f"JSON 解析失败: {e}")


def _read_json_file(path: str) -> Any:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"JSON 文件不存在: {path}")
    return _json_loads_maybe(p.read_text(encoding="utf-8", errors="ignore"))


def _extract_error_meta(resp_json: Any) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """从返回 JSON 中提取 business_code/error_msg/request_id（若存在）。"""

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
    """获取 region。

优先级：CLI 参数 > 环境变量 > 默认值。

支持环境变量（大小写敏感，按顺序取第一个非空）：
- LAS_REGION: cn-beijing / cn-shanghai
- REGION: cn-beijing / cn-shanghai
- region: cn-beijing / cn-shanghai
"""

    if cli_region:
        return cli_region
    env_region = os.environ.get("LAS_REGION")
    if env_region:
        return env_region
    env_region = os.environ.get("REGION")
    if env_region:
        return env_region
    env_region = os.environ.get("region")
    if env_region:
        return env_region
    return DEFAULT_REGION


def get_api_base(*, cli_region: Optional[str] = None) -> str:
    """获取 operator API base。"""
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
        if "\"" in line:
            parts = line.split("\"")
            if len(parts) >= 2:
                return parts[1].strip()
        if "'" in line:
            parts = line.split("'")
            if len(parts) >= 2:
                return parts[1].strip()
        if "=" in line:
            return line.split("=", 1)[1].strip().strip('"').strip("'")
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


def _headers() -> Dict[str, str]:
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {get_api_key()}",
    }


def submit_task(
    *,
    region: Optional[str] = None,
    video_url: str,
    output_tos_path: str,
    task_name: Optional[str] = None,
    task_description: Optional[str] = None,
    reference_images: Optional[List[str]] = None,
    reference_target: Optional[str] = None,
    segment_duration: Optional[int] = None,
    mode: Optional[str] = None,
    min_segment_duration: Optional[int] = None,
    output_format: Optional[str] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    if not video_url:
        raise ValueError("video_url 不能为空")
    _validate_url(video_url)
    if not output_tos_path:
        raise ValueError("output_tos_path 不能为空")
    _validate_url(output_tos_path)
    if not task_name and not task_description:
        raise ValueError("task_name 与 task_description 至少提供一个")

    data: Dict[str, Any] = {
        "video_url": video_url,
        "output_tos_path": output_tos_path,
    }
    if task_name:
        data["task_name"] = task_name
    if task_description:
        data["task_description"] = task_description
    if reference_images:
        # 参考图像字段：以服务端 schema 为准。
        # 当前已知可用样例：
        # "reference_images": [{"target": "杜兰特", "images": ["https://...jpeg", "tos://..."]}]

        # 兼容用户直接传入 [{target, images}] 的结构（advanced usage）
        if all(isinstance(x, dict) and ("target" in x or "images" in x) for x in reference_images):
            data["reference_images"] = reference_images
            # 收集 reference_images 中的 URL 并做安全校验，避免绕过内网地址限制
            urls: List[str] = []
            for obj in reference_images:
                if isinstance(obj, dict):
                    images_field = obj.get("images")
                    if isinstance(images_field, list):
                        for img in images_field:
                            if isinstance(img, str):
                                urls.append(img)
            if urls:
                _validate_urls(urls)
        else:
            if not reference_target:
                raise ValueError(
                    "使用 --ref-image 时需要同时提供 --ref-target（例如：--ref-target 杜兰特），"
                    "或直接传入完整的 reference_images 结构（包含 target/images）。"
                )
            images: List[str] = []
            for item in reference_images:
                if isinstance(item, str):
                    images.append(item)
                elif isinstance(item, dict):
                    # 容错：把常见 key 里的值当作图片地址
                    for k in ("url", "image_url", "uri"):
                        v = item.get(k)
                        if isinstance(v, str) and v:
                            images.append(v)
                            break
                    else:
                        raise ValueError(f"无法从 reference_images 对象中提取图片地址: {item}")
                else:
                    raise ValueError(f"reference_images 元素类型不支持: {type(item)}")

            data["reference_images"] = [{"target": reference_target, "images": images}]
            _validate_urls(images)
    if segment_duration is not None:
        data["segment_duration"] = int(segment_duration)
    if mode:
        normalized_mode = MODE_ALIASES.get(str(mode).strip().lower(), MODE_ALIASES.get(str(mode).strip(), None))
        data["mode"] = normalized_mode or mode
    if min_segment_duration is not None:
        data["min_segment_duration"] = int(min_segment_duration)
    if output_format:
        data["output_format"] = output_format

    payload = {
        "operator_id": OPERATOR_ID,
        "operator_version": OPERATOR_VERSION,
        "data": data,
    }

    if dry_run:
        print("--- request payload (dry-run) ---")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return {"metadata": {"task_status": "DRY_RUN", "business_code": "0", "error_msg": ""}, "data": {}}

    submit_endpoint, _ = get_endpoints(cli_region=region)
    resp = requests.post(submit_endpoint, headers=_headers(), json=payload, timeout=60)
    try:
        resp_json: Any = resp.json()
    except Exception:
        resp_json = None
    if not resp.ok:
        bc, em, rid = _extract_error_meta(resp_json)
        raise requests.HTTPError(
            f"HTTP {resp.status_code} submit failed; business_code={bc}; error_msg={em}; request_id={rid}",
            response=resp,
        )
    if isinstance(resp_json, dict):
        return resp_json
    raise ValueError("submit 返回不是 JSON object")


def poll_task(task_id: str, *, region: Optional[str] = None) -> Dict[str, Any]:
    if not task_id:
        raise ValueError("task_id 不能为空")
    payload = {
        "operator_id": OPERATOR_ID,
        "operator_version": OPERATOR_VERSION,
        "task_id": task_id,
    }
    _, poll_endpoint = get_endpoints(cli_region=region)
    resp = requests.post(poll_endpoint, headers=_headers(), json=payload, timeout=60)
    try:
        resp_json: Any = resp.json()
    except Exception:
        resp_json = None
    if not resp.ok:
        bc, em, rid = _extract_error_meta(resp_json)
        raise requests.HTTPError(
            f"HTTP {resp.status_code} poll failed; business_code={bc}; error_msg={em}; request_id={rid}",
            response=resp,
        )
    if isinstance(resp_json, dict):
        return resp_json
    raise ValueError("poll 返回不是 JSON object")


def wait_for_completion(
    task_id: str,
    *,
    region: Optional[str] = None,
    timeout: int = 1800,
    interval: int = 5,
) -> Dict[str, Any]:
    start = time.time()
    while True:
        result = poll_task(task_id, region=region)
        meta = result.get("metadata", {})
        status = meta.get("task_status")

        if status == "COMPLETED":
            return result
        if status in {"FAILED", "TIMEOUT"}:
            raise RuntimeError(
                "任务失败: "
                f"status={status}, business_code={meta.get('business_code')}, "
                f"error_msg={meta.get('error_msg')}, request_id={meta.get('request_id')}"
            )

        if time.time() - start > timeout:
            raise TimeoutError(f"等待超时（{timeout}秒），任务仍未完成：{status}")
        time.sleep(interval)


def _format_summary(result: Dict[str, Any]) -> str:
    meta = result.get("metadata", {})
    status = meta.get("task_status", "UNKNOWN")
    lines: List[str] = []
    lines.append("## 视频智能剪辑任务")
    lines.append("")
    lines.append(f"task_id: {meta.get('task_id', 'unknown')}")
    lines.append(f"task_status: {status}")
    lines.append(f"business_code: {meta.get('business_code', 'unknown')}")
    if meta.get("error_msg"):
        lines.append(f"error_msg: {meta.get('error_msg')}")

    data = result.get("data") or {}
    if status == "COMPLETED" and isinstance(data, dict):
        lines.append("")
        lines.append("---")
        lines.append(f"total_segments: {data.get('total_segments', 0)}")
        if data.get("video_duration") is not None:
            lines.append(f"video_duration: {data.get('video_duration')}s")
        if data.get("resolution"):
            lines.append(f"resolution: {data.get('resolution')}")

        clips = data.get("clips") or []
        if isinstance(clips, list) and clips:
            lines.append("")
            lines.append("### clips")
            for c in clips[:20]:
                if not isinstance(c, dict):
                    continue
                clip_id = c.get("clip_id", "unknown")
                st = c.get("start_time", "")
                et = c.get("end_time", "")
                desc = c.get("description", "")
                url = c.get("clip_url", "")
                lines.append(f"- {clip_id} {st}-{et} | {desc}")
                if url:
                    lines.append(f"  {url}")
            if len(clips) > 20:
                lines.append(f"(仅展示前 20 段，共 {len(clips)} 段)")

    return "\n".join(lines)


def _parse_kv_args(args: List[str]) -> Tuple[List[str], Dict[str, Any]]:
    """Parse argv into positional and flag dict.

    Flags are like: --key value, --key=value, --bool-flag
    Multi flags: --ref-image can repeat.
    """

    positional: List[str] = []
    flags: Dict[str, Any] = {"ref_image": []}

    i = 0
    while i < len(args):
        a = args[i]
        if not a.startswith("--"):
            positional.append(a)
            i += 1
            continue

        if "=" in a:
            k, v = a[2:].split("=", 1)
            key = k.replace("-", "_")
            if key in {"ref_image", "reference_image"}:
                flags["ref_image"].append(v)
            else:
                flags[key] = v
            i += 1
            continue

        key = a[2:].replace("-", "_")

        # bool flag
        if key in {"no_wait"}:
            flags[key] = True
            i += 1
            continue

        # expecting value
        if i + 1 >= len(args):
            raise ValueError(f"参数缺少值: {a}")
        val = args[i + 1]
        if key in {"ref_image", "reference_image"}:
            flags["ref_image"].append(val)
        else:
            flags[key] = val
        i += 2

    return positional, flags


def _write_json(path: str, data: Dict[str, Any]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _print_help() -> None:
    print("LAS 视频智能剪辑（las_video_edit）")
    print("")
    print("命令:")
    print("  submit [task_description] --video <url> --output-tos <tos://...> [options]")
    print("  poll <task_id>")
    print("  wait <task_id> [--timeout <sec>] [--interval <sec>] [--out <file.json>]")
    print("  info")
    print("")
    print("submit options:")
    print("  --task-name <name>           内置场景名（优先级高于 task_description）")
    print("  --task-desc <desc>           自然语言描述")
    print("  --ref-target <name>          参考图目标名称（如: 杜兰特）；与 --ref-image 配套")
    print("  --ref-image <url_or_tos>     参考图像 URL/TOS，可重复")
    print("  --ref-json <json>            直接传入 reference_images JSON（覆盖 --ref-target/--ref-image）")
    print("  --ref-json-file <path>       从文件读取 reference_images JSON（覆盖 --ref-target/--ref-image）")
    print("  --segment-duration <sec>     子视频切分时长")
    print("  --mode <mode>                处理模式（合法值: simple/detail；兼容别名 normal/标准/精细 等）")
    print("  --min-segment-duration <sec> 过滤过短片段")
    print("  --output-format <mp4|mkv>    输出格式")
    print("  --no-wait                    只提交不等待")
    print("  --dry-run                    只打印请求体，不发请求")
    print("  --timeout <sec>              等待超时（默认 1800）")
    print("  --interval <sec>             轮询间隔（默认 5）")
    print("  --out <file.json>            保存原始 JSON")
    print(
        "  --region <cn-beijing|cn-shanghai>  选择 operator region（也可用环境变量 LAS_REGION/REGION/region）"
    )
    print("  --api-base <https://.../api/v1>    显式指定 API base（也可用环境变量 LAS_API_BASE）")
    print("")
    print("示例:")
    print("  python3 scripts/skill.py submit --video https://... --output-tos tos://... --task-desc \"提取高光片段\"")
    print("  python3 scripts/skill.py submit --video https://... --output-tos tos://... --task-desc \"找杜兰特\" --ref-target 杜兰特 --ref-image https://...jpeg")
    print("  python3 scripts/skill.py submit --video https://... --output-tos tos://... --task-desc \"找杜兰特\" \\")
    print("    --ref-json '[{\"target\":\"杜兰特\",\"images\":[\"https://...jpeg\"]}]'")
    print("  python3 scripts/skill.py poll task-xxx")


def main_legacy(argv: List[str]) -> None:
    if not argv or argv[0] in {"-h", "--help", "help"}:
        _print_help()
        return

    cmd = argv[0]
    cmd_args = argv[1:]

    if cmd == "info":
        positional, flags = _parse_kv_args(cmd_args)
        region = flags.get("region")
        api_base = flags.get("api_base")
        submit_endpoint, poll_endpoint = get_endpoints(cli_api_base=api_base, cli_region=region)

        print("operator_id:", OPERATOR_ID)
        print("operator_version:", OPERATOR_VERSION)
        # 展示“解析后的 region”以及“环境变量原值”，方便排查 region 选择问题
        print("region:", get_region(region))
        print("env.LAS_REGION:", os.environ.get("LAS_REGION"))
        print("env.REGION:", os.environ.get("REGION"))
        print("env.region:", os.environ.get("region"))
        print("api_base:", get_api_base(cli_api_base=api_base, cli_region=region))
        print("submit:", submit_endpoint)
        print("poll:", poll_endpoint)
        return

    if cmd == "poll":
        if not cmd_args:
            raise ValueError("用法: poll <task_id>")
        positional, flags = _parse_kv_args(cmd_args)
        task_id = positional[0]
        region = flags.get("region")
        api_base = flags.get("api_base")
        try:
            result = poll_task(task_id, api_base=api_base, region=region)
            print(_format_summary(result))
        except Exception as e:
            _print_http_error(e)
        return

    if cmd == "wait":
        if not cmd_args:
            raise ValueError("用法: wait <task_id> [--timeout <sec>] [--interval <sec>] [--out <file.json>]")
        positional, flags = _parse_kv_args(cmd_args)
        task_id = positional[0]
        region = flags.get("region")
        api_base = flags.get("api_base")
        timeout = int(flags.get("timeout", 1800))
        interval = int(flags.get("interval", 5))
        out = flags.get("out")

        result = wait_for_completion(task_id, api_base=api_base, region=region, timeout=timeout, interval=interval)
        if out:
            _write_json(str(out), result)
        print(_format_summary(result))
        return

    if cmd == "submit":
        positional, flags = _parse_kv_args(cmd_args)

        # 兼容: submit <task_description> ...
        task_desc = flags.get("task_desc") or flags.get("task_description")
        if positional and not task_desc:
            task_desc = positional[0]

        region = flags.get("region")
        api_base = flags.get("api_base")
        dry_run = bool(flags.get("dry_run", False))

        video = flags.get("video") or flags.get("video_url")
        output_tos = flags.get("output_tos") or flags.get("output_tos_path") or flags.get("output_tos_dir")
        task_name = flags.get("task_name")
        mode = flags.get("mode")
        segment_duration = flags.get("segment_duration")
        min_seg = flags.get("min_segment_duration")
        out_fmt = flags.get("output_format")
        no_wait = bool(flags.get("no_wait", False))

        timeout = int(flags.get("timeout", 1800))
        interval = int(flags.get("interval", 5))
        out = flags.get("out")

        ref_target = flags.get("ref_target") or flags.get("target")

        # 优先支持用户直接输入 reference_images 的 JSON
        ref_json = flags.get("ref_json")
        ref_json_file = flags.get("ref_json_file")

        ref_images: List[Any]
        if ref_json_file:
            parsed = _read_json_file(str(ref_json_file))
            if not isinstance(parsed, list):
                raise ValueError("--ref-json-file 内容必须是 JSON array")
            ref_images = parsed
            ref_target = None
        elif ref_json:
            parsed = _json_loads_maybe(str(ref_json))
            if not isinstance(parsed, list):
                raise ValueError("--ref-json 内容必须是 JSON array")
            ref_images = parsed
            ref_target = None
        else:
            ref_images = flags.get("ref_image") or []
            if not isinstance(ref_images, list):
                ref_images = [str(ref_images)]

        print("正在提交剪辑任务...")
        try:
            result = submit_task(
                api_base=str(api_base) if api_base else None,
                region=str(region) if region else None,
                video_url=str(video),
                output_tos_path=str(output_tos),
                task_name=str(task_name) if task_name else None,
                task_description=str(task_desc) if task_desc else None,
                reference_images=ref_images if ref_images else None,  # type: ignore[arg-type]
                reference_target=str(ref_target) if ref_target else None,
                segment_duration=int(segment_duration) if segment_duration is not None else None,
                mode=str(mode) if mode else None,
                min_segment_duration=int(min_seg) if min_seg is not None else None,
                output_format=str(out_fmt) if out_fmt else None,
                dry_run=dry_run,
            )
        except Exception as e:
            _print_http_error(e)
            return

        meta = result.get("metadata", {})
        task_id = meta.get("task_id")
        if meta.get("task_status") == "DRY_RUN":
            return

        print("提交成功")
        print(f"task_id: {task_id}")

        if no_wait or not task_id:
            if out:
                _write_json(str(out), result)
            return

        print("等待任务完成...")
        final_result = wait_for_completion(
            str(task_id),
            api_base=str(api_base) if api_base else None,
            region=str(region) if region else None,
            timeout=timeout,
            interval=interval,
        )
        if out:
            _write_json(str(out), final_result)
        print(_format_summary(final_result))
        return

    # 默认：把整段当作 submit
    positional, flags = _parse_kv_args(argv)
    # argv[0] 不是命令时，positional 里会包含它；这里复用 submit 的逻辑
    main_legacy(["submit"] + argv)


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--region",
        choices=sorted(REGION_TO_DOMAIN.keys()),
        help="operator region（也可用环境变量 LAS_REGION/REGION/region；默认 cn-beijing）",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="skill.py",
        description="LAS 视频智能剪辑（las_video_edit）CLI",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_info = subparsers.add_parser("info", help="打印当前 operator endpoint 信息")
    _add_common_args(p_info)

    p_poll = subparsers.add_parser("poll", help="查询任务状态与结果")
    p_poll.add_argument("task_id", help="任务 ID")
    _add_common_args(p_poll)

    p_wait = subparsers.add_parser("wait", help="等待任务完成")
    p_wait.add_argument("task_id", help="任务 ID")
    p_wait.add_argument("--timeout", type=int, default=1800, help="等待超时（秒）")
    p_wait.add_argument("--interval", type=int, default=5, help="轮询间隔（秒）")
    p_wait.add_argument("--out", help="保存原始 JSON 到文件")
    _add_common_args(p_wait)

    p_submit = subparsers.add_parser("submit", help="提交剪辑任务（可选等待完成）")
    p_submit.add_argument("--video", required=True, help="视频 URL（http/https 或 tos://）")
    p_submit.add_argument("--output-tos", required=True, dest="output_tos", help="输出片段目录 tos://bucket/prefix")
    p_submit.add_argument("--task-name", dest="task_name", help="内置场景名（优先级高于 task_description）")
    p_submit.add_argument("--task-desc", dest="task_desc", help="自然语言剪辑需求描述")
    p_submit.add_argument("task_desc_pos", nargs="?", help="可选：把 task_desc 作为位置参数传入")

    ref_group = p_submit.add_mutually_exclusive_group()
    ref_group.add_argument("--ref-json", help="直接传入 reference_images JSON（JSON array）")
    ref_group.add_argument("--ref-json-file", help="从文件读取 reference_images JSON（JSON array）")

    p_submit.add_argument("--ref-target", help="参考图目标名称（如：杜兰特）")
    p_submit.add_argument("--ref-image", action="append", default=[], help="参考图 URL/TOS，可重复")

    p_submit.add_argument("--segment-duration", type=int, help="子视频切分时长（秒）")
    p_submit.add_argument("--mode", help="处理模式（合法值: simple/detail；兼容别名 normal/标准/精细 等）")
    p_submit.add_argument("--min-segment-duration", type=int, help="过滤过短片段（秒）")
    p_submit.add_argument("--output-format", help="输出格式（mp4/mkv）")

    p_submit.add_argument("--no-wait", action="store_true", help="只提交不等待")
    p_submit.add_argument("--dry-run", action="store_true", help="只打印请求体，不发请求")
    p_submit.add_argument("--timeout", type=int, default=1800, help="等待超时（秒）")
    p_submit.add_argument("--interval", type=int, default=5, help="轮询间隔（秒）")
    p_submit.add_argument("--out", help="保存原始 JSON 到文件")
    _add_common_args(p_submit)

    return parser


def _normalize_submit_args(args: argparse.Namespace) -> None:
    if not args.task_desc and getattr(args, "task_desc_pos", None):
        args.task_desc = args.task_desc_pos
    if not args.task_name and not args.task_desc:
        raise ValueError("submit 需要至少提供一个：--task-name 或 --task-desc（或位置参数 task_desc）")


def _build_reference_images(args: argparse.Namespace) -> Optional[List[Any]]:
    if getattr(args, "ref_json_file", None):
        parsed = _read_json_file(str(args.ref_json_file))
        if not isinstance(parsed, list):
            raise ValueError("--ref-json-file 内容必须是 JSON array")
        return parsed
    if getattr(args, "ref_json", None):
        parsed = _json_loads_maybe(str(args.ref_json))
        if not isinstance(parsed, list):
            raise ValueError("--ref-json 内容必须是 JSON array")
        return parsed
    if getattr(args, "ref_image", None):
        if args.ref_image and not args.ref_target:
            raise ValueError("使用 --ref-image 时需要同时提供 --ref-target")
        if args.ref_image:
            return list(args.ref_image)
    return None


def main(argv: List[str]) -> None:
    # 兼容历史用法：未显式写子命令时，默认当作 submit
    if argv and argv[0] not in {"submit", "poll", "wait", "info", "-h", "--help"}:
        argv = ["submit"] + argv

    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "info":
            submit_endpoint, poll_endpoint = get_endpoints(cli_region=args.region)
            print("operator_id:", OPERATOR_ID)
            print("operator_version:", OPERATOR_VERSION)
            print("region:", get_region(args.region))
            print("env.LAS_REGION:", os.environ.get("LAS_REGION"))
            print("env.REGION:", os.environ.get("REGION"))
            print("env.region:", os.environ.get("region"))
            print("api_base:", get_api_base(cli_region=args.region))
            print("submit:", submit_endpoint)
            print("poll:", poll_endpoint)
            return

        if args.command == "poll":
            result = poll_task(args.task_id, region=args.region)
            print(_format_summary(result))
            return

        if args.command == "wait":
            result = wait_for_completion(
                args.task_id,
                region=args.region,
                timeout=args.timeout,
                interval=args.interval,
            )
            if args.out:
                _write_json(str(args.out), result)
            print(_format_summary(result))
            return

        if args.command == "submit":
            _normalize_submit_args(args)
            ref_images = _build_reference_images(args)
            print("正在提交剪辑任务...")

            result = submit_task(
                region=args.region,
                video_url=str(args.video),
                output_tos_path=str(args.output_tos),
                task_name=args.task_name,
                task_description=args.task_desc,
                reference_images=ref_images,  # type: ignore[arg-type]
                reference_target=args.ref_target,
                segment_duration=args.segment_duration,
                mode=args.mode,
                min_segment_duration=args.min_segment_duration,
                output_format=args.output_format,
                dry_run=bool(args.dry_run),
            )

            meta = result.get("metadata", {})
            task_id = meta.get("task_id")
            if meta.get("task_status") == "DRY_RUN":
                return

            print("提交成功")
            print(f"task_id: {task_id}")

            if args.out:
                _write_json(str(args.out), result)

            if args.no_wait or not task_id:
                return

            print("等待任务完成...")
            final_result = wait_for_completion(
                str(task_id),
                region=args.region,
                timeout=args.timeout,
                interval=args.interval,
            )
            if args.out:
                _write_json(str(args.out), final_result)
            print(_format_summary(final_result))
            return

        raise ValueError(f"未知命令: {args.command}")

    except Exception as e:
        _print_http_error(e)
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv[1:])
