#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) 2025 Beijing Volcano Engine Technology Co., Ltd. and/or its affiliates.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
口播剪辑导出：SubmitDirectEditTaskAsync + GetDirectEditResult

任务提交与查询，UploadInfo 结构（文档规范）：
- SpaceName: 必选，任务产物的上传空间
- VideoName: 可选，产物名称，需匹配 ^[\\p{Han}.() ()\\w\\s:-]+$，最大 2048 字节
- FileName: 可选，产物文件路径，如 Project/VideoFiles/123.mp4

使用：
  cd SKILL_DIR/scripts && source .venv/bin/activate && python vod_direct_export.py --output-dir <绝对路径> submit --wait
  cd SKILL_DIR/scripts && source .venv/bin/activate && python vod_direct_export.py --output-dir <绝对路径> query --req-id <ReqId> --wait

⚠️ --output-dir 必须在 submit/query 子命令之前，支持绝对路径。

完整示例：
  cd /path/to/byted-mediakit-voiceover-editing/scripts && source .venv/bin/activate && python vod_direct_export.py --output-dir /path/to/output/task_id submit --wait
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None


from project_paths import get_project_root


def _skill_dir() -> Path:
    return Path(__file__).resolve().parents[1]


_VOD_OUTPUT_DIR: Path | None = None


def _output_dir() -> Path:
    if _VOD_OUTPUT_DIR is not None:
        _VOD_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        return _VOD_OUTPUT_DIR
    return get_project_root() / "output"


def _load_env() -> None:
    if load_dotenv:
        load_dotenv(dotenv_path=_skill_dir() / ".env", override=False)


def _require_env(key: str) -> str:
    v = os.getenv(key)
    if not v:
        raise SystemExit(f"❌ 缺少环境变量 {key}，请在 .env 中配置")
    return v


# VideoName 规范：^[\p{Han}.() ()\w\s:-]+$，最大 2048 字节
_VIDEO_NAME_PATTERN = re.compile(
    r"^[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef.() \w\s:-]+$",
    re.UNICODE,
)


def _normalize_track_target_time(track: List[Any]) -> None:
    """修正无效 TargetTime（end<=start、浮点、负值），避免 VOD 21020004 TargetTime unvalid"""
    for lane in track or []:
        if not isinstance(lane, list):
            continue
        for el in lane or []:
            if not isinstance(el, dict):
                continue
            typ = (el.get("Type") or "").lower()
            if typ not in ("video", "audio"):
                continue
            tt = el.get("TargetTime")
            if not isinstance(tt, list) or len(tt) < 2:
                el["TargetTime"] = [0, 1]
                continue
            st = int(tt[0]) if tt[0] is not None else 0
            et = int(tt[1]) if tt[1] is not None else 0
            st = max(0, st)
            et = max(st + 1, et) if et <= st else max(0, et)
            el["TargetTime"] = [st, et]


def _normalize_track_trim(track: List[Any]) -> None:
    """修正无效 trim（StartTime >= EndTime），用 TargetTime 替代，避免 VOD invalid trim param"""
    for lane in track or []:
        if not isinstance(lane, list):
            continue
        for el in lane or []:
            if not isinstance(el, dict):
                continue
            typ = (el.get("Type") or "").lower()
            if typ not in ("video", "audio"):
                continue
            extra = el.get("Extra") or []
            target = el.get("TargetTime") or [0, 0]
            tt_end = int(target[1]) if len(target) > 1 else 0
            tt_start = int(target[0]) if target else 0
            for f in extra:
                if not f or f.get("Type") != "trim":
                    continue
                st, et = f.get("StartTime", 0), f.get("EndTime", 0)
                if et <= st:
                    f["StartTime"] = tt_start
                    f["EndTime"] = tt_end if tt_end > tt_start else tt_start + 1


def _normalize_track_source(track: List[Any]) -> None:
    """VOD 要求 DirectUrl 类型 Source 带 directurl:// 前缀，原地修正"""
    for lane in track or []:
        if not isinstance(lane, list):
            continue
        for el in lane or []:
            if not isinstance(el, dict):
                continue
            typ = (el.get("Type") or "").lower()
            if typ not in ("video", "audio"):
                continue
            src = el.get("Source", "")
            if not src or not isinstance(src, str):
                continue
            s = src.strip()
            if s.startswith(("vid://", "http://", "https://", "directurl://")):
                continue
            el["Source"] = f"directurl://{s}"


def _validate_upload_info(upload: Dict[str, Any]) -> Dict[str, Any]:
    """
    校验并构建 UploadInfo，符合文档规范：
    - SpaceName: 必选
    - VideoName: 可选，需符合正则，最大 2048 字节
    - FileName: 可选
    """
    space = (upload.get("SpaceName") or upload.get("Uploader") or "").strip()
    if not space:
        raise ValueError(
            "UploadInfo.SpaceName 为必选，请设置 SpaceName 或 VOLC_SPACE_NAME"
        )

    out = {"SpaceName": space}

    video_name = (upload.get("VideoName") or "").strip()
    if video_name:
        if len(video_name.encode("utf-8")) > 2048:
            raise ValueError("VideoName 最大 2048 字节")
        if not _VIDEO_NAME_PATTERN.match(video_name):
            raise ValueError(
                "VideoName 需匹配 ^[\\p{Han}.() ()\\w\\s:-]+$，"
                "仅支持中文、英文、数字、.()空格:- 等"
            )
        out["VideoName"] = video_name

    file_name = (upload.get("FileName") or "").strip()
    if file_name:
        out["FileName"] = file_name

    return out


def _read_json(path: str | Path) -> Any:
    p = Path(path).expanduser().resolve()
    if not p.is_file():
        raise SystemExit(f"❌ 文件不存在: {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def _calc_file_sha1(p: Path) -> str:
    return hashlib.sha1(p.read_bytes()).hexdigest()


def _maybe_guard_step6_mismatch(param_path: Path, data: Dict[str, Any]) -> None:
    """
    防止“改了 step6_speech_cut.json，但没重跑 Step6a 刷新 export_request.json”。
    规则：
    - 仅当 data 中存在 _source_step6 且同目录存在 step6_speech_cut.json 时启用
    - 若 step6 当前 sha1 与 _source_step6.sha1 不一致，则拒绝 submit
    """
    src = data.get("_source_step6")
    if not isinstance(src, dict):
        return
    step6_path = param_path.parent / "step6_speech_cut.json"
    if not step6_path.is_file():
        return
    old_sha1 = str(src.get("sha1") or "").strip()
    if not old_sha1:
        return
    new_sha1 = _calc_file_sha1(step6_path)
    if new_sha1 != old_sha1:
        old_mtime = src.get("mtime_ms")
        raise SystemExit(
            "❌ 检测到 step6_speech_cut.json 已更新，但 export_request.json 仍为旧版本。\n"
            f"- export_request: {param_path}\n"
            f"- step6: {step6_path}\n"
            f"- export_request._source_step6.mtime_ms: {old_mtime}\n"
            f"- export_request._source_step6.sha1: {old_sha1}\n"
            f"- step6 当前 sha1: {new_sha1}\n\n"
            "请先重新运行 Step6a 生成最新 export_request.json：\n"
            f'  cd {Path(__file__).resolve().parent} && python prepare_export_data.py --output-dir "{step6_path.parent}" \n'
        )


class VodEditClient:
    """SubmitDirectEditTaskAsync / GetDirectEditResult 客户端"""

    def __init__(self, host: str, region: str):
        from vod_transport import get_vod_transport_client, resolve_vod_transport

        if resolve_vod_transport() == "cloud":
            _require_env("VOLC_ACCESS_KEY_ID")
            _require_env("VOLC_ACCESS_KEY_SECRET")
        else:
            _require_env("ARK_SKILL_API_BASE")
            _require_env("ARK_SKILL_API_KEY")
        self._client = get_vod_transport_client()

    def post(self, action: str, version: str, body: Dict[str, Any]) -> Dict[str, Any]:
        resp = self._client.post(action=action, version=version, body=body)
        return json.loads(resp) if isinstance(resp, str) else (resp or {})

    def submit(
        self, body: Dict[str, Any], version: str = "2018-01-01"
    ) -> Dict[str, Any]:
        return self.post("SubmitDirectEditTaskAsync", version, body)

    def get_result(
        self, req_ids: List[str], version: str = "2018-01-01"
    ) -> Dict[str, Any]:
        return self.post("GetDirectEditResult", version, {"ReqIds": req_ids})


def _build_edit_param_from_export_request(
    data: Dict[str, Any],
    *,
    space_name: Optional[str] = None,
    video_name: Optional[str] = None,
    file_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    从 export_request.json 构建 EditParam。
    若 data 已含 Upload，则用 _validate_upload_info 校验；否则用传入参数补全。
    """
    track = data.get("Track")
    canvas = data.get("Canvas", {})
    if not track:
        raise ValueError("export_request 缺少 Track")

    # 提交前强制补全 directurl:// 前缀，避免 VOD failed_run (Unsupported source protocol)
    _normalize_track_source(track)
    # 修正无效 TargetTime，避免 VOD 21020004 TargetTime unvalid
    _normalize_track_target_time(track)
    # 修正无效 trim（StartTime >= EndTime），避免 VOD invalid trim param
    _normalize_track_trim(track)

    edit_param: Dict[str, Any] = {
        "Canvas": {
            "Width": canvas.get("Width", 1280),
            "Height": canvas.get("Height", 2160),
        },
        "Output": {
            "Alpha": False,
            "Codec": {
                "VideoCodec": "h264",
                "AudioCodec": "aac",
                "AudioBitrate": 128,
                "Crf": 23,
                "Preset": "slow",
            },
            "DisableAudio": False,
            "DisableVideo": False,
            "Fps": 30,
        },
        "Track": track,
    }

    upload_raw = data.get("Upload") or {}
    space = (
        space_name
        or upload_raw.get("SpaceName")
        or upload_raw.get("Uploader")
        or os.getenv("VOLC_SPACE_NAME")
    )
    video = video_name or upload_raw.get("VideoName", "口播剪辑")
    file = file_name or upload_raw.get("FileName")

    upload = {
        "SpaceName": space,
        "VideoName": video,
    }
    if file:
        upload["FileName"] = file
    edit_param["Upload"] = _validate_upload_info(upload)
    edit_param["Uploader"] = edit_param["Upload"]["SpaceName"]
    return edit_param


def _ensure_audio_track(track: List[Any]) -> List[Any]:
    """若 Track 无 audio 轨，从 video 轨镜像生成 audio，避免合成无声"""
    for lane in track:
        if not isinstance(lane, list):
            continue
        for el in lane or []:
            if isinstance(el, dict) and (el.get("Type") or "").lower() == "audio":
                return track

    audio_elems: List[Dict] = []
    for lane in track:
        if not isinstance(lane, list):
            continue
        for el in lane or []:
            if not isinstance(el, dict) or (el.get("Type") or "").lower() != "video":
                continue
            src = el.get("Source")
            tt = el.get("TargetTime")
            if not src or not (isinstance(tt, list) and len(tt) == 2):
                continue
            extra = el.get("Extra") or []
            trim = next(
                (x for x in extra if isinstance(x, dict) and x.get("Type") == "trim"),
                None,
            )
            ae: Dict[str, Any] = {"Type": "audio", "Source": src, "TargetTime": tt}
            if trim:
                ae["Extra"] = [
                    {
                        "Type": "trim",
                        "StartTime": trim.get("StartTime"),
                        "EndTime": trim.get("EndTime"),
                    }
                ]
            audio_elems.append(ae)
    if not audio_elems:
        return track
    out = json.loads(json.dumps(track, ensure_ascii=False))
    out.append(audio_elems)
    return out


def _detect_local_mode() -> bool:
    """检测 local 模式（统一使用 execution_mode 模块）"""
    try:
        from execution_mode import detect_local_mode

        return detect_local_mode()
    except Exception:
        return os.getenv("EXECUTION_MODE", "").strip().lower() == "local"


def cmd_submit(args: argparse.Namespace) -> None:
    """提交导出任务"""
    _load_env()

    param_path = args.edit_param or str(_output_dir() / "export_request.json")
    param_p = Path(param_path).expanduser().resolve()
    data = _read_json(param_p)

    if not isinstance(data, dict) or "Track" not in data:
        raise SystemExit("❌ 输入须为包含 Track 的 EditParam/export_request JSON")

    # 防错：step6 更新但 export_request 未刷新时拒绝提交
    _maybe_guard_step6_mismatch(param_p, data)

    # Local 模式：使用 ffmpeg 在本地合成，无需 VOD 服务
    if _detect_local_mode():
        print("【local】使用本地 ffmpeg 导出视频...")
        from local_export import export_local

        output_file = export_local(param_p, _output_dir())
        result = {
            "Status": "success",
            "OutputFile": str(output_file),
            "PlayURL": str(output_file),
            "_execution_mode": "local",
        }
        _output_dir().mkdir(parents=True, exist_ok=True)
        submit_path = _output_dir() / "export_submit.json"
        submit_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        json_output = getattr(args, "json_output", False)
        if json_output:
            print(json.dumps(result, ensure_ascii=False))
        else:
            print(f"✅ 本地导出完成: {output_file}")
        return

    host = os.getenv("VOLC_HOST", "vod.volcengineapi.com")
    region = os.getenv("VOLC_REGION", "cn-north-1")

    edit_param = _build_edit_param_from_export_request(
        data,
        space_name=args.space_name,
        video_name=args.video_name,
        file_name=args.file_name,
    )
    if args.ensure_audio:
        edit_param["Track"] = _ensure_audio_track(edit_param["Track"])

    client = VodEditClient(host=host, region=region)
    body = {
        "Application": args.application,
        "CallbackArgs": args.callback_args or "",
        "Uploader": edit_param["Upload"]["SpaceName"],
        "EditParam": edit_param,
    }

    resp = client.submit(body, version=args.version)
    result = resp.get("Result") or {}
    req_id = result.get("ReqId")
    if not req_id:
        raise SystemExit(
            f"❌ 未返回 ReqId，响应: {json.dumps(resp, ensure_ascii=False, indent=2)}"
        )

    _output_dir().mkdir(parents=True, exist_ok=True)
    submit_record = {
        "ReqId": req_id,
        "EditParamPath": param_path,
        "Body": body,
        "Response": resp,
    }
    submit_path = _output_dir() / "export_submit.json"
    submit_path.write_text(
        json.dumps(submit_record, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if not getattr(args, "json_output", False):
        print("[OK] 已记录提交参数至 output/export_submit.json")

    json_output = getattr(args, "json_output", False)
    if not json_output:
        print(f"✅ 任务已提交 ReqId: {req_id}")
    if args.wait:
        _poll_and_print(client, req_id, args, json_output=json_output)
    elif not json_output:
        print("提示: 使用 query 子命令查询结果，或加上 --wait 等待完成")


def _fetch_play_url(output_vid: str, req_id: str) -> Optional[str]:
    """OutputVid 成功后获取播放地址，失败返回 None"""
    space = os.getenv("VOLC_SPACE_NAME", "").strip()
    if not space:
        print("[提示] 未设置 VOLC_SPACE_NAME，无法获取播放地址")
        return None
    try:
        from api_manage import ApiManage

        api = ApiManage()
        url = api.get_play_url(type="vid", source=output_vid, space_name=space)
        return url or None
    except Exception as e:
        print(f"[警告] 获取播放地址失败: {e}")
        return None


def _poll_and_print(
    client: VodEditClient,
    req_id: str,
    args: argparse.Namespace,
    *,
    json_output: bool = False,
) -> None:
    interval = args.poll_interval
    timeout = args.timeout
    start = time.time()
    last = None
    while True:
        data = client.get_result([req_id], version=args.version)
        items = data.get("Result") or []
        item = items[0] if items else {}
        status = item.get("Status")
        if status and status != last:
            last = status
            if not json_output:
                print(f"⏳ 状态: {status}")
        if status in ("success", "failed_run", "user_canceled"):
            if not json_output:
                print("✅ 最终结果:", json.dumps(item, ensure_ascii=False, indent=2))
            play_url = ""
            if status == "success" and item.get("OutputVid"):
                output_vid = item["OutputVid"]
                play_url = _fetch_play_url(output_vid, req_id) or ""
                if not json_output:
                    print(f"🎬 OutputVid: {output_vid}")
                    if play_url:
                        print(f"🔗 PlayURL: {play_url}")
                out_data = {
                    "ReqId": req_id,
                    "OutputVid": output_vid,
                    "PlayURL": play_url,
                }
                out_path = _output_dir() / "export_play_url.json"
                out_path.write_text(
                    json.dumps(out_data, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                if not json_output:
                    print("[OK] 已保存至 output/export_play_url.json")
            if json_output:
                result = {
                    "ReqId": req_id,
                    "Status": status,
                    "OutputVid": item.get("OutputVid", ""),
                    "PlayURL": play_url,
                }
                if status == "failed_run" and item.get("Message"):
                    result["Message"] = item.get("Message")
                print(json.dumps(result, ensure_ascii=False))
            return
        if time.time() - start > timeout:
            if json_output:
                print(
                    json.dumps(
                        {"error": f"超时 {timeout}s", "ReqId": req_id},
                        ensure_ascii=False,
                    )
                )
            else:
                raise TimeoutError(f"超时 {timeout}s，ReqId={req_id}")
            return
        time.sleep(interval)


def cmd_query(args: argparse.Namespace) -> None:
    """查询导出任务结果"""
    _load_env()
    host = os.getenv("VOLC_HOST", "vod.volcengineapi.com")
    region = os.getenv("VOLC_REGION", "cn-north-1")
    client = VodEditClient(host=host, region=region)

    if args.wait:
        _poll_and_print(client, args.req_id, args)
    else:
        data = client.get_result([args.req_id], version=args.version)
        items = data.get("Result") or []
        item = items[0] if items else {}
        print(json.dumps(item, ensure_ascii=False, indent=2))
        if item.get("Status") == "success" and item.get("OutputVid"):
            output_vid = item["OutputVid"]
            print(f"\n🎬 OutputVid: {output_vid}")
            play_url = _fetch_play_url(output_vid, args.req_id)
            if play_url:
                print(f"🔗 PlayURL: {play_url}")
                out_data = {
                    "ReqId": args.req_id,
                    "OutputVid": output_vid,
                    "PlayURL": play_url,
                }
                out_path = _output_dir() / "export_play_url.json"
                out_path.write_text(
                    json.dumps(out_data, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                print("[OK] 已保存至 output/export_play_url.json")


def main() -> None:
    global _VOD_OUTPUT_DIR
    parser = argparse.ArgumentParser(
        description="口播剪辑导出：SubmitDirectEditTaskAsync / GetDirectEditResult",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--output-dir", default="", help="输出目录，默认 output；可指定 output/<文件名>"
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    # submit
    p_submit = sub.add_parser("submit", help="提交导出任务")
    p_submit.add_argument(
        "--edit-param",
        help="EditParam/export_request JSON 路径，默认 output/export_request.json",
    )
    p_submit.add_argument("--space-name", help="UploadInfo.SpaceName，覆盖 JSON 内值")
    p_submit.add_argument(
        "--video-name", default="口播剪辑", help="UploadInfo.VideoName"
    )
    p_submit.add_argument(
        "--file-name", help="UploadInfo.FileName，如 Project/VideoFiles/xxx.mp4"
    )
    p_submit.add_argument("--application", default="VideoTrackToB")
    p_submit.add_argument("--callback-args", default="")
    p_submit.add_argument(
        "--ensure-audio",
        action="store_true",
        default=True,
        help="无 audio 轨时从 video 镜像",
    )
    p_submit.add_argument("--version", default="2018-01-01")
    p_submit.add_argument("--wait", action="store_true", help="提交后轮询直到完成")
    p_submit.add_argument(
        "--json-output",
        action="store_true",
        help="输出 JSON 结果（供 export_server 调用）",
    )
    p_submit.add_argument("--poll-interval", type=float, default=3.0)
    p_submit.add_argument("--timeout", type=float, default=30 * 60)
    p_submit.set_defaults(func=cmd_submit)

    # query
    p_query = sub.add_parser("query", help="查询任务结果")
    p_query.add_argument(
        "--req-id", required=True, help="SubmitDirectEditTaskAsync 返回的 ReqId"
    )
    p_query.add_argument("--version", default="2018-01-01")
    p_query.add_argument("--wait", action="store_true", help="轮询直到完成")
    p_query.add_argument("--poll-interval", type=float, default=3.0)
    p_query.add_argument("--timeout", type=float, default=30 * 60)
    p_query.set_defaults(func=cmd_query)

    args = parser.parse_args()
    out_override = str(getattr(args, "output_dir", "") or "").strip()
    if not out_override and args.cmd == "submit":
        ep = getattr(args, "edit_param", None) or ""
        if ep:
            ep_path = Path(ep).expanduser()
            if ep_path.is_file():
                proj_root = get_project_root()
                out_base = (proj_root / "output").resolve()
                try:
                    ep_path.resolve().relative_to(out_base)
                    out_override = str(ep_path.parent.resolve())
                except ValueError:
                    pass

    if out_override:
        out_str = out_override
        proj_root = get_project_root()
        out_base = (proj_root / "output").resolve()
        cand = Path(out_str)

        if cand.is_absolute():
            resolved = cand.resolve()
            _VOD_OUTPUT_DIR = resolved
        else:
            resolved = (proj_root / out_str).resolve()
            _VOD_OUTPUT_DIR = resolved

        _VOD_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    else:
        _VOD_OUTPUT_DIR = None
    try:
        args.func(args)
    except KeyboardInterrupt:
        print("\n已取消")
        sys.exit(130)


if __name__ == "__main__":
    main()
