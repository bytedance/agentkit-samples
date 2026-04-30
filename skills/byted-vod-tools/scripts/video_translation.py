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
video_translation.py — 提交 AI 视频翻译任务（SubmitAITranslationWorkflow）

提交翻译任务后自动轮询 GetAITranslationProject 直到终态，
返回项目信息（含输出视频播放链接）。

用法:
  python <SKILL_DIR>/scripts/video_translation.py '<json_args>' [space_name]
  python <SKILL_DIR>/scripts/video_translation.py @params.json [space_name]

JSON 参数说明:
  必选:
    Vid                 — 视频 ID（如 v0d225g10002d6tab1iljhtf5buiu8v0）
    SourceLanguage      — 源语言（如 "zh"、"en"），必须由用户明确指定
    TargetLanguage      — 目标语言（如 "es"、"ja"），必须由用户明确指定
  可选（有默认值）:
    SpaceName           — 点播空间名（命令行或环境变量优先）
    TranslationTypeList — 翻译类型组合，默认全部三种
    RecognitionType     — 字幕识别方式，默认 "OCR"
    IsVision            — 是否开启视频理解，默认 false
    IsHardSubtitle      — 是否硬字幕，默认 true
    FontSize            — 字体大小，默认 30
    IsEraseSource       — 是否擦除原字幕，默认 false
    MarginL             — 左边距比例，默认 0.1
    MarginR             — 右边距比例，默认 0.09
    MarginV             — 底部边距比例，默认 0.12
    ShowLines           — 最多显示行数，0 不限制，默认 0

输出:
  成功:
    {"Status":"ProcessSucceed","ProjectId":"xxx","OutputVideo":{"Vid":"...","Url":"...",...},...}
  失败:
    {"error":"..."}
  超时:
    {"error":"轮询超时...","resume_hint":{"command":"python .../poll_translation.py <ProjectId> [space_name]"}}
"""

import sys
import os
import json
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from vod_common import (
    init_and_parse,
    log,
    bail,
    out,
    POLL_INTERVAL,
    POLL_MAX,
)


# ══════════════════════════════════════════════════════
# 默认配置（不含 SourceLanguage / TargetLanguage，这两个必须用户明确提供）
# ══════════════════════════════════════════════════════

DEFAULT_CONFIG = {
    "TranslationTypeList": [
        "SubtitleTranslation",
        "VoiceTranslation",
        "FacialTranslation",
    ],
    "RecognitionType": "OCR",
    "IsVision": False,
    "IsHardSubtitle": True,
    "FontSize": 30,
    "IsEraseSource": False,
    "MarginL": 0.1,
    "MarginR": 0.09,
    "MarginV": 0.12,
    "ShowLines": 0,
}


# ══════════════════════════════════════════════════════
# 支持的语言列表（用于校验）
# ══════════════════════════════════════════════════════

SUPPORTED_SOURCE_LANGUAGES = {"zh", "en"}

SUPPORTED_TARGET_LANGUAGES = {
    "zh",
    "en",
    "ja",
    "ko",
    "de",
    "fr",
    "ru",
    "es",
    "pt",
    "it",
    "id",
    "vi",
    "th",
    "ar",
    "tr",
}

LANGUAGE_NAMES = {
    "zh": "中文",
    "en": "英文",
    "ja": "日语",
    "ko": "韩语",
    "de": "德语",
    "fr": "法语",
    "ru": "俄语",
    "es": "西班牙语",
    "pt": "葡萄牙语",
    "it": "意大利语",
    "id": "印尼语",
    "vi": "越南语",
    "th": "泰语",
    "ar": "阿拉伯语",
    "tr": "土耳其语",
}


# ══════════════════════════════════════════════════════
# 翻译项目终态
# ══════════════════════════════════════════════════════

TERMINAL_SUCCESS = {"ProcessSucceed", "ExportSucceed"}
TERMINAL_FAIL = {"ProcessFailed", "ExportFailed"}
SUSPENDED = {"ProcessSuspended"}
IN_PROGRESS = {"InProcessing", "InExporting"}


# ══════════════════════════════════════════════════════
# 轮询翻译项目状态
# ══════════════════════════════════════════════════════


def poll_translation_project(api, project_id: str, space_name: str) -> dict:
    """
    轮询 GetAITranslationProject 直到项目进入终态。

    终态:
      ProcessSucceed / ExportSucceed → 成功，返回项目详情
      ProcessFailed / ExportFailed   → 失败
      ProcessSuspended              → 暂停（人工干预），也作为终态返回
    """
    for i in range(1, POLL_MAX + 1):
        log(f"轮询翻译项目 [{i}/{POLL_MAX}] ProjectId={project_id}")
        try:
            raw = api.get_ai_translation_project(
                {
                    "SpaceName": space_name,
                    "ProjectId": project_id,
                }
            )
        except Exception as e:
            log(f"  查询失败: {e}，等待重试...")
            time.sleep(POLL_INTERVAL)
            continue

        if isinstance(raw, str):
            raw = json.loads(raw)

        result = raw.get("Result", raw)
        project_info = result.get("ProjectInfo", result)
        status = project_info.get("Status", "")
        log(f"  状态: {status}")

        # 成功终态
        if status in TERMINAL_SUCCESS:
            return _format_project_result(project_info, status)

        # 失败终态
        if status in TERMINAL_FAIL:
            return {
                "Status": status,
                "ProjectId": project_id,
                "error": f"翻译任务失败，状态: {status}",
                "detail": project_info,
            }

        # 暂停态（需要人工干预）
        if status in SUSPENDED:
            return {
                "Status": status,
                "ProjectId": project_id,
                "message": "翻译任务已暂停，等待人工干预。可通过 ContinueAITranslationWorkflow 恢复。",
                "detail": project_info,
            }

        time.sleep(POLL_INTERVAL)

    # 超时
    return {
        "error": f"轮询超时（{POLL_MAX} 次 × {POLL_INTERVAL}s），翻译任务仍在处理中",
        "ProjectId": project_id,
        "resume_hint": {
            "description": "任务尚未完成，可用以下命令重启轮询",
            "command": f"python <SKILL_DIR>/scripts/poll_translation.py '{project_id}' {space_name}",
        },
    }


def _format_project_result(project_info: dict, status: str) -> dict:
    """格式化成功的项目结果。"""
    output_video = project_info.get("OutputVideo", {})
    input_video = project_info.get("InputVideo", {})

    result = {
        "Status": status,
        "ProjectId": project_info.get("ProjectId", ""),
        "ProjectVersion": project_info.get("ProjectVersion", ""),
        "InputVideo": {
            "Title": project_info.get("InputVideoTitle", ""),
            "Vid": input_video.get("Vid", ""),
            "Url": input_video.get("Url", ""),
            "Duration": input_video.get("DurationSecond", 0),
        },
        "OutputVideo": {
            "Vid": output_video.get("Vid", ""),
            "Url": output_video.get("Url", ""),
            "FileName": output_video.get("FileName", ""),
            "Duration": output_video.get("DurationSecond", 0),
        },
    }

    # 如果有语音翻译视频
    voice_video = project_info.get("VoiceTranslationVideo", {})
    if voice_video.get("Url"):
        result["VoiceTranslationVideo"] = {
            "Vid": voice_video.get("Vid", ""),
            "Url": voice_video.get("Url", ""),
            "Duration": voice_video.get("DurationSecond", 0),
        }

    # 如果有面容翻译视频
    facial_video = project_info.get("FacialTranslationVideo", {})
    if facial_video.get("Url"):
        result["FacialTranslationVideo"] = {
            "Vid": facial_video.get("Vid", ""),
            "Url": facial_video.get("Url", ""),
            "Duration": facial_video.get("DurationSecond", 0),
        }

    return result


# ══════════════════════════════════════════════════════
# 主流程
# ══════════════════════════════════════════════════════


def main():
    api, space_name, args = init_and_parse(argv_pos=1)

    # ── 参数校验 ──
    vid = args.get("Vid") or args.get("vid") or args.get("Vids", [""])[0]
    if not vid:
        bail("必须提供 Vid 参数（视频 ID）")

    # 如果传入的是列表取第一个
    if isinstance(vid, list):
        vid = vid[0] if vid else ""
    if not vid:
        bail("Vid 不能为空")

    # 覆盖 space_name（JSON 内可指定）
    sp = args.get("SpaceName") or space_name

    # ── 视频时长校验（≤10 分钟）──
    api.check_video_duration(vid, sp)

    # ── SourceLanguage / TargetLanguage 必须由用户明确提供 ──
    source_lang = args.get("SourceLanguage")
    target_lang = args.get("TargetLanguage")

    if not source_lang:
        supported = ", ".join(
            f"{k}({v})"
            for k, v in sorted(LANGUAGE_NAMES.items())
            if k in SUPPORTED_SOURCE_LANGUAGES
        )
        bail(
            f"必须提供 SourceLanguage（源语言）。"
            f"支持的源语言: {supported}。"
            f"请让用户明确指定源语言后重试。"
        )

    if not target_lang:
        supported = ", ".join(
            f"{k}({v})"
            for k, v in sorted(LANGUAGE_NAMES.items())
            if k in SUPPORTED_TARGET_LANGUAGES
        )
        bail(
            f"必须提供 TargetLanguage（目标语言）。"
            f"支持的目标语言: {supported}。"
            f"请让用户明确指定目标语言后重试。"
        )

    if source_lang not in SUPPORTED_SOURCE_LANGUAGES:
        supported = ", ".join(
            f"{k}({v})"
            for k, v in sorted(LANGUAGE_NAMES.items())
            if k in SUPPORTED_SOURCE_LANGUAGES
        )
        bail(f"不支持的源语言: {source_lang}。支持的源语言: {supported}")

    if target_lang not in SUPPORTED_TARGET_LANGUAGES:
        supported = ", ".join(
            f"{k}({v})"
            for k, v in sorted(LANGUAGE_NAMES.items())
            if k in SUPPORTED_TARGET_LANGUAGES
        )
        bail(f"不支持的目标语言: {target_lang}。支持的目标语言: {supported}")

    if source_lang == target_lang:
        bail(f"源语言和目标语言不能相同: {source_lang}")

    # ── 合并用户参数与默认值 ──
    translation_type_list = args.get(
        "TranslationTypeList", DEFAULT_CONFIG["TranslationTypeList"]
    )
    recognition_type = args.get("RecognitionType", DEFAULT_CONFIG["RecognitionType"])
    is_vision = args.get("IsVision", DEFAULT_CONFIG["IsVision"])
    is_hard_subtitle = args.get("IsHardSubtitle", DEFAULT_CONFIG["IsHardSubtitle"])
    font_size = args.get("FontSize", DEFAULT_CONFIG["FontSize"])
    is_erase_source = args.get("IsEraseSource", DEFAULT_CONFIG["IsEraseSource"])
    margin_l = args.get("MarginL", DEFAULT_CONFIG["MarginL"])
    margin_r = args.get("MarginR", DEFAULT_CONFIG["MarginR"])
    margin_v = args.get("MarginV", DEFAULT_CONFIG["MarginV"])
    show_lines = args.get("ShowLines", DEFAULT_CONFIG["ShowLines"])

    # ── 构造请求体 ──
    body = {
        "SpaceName": sp,
        "Vid": vid,
        "TranslationConfig": {
            "SourceLanguage": source_lang,
            "TargetLanguage": target_lang,
            "TranslationTypeList": translation_type_list,
        },
        "OperatorConfig": {
            "SubtitleRecognitionConfig": {
                "IsVision": is_vision,
                "RecognitionType": recognition_type,
            },
        },
        "SubtitleConfig": {
            "IsHardSubtitle": is_hard_subtitle,
            "IsEraseSource": is_erase_source,
        },
    }

    # 硬字幕时补充字幕样式参数
    if is_hard_subtitle:
        body["SubtitleConfig"].update(
            {
                "FontSize": font_size,
                "MarginL": margin_l,
                "MarginR": margin_r,
                "MarginV": margin_v,
                "ShowLines": show_lines,
            }
        )

    # 用户传入的术语库配置
    termbase_config = args.get("TermbaseConfig")
    if termbase_config:
        body["TranslationConfig"]["TermbaseConfig"] = termbase_config

    # 用户传入的流程配置（如暂停阶段）
    process_config = args.get("ProcessConfig")
    if process_config:
        body["ProcessConfig"] = process_config

    # 用户传入的声音克隆配置
    voice_clone_config = args.get("VoiceCloneConfig")
    if voice_clone_config:
        body["OperatorConfig"]["VoiceCloneConfig"] = voice_clone_config

    # ── 提交任务 ──
    log(
        f"提交 AI 翻译任务: Vid={vid}, {source_lang}→{target_lang}, 类型={translation_type_list}"
    )
    try:
        raw = api.submit_ai_translation_workflow(body)
    except Exception as e:
        bail(f"提交翻译任务失败: {e}")

    if isinstance(raw, str):
        raw = json.loads(raw)

    # 检查响应错误
    resp_meta = raw.get("ResponseMetadata", {})
    error = resp_meta.get("Error", {})
    if error and error.get("Code"):
        bail(f"API 错误: Code={error.get('Code')}, Message={error.get('Message', '')}")

    result = raw.get("Result", raw)
    project_base = result.get("ProjectBaseInfo", result)
    project_id = project_base.get("ProjectId", "")

    if not project_id:
        bail(
            f"提交任务未返回 ProjectId，原始响应：{json.dumps(raw, ensure_ascii=False)}"
        )

    log(f"翻译任务已提交，ProjectId={project_id}，开始轮询...")

    # ── 轮询任务状态 ──
    poll_result = poll_translation_project(api, project_id, sp)
    out(poll_result)


if __name__ == "__main__":
    main()
