#!/usr/bin/env python3
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
导出服务：接收审核页 POST，将 sentences + baseTrack + mergedTrack 转为服务端格式，
写入 output/export_submit_<ts>.json，并调用 vod_direct_export.py 提交视频导出任务。
"""

from __future__ import annotations

import argparse
import errno
import json
import subprocess
import sys
import time
from pathlib import Path

# 加载 .env 环境变量（保证 EXECUTION_MODE 等配置可见）
try:
    from dotenv import load_dotenv as _load_dotenv

    _skill_dir_env = Path(__file__).resolve().parents[1]
    _env_path = _skill_dir_env / ".env"
    if _env_path.is_file():
        _load_dotenv(dotenv_path=_env_path, override=False)
except ImportError:
    pass
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

from apply_review_to_export import apply_review_to_export
from output_dir_resolve import infer_task_output_dir
from project_paths import get_project_root


_EXPORT_OUTPUT_DIR: Path | None = None


def _skip_subtitle_export() -> bool:
    """是否跳过字幕压制：默认跳过；设为 0/false/no 时启用"""
    v = (os.getenv("VOD_EXPORT_SKIP_SUBTITLE") or "").strip().lower()
    return v not in ("0", "false", "no")


def _should_video_cut() -> bool:
    """是否进行视频剪切：默认开启；设为 0/false/no 时关闭"""
    v = (os.getenv("TALKING_VIDEO_AUTO_EDIT_VIDEO_CUT") or "").strip().lower()
    return v not in ("0", "false", "no")


def _apply_env_track_processing(export_req: dict) -> dict:
    """
    根据环境变量处理 export_req 的 Track，与 prepare_export_data.py 行为对齐：
    - TALKING_VIDEO_AUTO_EDIT_VIDEO_CUT=0: 移除视频剪切（保留原始 trim）
    - VOD_EXPORT_SKIP_SUBTITLE 未设为 0: 移除 text lane（跳过字幕）
    """
    track = export_req.get("Track")
    if not track or not isinstance(track, list):
        return export_req

    # 字幕处理：如果跳过字幕，移除 text lane
    if _skip_subtitle_export():
        new_track = []
        for lane in track:
            if not isinstance(lane, list):
                new_track.append(lane)
                continue
            # 检查 lane 中是否全是 text 类型
            has_text = any(
                isinstance(el, dict) and (el.get("Type") or "").lower() == "text"
                for el in lane
            )
            has_non_text = any(
                isinstance(el, dict) and (el.get("Type") or "").lower() != "text"
                for el in lane
            )
            if has_text and not has_non_text:
                # 纯 text lane，跳过
                continue
            new_track.append(lane)
        export_req["Track"] = new_track

    # 视频剪切处理：如果关闭，保留原始结构（不做 realign）
    # 注意：realign 在 local_export 中调用，VOD 提交前不需要 realign
    # 此处主要确保 Track 结构完整性
    if not _should_video_cut():
        # 不做视频剪切时，移除 mute 段的 volume=0 标记恢复为正常音量
        for lane in export_req.get("Track", []):
            if not isinstance(lane, list):
                continue
            for el in lane:
                if not isinstance(el, dict):
                    continue
                for extra in el.get("Extra") or []:
                    if isinstance(extra, dict) and extra.get("Type") == "volume":
                        if extra.get("Volume", 1) == 0:
                            extra["Volume"] = 1

    return export_req


def _detect_local_mode() -> bool:
    """检测 local 模式（统一使用 execution_mode 模块）"""
    try:
        from execution_mode import detect_local_mode

        return detect_local_mode()
    except Exception:
        return os.getenv("EXECUTION_MODE", "").strip().lower() == "local"


def _output_dir() -> Path:
    if _EXPORT_OUTPUT_DIR is not None:
        _EXPORT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        return _EXPORT_OUTPUT_DIR
    out = get_project_root() / "output"
    out.mkdir(parents=True, exist_ok=True)
    return out


class ExportHandler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(204)
        self._cors_headers()
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in ("/export", "/", "/health"):
            self._send_json(
                200,
                {
                    "ok": True,
                    "message": "导出服务运行中，请使用 POST /export 提交导出任务",
                },
            )
            return
        self.send_error(404, "Not Found")

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != "/export" and parsed.path != "/":
            self.send_error(404, "Not Found")
            return

        content_length = int(self.headers.get("Content-Length", 0))
        if content_length <= 0:
            self.send_error(400, "Empty body")
            return

        body_bytes = self.rfile.read(content_length)
        try:
            body = json.loads(body_bytes.decode("utf-8"))
        except json.JSONDecodeError as e:
            self.send_error(400, f"Invalid JSON: {e}")
            return

        try:
            # 从原始 export_request.json 注入 Upload/Uploader（审核页前端不传这些字段）
            orig_export_path = _output_dir() / "export_request.json"
            if orig_export_path.exists():
                try:
                    _orig = json.loads(orig_export_path.read_text(encoding="utf-8"))
                    if "Upload" in _orig and "Upload" not in body:
                        body["_upload"] = _orig["Upload"]
                    if "Uploader" in _orig and "Uploader" not in body:
                        body["_uploader"] = _orig["Uploader"]
                    # 保留 Step6a 写入的 step6 指纹（用于导出防错）
                    if "_source_step6" in _orig and "_source_step6" not in body:
                        body["_source_step6"] = _orig.get("_source_step6")
                except Exception:
                    pass
            export_req = apply_review_to_export(body)

            # 根据环境变量处理 Track（与 prepare_export_data 行为对齐）
            export_req = _apply_env_track_processing(export_req)
            # 保留 step6 指纹
            if body.get("_source_step6"):
                export_req["_source_step6"] = body["_source_step6"]

            ts = int(time.time() * 1000)
            out_path = _output_dir() / f"export_submit_{ts}.json"
            _output_dir().mkdir(parents=True, exist_ok=True)
            out_path.write_text(
                json.dumps(export_req, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            # 检测 local 模式
            is_local = _detect_local_mode()

            if is_local:
                result = self._run_local_export(out_path)
            else:
                result = self._run_vod_export(out_path)
            self._send_json(200, result)
        except subprocess.TimeoutExpired:
            self._send_json(500, {"error": "导出任务超时（35分钟）"})
        except Exception as e:
            self._send_json(500, {"error": str(e)})

    def _run_local_export(self, out_path: Path) -> dict:
        """Local 模式：使用 ffmpeg 在本地合成（审核页导出用 export_reviewed.mp4 区分）"""
        from local_export import export_local

        output_file = export_local(
            out_path, _output_dir(), output_filename="export_reviewed.mp4"
        )
        return {
            "Status": "success",
            "OutputFile": str(output_file),
            "PlayURL": str(output_file),
            "_execution_mode": "local",
        }

    def _run_vod_export(self, out_path: Path) -> dict:
        """Cloud/APIG 模式：调用 vod_direct_export.py"""
        script_dir = Path(__file__).resolve().parent
        cmd = [sys.executable, str(script_dir / "vod_direct_export.py")]
        if _EXPORT_OUTPUT_DIR is not None:
            cmd.extend(["--output-dir", str(_EXPORT_OUTPUT_DIR)])
        cmd.extend(
            [
                "submit",
                "--edit-param",
                str(out_path),
                "--wait",
                "--json-output",
            ]
        )
        proc = subprocess.run(
            cmd,
            cwd=script_dir,
            capture_output=True,
            text=True,
            timeout=35 * 60,
        )
        if proc.returncode != 0:
            err = proc.stderr or proc.stdout or "未知错误"
            raise RuntimeError(f"vod_direct_export 失败: {err[:500]}")
        try:
            lines = [l.strip() for l in proc.stdout.strip().split("\n") if l.strip()]
            for line in reversed(lines):
                if line.startswith("{"):
                    return json.loads(line)
            return {"message": "任务已提交", "path": str(out_path)}
        except (json.JSONDecodeError, IndexError):
            return {
                "message": "任务已提交",
                "path": str(out_path),
                "stdout": proc.stdout[:500],
            }

    def _cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _send_json(self, status: int, data: dict):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self._cors_headers()
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        print(f"[export] {args[0]}")


def main() -> None:
    global _EXPORT_OUTPUT_DIR
    parser = argparse.ArgumentParser(
        description="导出服务：接收审核页 POST，写入 export_submit_*.json"
    )
    parser.add_argument("--port", type=int, default=7860, help="端口，默认 7860")
    parser.add_argument("--host", default="127.0.0.1", help="主机，默认 127.0.0.1")
    parser.add_argument(
        "--output-dir", default="", help="输出目录，默认 output；可指定 output/<文件名>"
    )
    args = parser.parse_args()

    if args.output_dir:
        out_str = str(args.output_dir).strip()
        proj_root = get_project_root()
        cand = Path(out_str)
        if cand.is_absolute():
            resolved = cand.resolve()
            _EXPORT_OUTPUT_DIR = resolved
        else:
            resolved = (proj_root / out_str).resolve()
            _EXPORT_OUTPUT_DIR = resolved
        _EXPORT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    else:
        _EXPORT_OUTPUT_DIR = infer_task_output_dir("")
        _EXPORT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    port = args.port
    for attempt in range(20):
        try:
            server = HTTPServer((args.host, port), ExportHandler)
            break
        except OSError as e:
            if getattr(
                e, "errno", None
            ) == errno.EADDRINUSE or "Address already in use" in str(e):
                port = args.port + attempt + 1
                if attempt < 19:
                    continue
            raise
    url = f"http://{args.host}:{port}"
    if port != args.port:
        print(f"[提示] 端口 {args.port} 已被占用，已使用 {port}")
    print(f"导出服务已启动: {url}/export")
    print(
        "审核页点击「提交视频导出任务」后，将保存数据并调用 vod_direct_export 导出视频"
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")


if __name__ == "__main__":
    main()
