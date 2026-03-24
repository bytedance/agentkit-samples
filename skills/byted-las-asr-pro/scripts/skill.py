#!/usr/bin/env python3
"""LAS-ASR-PRO Skill（las_asr_pro，scripts/skill.py）

封装文档中的异步调用流程：

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

OPERATOR_ID = "las_asr_pro"
OPERATOR_VERSION = "v1"

TASK_TERMINAL_OK = {"COMPLETED"}
TASK_TERMINAL_FAIL = {"FAILED", "TIMEOUT"}

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

    key_name = "".join(["LAS", "_", "API", "_", "KEY"])
    raise ValueError(f"无法找到 {key_name}：请设置环境变量 {key_name} 或在当前目录提供 env.sh")


def _headers() -> Dict[str, str]:
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {get_api_key()}",
    }


def submit_task(
    *,
    region: Optional[str] = None,
    audio_url: str,
    audio_format: str,
    language: Optional[str] = None,
    resource: Optional[str] = None,
    uid: Optional[str] = None,
    model_name: str = "bigmodel",
    model_version: Optional[str] = None,
    enable_itn: Optional[bool] = None,
    enable_punc: bool = False,
    enable_ddc: bool = False,
    enable_speaker_info: bool = False,
    enable_channel_split: bool = False,
    show_utterances: bool = False,
    show_speech_rate: bool = False,
    show_volume: bool = False,
    enable_lid: bool = False,
    enable_emotion_detection: bool = False,
    enable_gender_detection: bool = False,
    vad_segment: bool = False,
    end_window_size: Optional[int] = None,
    enable_denoise: bool = False,
    enable_multi_language: Optional[bool] = None,
    sensitive_words_filter: Optional[str] = None,
    corpus_context: Optional[str] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    if not audio_url:
        raise ValueError("audio_url 不能为空")
    _validate_url(audio_url)
    if not audio_format:
        raise ValueError("audio_format 不能为空")

    data: Dict[str, Any] = {}

    if uid:
        data["user"] = {"uid": str(uid)}

    audio: Dict[str, Any] = {
        "url": str(audio_url),
        "format": str(audio_format),
    }
    if language:
        audio["language"] = str(language)
    data["audio"] = audio

    if resource:
        data["resource"] = str(resource)

    request: Dict[str, Any] = {
        "model_name": str(model_name),
    }
    if model_version:
        request["model_version"] = str(model_version)
    if enable_itn is not None:
        request["enable_itn"] = bool(enable_itn)
    if enable_punc:
        request["enable_punc"] = True
    if enable_ddc:
        request["enable_ddc"] = True
    if enable_speaker_info:
        request["enable_speaker_info"] = True
    if enable_channel_split:
        request["enable_channel_split"] = True
    if show_utterances:
        request["show_utterances"] = True
    if show_speech_rate:
        request["show_speech_rate"] = True
    if show_volume:
        request["show_volume"] = True
    if enable_lid:
        request["enable_lid"] = True
    if enable_emotion_detection:
        request["enable_emotion_detection"] = True
    if enable_gender_detection:
        request["enable_gender_detection"] = True
    if vad_segment:
        request["vad_segment"] = True
    if end_window_size is not None:
        request["end_window_size"] = int(end_window_size)
    if enable_denoise:
        request["enable_denoise"] = True
    if enable_multi_language is not None:
        request["enable_multi_language"] = bool(enable_multi_language)
    if sensitive_words_filter:
        # 文档中该字段类型为 String（通常为 JSON 字符串），这里原样透传。
        request["sensitive_words_filter"] = str(sensitive_words_filter)
    if corpus_context:
        request["corpus"] = {"context": str(corpus_context)}

    data["request"] = request

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

        if status in TASK_TERMINAL_OK:
            return result
        if status in TASK_TERMINAL_FAIL:
            raise RuntimeError(
                "任务失败: "
                f"status={status}, business_code={meta.get('business_code')}, "
                f"error_msg={meta.get('error_msg')}, request_id={meta.get('request_id')}"
            )

        if time.time() - start > timeout:
            raise TimeoutError(f"等待超时（{timeout}秒），任务仍未完成：{status}")
        time.sleep(interval)


def _write_json(path: str, data: Dict[str, Any]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _format_summary(result: Dict[str, Any]) -> str:
    meta = result.get("metadata", {})
    status = meta.get("task_status", "UNKNOWN")
    lines: List[str] = []
    lines.append("## ASR 任务")
    lines.append("")
    lines.append(f"task_id: {meta.get('task_id', 'unknown')}")
    lines.append(f"task_status: {status}")
    lines.append(f"business_code: {meta.get('business_code', 'unknown')}")
    if meta.get("error_msg"):
        lines.append(f"error_msg: {meta.get('error_msg')}")

    data = result.get("data") or {}
    if status == "COMPLETED" and isinstance(data, dict):
        audio_info = data.get("audio_info") or {}
        if isinstance(audio_info, dict) and audio_info.get("duration") is not None:
            lines.append(f"duration: {audio_info.get('duration')}ms")

        res = data.get("result") or {}
        if isinstance(res, dict):
            text = res.get("text")
            if isinstance(text, str) and text.strip():
                lines.append("")
                lines.append("---")
                lines.append("### text")
                lines.append(text.strip())

            utterances = res.get("utterances")
            if isinstance(utterances, list) and utterances:
                lines.append("")
                lines.append("### utterances (top 10)")
                for u in utterances[:10]:
                    if not isinstance(u, dict):
                        continue
                    st = u.get("start_time")
                    et = u.get("end_time")
                    t = (u.get("text") or "").strip()
                    add = u.get("additions") or {}
                    speaker = add.get("speaker") if isinstance(add, dict) else None
                    channel_id = add.get("channel_id") if isinstance(add, dict) else None
                    extra = []
                    if speaker:
                        extra.append(f"speaker={speaker}")
                    if channel_id:
                        extra.append(f"channel={channel_id}")
                    extra_s = (" | " + ", ".join(extra)) if extra else ""
                    lines.append(f"- {st}-{et}{extra_s}: {t}")
                if len(utterances) > 10:
                    lines.append(f"(仅展示前 10 条，共 {len(utterances)} 条)")

    return "\n".join(lines)


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--region",
        choices=sorted(REGION_TO_DOMAIN.keys()),
        help="operator region（也可用环境变量 LAS_REGION/REGION/region；默认 cn-beijing）",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="skill.py",
        description="LAS-ASR-PRO（las_asr_pro）CLI",
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

    p_submit = subparsers.add_parser("submit", help="提交转写任务（可选等待完成）")
    p_submit.add_argument("--audio-url", required=True, help="音频 URL（http/https 或 tos://bucket/key）")
    p_submit.add_argument(
        "--audio-format",
        required=True,
        help="音频容器格式（例如 wav/mp3/m4a/aac/flac；以服务端支持为准）",
    )
    p_submit.add_argument("--language", help="语种（不传则自动识别；例如 zh/en/ja/de 等）")
    p_submit.add_argument("--resource", choices=["bigasr", "seedasr"], help="资源池（默认 bigasr）")
    p_submit.add_argument("--uid", help="用户标识（可选）")

    p_submit.add_argument("--model-name", default="bigmodel", help="模型名称（文档目前为 bigmodel）")
    p_submit.add_argument("--model-version", help='模型版本（如 "400"；不传则默认 310）')

    itn_group = p_submit.add_mutually_exclusive_group()
    itn_group.add_argument("--enable-itn", action="store_true", help="开启 ITN（默认开启）")
    itn_group.add_argument("--disable-itn", action="store_true", help="关闭 ITN")

    multi_lang_group = p_submit.add_mutually_exclusive_group()
    multi_lang_group.add_argument("--enable-multi-language", action="store_true", help="开启多语种支持（默认开启）")
    multi_lang_group.add_argument("--disable-multi-language", action="store_true", help="关闭多语种支持")

    p_submit.add_argument("--enable-punc", action="store_true", help="开启标点（默认关闭）")
    p_submit.add_argument("--enable-ddc", action="store_true", help="开启语义顺滑（默认关闭）")
    p_submit.add_argument("--enable-speaker-info", action="store_true", help="开启说话人信息（默认关闭）")
    p_submit.add_argument("--enable-channel-split", action="store_true", help="开启双声道区分（默认关闭）")
    p_submit.add_argument("--show-utterances", action="store_true", help="输出分句/分词信息")
    p_submit.add_argument("--show-speech-rate", action="store_true", help="分句携带语速")
    p_submit.add_argument("--show-volume", action="store_true", help="分句携带音量")
    p_submit.add_argument("--enable-lid", action="store_true", help="启用语种识别")
    p_submit.add_argument("--enable-emotion-detection", action="store_true", help="启用情绪识别")
    p_submit.add_argument("--enable-gender-detection", action="store_true", help="启用性别识别")
    p_submit.add_argument("--vad-segment", action="store_true", help="使用 VAD 分句")
    p_submit.add_argument("--end-window-size", type=int, help="静音分句窗口（ms），建议 800/1000，范围 300-5000")
    p_submit.add_argument("--enable-denoise", action="store_true", help="开启降噪")

    p_submit.add_argument(
        "--sensitive-words-filter",
        help="敏感词过滤配置（文档字段为字符串，通常为 JSON 字符串；示例见 references/api.md）",
    )
    p_submit.add_argument(
        "--corpus-context",
        help="语料/热词/上下文（Corpus.context，字符串；如果是 JSON 需自行转义引号）",
    )

    p_submit.add_argument("--no-wait", action="store_true", help="只提交不等待")
    p_submit.add_argument("--dry-run", action="store_true", help="只打印请求体，不发请求")
    p_submit.add_argument("--timeout", type=int, default=1800, help="等待超时（秒）")
    p_submit.add_argument("--interval", type=int, default=5, help="轮询间隔（秒）")
    p_submit.add_argument("--out", help="保存原始 JSON 到文件")
    _add_common_args(p_submit)

    return parser


def main(argv: List[str]) -> None:
    # 兼容：未显式写子命令时，默认当作 submit
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
            enable_itn: Optional[bool] = None
            if args.enable_itn:
                enable_itn = True
            if args.disable_itn:
                enable_itn = False

            enable_multi_language: Optional[bool] = None
            if args.enable_multi_language:
                enable_multi_language = True
            if args.disable_multi_language:
                enable_multi_language = False

            print("正在提交转写任务...")
            result = submit_task(
                region=args.region,
                audio_url=str(args.audio_url),
                audio_format=str(args.audio_format),
                language=str(args.language) if args.language else None,
                resource=str(args.resource) if args.resource else None,
                uid=str(args.uid) if args.uid else None,
                model_name=str(args.model_name),
                model_version=str(args.model_version) if args.model_version else None,
                enable_itn=enable_itn,
                enable_punc=bool(args.enable_punc),
                enable_ddc=bool(args.enable_ddc),
                enable_speaker_info=bool(args.enable_speaker_info),
                enable_channel_split=bool(args.enable_channel_split),
                show_utterances=bool(args.show_utterances),
                show_speech_rate=bool(args.show_speech_rate),
                show_volume=bool(args.show_volume),
                enable_lid=bool(args.enable_lid),
                enable_emotion_detection=bool(args.enable_emotion_detection),
                enable_gender_detection=bool(args.enable_gender_detection),
                vad_segment=bool(args.vad_segment),
                end_window_size=int(args.end_window_size) if args.end_window_size is not None else None,
                enable_denoise=bool(args.enable_denoise),
                enable_multi_language=enable_multi_language,
                sensitive_words_filter=str(args.sensitive_words_filter) if args.sensitive_words_filter else None,
                corpus_context=str(args.corpus_context) if args.corpus_context else None,
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
