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
comic_style.py — AI 漫剧转绘（Comic Style Transfer）

使用 AsyncVCreativeTask（Scene=videostyletrans）提交转绘任务，
通过 GetVCreativeTaskResult 轮询到终态。

用法:
  # 直接执行（提交 + 自动轮询）
  python <SKILL_DIR>/scripts/comic_style.py @params.json

  # 恢复轮询已提交的任务
  python <SKILL_DIR>/scripts/comic_style.py --poll <VCreativeId> [space_name]

params.json 示例:
{
  "Vid": "v0d012xxxx",
  "Style": "漫画风",
  "Resolution": "720p"
}

参数说明:
  Vid        (必填) 视频 ID，也可传入 vid://xxx 格式
  Style      (选填) 转绘风格，默认 "漫画风"。可选："漫画风" | "3D卡通风格"
  Resolution (必填) 输出分辨率："480p" | "720p" | "1080p"
"""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vod_common import (
    init_and_parse,
    get_space_name,
    out,
    bail,
    log,
)
from api_manage import ApiManage
from vod_api_constants import (
    VOD_ACTION_SUBMIT_ASYNC_AI_CLIP,
    VOD_FIELD_AI_CLIP_TASK_ID,
)


# ── 限制 ────────────────────────────────────────────
MAX_DURATION_SEC = 300  # 视频时长 ≤ 5 分钟

VALID_STYLES = {"漫画风", "3D卡通风格"}
VALID_RESOLUTIONS = {"480p", "720p", "1080p"}


def get_duration(api: ApiManage, vid: str, space_name: str) -> float:
    """通过 GetMediaInfos 获取视频时长（秒）。"""
    raw = api.get_media_infos(vid, space_name)
    result = raw.get("Result", raw)
    info_list = result.get("MediaInfoList", [])
    if not info_list:
        bail(f"未找到 Vid={vid} 的媒资信息，请确认 Vid 及空间名称")
    basic = info_list[0].get("BasicInfo", {})
    duration = basic.get("Duration", 0)
    return float(duration)


def submit_comic_style(api: ApiManage, vid: str, style: str, resolution: str, space_name: str) -> dict:
    """提交 AsyncVCreativeTask (Scene=videostyletrans) 并自动轮询。"""

    # 构建 vid:// 格式输入
    vid_input = vid if vid.startswith("vid://") else f"vid://{vid}"

    param_obj = {
        "input":      vid_input,
        "style":      style,
        "resolution": resolution,
    }

    payload = {
        "Uploader": space_name,
        "Scene":    "videostyletrans",
        # ParamObj 需要是对象而不是字符串
        "ParamObj": param_obj,
    }

    log(f"提交漫剧转绘任务：Vid={vid}, Style={style}, Resolution={resolution}")

    # 直接调用底层 _post 接口，因为 comic_style 使用 Scene 而非 WorkflowId
    try:
        resp = api._post(VOD_ACTION_SUBMIT_ASYNC_AI_CLIP, payload)
    except Exception as e:
        bail(f"提交任务失败：{e}")

    if isinstance(resp, str):
        resp = json.loads(resp)

    result = resp.get("Result", {})
    base_resp = result.get("BaseResp", {}) or {}
    sc = base_resp.get("StatusCode", 0)
    if sc != 0:
        bail(f"提交任务失败：StatusCode={sc} msg={base_resp.get('StatusMessage', '')}")

    vcreative_id = result.get(VOD_FIELD_AI_CLIP_TASK_ID, "") or result.get("VCreativeId", "")
    if not vcreative_id:
        bail(f"提交任务未返回 VCreativeId，原始响应：{json.dumps(resp)}")

    log(f"任务已提交，VCreativeId={vcreative_id}，开始轮询...")
    return api.poll_vcreative(vcreative_id, space_name)


def main():
    # ── 恢复轮询模式 ───────────────────────────────
    if len(sys.argv) >= 3 and sys.argv[1] == "--poll":
        vcreative_id = sys.argv[2]
        api = ApiManage()
        space_name = get_space_name(argv_pos=3)
        result = api.poll_vcreative(vcreative_id, space_name)
        out(result)
        return

    # ── 正常提交模式 ───────────────────────────────
    api, space_name, params = init_and_parse(argv_pos=1)

    vid = params.get("Vid", "").strip()
    if not vid:
        bail("缺少必填参数 Vid（视频 ID）")

    # 去掉 vid:// 前缀用于校验
    raw_vid = vid.replace("vid://", "") if vid.startswith("vid://") else vid

    resolution = params.get("Resolution", "").strip()
    if not resolution:
        bail(f"缺少必填参数 Resolution，可选值：{', '.join(sorted(VALID_RESOLUTIONS))}")
    if resolution not in VALID_RESOLUTIONS:
        bail(f"Resolution 不合法：{resolution}，可选值：{', '.join(sorted(VALID_RESOLUTIONS))}")

    style = params.get("Style", "漫画风").strip()
    if style not in VALID_STYLES:
        bail(f"Style 不合法：{style}，可选值：{', '.join(sorted(VALID_STYLES))}")

    # ── 时长校验 ─────────────────────────────────
    log("检查视频时长...")
    duration = get_duration(api, raw_vid, space_name)
    log(f"视频时长：{duration:.1f}s")
    if duration > MAX_DURATION_SEC:
        bail(f"视频时长 {duration:.0f}s 超过限制（最大 {MAX_DURATION_SEC}s / 5 分钟）")

    # ── 提交 ─────────────────────────────────────
    result = submit_comic_style(api, raw_vid, style, resolution, space_name)
    out(result)


if __name__ == "__main__":
    main()
