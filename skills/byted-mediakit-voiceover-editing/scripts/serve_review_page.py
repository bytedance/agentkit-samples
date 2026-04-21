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
审核页静态服务：托管 templates/review-page/，提供 GET /api/review-data 返回 review_import_data.json，
POST /export 代理到导出服务（避免 501），POST /api/save-review 持久化审核修改。
是否自动打开浏览器由环境变量 TALKING_VIDEO_AUTO_EDIT_REVIEW_AUTO_OPEN 决定：默认不打开；1/true/yes 时打开。
"""

from __future__ import annotations

import argparse
import errno
import json
import mimetypes
import os
import sys
import threading
import time
from urllib.parse import urlparse, unquote
import webbrowser
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler

from output_dir_resolve import infer_task_output_dir, review_import_data_path

# 加载 skill .env（override=False：进程环境优先，与容器注入 ARK_SKILL_* 等一致）
try:
    from dotenv import load_dotenv

    skill_dir = Path(__file__).resolve().parents[1]
    env_path = skill_dir / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path, override=False)
except Exception:
    pass


def _should_auto_open_browser() -> bool:
    """默认不打开；仅当 TALKING_VIDEO_AUTO_EDIT_REVIEW_AUTO_OPEN=1/true/yes 时打开"""
    v = (os.getenv("TALKING_VIDEO_AUTO_EDIT_REVIEW_AUTO_OPEN") or "").strip().lower()
    return v in ("1", "true", "yes")


def _detect_local_mode(output_dir: Path) -> bool:
    """统一检测 local 模式（使用 execution_mode 模块）"""
    try:
        from execution_mode import detect_local_mode

        return detect_local_mode()
    except Exception:
        return os.getenv("EXECUTION_MODE", "").strip().lower() == "local"


def _detect_execution_mode_str() -> str:
    """返回当前执行模式字符串: 'apig' | 'cloud' | 'local'"""
    try:
        from execution_mode import detect_execution_mode

        return detect_execution_mode().value
    except Exception:
        return os.getenv("EXECUTION_MODE", "").strip().lower() or "cloud"


def _validate_script_dir() -> Path:
    """校验脚本运行目录，拒绝从回收站、临时目录等异常位置启动。"""
    script_path = Path(__file__).resolve()
    script_dir = script_path.parent
    bad_markers = [".Trash", "__MACOSX", "/tmp/"]
    for marker in bad_markers:
        if marker in str(script_dir):
            raise SystemExit(
                f"ERROR: 审核页服务正在从异常目录运行，请确认使用正确的代码副本。\n"
                f"  当前路径: {script_dir}\n"
                f"  匹配异常标记: {marker}"
            )
    return script_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="审核页静态服务")
    parser.add_argument("--port", type=int, default=5173, help="端口，默认 5173")
    parser.add_argument("--host", default="127.0.0.1", help="主机，默认 127.0.0.1")
    parser.add_argument(
        "--output-dir", default="", help="输出目录，默认 output；可指定 output/<文件名>"
    )
    parser.add_argument(
        "--export-server",
        default="http://127.0.0.1:7860",
        help="导出服务地址，POST /export 将代理到此地址",
    )
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="不自动打开浏览器（覆盖环境变量 TALKING_VIDEO_AUTO_EDIT_REVIEW_AUTO_OPEN）",
    )
    args = parser.parse_args()

    script_dir = _validate_script_dir()
    skill_dir = script_dir.parent
    template_dir = skill_dir / "templates" / "review-page"
    if not template_dir.exists():
        raise FileNotFoundError(f"审核页目录不存在: {template_dir}")

    class CustomHandler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(template_dir), **kwargs)

        @staticmethod
        def _request_path(path: str) -> str:
            """self.path 可能带查询串或片段，仅取 path 段做路由。"""
            p = urlparse(path).path or "/"
            if len(p) > 1 and p.endswith("/"):
                p = p.rstrip("/")
            return p

        def do_OPTIONS(self):
            req_path = self._request_path(self.path)
            out_dir = infer_task_output_dir(args.output_dir)
            if req_path == "/export" and not _detect_local_mode(out_dir):
                self._proxy_export("OPTIONS")
                return
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Range")
            self.end_headers()

        def do_GET(self):
            req_path = self._request_path(self.path)
            if req_path == "/api/review-data":
                self._serve_review_data()
                return
            if req_path == "/api/mode":
                self._serve_mode()
                return
            if req_path.startswith("/local-media/"):
                self._serve_local_media(req_path)
                return
            if req_path == "/export":
                self._send_json(
                    200,
                    {
                        "ok": True,
                        "message": "导出接口需使用 POST 提交。请在审核页点击「提交视频导出任务」按钮。",
                    },
                )
                return
            super().do_GET()

        def do_POST(self):
            req_path = self._request_path(self.path)
            if req_path == "/export":
                out_dir = infer_task_output_dir(args.output_dir)
                if _detect_local_mode(out_dir):
                    self._handle_local_export(out_dir)
                else:
                    self._handle_cloud_export(out_dir)
                return
            if req_path == "/api/save-review":
                out_dir = infer_task_output_dir(args.output_dir)
                self._handle_save_review(out_dir)
                return
            self.send_error(501, "Unsupported method (%r)" % self.command)

        # ─── 保存审核修改 ───────────────────────────────────
        def _handle_save_review(self, out_dir: Path):
            """持久化审核修改：回写 review_import_data.json + 重新生成 export_request.json"""
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length <= 0:
                self._send_json(400, {"error": "Empty body"})
                return
            try:
                body = json.loads(self.rfile.read(content_length).decode("utf-8"))
            except json.JSONDecodeError as e:
                self._send_json(400, {"error": f"Invalid JSON: {e}"})
                return

            try:
                out_dir.mkdir(parents=True, exist_ok=True)
                updated_files = []

                # 1. 回写 review_import_data.json
                review_path = review_import_data_path(args.output_dir)
                if review_path.exists():
                    old_review = json.loads(review_path.read_text(encoding="utf-8"))
                else:
                    old_review = {}

                if body.get("sentences"):
                    old_review["sentences"] = body["sentences"]
                if body.get("baseTrack"):
                    old_review["track"] = body["baseTrack"]
                if body.get("canvas"):
                    old_review["canvas"] = body["canvas"]
                if body.get("_execution_mode"):
                    old_review["_execution_mode"] = body["_execution_mode"]

                review_path.write_text(
                    json.dumps(old_review, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                updated_files.append(str(review_path.name))
                print(f"[save-review] 已更新 {review_path}")

                # 2. 重新生成 export_request.json（从 mergedTrack 转换）
                try:
                    from apply_review_to_export import apply_review_to_export

                    export_path = out_dir / "export_request.json"
                    # 保留原始 export_request 中的 Upload/Uploader（直接导出所需）
                    if export_path.exists():
                        try:
                            _old_export = json.loads(
                                export_path.read_text(encoding="utf-8")
                            )
                            if (
                                "Upload" in _old_export
                                and "Upload" not in body
                                and "_upload" not in body
                            ):
                                body["_upload"] = _old_export["Upload"]
                            if (
                                "Uploader" in _old_export
                                and "Uploader" not in body
                                and "_uploader" not in body
                            ):
                                body["_uploader"] = _old_export["Uploader"]
                            # 保留 Step6a 写入的 step6 指纹（用于导出防错）
                            if (
                                "_source_step6" in _old_export
                                and "_source_step6" not in body
                            ):
                                body["_source_step6"] = _old_export.get("_source_step6")
                        except Exception:
                            pass
                    export_req = apply_review_to_export(body)
                    # 保留 _execution_mode
                    if body.get("_execution_mode"):
                        export_req["_execution_mode"] = body["_execution_mode"]
                    # 保留 step6 指纹
                    if body.get("_source_step6"):
                        export_req["_source_step6"] = body["_source_step6"]
                    export_path.write_text(
                        json.dumps(export_req, ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )
                    updated_files.append("export_request.json")
                    print(f"[save-review] 已更新 {export_path}")
                except Exception as e:
                    print(f"[save-review] 警告: export_request.json 更新失败: {e}")

                self._send_json(
                    200,
                    {
                        "status": "saved",
                        "updated": updated_files,
                    },
                )
            except Exception as e:
                import traceback

                traceback.print_exc()
                self._send_json(500, {"error": f"保存失败: {e}"})

        def _serve_mode(self):
            """返回当前执行模式"""
            mode = _detect_execution_mode_str()
            self._send_json(200, {"mode": mode})

        def _handle_local_export(self, out_dir: Path):
            """Local 模式：直接在本进程内完成导出，无需 export_server"""
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length <= 0:
                self._send_json(400, {"error": "Empty body"})
                return
            try:
                body = json.loads(self.rfile.read(content_length).decode("utf-8"))
            except json.JSONDecodeError as e:
                self._send_json(400, {"error": f"Invalid JSON: {e}"})
                return
            try:
                from apply_review_to_export import apply_review_to_export
                from local_export import export_local

                export_req = apply_review_to_export(body)
                ts = int(time.time() * 1000)
                req_path = out_dir / f"export_submit_{ts}.json"
                out_dir.mkdir(parents=True, exist_ok=True)
                req_path.write_text(
                    json.dumps(export_req, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                print(f"[local] 导出请求已保存: {req_path}")

                output_file = export_local(req_path, out_dir)
                self._send_json(
                    200,
                    {
                        "Status": "success",
                        "OutputFile": str(output_file),
                        "PlayURL": str(output_file),
                        "_execution_mode": "local",
                    },
                )
            except Exception as e:
                import traceback

                traceback.print_exc()
                self._send_json(500, {"error": f"导出失败: {e}"})

        def _handle_cloud_export(self, out_dir: Path):
            """APIG/Cloud 模式：直接在本进程内生成 export_submit 并调用 vod_direct_export"""
            import subprocess as _sp

            content_length = int(self.headers.get("Content-Length", 0))
            if content_length <= 0:
                self._send_json(400, {"error": "Empty body"})
                return
            try:
                body = json.loads(self.rfile.read(content_length).decode("utf-8"))
            except json.JSONDecodeError as e:
                self._send_json(400, {"error": f"Invalid JSON: {e}"})
                return
            try:
                from apply_review_to_export import apply_review_to_export

                export_req = apply_review_to_export(body)
                ts = int(time.time() * 1000)
                req_path = out_dir / f"export_submit_{ts}.json"
                out_dir.mkdir(parents=True, exist_ok=True)
                req_path.write_text(
                    json.dumps(export_req, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                print(f"[cloud/apig] 导出请求已保存: {req_path}")

                script_dir = Path(__file__).resolve().parent
                cmd = [sys.executable, str(script_dir / "vod_direct_export.py")]
                cmd.extend(
                    [
                        "--output-dir",
                        str(out_dir),
                        "submit",
                        "--edit-param",
                        str(req_path),
                        "--wait",
                        "--json-output",
                    ]
                )
                proc = _sp.run(
                    cmd,
                    cwd=script_dir,
                    capture_output=True,
                    text=True,
                    timeout=35 * 60,
                )
                if proc.returncode != 0:
                    err = proc.stderr or proc.stdout or "未知错误"
                    raise RuntimeError(f"vod_direct_export 失败: {err[:500]}")

                lines = [
                    l.strip() for l in proc.stdout.strip().split("\n") if l.strip()
                ]
                result = {"message": "任务已提交", "path": str(req_path)}
                for line in reversed(lines):
                    if line.startswith("{"):
                        result = json.loads(line)
                        break
                self._send_json(200, result)
            except _sp.TimeoutExpired:
                self._send_json(500, {"error": "导出任务超时（35分钟）"})
            except Exception as e:
                import traceback

                traceback.print_exc()
                self._send_json(500, {"error": f"导出失败: {e}"})

        def _send_json(self, status: int, data: dict):
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _serve_local_media(self, req_path: str):
            """服务本地媒体文件，路径格式: /local-media/<绝对路径>"""
            raw = unquote(req_path[len("/local-media") :])
            if not raw.startswith("/"):
                self.send_error(400, "路径必须为绝对路径")
                return
            file_path = Path(raw)
            if not file_path.is_file():
                self.send_error(404, f"文件不存在: {raw}")
                return

            content_type, _ = mimetypes.guess_type(str(file_path))
            if not content_type:
                content_type = "application/octet-stream"

            file_size = file_path.stat().st_size
            range_header = self.headers.get("Range")

            if range_header:
                try:
                    range_spec = range_header.strip().replace("bytes=", "")
                    start_str, end_str = range_spec.split("-", 1)
                    start = int(start_str) if start_str else 0
                    end = int(end_str) if end_str else file_size - 1
                    end = min(end, file_size - 1)
                    length = end - start + 1

                    self.send_response(206)
                    self.send_header("Content-Type", content_type)
                    self.send_header(
                        "Content-Range", f"bytes {start}-{end}/{file_size}"
                    )
                    self.send_header("Content-Length", str(length))
                    self.send_header("Accept-Ranges", "bytes")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()

                    with open(file_path, "rb") as f:
                        f.seek(start)
                        remaining = length
                        while remaining > 0:
                            chunk = f.read(min(65536, remaining))
                            if not chunk:
                                break
                            self.wfile.write(chunk)
                            remaining -= len(chunk)
                except Exception:
                    self.send_error(416, "Range Not Satisfiable")
            else:
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(file_size))
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                with open(file_path, "rb") as f:
                    while True:
                        chunk = f.read(65536)
                        if not chunk:
                            break
                        self.wfile.write(chunk)

        def _serve_review_data(self):
            path = review_import_data_path(args.output_dir)
            if not path.exists():
                self.send_error(
                    404,
                    "review_import_data.json 未生成，请先运行 prepare_export_data.py",
                )
                return
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                body = json.dumps(data, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except Exception as e:
                self.send_error(500, str(e))

        def log_message(self, format, *args):
            print(f"[serve] {args[0]}")

    port = args.port
    for attempt in range(20):
        try:
            server = HTTPServer((args.host, port), CustomHandler)
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
    mode_str = _detect_execution_mode_str()
    if port != args.port:
        print(f"[提示] 端口 {args.port} 已被占用，已使用 {port}")
    print(f"审核页服务已启动: {url}")
    print(f"  当前模式: {mode_str}")
    print(f"  脚本路径: {Path(__file__).resolve()}")
    print(f"  - 审核页: {url}/")
    print(f"  - 数据 API: {url}/api/review-data")
    print(f"  - 模式 API: {url}/api/mode")
    print(f"  - 保存审核: POST {url}/api/save-review")
    inferred_dir = infer_task_output_dir(args.output_dir)
    print(f"  - 输出目录: {inferred_dir}")
    if mode_str == "local":
        print("  - 导出: 内置（local 模式，ffmpeg 本地合成）")
    else:
        print(f"  - 导出: 内置（{mode_str} 模式，调用 vod_direct_export）")

    if not args.no_open and _should_auto_open_browser():

        def _open_later():
            import time

            time.sleep(1.2)
            webbrowser.open(url)
            print("[提示] 已自动打开审核页")

        threading.Thread(target=_open_later, daemon=True).start()
    else:
        print(
            "[提示] 未自动打开（TALKING_VIDEO_AUTO_EDIT_REVIEW_AUTO_OPEN=0 或 --no-open），请手动访问上述 URL"
        )

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")


if __name__ == "__main__":
    main()
