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
upload_media.py — 上传媒资到 VOD，返回 Vid

支持两种输入：
  1) 本地文件路径：直接上传（同步返回 Vid）
  2) http/https 链接：URL 拉取上传（异步），轮询 QueryUploadTaskInfo 直到返回 Vid

用法:
  python <SKILL_DIR>/scripts/upload_media.py "<local_file_path_or_http_url>" [space_name]

输出:
  {"Vid":"vxxxx","Source":"vid://vxxxx","PosterUri":"...","FileName":"...","SpaceName":"..."}
"""

import os
import sys
import time
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from api_manage import ApiManage
from vod_common import get_space_name, out, bail, log, POLL_INTERVAL, POLL_MAX


# ══════════════════════════════════════════════════════
# 安全：本地文件路径白名单
# ══════════════════════════════════════════════════════

_ALLOWED_PATH_PREFIXES = None


def _get_allowed_prefixes():
    global _ALLOWED_PATH_PREFIXES
    if _ALLOWED_PATH_PREFIXES is None:
        prefixes = []
        ws = os.environ.get("WORKSPACE", os.getcwd())
        prefixes.append(os.path.realpath(ws))
        ud = os.path.join(os.path.dirname(ws), "userdata") if ws else ""
        if ud:
            prefixes.append(os.path.realpath(ud))
        prefixes.append("/tmp")
        _ALLOWED_PATH_PREFIXES = prefixes
    return _ALLOWED_PATH_PREFIXES


def _validate_local_path(file_path: str):
    """校验本地文件路径是否在允许的目录范围内。"""
    real = os.path.realpath(file_path)
    for prefix in _get_allowed_prefixes():
        if real.startswith(prefix + os.sep) or real == prefix:
            return
    bail(
        f"安全限制：只允许上传 workspace/、userdata/ 或 /tmp 下的文件。"
        f"拒绝路径：{file_path}"
    )


def _guess_ext_from_path(path: str) -> str:
    _, ext = os.path.splitext(path or "")
    ext = (ext or "").strip()
    if not ext:
        bail("上传文件必须携带文件后缀（例如 .mp4 / .mp3）")
    if not ext.startswith("."):
        ext = "." + ext
    return ext


def _is_http_url(s: str) -> bool:
    s = (s or "").strip().lower()
    return s.startswith("http://") or s.startswith("https://")


def _poll_url_upload(api: ApiManage, job_ids: str) -> dict:
    """
    轮询 QueryUploadTaskInfo 直到成功/失败/超时。
    """
    if not job_ids:
        bail("URL 上传未返回 JobId")

    last_state = ""
    for i in range(1, POLL_MAX + 1):
        log(f"轮询 URL 上传任务 [{i}/{POLL_MAX}] JobIds={job_ids}")
        try:
            result = api.query_batch_upload_task_info(job_ids)
        except Exception as e:
            log(f"  查询异常: {e}")
            time.sleep(POLL_INTERVAL)
            continue

        urls = result.get("Urls", [])
        if not urls:
            time.sleep(POLL_INTERVAL)
            continue

        info = urls[0]
        state = info.get("State", "")
        last_state = state or last_state
        vid = info.get("Vid", "")

        # 成功：拿到 Vid 即可返回
        if vid:
            return info

        # 失败
        state_l = state.lower()
        if state_l in {"fail", "failed", "error"}:
            bail(f"URL 拉取上传失败：State={state!r} JobIds={job_ids}")

        time.sleep(POLL_INTERVAL)

    return {
        "error": f"轮询超时（{POLL_MAX} 次 × {POLL_INTERVAL}s），URL 拉取上传仍在处理中",
        "resume_hint": {
            "description": "URL 上传尚未完成，可用以下命令重试",
            "command": 'python <SKILL_DIR>/scripts/upload_media.py "<http_url>" [space_name]',
        },
        "JobIds": job_ids,
        "State": last_state,
    }


def main():
    if len(sys.argv) < 2:
        bail(
            '用法: python <SKILL_DIR>/scripts/upload_media.py "<local_file_path_or_http_url>" [space_name]'
        )

    src = sys.argv[1].strip()
    api = ApiManage()
    sp = get_space_name(argv_pos=2)

    if _is_http_url(src):
        # ── URL 上传 ──────────────────────────────────────
        ext = _guess_ext_from_path(urlparse(src).path)
        try:
            resp = api.upload_media_auto(src, sp, file_ext=ext)
        except Exception as e:
            bail(f"URL 上传提交失败: {e}")

        if resp.get("type") == "url":
            job_ids = resp.get("JobIds", [])
            if not job_ids:
                bail("URL 上传提交成功但未返回 JobId")
            job_id_str = ",".join(job_ids)

            info = _poll_url_upload(api, job_id_str)
            if "error" in info:
                out(info)
                return

            vid = info.get("Vid", "")
            if not vid:
                bail(f"URL 上传已完成但未返回 Vid：JobIds={job_id_str}")

            file_name = info.get("DirectUrl", "")
            out(
                {
                    "Vid": vid,
                    "Source": f"vid://{vid}",
                    "PosterUri": "",
                    "FileName": file_name,
                    "SpaceName": sp,
                    "SourceUrl": src,
                    "JobId": job_id_str,
                }
            )
        else:
            # upload_media_auto 对 URL 应返回 type=url，防御性处理
            vid = resp.get("Vid", "")
            out(
                {
                    "Vid": vid,
                    "Source": f"vid://{vid}" if vid else "",
                    "PosterUri": resp.get("PosterUri", ""),
                    "FileName": resp.get("DirectUrl", ""),
                    "SpaceName": sp,
                    "SourceUrl": src,
                }
            )
        return

    # ── 本地文件上传 ──────────────────────────────────
    file_path = src
    _validate_local_path(file_path)
    if not os.path.isfile(file_path):
        bail(f"本地文件不存在：{file_path}")

    ext = _guess_ext_from_path(file_path)
    try:
        resp = api.upload_media_auto(file_path, sp, file_ext=ext)
    except Exception as e:
        bail(f"本地文件上传失败: {e}")

    vid = resp.get("Vid", "")
    if not vid:
        bail("上传成功但未返回 Vid（请检查账号权限/空间配置）")

    out(
        {
            "Vid": vid,
            "Source": f"vid://{vid}",
            "PosterUri": resp.get("PosterUri", ""),
            "FileName": resp.get("DirectUrl", ""),
            "SpaceName": sp,
        }
    )


if __name__ == "__main__":
    main()
