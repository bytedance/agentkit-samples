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
drama_recap.py — 提交解说视频生成任务（CreateDramaRecapTask / QueryDramaRecapTask）

基于大模型视频理解，根据原视频生成不同风格的 AI 解说视频，支持自定义解说词或 AI 自动生成，
支持多种音色、字幕样式和短剧三要素模板。

用法:
  python <SKILL_DIR>/scripts/drama_recap.py '<json_args>' [space_name]
  python <SKILL_DIR>/scripts/drama_recap.py @params.json [space_name]
  python <SKILL_DIR>/scripts/drama_recap.py --poll <TaskId> [space_name]

JSON 参数说明:
  视频输入（二选一）:
    Vids                  — 视频 ID 列表（至少 1 个）
    DramaScriptTaskId     — 已完成的剧本还原任务 ID（与 Vids 互斥）

  解说词（根据模式必选或可选）:
    RecapText             — 自定义解说词文本（AutoGenerateRecapText=false 时必选）

  可选:
    AutoGenerateRecapText — 是否 AI 自动生成解说词，默认 false
    RecapStyle            — AI 解说风格关键词（如"搞笑"、"悬疑"），≤500 字符
    RecapTextSpeed        — 解说语速 [0.5, 2.0]，默认 1.0，推荐 1.2
    RecapTextLength       — AI 生成解说词长度（字符数），≤5000
    PauseTime             — 句间停顿（毫秒）[1, 1000]，默认 120
    AllowRepeatMatch      — 是否允许匹配重复画面，默认 false
    IsEraseSubtitle       — 是否擦除原字幕，默认 false
    BatchGenerateCount    — 批量生成数量，默认 1，最大 100
    VoiceType             — 音色名称（默认 Yunxi），预置: Yunxi/Yunjian/Yunfeng/Yunyi/Yunjie/Yunze/Yunye/Xiaoxiao/Xiaochen/Xiaohan/Xiaomo
    AppId                 — 豆包语音 App ID（使用高级音色时需要）
    FontConfig            — 字幕样式配置（详见 reference 文档）
    MiniseriesEdit        — 短剧三要素配置（Template/Title/Hint）

输出:
  成功: {"Status":"success","TaskId":"...","Vid":"...","MultipleResult":{...}}
  失败: {"error":"..."}
  超时: {"error":"轮询超时...","resume_hint":{"command":"python .../drama_recap.py --poll <TaskId> <space>"}}
"""

import sys
import os
import json
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from vod_common import (
    init_and_parse,
    get_space_name,
    log,
    bail,
    out,
)
from api_manage import ApiManage


# ══════════════════════════════════════════════════════
# 预置音色列表
# ══════════════════════════════════════════════════════

PRESET_VOICES = {
    "Yunxi",
    "Yunjian",
    "Yunfeng",
    "Yunyi",
    "Yunjie",
    "Yunze",
    "Yunye",
    "Xiaoxiao",
    "Xiaochen",
    "Xiaohan",
    "Xiaomo",
}

# 短剧三要素模板
SUPPORTED_TEMPLATES = {
    "热门短剧1",
    "热门短剧2",
    "热门短剧3",
    "热门短剧4",
    "热门短剧5",
}


# ══════════════════════════════════════════════════════
# 轮询逻辑
# ══════════════════════════════════════════════════════


def poll_drama_recap(api, space_name, task_id, max_rounds=360, interval=5):
    """
    轮询 QueryDramaRecapTask 直到终态。
    终态: success / failed / timeout
    """
    log(f"开始轮询解说视频任务: TaskId={task_id}")

    for i in range(1, max_rounds + 1):
        try:
            raw = api.query_drama_recap_task(
                {
                    "SpaceName": space_name,
                    "TaskId": task_id,
                }
            )
            resp = json.loads(raw) if isinstance(raw, str) else raw
            result = resp.get("Result", {})
            status = result.get("Status", "")

            if i % 12 == 1:  # 每分钟打一次日志
                log(f"轮询第 {i}/{max_rounds} 次, Status={status}")

            if status == "success":
                log("解说视频生成成功")
                output = {
                    "Status": "success",
                    "TaskId": task_id,
                    "SpaceName": space_name,
                }
                # 单个视频时有 Vid
                if result.get("Vid"):
                    output["Vid"] = result["Vid"]
                # 批量时有 MultipleResult
                if result.get("MultipleResult"):
                    output["MultipleResult"] = result["MultipleResult"]
                return output

            if status in ("failed", "timeout"):
                log(f"任务终态: {status}")
                return {
                    "Status": status,
                    "TaskId": task_id,
                    "SpaceName": space_name,
                    "detail": result,
                    "note": f"任务{status}，请检查输入视频和参数后重试。",
                }

            # running — 继续等待
        except Exception as e:
            if i % 12 == 1:
                log(f"轮询异常: {e}")

        time.sleep(interval)

    # 超时
    return {
        "error": f"轮询超时（{max_rounds} 次 × {interval}s），任务仍在处理中",
        "TaskId": task_id,
        "resume_hint": {
            "description": "任务尚未完成，可用以下命令重启轮询",
            "command": f"python <SKILL_DIR>/scripts/drama_recap.py --poll '{task_id}' {space_name}",
        },
    }


# ══════════════════════════════════════════════════════
# 主流程
# ══════════════════════════════════════════════════════


def main():
    # ── 检查恢复轮询模式 ──
    if len(sys.argv) >= 3 and sys.argv[1] == "--poll":
        task_id = sys.argv[2]
        space_name = get_space_name(argv_pos=3)
        api = ApiManage()
        result = poll_drama_recap(api, space_name, task_id)
        out(result)
        return

    api, space_name, args = init_and_parse(argv_pos=1)

    # ── 解析视频输入（Vids 和 DramaScriptTaskId 二选一）──
    vids = args.get("Vids") or args.get("vids") or []
    if isinstance(vids, str):
        vids = [vids]
    drama_script_task_id = (
        args.get("DramaScriptTaskId") or args.get("dramaScriptTaskId") or ""
    )

    if vids and drama_script_task_id:
        bail("Vids 和 DramaScriptTaskId 互斥，只能提供其中一个")
    if not vids and not drama_script_task_id:
        bail("必须提供 Vids（视频 ID 列表）或 DramaScriptTaskId（剧本还原任务 ID）之一")

    # ── 解析解说词相关 ──
    auto_generate = args.get("AutoGenerateRecapText", False)
    recap_text = args.get("RecapText") or args.get("recapText") or ""

    if not auto_generate and not recap_text:
        bail(
            "当 AutoGenerateRecapText 为 false（默认）时，必须提供 RecapText（解说词文本）。\n"
            "或设置 AutoGenerateRecapText=true 让 AI 自动生成解说词。"
        )
    if auto_generate and recap_text:
        bail("AutoGenerateRecapText=true 时不可同时设置 RecapText，请二选一")

    # ── 构造请求体 ──
    body = {"SpaceName": space_name}

    if vids:
        body["Vids"] = [v for v in vids if v]
        if not body["Vids"]:
            bail("Vids 列表中没有有效的视频 ID")
    else:
        body["DramaScriptTaskId"] = drama_script_task_id

    if recap_text:
        body["RecapText"] = recap_text

    # IsEraseSubtitle
    if "IsEraseSubtitle" in args:
        body["IsEraseSubtitle"] = args["IsEraseSubtitle"]

    # BatchGenerateCount
    batch_count = args.get("BatchGenerateCount", 1)
    if batch_count != 1:
        body["BatchGenerateCount"] = batch_count

    # ── SpeakerConfig ──
    voice_type = args.get("VoiceType") or args.get("voiceType") or ""
    app_id = args.get("AppId") or args.get("appId") or ""
    if voice_type or app_id:
        speaker = {}
        if voice_type:
            speaker["VoiceType"] = voice_type
        if app_id:
            speaker["AppId"] = app_id
            speaker["Cluster"] = "volcano_tts"
        body["SpeakerConfig"] = speaker

    # ── FontConfig (pass-through) ──
    font_config = args.get("FontConfig") or args.get("fontConfig")
    if font_config and isinstance(font_config, dict):
        body["FontConfig"] = font_config

    # ── DramaRecapConfig ──
    recap_config = {}
    if auto_generate:
        recap_config["AutoGenerateRecapText"] = True
    recap_style = args.get("RecapStyle") or args.get("recapStyle") or ""
    if recap_style:
        recap_config["RecapStyle"] = recap_style
    recap_speed = args.get("RecapTextSpeed") or args.get("recapTextSpeed")
    if recap_speed is not None:
        recap_config["RecapTextSpeed"] = float(recap_speed)
    recap_length = args.get("RecapTextLength") or args.get("recapTextLength")
    if recap_length is not None:
        recap_config["RecapTextLength"] = int(recap_length)
    pause_time = args.get("PauseTime") or args.get("pauseTime")
    if pause_time is not None:
        recap_config["PauseTime"] = int(pause_time)
    allow_repeat = args.get("AllowRepeatMatch")
    if allow_repeat is not None:
        recap_config["AllowRepeatMatch"] = allow_repeat

    if recap_config:
        body["DramaRecapConfig"] = recap_config

    # ── MiniseriesEdit (短剧三要素) ──
    mini_edit = args.get("MiniseriesEdit") or args.get("miniseriesEdit")
    if mini_edit and isinstance(mini_edit, dict):
        tmpl = mini_edit.get("Template", "")
        if tmpl and tmpl not in SUPPORTED_TEMPLATES:
            bail(
                f"不支持的短剧三要素模板: {tmpl}。支持: {', '.join(sorted(SUPPORTED_TEMPLATES))}"
            )
        body["MiniseriesEdit"] = mini_edit

    input_desc = (
        f"{len(vids)} 个视频" if vids else f"DramaScriptTaskId={drama_script_task_id}"
    )
    log(
        f"提交解说视频生成任务: {input_desc}, AutoGenerate={auto_generate}, BatchCount={batch_count}"
    )

    # ── 提交任务 ──
    try:
        raw = api.create_drama_recap_task(body)
        resp = json.loads(raw) if isinstance(raw, str) else raw
    except Exception as e:
        bail(f"CreateDramaRecapTask 调用失败: {e}")

    resp_meta = resp.get("ResponseMetadata", {})
    if resp_meta.get("Error"):
        bail(
            f"CreateDramaRecapTask 返回错误: {json.dumps(resp_meta['Error'], ensure_ascii=False)}"
        )

    result = resp.get("Result", {})
    task_id = result.get("TaskId", "")
    if not task_id:
        bail(
            f"CreateDramaRecapTask 未返回 TaskId: {json.dumps(resp, ensure_ascii=False)}"
        )

    drama_script_tid = result.get("DramaScriptTaskId", "")
    log(
        f"任务已提交: TaskId={task_id}"
        + (f", DramaScriptTaskId={drama_script_tid}" if drama_script_tid else "")
    )

    # ── 轮询 ──
    poll_result = poll_drama_recap(api, space_name, task_id)
    out(poll_result)


if __name__ == "__main__":
    main()
