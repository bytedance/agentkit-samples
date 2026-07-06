# Copyright (c) 2026 BytePlus. All rights reserved.
# SPDX-License-Identifier: Proprietary
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from schemas import (
    GeneratedVideoArtifact,
    GenerationPrompt,
    PreparedRewrite,
    PromptPreview,
    PromptPackage,
    RewriteBrief,
    RewritePlan,
    RewriteRequest,
    RewriteVideoResponse,
    RewrittenStoryboard,
    TemplateProfile,
    RewriteStrategy,
    VideoAnalysis,
)

BASE_DIR = Path(__file__).resolve().parent.parent


def _dir_from_env(name: str, default: Path) -> Path:
    value = os.getenv(name, "").strip()
    if not value:
        return default
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = BASE_DIR / path
    return path.resolve()


OUTPUT_DIR = _dir_from_env("OUTPUT_DIR", Path.cwd() / "output")
CACHE_DIR = _dir_from_env("VIRAL_REWRITE_CACHE_DIR", OUTPUT_DIR / "cache")
PREVIEW_DIR = OUTPUT_DIR / "previews"
CONTACT_SHEET_SAMPLE_FPS = 1
CONTACT_SHEET_MAX_FRAMES = 15
MUSIC_PROMPT = (
    "音乐: 原创配乐、不可识别，不出现清晰可哼唱的主旋律、不出现重复钩子段、"
    "不使用任何现有作品的旋律/和弦/节奏动机；禁止模仿任何具体艺人、"
    "禁止复刻任何年代经典曲风细节到可识别程度；无采样、无人声。"
)
MUSIC_PROMPT_EN = (
    "Music: original background score, non-identifiable, no clear hummable melody, no repeated hook, "
    "no use of any existing work's melody, chord progression, or rhythmic motif; do not imitate any specific artist "
    "or recognizable era/genre details; no samples, no vocals."
)


def _log(message: str) -> None:
    print(f"[rewrite-skill] {message}", flush=True)


def _join_items(items: list[str], *, limit: int = 5) -> str:
    clean = [item.strip() for item in items if item and item.strip()]
    if not clean:
        return "无"
    return "；".join(clean[:limit])


def _join_items_for_language(items: list[str], *, limit: int = 5, language: str = "zh") -> str:
    clean = [item.strip() for item in items if item and item.strip()]
    if not clean:
        return "none" if language == "en" else "无"
    return ("; " if language == "en" else "；").join(clean[:limit])


PROFILE_LABELS_ZH = {
    "unknown": "未识别",
    "visual_product_texture": "视觉质感型（产品/食物/饮品）",
    "human_demo": "真人演示型",
    "human_voiceover": "真人口播讲解型",
    "platform_cta": "平台行动收口型",
    "mixed": "混合型",
}

PROFILE_LABELS_EN = {
    "unknown": "Unknown",
    "visual_product_texture": "Visual product texture",
    "human_demo": "Human demo",
    "human_voiceover": "Human presenter with voiceover",
    "platform_cta": "Platform CTA",
    "mixed": "Mixed template",
}

SLOT_LABELS_ZH = {
    "shot_order": "镜头顺序",
    "camera_pacing": "镜头节奏",
    "product_state": "产品状态/外观",
    "texture_satisfaction": "质感爽点",
    "scene_mood": "场景氛围",
    "forbidden_text_carryover": "禁止继承文字/平台元素",
    "person_framing": "人物构图",
    "person_action": "人物动作",
    "broad_person_appearance_context": "人物外观/市场语境",
    "real_scene_context": "真实场景语境",
    "spoken_language": "口播语言",
    "voiceover_rhythm": "口播节奏",
    "lip_sync": "口型同步",
    "cta_function_only": "只借行动收口功能",
    "product_detail_pointing": "产品细节指向",
    "music_mood": "音乐氛围",
    "lifestyle_satisfaction": "生活方式爽点",
    "ingredient_proof": "原料证明",
    "liquid_texture": "液体质感",
}

SLOT_LABELS_EN = {
    "shot_order": "shot order",
    "camera_pacing": "camera pacing",
    "product_state": "product state and appearance",
    "texture_satisfaction": "texture satisfaction",
    "scene_mood": "scene mood",
    "forbidden_text_carryover": "forbidden text/platform carryover",
    "person_framing": "person framing",
    "person_action": "person actions",
    "broad_person_appearance_context": "broad person/market appearance context",
    "real_scene_context": "real scene context",
    "spoken_language": "spoken language",
    "voiceover_rhythm": "voiceover rhythm",
    "lip_sync": "lip sync",
    "cta_function_only": "CTA function only",
    "product_detail_pointing": "product detail pointing",
    "music_mood": "music mood",
    "lifestyle_satisfaction": "lifestyle satisfaction",
    "ingredient_proof": "ingredient proof",
    "liquid_texture": "liquid texture",
}


def _profile_label(profile: str, *, language: str = "zh") -> str:
    if language == "en":
        return PROFILE_LABELS_EN.get(profile, profile.replace("_", " ").strip().title())
    return PROFILE_LABELS_ZH.get(profile, profile)


def _slot_label(slot: str, *, language: str = "zh") -> str:
    if language == "en":
        return SLOT_LABELS_EN.get(slot, slot.replace("_", " "))
    return SLOT_LABELS_ZH.get(slot, slot)


def _join_slots(slots: list[str], *, limit: int = 10, language: str = "zh") -> str:
    return _join_items_for_language([_slot_label(slot, language=language) for slot in slots], limit=limit, language=language)


ZH_DISPLAY_REPLACEMENTS = {
    "自动 captions": "自动字幕",
    "AI-generated": "生成标记",
    "AI generated": "生成标记",
    "AI生成": "生成标记",
    "TikTok": "短视频平台",
    "BGM": "背景音乐",
    "captions": "自动字幕",
    "caption": "字幕",
    "平台 UI": "平台界面",
    "UI": "界面",
    "logo": "标志",
    "CTA": "行动收口",
    "hook": "开场钩子",
    "source 商品": "商品图",
    "source": "商品图",
    "ID": "标识",
    "profile": "类型",
    "human_voiceover": "真人口播讲解型",
    "human_demo": "真人演示型",
    "visual_product_texture": "视觉质感型",
    "platform_cta": "平台行动收口型",
    "person_framing": "人物构图",
    "person_action": "人物动作",
    "broad_person_appearance_context": "人物外观/市场语境",
    "real_scene_context": "真实场景语境",
    "spoken_language": "口播语言",
    "voiceover_rhythm": "口播节奏",
    "lip_sync": "口型同步",
    "cta_function_only": "只借行动收口功能",
    "forbidden_text_carryover": "禁止继承文字/平台元素",
    "QuickTime/MOV": "视频文件",
    "MOV": "视频格式",
    "AAC": "音频编码",
    "fps": "帧/秒",
    "same as the original template spoken language": "与原模板口播语言一致",
}


def _zh_display_text(value: str | None) -> str:
    text = str(value or "")
    for source, target in ZH_DISPLAY_REPLACEMENTS.items():
        text = text.replace(source, target)
    text = text.replace("平台 界面", "平台界面")
    text = re.sub(r"@[A-Za-z0-9_.-]+", "账号文字", text)
    return text


def _join_display_items(items: list[str], *, limit: int = 5) -> str:
    return _join_items([_zh_display_text(item) for item in items], limit=limit)


def _contains_cjk(text: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in text)


def _ui_language(request: RewriteRequest | None = None, value: str | None = None) -> str:
    explicit = (request.ui_language if request else value) or "auto"
    if explicit in {"zh", "en"}:
        return explicit
    text = ""
    if request:
        text = "\n".join([request.product_context, request.target_audience, request.objective, *request.extra_constraints])
    return "zh" if _contains_cjk(text) else "en"


def _is_en(request: RewriteRequest | None = None, value: str | None = None) -> bool:
    return _ui_language(request, value) == "en"


def _music_prompt(request: RewriteRequest | None = None) -> str:
    return MUSIC_PROMPT_EN if _is_en(request) else MUSIC_PROMPT


def _all_analysis_text(analysis: VideoAnalysis) -> str:
    parts: list[str] = [
        analysis.basic_info,
        analysis.audio_facts,
        analysis.camera_and_editing,
        analysis.material_type,
        analysis.subject_framing,
        analysis.person_appearance_context,
        analysis.spoken_language,
        analysis.subtitle_state,
        analysis.core_satisfaction_mechanism,
        analysis.replication_script,
        analysis.replication_framework,
        analysis.extend_to_15s_plan,
        *analysis.scene_and_people,
        *analysis.scene_details,
        *analysis.shot_sequence,
        *analysis.subtitle_messages,
        *analysis.structure.trust_signals,
    ]
    for window in analysis.five_second_windows:
        parts.extend(
            [
                window.scene,
                window.shot_type,
                window.composition,
                window.camera,
                window.camera_position,
                window.camera_movement,
                window.product_presence,
                window.subtitle_text,
                window.voiceover_text,
                window.audio_state,
                *window.scene_details,
                *window.action_sequence,
                *window.borrowable_function,
                *window.replication_notes,
            ]
        )
    return "\n".join(part for part in parts if part)


def _has_any(text: str, keywords: list[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def _is_absent_or_unknown(value: str) -> bool:
    normalized = value.strip().lower()
    if not normalized:
        return True
    absent_markers = [
        "unknown",
        "none",
        "n/a",
        "无",
        "无口播",
        "无旁白",
        "无人声",
        "无台词",
        "不存在口播",
        "没有口播",
        "no voiceover",
        "no spoken",
        "no speech",
    ]
    return any(marker in normalized for marker in absent_markers)


def _spoken_language_kind(value: str | None) -> str:
    """Return en/zh/same/unknown for template voiceover language text."""
    text = (value or "").strip()
    lowered = text.lower()
    if not text or _is_absent_or_unknown(text):
        return "unknown"
    if _has_any(lowered, ["english", "eng voice", "english voiceover"]) or _has_any(text, ["英文", "英语", "英語", "类英文"]):
        return "en"
    if _has_any(lowered, ["mandarin", "chinese"]) or _has_any(text, ["中文", "普通话", "普通話", "汉语", "漢語"]):
        target_driven_chinese = _has_any(text, ["原创中文短句服务目标受众", "服务目标受众", "中文导购式表达", "中文短句"])
        explicit_template_chinese = bool(
            re.search(r"(模板|原片|原视频|原始|template|source).{0,16}(中文|普通话|普通話|Chinese|Mandarin)", text, re.I)
            or re.search(r"(中文|普通话|普通話|Chinese|Mandarin).{0,16}(模板|原片|原视频|原始|template|source)", text, re.I)
            or _has_any(text, ["模板口播语言：中文", "模板口播语言为中文", "原视频是中文口播", "原片是中文口播"])
        )
        if target_driven_chinese and not explicit_template_chinese:
            return "unknown"
        return "zh"
    if _has_any(text, ["模板原口播语言", "与模板相同", "同模板", "原始讲解节奏", "原视频口播语言"]) or _has_any(
        lowered, ["same as the template", "same language as the template", "original template spoken language"]
    ):
        return "same"
    return "unknown"


def _canonical_spoken_language(value: str | None) -> str:
    kind = _spoken_language_kind(value)
    if kind == "en":
        return "English"
    if kind == "zh":
        return "Chinese Mandarin"
    if kind == "same":
        return "same as the original template spoken language"
    return ""


def _infer_template_spoken_language(analysis: VideoAnalysis, brief: RewriteBrief | None = None) -> str:
    candidates = [
        analysis.spoken_language,
        brief.template_spoken_language if brief else "",
        analysis.audio_facts,
        analysis.subtitle_state,
        analysis.person_appearance_context,
        *analysis.subtitle_messages,
    ]
    for window in analysis.five_second_windows:
        candidates.extend([window.voiceover_text, window.audio_state, window.subtitle_text])
    for candidate in candidates:
        canonical = _canonical_spoken_language(candidate)
        if canonical and canonical != "same as the original template spoken language":
            return canonical
    for candidate in candidates:
        canonical = _canonical_spoken_language(candidate)
        if canonical:
            return canonical
    return ""


def _template_voice_language_prompt_label(brief: RewriteBrief | None) -> str:
    if not brief:
        return ""
    canonical = _canonical_spoken_language(brief.template_spoken_language)
    return canonical or brief.template_spoken_language.strip()


def _person_context_prompt_label(brief: RewriteBrief | None) -> str:
    if not brief:
        return ""
    return (brief.template_person_appearance_context or "").strip()


def _person_context_has_template_anchor(value: str) -> bool:
    text = value.strip()
    lowered = text.lower()
    anchors = [
        "original video",
        "source video",
        "same broad",
        "same as the template",
        "template person",
        "template presenter",
        "template creator",
        "western",
        "tiktok",
        "caucasian",
        "european",
        "american",
        "模板人物",
        "模板博主",
        "模板模特",
        "模板导购",
        "模板讲解者",
        "模板同类",
        "原视频",
        "原片",
        "与模板",
        "同类",
        "相近肤色",
        "人种语境",
        "欧美",
        "英美",
    ]
    return _has_any(lowered, anchors) or _has_any(text, anchors)


def _person_context_is_target_audience_drift(
    context: str,
    request: RewriteRequest | None,
    brief: RewriteBrief | None,
) -> bool:
    text = (context or "").strip()
    if not brief or brief.template_profile not in {"human_demo", "human_voiceover"}:
        return False
    if _is_absent_or_unknown(text):
        return True
    target = (request.target_audience if request else "").strip()
    product_context = (request.product_context if request else "").strip()
    target_hit = bool(target and target in text)
    target_markers = [
        "目标人群",
        "目标受众",
        "服务目标受众",
        "一线城市",
        "tier_1_city",
        "target audience",
        "for the target audience",
        "based on the audience",
    ]
    target_hit = target_hit or _has_any(text.lower(), [item.lower() for item in target_markers]) or _has_any(text, target_markers)
    if not target_hit:
        return False
    if _person_context_has_template_anchor(text):
        return False
    if product_context and text in product_context:
        return True
    return True


def _usable_template_person_context(
    context: str,
    request: RewriteRequest | None,
    brief: RewriteBrief | None,
) -> bool:
    text = (context or "").strip()
    if _is_absent_or_unknown(text):
        return False
    if _person_context_is_target_audience_drift(text, request, brief):
        return False
    return True


def _voice_language_is_unknown_for_generation(brief: RewriteBrief | None) -> bool:
    if not brief or brief.template_profile != "human_voiceover":
        return False
    language = _template_voice_language_prompt_label(brief)
    return _spoken_language_kind(language) in {"unknown", "same"}


def voice_language_blocking_message(prepared: PreparedRewrite, *, language: str = "zh") -> str:
    brief = prepared.rewrite_brief
    if not _voice_language_is_unknown_for_generation(brief):
        return ""
    if language == "en":
        return (
            "Generation is blocked before Seedance because this is a human_voiceover template but the template spoken language is not confirmed. "
            "Please patch the prepared brief with the template voiceover language first, for example template_spoken_language=\"English\". "
            "The skill must not choose Chinese or English from the UI language or target audience."
        )
    return (
        "已在提交 Seedance 前阻断：这是口播模板，但模板口播语言还没有被明确确认。"
        "请先把 prepared brief 里的 template_spoken_language 补成真实模板语言，例如 “English”。"
        "这个 skill 不能根据中文前台或目标人群自动选择中文口播。"
    )


def person_context_blocking_message(prepared: PreparedRewrite, *, language: str = "zh") -> str:
    brief = prepared.rewrite_brief
    profile = _resolved_template_profile(prepared.viral_analysis)
    if brief.template_profile not in {"human_demo", "human_voiceover"} and profile.profile not in {"human_demo", "human_voiceover"}:
        return ""
    context = _person_context_prompt_label(brief)
    if _usable_template_person_context(context, prepared.request, brief):
        return ""
    if language == "en":
        return (
            "Generation is blocked before Seedance because this human-presenter template does not have a reliable template person / market visual context. "
            "The current person context is missing or appears to come from the target audience instead of the template. "
            "Please patch template_person_appearance_context with the template's broad person appearance / market visual context, for example "
            "\"same broad Western/TikTok fashion creator visual context\". Generate a new non-identical person and do not copy the exact face."
        )
    return (
        "已在提交 Seedance 前阻断：这是真人出镜/口播模板，但模板人物外观/市场语境没有可靠确认。"
        "当前人物语境为空，或像是从目标人群推出来的，而不是从模板视频观察出来的。"
        "请先把 prepared brief 的 template_person_appearance_context 补成模板里真实的 broad 人物外观/市场视觉语境，"
        "例如“与模板同类的欧美/TikTok 女装博主视觉语境”。生成时会换成新人物，不复制模板具体脸或身份。"
    )


def profile_audio_unresolved_blocking_message(prepared: PreparedRewrite, *, language: str = "zh") -> str:
    """Block before Seedance when a human-presenter template's audio track was never confirmed.

    This closes the "classify as human_demo to silently skip the whole voiceover question"
    backdoor: any human-presenter template must explicitly assert audio_track_confirmed=True
    (which presupposes the agent actually listened to the audio track) before generation.

    Deliberately scoped to human_demo / human_voiceover only. It does NOT fire on
    visual_product_texture templates that merely contain an incidental lifestyle person
    (e.g. a drink ad), so it will not false-positive on those.
    """
    brief = prepared.rewrite_brief
    resolved = _resolved_template_profile(prepared.viral_analysis)
    is_human_presenter = (
        brief.template_profile in {"human_demo", "human_voiceover"}
        or resolved.profile in {"human_demo", "human_voiceover"}
    )
    if not is_human_presenter:
        return ""
    # audio_track_confirmed lives on the raw analysis profile (the resolved one drops it).
    if prepared.viral_analysis.template_profile.audio_track_confirmed:
        return ""
    if language == "en":
        return (
            "Generation is blocked before Seedance because this is a human-presenter template "
            "but whether the audio track contains voiceover (human_demo vs human_voiceover) is not confirmed. "
            "Listen to the audio track (use scripts/extract_video_frames.py --with-audio, which exports audio_track.m4a), "
            "expose the demo/voiceover choice in the brief for the user to decide, then set "
            "template_profile.audio_track_confirmed = true before continuing."
        )
    return (
        "已在提交 Seedance 前阻断：这是真人出镜模板，但音轨是否含口播（human_demo vs human_voiceover）尚未确认。"
        "请先听音轨（用 scripts/extract_video_frames.py --with-audio，会导出 audio_track.m4a），"
        "在 brief 里暴露 demo/voiceover 选择交用户定；确认后把 template_profile.audio_track_confirmed 置真再继续。"
    )


def generation_contract_blocking_message(prepared: PreparedRewrite, *, language: str = "zh") -> str:
    """Final gate before Seedance: block prompt/package contradictions, not just missing keys."""
    audio_issue = profile_audio_unresolved_blocking_message(prepared, language=language)
    if audio_issue:
        return audio_issue
    voice_issue = voice_language_blocking_message(prepared, language=language)
    if voice_issue:
        return voice_issue
    person_issue = person_context_blocking_message(prepared, language=language)
    if person_issue:
        return person_issue
    brief = prepared.rewrite_brief
    prompt = prepared.prompt_preview.full_prompt or prepared.rewrite_plan.generation_prompt.prompt
    storyboard_text = "\n".join(
        f"{shot.visual_instruction}\n{shot.voiceover}" for shot in prepared.rewrite_plan.rewritten_storyboard.shots
    )
    combined = f"{prompt}\n{storyboard_text}"
    if brief.template_profile == "visual_product_texture":
        forbidden_visual_voice = ["原创口播式讲解节奏", "人物使用与模板相同语言的原创口播", "lip sync", "VOICEOVER LANGUAGE LOCK"]
        hit = next((item for item in forbidden_visual_voice if item in combined), "")
        if hit:
            if language == "en":
                return (
                    "Generation is blocked before Seedance because a visual_product_texture template contains voiceover/lip-sync hard constraints. "
                    f"Remove the conflicting prompt fragment first: {hit}"
                )
            return f"已在提交 Seedance 前阻断：视觉质感型模板不应包含口播/口型同步硬约束。请先移除冲突片段：{hit}"
    voice_kind = _spoken_language_kind(_template_voice_language_prompt_label(brief))
    if voice_kind == "en":
        forbidden = ["原创中文短句", "中文导购式表达", "中文口播", "original Chinese presenter-style wording", "Chinese voiceover"]
        hit = next((item for item in forbidden if item in combined), "")
        if hit:
            if language == "en":
                return (
                    "Generation is blocked before Seedance because the template voiceover language is English but the prompt still contains Chinese-voiceover instructions. "
                    f"Conflicting fragment: {hit}"
                )
            return f"已在提交 Seedance 前阻断：模板口播语言是 English，但 prompt 仍包含中文口播指令：{hit}"
    if voice_kind == "zh":
        forbidden = ["English presenter-style wording", "English voiceover-style explanatory rhythm", "英文口播"]
        hit = next((item for item in forbidden if item in combined), "")
        if hit:
            if language == "en":
                return (
                    "Generation is blocked before Seedance because the template voiceover language is Chinese Mandarin but the prompt still contains English-voiceover instructions. "
                    f"Conflicting fragment: {hit}"
                )
            return f"已在提交 Seedance 前阻断：模板口播语言是中文普通话，但 prompt 仍包含英文口播指令：{hit}"
    return ""


def _sanitize_voice_language_drift(text: str, brief: RewriteBrief | None) -> str:
    if not text or not brief or not _wants_template_voice_from_brief(brief):
        return text
    language_label = _template_voice_language_prompt_label(brief)
    kind = _spoken_language_kind(language_label)
    result = text
    if kind == "en":
        replacements = {
            "use original Chinese presenter-style wording": "use original English presenter-style wording",
            "Chinese presenter-style wording": "English presenter-style wording",
            "Chinese voiceover": "English voiceover",
            "中文口播": "英文口播",
            "中文短句": "英文短句",
            "原创中文短句服务目标受众": "原创英文短句，保持模板口播语言",
            "原创中文导购式表达": "原创英文导购式表达",
            "使用原创中文短句服务目标受众": "使用原创英文短句，保持模板口播语言",
            "使用原创中文导购式表达": "使用原创英文导购式表达",
        }
    elif kind == "zh":
        replacements = {
            "English voiceover": "Chinese Mandarin voiceover",
            "English presenter-style wording": "Chinese Mandarin presenter-style wording",
            "英文口播": "中文普通话口播",
        }
    else:
        replacements = {
            "use original Chinese presenter-style wording": "use original wording in the same spoken language as the template",
            "Chinese presenter-style wording": "same-language presenter-style wording",
            "Chinese voiceover": "same-language voiceover",
            "中文口播": "与模板相同语言的口播",
            "中文短句": "与模板相同语言的短句",
            "原创中文短句服务目标受众": "与模板相同语言的原创口播，不根据目标受众改语言",
            "原创中文导购式表达": "与模板相同语言的原创导购式表达",
        }
    for source, target in replacements.items():
        result = result.replace(source, target)
    return result


def _wants_template_voice_from_brief(brief: RewriteBrief) -> bool:
    return brief.template_profile == "human_voiceover" or bool(brief.template_spoken_language)


def _has_positive_voiceover(text: str) -> bool:
    positive_markers = [
        "存在口播",
        "有口播",
        "自然口播",
        "口播讲解",
        "口播式讲解",
        "博主自然口播",
        "人声讲解",
        "对镜讲解",
        "开口介绍",
        "开口讲解",
        "spoken language",
        "voiceover language",
        "speaking to camera",
    ]
    if _has_any(text, positive_markers):
        return True
    generic_markers = ["口播", "人声", "讲解", "旁白", "开口", "对镜介绍", "voiceover", "spoken"]
    if not _has_any(text, generic_markers):
        return False
    negative_markers = [
        "无口播",
        "无旁白",
        "无人声",
        "无台词",
        "不存在口播",
        "没有口播",
        "没有旁白",
        "无任何口播",
        "全程无口播",
        "no voiceover",
        "no spoken",
        "no speech",
    ]
    return not _has_any(text.lower(), negative_markers)


def _resolved_template_profile(analysis: VideoAnalysis) -> TemplateProfile:
    profile = analysis.template_profile
    if profile.profile != "unknown" and profile.primary_transfer_slots:
        return profile
    text = _all_analysis_text(analysis)
    has_voiceover = profile.has_voiceover or (
        bool(analysis.spoken_language) and not _is_absent_or_unknown(analysis.spoken_language)
    ) or _has_positive_voiceover(text)
    has_platform = profile.has_platform_cta or _has_any(text, ["TikTok", "账号", "搜索栏", "结束页", "引导页", "平台logo", "platform"])
    has_text = profile.has_subtitles_or_text or bool(analysis.subtitle_state or analysis.subtitle_messages) or _has_any(
        text, ["字幕", "caption", "captions", "水印", "文字贴片", "账号", "搜索栏"]
    )
    has_human = profile.has_human or _has_any(text, ["博主", "真人", "人物", "模特", "女性", "男性", "人脸", "面部", "表情", "眼神", "看向镜头", "微笑"])
    has_face = profile.has_visible_face or _has_any(text, ["人脸", "面部", "脸部", "表情", "眼神", "看向镜头", "微笑"])
    has_real_scene = profile.has_real_scene or bool(analysis.scene_details) or _has_any(
        text, ["店内", "试衣间", "服装店", "家中", "厨房", "客厅", "地板", "墙面", "射灯", "挂衣杆", "服装陈列", "空间纵深", "真实场景"]
    )
    fashion_demo = _has_any(text, ["女装", "连衣裙", "上衣", "穿搭", "试穿", "版型", "挂样", "衣架", "裙摆", "领口", "模特"])
    product_texture = _has_any(text, ["液体", "倒入", "冰块", "果汁", "饮品", "食品", "产品静物", "微距", "质感", "原料", "水珠", "光影"])
    if has_voiceover and has_human:
        profile_name = "human_voiceover"
    elif has_human and fashion_demo:
        profile_name = "human_demo"
    elif has_platform and not (product_texture or fashion_demo):
        profile_name = "platform_cta"
    elif product_texture:
        profile_name = "visual_product_texture"
    elif has_platform:
        profile_name = "mixed"
    else:
        profile_name = profile.profile if profile.profile != "unknown" else "visual_product_texture"
    slots = []
    if product_texture or profile_name == "visual_product_texture":
        slots.extend(["shot_order", "camera_pacing", "product_state", "texture_satisfaction", "scene_mood"])
    if profile_name in {"human_demo", "human_voiceover"}:
        slots.extend(["person_framing", "person_action", "broad_person_appearance_context", "real_scene_context"])
    if profile_name == "human_voiceover":
        slots.extend(["spoken_language", "voiceover_rhythm", "lip_sync"])
    if has_platform:
        slots.append("cta_function_only")
    if has_text:
        slots.append("forbidden_text_carryover")
    return TemplateProfile(
        profile=profile_name,
        has_human=has_human,
        has_voiceover=has_voiceover,
        has_visible_face=has_face,
        has_real_scene=has_real_scene,
        has_platform_cta=has_platform,
        has_subtitles_or_text=has_text,
        should_preserve_person_context=profile_name in {"human_demo", "human_voiceover"},
        should_preserve_voice_language=profile_name == "human_voiceover",
        should_preserve_scene_context=profile_name in {"human_demo", "human_voiceover"},
        should_preserve_visual_product_texture=True,
        primary_transfer_slots=list(dict.fromkeys(slots)),
    )


def _template_transfer_cues(analysis: VideoAnalysis) -> tuple[list[str], list[str]]:
    """Promote fragile template signals into explicit borrow/risk controls."""
    text = _all_analysis_text(analysis)
    profile = _resolved_template_profile(analysis)
    language = "zh" if _contains_cjk(text) else "en"
    cues: list[str] = []
    risks: list[str] = []
    if language == "en":
        cues.append(f"Template type: {_profile_label(profile.profile, language='en')}; active transfer slots: {_join_slots(profile.primary_transfer_slots, limit=10, language='en')}")
    else:
        cues.append(f"模板类型：{_profile_label(profile.profile)}；复刻槽位：{_join_slots(profile.primary_transfer_slots, limit=10)}")
    if profile.profile == "visual_product_texture":
        cues.append("Pure visual product-texture structure: preserve shot order, edit rhythm, product-state changes, texture satisfaction, scene mood, and music mood" if language == "en" else "模板纯视觉商品质感结构：重点复刻镜头顺序、转场节奏、产品状态变化、质感爽点、场景氛围和音乐情绪")
        risks.append("Do not automatically add voiceover, person/ethnicity context, lip sync, or subtitle logic to a pure visual product template unless the user explicitly asks" if language == "en" else "纯视觉商品模板不要自动添加真人口播、人种/人物语境、口型同步或字幕逻辑，除非用户明确要求")
    if profile.should_preserve_person_context:
        cues.append("Human-presenter trust structure: keep a newly generated front-facing presenter, natural expression, eye contact, and to-camera display posture; do not copy the template person's identity" if language == "en" else "模板真人出镜信任结构：保留新生成人物的正面出镜、自然表情、眼神交流和对镜展示姿态；不复刻模板人物身份")
        risks.append("Do not downgrade a human-presenter template into a faceless model, back view, body-only crop, or pure still-life product video" if language == "en" else "不要把模板真人出镜误改成无脸模特、背影、只拍身体局部或纯静物展示")
    if profile.should_preserve_person_context and analysis.person_appearance_context:
        cues.append(f"Template person context: preserve the same broad person appearance / market visual context ({analysis.person_appearance_context}); do not copy exact identity or face" if language == "en" else f"模板人物外观语境：保持与模板同类的人物外观/市场视觉语境（{analysis.person_appearance_context}）；不复刻具体身份或脸")
        risks.append("Do not let the generated person's broad ethnicity, age range, styling, or market context drift away from the template" if language == "en" else "不要让生成人物的人种、年龄段、妆发气质或市场语境相对模板自由漂移")
    if profile.should_preserve_voice_language:
        cues.append("Voiceover-style creator structure: preserve to-camera explanation rhythm, mouth movement, gesture timing, and natural pauses; voiceover wording must be original" if language == "en" else "模板口播式种草结构：保留对镜讲解节奏、开口口型、手势指向和自然停顿；口播内容必须原创，不复刻模板原声或文案")
        risks.append("Do not downgrade a voiceover template into silent BGM-only display; if speech is unstable, keep visible to-camera explaining gestures" if language == "en" else "不要把含口播的模板自动降级成纯 BGM 静默展示；若不生成清晰口播，也要保留明显对镜讲解动作")
    spoken_language = _infer_template_spoken_language(analysis)
    if profile.should_preserve_voice_language and spoken_language:
        cues.append(f"Template spoken language: generated voiceover must use the same language as the template ({spoken_language}) with original wording; do not translate or switch languages" if language == "en" else f"模板口播语言：新生成口播必须使用与模板相同的语言（{spoken_language}），内容原创，不翻译成其他语言")
        risks.append("Do not switch the template spoken language to English, Chinese, or any default ad language" if language == "en" else "不要把模板口播语言自动切换成英文、中文或其他默认广告语言")
    elif profile.should_preserve_voice_language:
        cues.append("Template spoken language must be confirmed before generation; do not choose a voiceover language from the UI language or target audience" if language == "en" else "模板口播语言必须在生成前确认；不能根据前台语言或目标人群自动选择口播语言")
        risks.append("Block generation or ask the user to confirm the template spoken language if the human-voiceover template language is unknown" if language == "en" else "如果真人口播模板的语言未知，应先阻断生成或询问用户确认模板口播语言")
    if profile.should_preserve_scene_context and (analysis.scene_details or _has_any(text, ["店内", "试衣间", "服装店", "地板", "墙面", "射灯", "挂衣杆", "服装陈列", "空间纵深"])):
        scene = _join_items_for_language(analysis.scene_details, limit=8, language=language)
        cues.append(f"Real-scene structure: preserve the template's lived-in spatial texture and background layers, such as {scene}" if language == "en" else f"模板真实场景结构：保留模板的真实空间质感和背景层次，如 {scene}")
        risks.append("Do not let a white-background or studio product image overwrite the template's real background; the scene should preserve trust and use context" if language == "en" else "不要被商品图白底或棚拍信息覆盖模板真实背景；场景应服务模板的信任感和使用语境")
    if profile.has_platform_cta:
        cues.append("Template ending is a CTA close, but account pages, platform UI, watermarks, and search bars must not carry over" if language == "en" else "模板结尾功能是 CTA 收口，但不能继承账号页、平台 UI、水印或搜索栏")
        risks.append("Do not end with blank, white, black, plain-color fade, or platform page; the final second must keep the product visible" if language == "en" else "不要用空白、白屏、黑屏、纯色淡出或平台引导页结尾；最后一秒必须保留商品主体可见")
    if profile.has_subtitles_or_text:
        risks.append("Default output must not generate subtitles, automatic captions, voiceover captions, on-screen text, watermarks, platform stickers, prices, or shopping UI, even when voiceover is present" if language == "en" else "默认严禁生成字幕、自动 captions、口播字幕、屏幕文字、水印、平台贴纸、价格或购物 UI；即使有口播也不能自动加字幕")
    return list(dict.fromkeys(cues)), list(dict.fromkeys(risks))


def _wants_template_human_face(request: RewriteRequest, brief: RewriteBrief) -> bool:
    text = "\n".join([request.product_context, *request.extra_constraints, *brief.borrowable_elements, *brief.risks])
    return _has_any(text, ["真人博主", "真人出镜", "正面出镜", "人脸", "面部", "表情", "眼神交流", "看向镜头"])


def _wants_template_scene(request: RewriteRequest, brief: RewriteBrief) -> bool:
    text = "\n".join([request.product_context, *request.extra_constraints, *brief.borrowable_elements, *brief.risks])
    return _has_any(text, ["真实女装店", "真实场景", "试衣间背景", "服装店", "挂衣架", "轨道射灯", "背景结构", "空间纵深"])


def _wants_template_voice(request: RewriteRequest, brief: RewriteBrief) -> bool:
    if brief.template_profile == "human_voiceover" or bool(brief.template_spoken_language):
        return True
    user_text = "\n".join([request.product_context, *request.extra_constraints])
    if _has_positive_voiceover(user_text):
        return True
    if brief.template_profile in {"visual_product_texture", "human_demo", "platform_cta"}:
        return False
    template_text = "\n".join(brief.borrowable_elements)
    return _has_positive_voiceover(template_text)


def _normalized_extra_constraints(request: RewriteRequest, brief: RewriteBrief | None) -> list[str]:
    constraints = list(request.extra_constraints)
    if not brief or not _wants_template_human_face(request, brief):
        return [_sanitize_text_for_template_transfer(item, request, brief) for item in constraints] if brief else constraints
    normalized: list[str] = []
    for item in constraints:
        if _has_any(item, ["避免生成清晰可识别真人脸", "无清晰面部", "禁止出现可识别真人面部"]):
            normalized.append("人物必须是新生成的非特定身份，不复刻模板人物；但可以保留可见正面脸部、自然表情和眼神交流，用于复刻模板真人种草信任感")
        else:
            normalized.append(_sanitize_text_for_template_transfer(item, request, brief))
    return list(dict.fromkeys(normalized))


def _sanitize_text_for_template_transfer(text: str, request: RewriteRequest, brief: RewriteBrief) -> str:
    result = text
    if _wants_template_human_face(request, brief):
        result = result.replace("无清晰面部的年轻女性", "新的非特定年轻女性博主正面出镜，脸部、自然表情和眼神交流可见，")
        result = result.replace("无清晰面部的模特", "新的非特定模特正面出镜，脸部、自然表情和眼神交流可见，")
        result = result.replace("模特为新的非特定年轻女性博主正面出镜，脸部、自然表情和眼神交流可见，身形", "模特为新的非特定年轻女性博主正面出镜，脸部、自然表情和眼神交流可见")
        result = result.replace("禁止出现可识别真人面部", "不要复刻模板中具体人物身份；可以保留新生成人物的可见脸部、自然表情和眼神交流")
        result = result.replace("避免生成清晰可识别真人脸", "不要复刻模板中具体人物身份；可以保留新生成人物的可见脸部、自然表情和眼神交流")
    if _wants_template_scene(request, brief):
        result = result.replace("站在极简纯白试衣间内", "站在真实女装店/试衣间内，背景可见浅木地板、白墙、黑色轨道射灯、左右挂衣架或服装陈列和空间纵深")
        result = result.replace("极简纯白试衣间", "真实女装店/试衣间，包含浅木地板、白墙、黑色轨道射灯、左右挂衣架或服装陈列和空间纵深")
        result = result.replace("纯白无影棚", "真实女装店/试衣间背景")
        result = result.replace("空白背景", "真实女装店/试衣间背景")
    if _wants_template_voice(request, brief):
        result = result.replace("全程仅保留轻快BGM，无任何口播语音", "保留原创轻快背景音乐，并保留原创口播式对镜讲解节奏；不复刻模板原声、原文案或账号信息")
        result = result.replace("无任何口播语音", "保留原创口播式对镜讲解节奏，不复刻模板原声或文案")
        result = result.replace("无口播无字幕", "可有原创口播式讲解动作/口播节奏，但不出现字幕")
        result = _sanitize_voice_language_drift(result, brief)
    result = result.replace("不要使用柔和淡出到空画面作为结尾", "不要使用任何淡出到空画面的结尾")
    result = result.replace("镜头定格2秒后缓慢柔和淡出", "镜头定格到结束，最后一秒仍保持人物和商品完整可见，不淡出到空白")
    result = result.replace("缓慢柔和淡出", "保持商品主体可见直至结束")
    result = result.replace("柔和淡出", "保持商品主体可见直至结束")
    return result


def _sanitize_nested_prompt_value(value, request: RewriteRequest, brief: RewriteBrief):
    if isinstance(value, str):
        return _sanitize_text_for_template_transfer(value, request, brief)
    if isinstance(value, list):
        return [_sanitize_nested_prompt_value(item, request, brief) for item in value]
    if isinstance(value, dict):
        return {key: _sanitize_nested_prompt_value(item, request, brief) for key, item in value.items()}
    return value


def _media_block(value: str, media_type: str) -> dict:
    raise RuntimeError(
        "ModelArk/Seed media analysis has been removed. "
        "Use the host agent to analyze the template video and product image, then pass a prepared JSON to the runner."
    )


def _print_analysis_readout(title: str, analysis: VideoAnalysis, *, language: str = "zh") -> None:
    print(f"\n{title}")
    if language == "en":
        print("\n1. Basic Media Facts")
        if analysis.basic_info:
            print(analysis.basic_info)
        profile = _resolved_template_profile(analysis)
        if profile.profile != "unknown":
            print(f"Template type: {_profile_label(profile.profile, language='en')}; transfer slots: {_join_slots(profile.primary_transfer_slots, limit=10, language='en')}")
        if analysis.audio_facts:
            print(f"Audio: {analysis.audio_facts}")
        if analysis.camera_and_editing:
            print(f"Editing and camera: {analysis.camera_and_editing}")

        print("\n2. Template Flow And Core Satisfaction" if analysis.video_label == "viral_video" else "\n2. Product Image Information And Anchors")
        print(f"- Creative type: {analysis.summary.creative_type}")
        print(f"- Product category: {analysis.summary.product_category}")
        print(f"- Main value prop: {analysis.summary.main_value_prop}")
        if analysis.shot_sequence:
            print(f"- Shot/action order: {_join_items_for_language(analysis.shot_sequence, limit=10, language='en')}")
        if analysis.product_selling_points:
            print(f"- Selling points: {_join_items_for_language(analysis.product_selling_points, language='en')}")
        if analysis.product_satisfaction_points:
            print(f"- Satisfaction points: {_join_items_for_language(analysis.product_satisfaction_points, language='en')}")
        if analysis.core_satisfaction_mechanism:
            print(f"- Core satisfaction mechanism: {analysis.core_satisfaction_mechanism}")

        print("\n3. Scene, People, And Visual Focus")
        if analysis.material_type:
            print(f"- Material type: {analysis.material_type}")
        if analysis.scene_and_people:
            print(f"- Scene/people: {_join_items_for_language(analysis.scene_and_people, language='en')}")
        if analysis.scene_details:
            print(f"- Scene details: {_join_items_for_language(analysis.scene_details, limit=8, language='en')}")
        if analysis.subject_framing:
            print(f"- Framing: {analysis.subject_framing}")
        if analysis.person_appearance_context:
            print(f"- Person appearance context: {analysis.person_appearance_context}")
        if analysis.spoken_language:
            print(f"- Spoken language: {analysis.spoken_language}")
        if analysis.subtitle_state:
            print(f"- Subtitle/text state: {analysis.subtitle_state}")
        if analysis.subtitle_messages:
            print(f"- Subtitle/voiceover messages: {_join_items_for_language(analysis.subtitle_messages, language='en')}")

        print("\n4. Every-5-Second Detailed Breakdown")
        if analysis.five_second_windows:
            for window in analysis.five_second_windows:
                print(f"{window.start_sec:.1f}-{window.end_sec:.1f}s:")
                print(f"- Material type: {window.material_type or 'unknown'}")
                print(f"- Shot/composition: {window.shot_type or 'unknown'}; {window.composition or 'unknown'}")
                print(f"- Camera: {window.camera or window.camera_position or 'unknown'}; movement={window.camera_movement or 'unknown'}")
                print(f"- Scene: {window.scene or 'unknown'}; details={_join_items_for_language(window.scene_details, limit=5, language='en')}")
                print(f"- Actions: {_join_items_for_language(window.action_sequence, limit=6, language='en')}")
                print(f"- Product presence: {window.product_presence or 'unknown'}")
                print(f"- Materials to capture: {_join_items_for_language(window.materials_to_capture, limit=6, language='en')}")
                print(f"- Selling points: {_join_items_for_language(window.product_selling_points, limit=5, language='en')}")
                print(f"- Satisfaction points: {_join_items_for_language(window.product_satisfaction_points, limit=5, language='en')}")
                subtitle_bits = [window.subtitle_text, window.voiceover_text, window.audio_state]
                print(f"- Subtitles/voice/audio: {_join_items_for_language(subtitle_bits, limit=3, language='en')}")
                print(f"- Borrowable elements: {_join_items_for_language(window.borrowable_function, limit=5, language='en')}")
                print(f"- Forbidden carryover: {_join_items_for_language(window.forbidden_carryover, limit=5, language='en')}")
                if window.replication_notes:
                    print(f"- Replication notes: {_join_items_for_language(window.replication_notes, limit=5, language='en')}")
        else:
            print("- No window analysis generated.")

        print("\n5. Script For Rewriting Into The New Product Video")
        if analysis.replication_framework:
            print(f"- Replication framework: {analysis.replication_framework}")
        if analysis.extend_to_15s_plan:
            print(f"- 12-15 second extension: {analysis.extend_to_15s_plan}")
        if analysis.replication_script:
            print(f"- Replication script: {analysis.replication_script}")
        return
    print("\n一、视频基础信息")
    if analysis.basic_info:
        print(_zh_display_text(analysis.basic_info))
    profile = _resolved_template_profile(analysis)
    if profile.profile != "unknown":
        print(f"模板类型：{_profile_label(profile.profile)}；复刻槽位：{_join_slots(profile.primary_transfer_slots, limit=10)}")
    if analysis.audio_facts:
        print(f"音频：{_zh_display_text(analysis.audio_facts)}")
    if analysis.camera_and_editing:
        print(f"剪辑与镜头：{_zh_display_text(analysis.camera_and_editing)}")

    print("\n二、模板流程与核心爽点" if analysis.video_label == "viral_video" else "\n二、商品图可用信息与核心锚点")
    print(f"- 创意类型：{_zh_display_text(analysis.summary.creative_type)}")
    print(f"- 产品品类：{_zh_display_text(analysis.summary.product_category)}")
    print(f"- 核心利益：{_zh_display_text(analysis.summary.main_value_prop)}")
    if analysis.shot_sequence:
        print(f"- 镜头/动作顺序：{_join_display_items(analysis.shot_sequence, limit=10)}")
    if analysis.product_selling_points:
        print(f"- 产品卖点：{_join_display_items(analysis.product_selling_points)}")
    if analysis.product_satisfaction_points:
        print(f"- 产品爽点：{_join_display_items(analysis.product_satisfaction_points)}")
    if analysis.core_satisfaction_mechanism:
        print(f"- 核心爽点机制：{_zh_display_text(analysis.core_satisfaction_mechanism)}")

    print("\n三、场景、人物与画面重点")
    if analysis.material_type:
        print(f"- 素材类型：{_zh_display_text(analysis.material_type)}")
    if analysis.scene_and_people:
        print(f"- 场景/人物：{_join_display_items(analysis.scene_and_people)}")
    if analysis.scene_details:
        print(f"- 场景细节：{_join_display_items(analysis.scene_details, limit=8)}")
    if analysis.subject_framing:
        print(f"- 人物/产品构图：{_zh_display_text(analysis.subject_framing)}")
    if analysis.person_appearance_context:
        print(f"- 人物外观语境：{_zh_display_text(analysis.person_appearance_context)}")
    if analysis.spoken_language:
        print(f"- 口播语言：{_zh_display_text(analysis.spoken_language)}")
    if analysis.subtitle_state:
        print(f"- 字幕/文字状态：{_zh_display_text(analysis.subtitle_state)}")
    if analysis.subtitle_messages:
        print(f"- 字幕/口播信息：{_join_display_items(analysis.subtitle_messages)}")

    print("\n四、每 5 秒窗口精细拆解")
    if analysis.five_second_windows:
        for window in analysis.five_second_windows:
            print(f"{window.start_sec:.1f}-{window.end_sec:.1f}s：")
            print(f"- 素材类型：{_zh_display_text(window.material_type) or '未识别'}")
            print(f"- 镜头/构图：{_zh_display_text(window.shot_type) or '未识别'}；{_zh_display_text(window.composition) or '未识别'}")
            print(f"- 摄影机：{_zh_display_text(window.camera or window.camera_position) or '未识别'}；运动={_zh_display_text(window.camera_movement) or '未识别'}")
            print(f"- 场景：{_zh_display_text(window.scene) or '未识别'}；细节={_join_display_items(window.scene_details, limit=5)}")
            print(f"- 动作：{_join_display_items(window.action_sequence, limit=6)}")
            print(f"- 产品出现方式：{_zh_display_text(window.product_presence) or '未识别'}")
            print(f"- 可抓取素材：{_join_display_items(window.materials_to_capture, limit=6)}")
            print(f"- 卖点：{_join_display_items(window.product_selling_points, limit=5)}")
            print(f"- 爽点：{_join_display_items(window.product_satisfaction_points, limit=5)}")
            subtitle_bits = [window.subtitle_text, window.voiceover_text, window.audio_state]
            print(f"- 字幕/口播/音频：{_join_display_items(subtitle_bits, limit=3)}")
            print(f"- 可复刻元素：{_join_display_items(window.borrowable_function, limit=5)}")
            print(f"- 禁止继承元素：{_join_display_items(window.forbidden_carryover, limit=5)}")
            if window.replication_notes:
                print(f"- 复刻备注：{_join_display_items(window.replication_notes, limit=5)}")
    else:
        print("- 未生成窗口分析。")

    print("\n五、复刻成新商品视频的生成脚本")
    if analysis.replication_framework:
        print(f"- 复刻框架：{_zh_display_text(analysis.replication_framework)}")
    if analysis.extend_to_15s_plan:
        print(f"- 12-15 秒延展：{_zh_display_text(analysis.extend_to_15s_plan)}")
    if analysis.replication_script:
        print(f"- 复刻脚本：{_zh_display_text(analysis.replication_script)}")


def _print_plan_readout(plan: RewritePlan, *, language: str = "zh") -> None:
    if language == "en":
        print("\nPre-generation Rewrite Plan")
        print(f"- Strategy: {plan.rewrite_strategy.strategy_summary}")
        print(f"- Keep from product image: {_join_items_for_language(plan.rewrite_strategy.keep_from_source, language='en')}")
        print(f"- Borrow from template: {_join_items_for_language(plan.rewrite_strategy.borrow_from_viral, language='en')}")
        print("- Shot script:")
        for shot in plan.rewritten_storyboard.shots:
            print(f"  - {shot.shot_index}. {shot.role} / {shot.duration_sec:.1f}s: {shot.visual_instruction}")
        return
    print("\n生成前复刻方案")
    print(f"- 策略：{plan.rewrite_strategy.strategy_summary}")
    print(f"- 保留商品图：{_join_items(plan.rewrite_strategy.keep_from_source)}")
    print(f"- 借模板：{_join_items(plan.rewrite_strategy.borrow_from_viral)}")
    print("- 镜头脚本：")
    for shot in plan.rewritten_storyboard.shots:
        print(
            f"  - {shot.shot_index}. {shot.role} / {shot.duration_sec:.1f}s："
            f"{shot.visual_instruction}"
        )


def _print_compact_template_understanding(prepared: PreparedRewrite, *, language: str = "zh") -> None:
    analysis = prepared.viral_analysis
    brief = prepared.rewrite_brief
    if language == "en":
        print("\nTemplate Video Understanding Summary")
        profile = _resolved_template_profile(analysis)
        print(f"- Template type: {_profile_label(brief.template_profile or profile.profile, language='en')}; slots: {_join_slots(brief.template_profile_slots or profile.primary_transfer_slots, limit=10, language='en')}")
        facts: list[str] = []
        if analysis.duration_sec is not None:
            facts.append(f"about {analysis.duration_sec:.1f}s")
        if analysis.fps is not None:
            facts.append(f"{analysis.fps:g}fps")
        if analysis.total_frames is not None:
            facts.append(f"{analysis.total_frames} frames")
        if analysis.basic_info:
            facts.append(analysis.basic_info)
        if facts:
            print(f"- Basic facts: {_join_items_for_language(facts, limit=4, language='en')}")
        if analysis.audio_facts:
            print(f"- Audio: {analysis.audio_facts}")
        if analysis.camera_and_editing:
            print(f"- Editing/camera: {analysis.camera_and_editing}")
        if brief.template_structure:
            print(f"- Template flow: {_join_items_for_language(brief.template_structure, limit=6, language='en')}")
        if brief.template_core_satisfaction_mechanism:
            print(f"- Core satisfaction mechanism: {brief.template_core_satisfaction_mechanism}")
        if brief.template_five_second_summary:
            print("- Every-5-second summary:")
            for item in brief.template_five_second_summary[:3]:
                print(f"  - {item}")
        if brief.borrowable_elements:
            print(f"- Borrowable elements: {_join_items_for_language(brief.borrowable_elements, limit=6, language='en')}")
        if brief.forbidden_template_elements:
            print(f"- Forbidden carryover: {_join_items_for_language(brief.forbidden_template_elements, limit=6, language='en')}")
        return
    print("\n模板视频理解摘要")
    profile = _resolved_template_profile(analysis)
    print(f"- 模板类型：{_profile_label(brief.template_profile or profile.profile)}；槽位：{_join_slots(brief.template_profile_slots or profile.primary_transfer_slots, limit=10)}")
    facts: list[str] = []
    if analysis.duration_sec is not None:
        facts.append(f"约 {analysis.duration_sec:.1f}s")
    if analysis.fps is not None:
        facts.append(f"{analysis.fps:g}fps")
    if analysis.total_frames is not None:
        facts.append(f"{analysis.total_frames} 帧")
    if analysis.basic_info:
        facts.append(analysis.basic_info)
    if facts:
        print(f"- 基础信息：{_join_items(facts, limit=4)}")
    if analysis.audio_facts:
        print(f"- 音频：{analysis.audio_facts}")
    if analysis.camera_and_editing:
        print(f"- 剪辑/镜头：{analysis.camera_and_editing}")
    if brief.template_structure:
        print(f"- 模板流程：{_join_items(brief.template_structure, limit=6)}")
    if brief.template_core_satisfaction_mechanism:
        print(f"- 核心爽点：{brief.template_core_satisfaction_mechanism}")
    if brief.template_five_second_summary:
        print("- 每 5 秒摘要：")
        for item in brief.template_five_second_summary[:3]:
            print(f"  - {item}")
    if brief.borrowable_elements:
        print(f"- 可借元素：{_join_items(brief.borrowable_elements, limit=6)}")
    if brief.forbidden_template_elements:
        print(f"- 禁止继承：{_join_items(brief.forbidden_template_elements, limit=6)}")


def _print_conflict_context(prepared: PreparedRewrite, *, language: str = "zh") -> None:
    brief = prepared.rewrite_brief
    strategy = prepared.rewrite_plan.rewrite_strategy
    if language == "en":
        print("\nRewrite Evidence And Risks")
        print(f"- Product-image evidence: {brief.source_product_identity or 'source image is the truth'}; {_join_items_for_language(brief.source_product_anchors, limit=8, language='en')}")
        print(f"- Template borrow items: {_join_items_for_language(strategy.borrow_from_viral, limit=8, language='en')}")
        print(f"- Template info that must not carry over: {_join_items_for_language(brief.forbidden_template_elements, limit=8, language='en')}")
        print(f"- Risks/conflicts: {_join_items_for_language([*brief.risks, *strategy.risk_controls], limit=8, language='en')}")
        return
    print("\n复刻依据和风险")
    print(f"- 商品图依据：{brief.source_product_identity or '以商品图为准'}；{_join_items(brief.source_product_anchors, limit=8)}")
    print(f"- 模板借用项：{_join_items(strategy.borrow_from_viral, limit=8)}")
    print(f"- 不能带走的模板信息：{_join_items(brief.forbidden_template_elements, limit=8)}")
    print(f"- 风险/冲突：{_join_items([*brief.risks, *strategy.risk_controls], limit=8)}")


def _window_summary(analysis: VideoAnalysis) -> list[str]:
    summaries: list[str] = []
    for window in analysis.five_second_windows:
        bits = [
            f"{window.start_sec:.1f}-{window.end_sec:.1f}s",
            window.material_type,
            window.shot_type or "镜头",
            window.composition,
            window.scene,
            _join_items(window.action_sequence, limit=4),
            _join_items(window.product_satisfaction_points, limit=3),
        ]
        summaries.append(" / ".join(bit for bit in bits if bit and bit != "无"))
    return summaries


def _build_rewrite_brief(request: RewriteRequest, viral_analysis: VideoAnalysis, source_analysis: VideoAnalysis, plan: RewritePlan) -> RewriteBrief:
    profile = _resolved_template_profile(viral_analysis)
    template_cues, transfer_risks = _template_transfer_cues(viral_analysis)
    if _is_en(request):
        forbidden_template_elements = [
            f"Template product category: {viral_analysis.summary.product_category}",
            f"Template main value prop: {viral_analysis.summary.main_value_prop}",
            "Template brand, packaging, color naming, ingredients, prices, subtitles, and shopping prompts",
        ]
        risks = [
            "Template product semantics leaking into the target product",
            "Model inventing claims not proven by the source image",
            "Generated subtitles, stickers, price tags, or shopping prompts",
            "Source product appearance drifting across shots",
            *transfer_risks,
        ]
        uncertain_or_unproven = [
            "Any function, efficacy, parameter, or brand promise not directly visible in the source material must not become a hard selling point.",
        ]
    else:
        forbidden_template_elements = [
            f"模板产品品类：{viral_analysis.summary.product_category}",
            f"模板主卖点：{viral_analysis.summary.main_value_prop}",
            "模板里的品牌、包装、颜色命名、食材、价格、字幕和购物提示",
        ]
        risks = [
            "模板产品语义混入目标商品",
            "模型脑补素材中无法证明的卖点",
            "生成字幕、贴纸、价格标签或购物提示",
            "source 商品外观在多镜头中不一致",
            *transfer_risks,
        ]
        uncertain_or_unproven = [
            "未在源素材中直接出现的功能、功效、参数和品牌承诺不能作为强卖点。",
        ]
    source_product_anchors = [
        source_analysis.summary.product_category,
        source_analysis.summary.main_value_prop,
        *source_analysis.product_selling_points,
        *source_analysis.scene_and_people[:2],
    ]
    return RewriteBrief(
        template_structure=viral_analysis.shot_sequence or [segment.summary for segment in viral_analysis.segments],
        template_five_second_summary=_window_summary(viral_analysis),
        template_director_analysis=[
            viral_analysis.basic_info,
            viral_analysis.audio_facts,
            viral_analysis.camera_and_editing,
            viral_analysis.material_type,
            viral_analysis.subject_framing,
            viral_analysis.person_appearance_context,
            viral_analysis.spoken_language,
            viral_analysis.subtitle_state,
            viral_analysis.replication_framework,
        ],
        template_core_satisfaction_mechanism=viral_analysis.core_satisfaction_mechanism,
        template_extend_to_15s_plan=viral_analysis.extend_to_15s_plan,
        template_person_appearance_context=viral_analysis.person_appearance_context if profile.should_preserve_person_context else "",
        template_spoken_language=viral_analysis.spoken_language if profile.should_preserve_voice_language else "",
        template_subtitle_state=viral_analysis.subtitle_state,
        template_profile=profile.profile,
        template_profile_slots=profile.primary_transfer_slots,
        borrowable_elements=list(dict.fromkeys([*plan.rewrite_strategy.borrow_from_viral, *template_cues])),
        forbidden_template_elements=forbidden_template_elements,
        source_product_identity=source_analysis.summary.product_category,
        source_product_anchors=[item for item in source_product_anchors if item],
        confirmed_selling_points=source_analysis.product_selling_points,
        uncertain_or_unproven_points=uncertain_or_unproven,
        rewrite_strategy=plan.rewrite_strategy.strategy_summary,
        risks=risks,
    )


def _print_brief_readout(brief: RewriteBrief, *, language: str = "zh") -> None:
    if language == "en":
        print("\nAnalytical Creative Brief")
        print(f"- Source product identity: {brief.source_product_identity or 'unknown'}")
        print(f"- Product anchors: {_join_items_for_language(brief.source_product_anchors, limit=8, language='en')}")
        print(f"- Confirmed selling points: {_join_items_for_language(brief.confirmed_selling_points, language='en')}")
        print(f"- Template structure: {_join_items_for_language(brief.template_structure, limit=8, language='en')}")
        print(f"- Every-5-second template summary: {_join_items_for_language(brief.template_five_second_summary, limit=6, language='en')}")
        print(f"- Core satisfaction mechanism: {brief.template_core_satisfaction_mechanism or 'unknown'}")
        print(f"- 12-15 second extension plan: {brief.template_extend_to_15s_plan or 'unknown'}")
        if brief.template_profile:
            print(f"- Template type: {_profile_label(brief.template_profile, language='en')}; slots: {_join_slots(brief.template_profile_slots, limit=10, language='en')}")
        if brief.template_person_appearance_context:
            print(f"- Template person appearance context: {brief.template_person_appearance_context}")
        if brief.template_spoken_language:
            print(f"- Template spoken language: {brief.template_spoken_language}")
        if brief.template_subtitle_state:
            print(f"- Template subtitle/text state: {brief.template_subtitle_state}")
        print(f"- Borrowable elements: {_join_items_for_language(brief.borrowable_elements, language='en')}")
        print(f"- Forbidden template carryover: {_join_items_for_language(brief.forbidden_template_elements, language='en')}")
        print(f"- Uncertain / must not invent: {_join_items_for_language(brief.uncertain_or_unproven_points, language='en')}")
        print(f"- Risks: {_join_items_for_language(brief.risks, language='en')}")
        return
    print("\n分析型创意简报")
    print(f"- 源产品身份：{_zh_display_text(brief.source_product_identity) or '未识别'}")
    print(f"- 产品锚点：{_join_display_items(brief.source_product_anchors, limit=8)}")
    print(f"- 已确认卖点：{_join_display_items(brief.confirmed_selling_points)}")
    print(f"- 模板结构：{_join_display_items(brief.template_structure, limit=8)}")
    print(f"- 每 5 秒模板摘要：{_join_display_items(brief.template_five_second_summary, limit=6)}")
    print(f"- 核心爽点机制：{_zh_display_text(brief.template_core_satisfaction_mechanism) or '未识别'}")
    print(f"- 12-15 秒延展方案：{_zh_display_text(brief.template_extend_to_15s_plan) or '未识别'}")
    if brief.template_profile:
        print(f"- 模板类型：{_profile_label(brief.template_profile)}；槽位：{_join_slots(brief.template_profile_slots, limit=10)}")
    if brief.template_person_appearance_context:
        print(f"- 模板人物外观语境：{_zh_display_text(brief.template_person_appearance_context)}")
    if brief.template_spoken_language:
        print(f"- 模板口播语言：{_zh_display_text(brief.template_spoken_language)}")
    if brief.template_subtitle_state:
        print(f"- 模板字幕/文字状态：{_zh_display_text(brief.template_subtitle_state)}")
    print(f"- 可复刻元素：{_join_display_items(brief.borrowable_elements)}")
    print(f"- 禁止继承模板元素：{_join_display_items(brief.forbidden_template_elements)}")
    print(f"- 不确定/不可脑补：{_join_display_items(brief.uncertain_or_unproven_points)}")
    print(f"- 风险点：{_join_display_items(brief.risks)}")


def _build_prompt_preview_user(request: RewriteRequest, plan: RewritePlan, brief: RewriteBrief | None = None) -> str:
    if _is_en(request):
        lines = [
            "Generation prompt preview (user-readable)",
            f"- Target audience: {request.target_audience}",
            f"- Objective: {request.objective}",
            f"- Product identity / must keep: {request.product_context or 'same as source image'}",
            f"- Output: {request.output_ratio}, {request.output_resolution}",
            f"- Generate audio: {'yes' if request.generate_audio else 'no'}",
            f"- Rewrite strategy: {plan.rewrite_strategy.strategy_summary}",
            f"- Keep from source image: {_join_items_for_language(plan.rewrite_strategy.keep_from_source, language='en')}",
            f"- Borrow from template: {_join_items_for_language(plan.rewrite_strategy.borrow_from_viral, language='en')}",
            f"- Risk controls: {_join_items_for_language(plan.rewrite_strategy.risk_controls, language='en')}",
            "- Shot script:",
        ]
        if brief:
            lines.extend(
                [
                    f"- Confirmed product identity: {brief.source_product_identity or 'source image is the truth'}",
                    f"- Product-image anchors: {_join_items_for_language(brief.source_product_anchors, limit=8, language='en')}",
                    f"- Forbidden template carryover: {_join_items_for_language(brief.forbidden_template_elements, limit=8, language='en')}",
                ]
            )
        for shot in plan.rewritten_storyboard.shots:
            lines.append(f"  {shot.shot_index}. {shot.role} / {shot.duration_sec:.1f}s: {shot.visual_instruction}")
        lines.append("- Forbidden: subtitles, on-screen text, stickers, price tags, shopping prompts, or template product identity leakage.")
        if request.generate_audio:
            lines.append(f"- {_music_prompt(request)}")
        return "\n".join(lines)
    lines = [
        "生成提示词预览（用户可读版）",
        f"- 目标人群：{request.target_audience}",
        f"- 优化目标：{request.objective}",
        f"- 产品身份/必须保留：{request.product_context or '以原始素材为准'}",
        f"- 输出规格：{request.output_ratio}，{request.output_resolution}",
        f"- 是否生成音频：{'是' if request.generate_audio else '否'}",
        f"- 改写策略：{plan.rewrite_strategy.strategy_summary}",
        f"- 保留源素材：{_join_items(plan.rewrite_strategy.keep_from_source)}",
        f"- 借模板：{_join_items(plan.rewrite_strategy.borrow_from_viral)}",
        f"- 风险控制：{_join_items(plan.rewrite_strategy.risk_controls)}",
    "- 镜头脚本：",
    ]
    if brief:
        lines.extend(
            [
                f"- 已确认产品身份：{brief.source_product_identity or '以商品图为准'}",
                f"- 商品图外观锚点：{_join_items(brief.source_product_anchors, limit=8)}",
                f"- 禁止继承模板元素：{_join_items(brief.forbidden_template_elements, limit=8)}",
            ]
        )
    for shot in plan.rewritten_storyboard.shots:
        lines.append(f"  {shot.shot_index}. {shot.role} / {shot.duration_sec:.1f}s：{shot.visual_instruction}")
    lines.append("- 禁止：字幕、屏幕文字、贴纸、价格标签、购物提示、模板产品身份混入。")
    if request.generate_audio:
        lines.append(f"- {_music_prompt(request)}")
    return "\n".join(lines)


def _build_prompt_preview(request: RewriteRequest, plan: RewritePlan, brief: RewriteBrief | None = None) -> PromptPreview:
    return PromptPreview(
        user_summary=_build_prompt_preview_user(request, plan, brief),
        full_prompt=plan.generation_prompt.prompt,
    )


def _soft_generation_beats(plan: RewritePlan) -> list[dict[str, str]]:
    shots = list(plan.rewritten_storyboard.shots)
    if not shots:
        return []
    if len(shots) <= 5:
        return [
            {
                "beat": str(index),
                "role": shot.role,
                "visual_goal": shot.visual_instruction,
                "timing": "approximate beat, not an exact second-by-second cut",
            }
            for index, shot in enumerate(shots, start=1)
        ]
    groups = [
        ("opening_hook", shots[:2]),
        ("product_proof_and_texture", shots[2:4]),
        ("scene_or_use_context", shots[4:6]),
        ("visual_cta_or_satisfaction_close", shots[6:]),
    ]
    beats: list[dict[str, str]] = []
    for index, (role, group) in enumerate(groups, start=1):
        if not group:
            continue
        beats.append(
            {
                "beat": str(index),
                "role": role,
                "visual_goal": "；".join(shot.visual_instruction for shot in group if shot.visual_instruction),
                "timing": "approximate beat; merge these ideas naturally instead of creating many fast exact cuts",
            }
        )
    return beats


def _natural_beat_sentence(plan: RewritePlan, *, language: str = "zh") -> str:
    def short_phrase(text: str, *, max_chars: int) -> str:
        phrase = text.strip().replace("\n", " ")
        for sep in ["，", "；", ",", ";", "."]:
            if sep in phrase:
                phrase = phrase.split(sep, 1)[0]
                break
        if len(phrase) > max_chars:
            phrase = phrase[: max_chars - 1].rstrip() + "…"
        return phrase

    shots = plan.rewritten_storyboard.shots[:5]
    if not shots:
        return "按自然镜头段落生成。" if language != "en" else "Generate through natural story beats."
    if language == "en":
        beats = [short_phrase(shot.visual_instruction.rstrip("."), max_chars=72) for shot in shots]
        return "Prompt preview will guide the model through these natural beats: " + "; ".join(beats) + "."
    beats = [short_phrase(shot.visual_instruction.rstrip("。"), max_chars=32) for shot in shots]
    return "提示词预览会让模型按 5 个自然 beat 生成：" + "；".join(beats) + "。"


def _print_decision_gate_footer(*, language: str = "zh", include_detail_option: bool = True) -> None:
    """The next-step gate shown after a brief or a detailed analysis: confirm / (view detail) / edit.

    Shared by the compact brief and the detailed analysis so the two never drift, and so the
    detailed-analysis stdout is self-contained — forwarding it verbatim already ends with the gate,
    leaving no reason to hand-write a "shown above / 以上是完整详细分析" recap.
    Set include_detail_option=False when the detailed analysis is already being shown.
    """
    if language == "en":
        print("If you want to continue, reply: confirm generation. This will submit to BytePlus Seedance and may take a few minutes and consume resources.")
        if include_detail_option:
            print("If you want the full detailed analysis first, reply: show detailed analysis. You can also tell me what to change.")
        else:
            print("You can also tell me what to change.")
        return
    print("如果你要继续，请回复：确认生成。确认后会提交 BytePlus Seedance，可能需要几分钟并消耗资源包。")
    if include_detail_option:
        print("如果想先看完整详细分析，回复：查看详细分析。也可以直接说要改哪里。")
    else:
        print("也可以直接说要改哪里。")


def _print_compact_decision_brief(prepared: PreparedRewrite, *, language: str = "zh") -> None:
    request = prepared.request
    brief = prepared.rewrite_brief
    strategy = prepared.rewrite_plan.rewrite_strategy
    product_anchors = list(dict.fromkeys([*brief.source_product_anchors, *brief.confirmed_selling_points]))
    if language == "en":
        print("Real analysis preview is complete. Seedance has not been called yet, and no new video has been generated.")
        print("Brief summary:")
        print(
            "- Template structure: borrow "
            f"{_join_items_for_language(strategy.borrow_from_viral or brief.borrowable_elements, limit=4, language='en')}. "
            f"Do not inherit {_join_items_for_language(brief.forbidden_template_elements, limit=3, language='en')}."
        )
        print(f"- Product anchors: {_join_items_for_language(product_anchors, limit=8, language='en')}.")
        print(f"- Generation direction: {strategy.strategy_summary}")
        print(f"- Default output: {request.output_ratio}, {request.output_resolution}, 12-15 seconds, {'audio on' if request.generate_audio else 'audio off'}, original unrecognizable instrumental background music.")
        print(f"- Forbidden carryover: {_join_items_for_language(brief.forbidden_template_elements, limit=4, language='en')}.")
        print(f"- Risk controls: {_join_items_for_language([*brief.uncertain_or_unproven_points, *brief.risks, *strategy.risk_controls], limit=5, language='en')}.")
        print(_natural_beat_sentence(prepared.rewrite_plan, language="en"))
        _print_decision_gate_footer(language="en", include_detail_option=True)
        return

    print("真实分析预览已完成，当前还没有调用 Seedance，也还没有生成新视频。")
    print("本次 brief 摘要：")
    print(
        "- 模板结构：借模板的"
        f"“{_join_display_items(strategy.borrow_from_viral or brief.borrowable_elements, limit=4)}”。"
        f"不继承{_join_display_items(brief.forbidden_template_elements, limit=3)}。"
    )
    print(f"- 商品锚点：{_join_display_items(product_anchors, limit=8)}。")
    print(f"- 生成方向：{_zh_display_text(strategy.strategy_summary)}")
    print(f"- 输出默认：{request.output_ratio}，{request.output_resolution}，12-15 秒，{'带' if request.generate_audio else '不带'}原创不可识别无歌词背景音乐。")
    print(f"- 禁止继承：{_join_display_items(brief.forbidden_template_elements, limit=4)}。")
    print(f"- 风险控制：{_join_display_items([*brief.uncertain_or_unproven_points, *brief.risks, *strategy.risk_controls], limit=5)}。")
    print(_zh_display_text(_natural_beat_sentence(prepared.rewrite_plan, language="zh")))
    _print_decision_gate_footer(language="zh", include_detail_option=True)


def print_prepared_readout(
    prepared: PreparedRewrite,
    *,
    show_full_prompt: bool = False,
    show_analysis_details: bool = False,
) -> None:
    language = _ui_language(prepared.request)
    if show_analysis_details:
        _print_analysis_readout("Template Video Logic Extraction" if language == "en" else "模板视频逻辑抽取", prepared.viral_analysis, language=language)
        _print_analysis_readout("Product Image Logic Extraction" if language == "en" else "商品图逻辑抽取", prepared.source_analysis, language=language)
        _print_brief_readout(prepared.rewrite_brief, language=language)
    else:
        _print_compact_decision_brief(prepared, language=language)
    if show_full_prompt:
        print("\nFull generation prompt" if language == "en" else "\n完整生成提示词")
        print(prepared.prompt_preview.full_prompt)


def print_analysis_details(prepared: PreparedRewrite, *, show_full_prompt: bool = False) -> None:
    language = _ui_language(prepared.request)
    _print_analysis_readout("Detailed Template Video Understanding" if language == "en" else "模板视频详细理解", prepared.viral_analysis, language=language)
    _print_analysis_readout("Detailed Product Image Understanding" if language == "en" else "商品图详细理解", prepared.source_analysis, language=language)
    _print_brief_readout(prepared.rewrite_brief, language=language)
    if show_full_prompt:
        print("\nFull generation prompt" if language == "en" else "\n完整生成提示词")
        print(prepared.prompt_preview.full_prompt)
    print()
    _print_decision_gate_footer(language=language, include_detail_option=False)


def analyze_video(video_path: str, *, video_label: str, media_type: str = "video", ui_language: str = "zh") -> VideoAnalysis:
    raise RuntimeError(
        "ModelArk/Seed video understanding has been removed. "
        "Use the host agent for video understanding and detailed analysis, then save the result as prepared JSON."
    )


def build_rewrite_plan(request: RewriteRequest, *, viral_analysis: VideoAnalysis, source_analysis: VideoAnalysis) -> RewritePlan:
    raise RuntimeError(
        "ModelArk/Seed rewrite planning has been removed. "
        "Use the host agent to create the rewrite plan and prompt preview, then pass prepared JSON to the runner."
    )


def _finalize_generation_prompt(request: RewriteRequest, plan: RewritePlan, brief: RewriteBrief | None = None) -> GenerationPrompt:
    original_prompt = plan.generation_prompt.prompt.strip()
    if original_prompt.startswith("Rewrite the product image into a stronger viral-style ad video"):
        original_prompt = plan.prompt_package.base_reference_summary
    if brief:
        original_prompt = _sanitize_text_for_template_transfer(original_prompt, request, brief)
    storyboard_json = json.dumps(plan.rewritten_storyboard.model_dump(), ensure_ascii=False)
    generation_beats_json = json.dumps(_soft_generation_beats(plan), ensure_ascii=False)
    prompt_package_json = json.dumps(plan.prompt_package.model_dump(), ensure_ascii=False)
    constraints = json.dumps(_normalized_extra_constraints(request, brief), ensure_ascii=False)
    brief_json = json.dumps(brief.model_dump(), ensure_ascii=False) if brief else "{}"
    priority_transfer = ""
    if brief:
        high_priority = [*brief.borrowable_elements, *brief.risks]
        if high_priority:
            priority_transfer = (
                "High-priority template transfer cues and failure guards: "
                + json.dumps(high_priority, ensure_ascii=False)
                + "\n"
            )
    hard_template_identity = ""
    if brief:
        identity_lines = [
            "HARD TEMPLATE-REPLICATION CONSTRAINTS:",
            f"- Template profile route: {brief.template_profile or 'unknown'}; active transfer slots: {_join_items(brief.template_profile_slots, limit=12)}.",
            "- Do not generate subtitles, automatic captions, lower-thirds, stickers, watermarks, platform UI, price tags, shopping prompts, or any on-screen text. This remains true even when voiceover is present.",
            "- Keep the final second product-visible; no blank, white, black, pure-color, or product-free ending frames.",
        ]
        if brief.template_person_appearance_context:
            identity_lines.append(
                "- PERSON CONTEXT LOCK: match the template's broad person appearance / market visual context: "
                f"{brief.template_person_appearance_context}. Generate a new non-identical person; do not copy the template person's identity or exact face. "
                "The target audience and UI language are not casting instructions; do not switch broad ethnicity, styling, or market look because of the target audience."
            )
        voice_language = _template_voice_language_prompt_label(brief)
        if voice_language:
            identity_lines.append(
                "- VOICEOVER LANGUAGE LOCK: spoken voiceover language must match the template language exactly: "
                f"{voice_language}. Use original new wording in the same language; do not translate or switch languages. "
                "Never choose the voiceover language from the UI language or target audience."
            )
            if _spoken_language_kind(voice_language) == "en":
                identity_lines.append(
                    "- The generated presenter voiceover must be English. Do not translate the voiceover to Chinese, do not add Chinese narration, and do not add bilingual subtitles."
                )
            elif _spoken_language_kind(voice_language) == "zh":
                identity_lines.append(
                    "- The generated presenter voiceover must be Chinese Mandarin. Do not switch the voiceover to English or another ad default language, and do not add subtitles."
                )
            if brief.template_profile == "human_voiceover":
                identity_lines.append(
                    "- LIP-SYNC LOCK: in every shot where the presenter speaks, visible mouth shapes, jaw movement, expression, eye contact, and hand gestures must synchronize with the generated "
                    f"{voice_language} audio. Mouth motion must match the spoken syllables/phoneme timing. If close-up lip sync is unstable, use shorter speaking beats or slightly wider framing, but do not produce off-language or unsynchronized mouth movement."
                )
        if brief.template_subtitle_state:
            identity_lines.append(
                "- Template text/subtitle state observed: "
                f"{brief.template_subtitle_state}. Do not reproduce template watermarks/accounts/platform text and do not add new subtitles."
            )
        hard_template_identity = "\n".join(identity_lines) + "\n"
    voice_note = ""
    if brief and _wants_template_voice(request, brief):
        voice_note = (
            "If preserving a voiceover-style template, any spoken/voiceover content must be newly generated, generic, and non-identifiable; "
            "do not copy the template speaker, voice, wording, account handle, or platform CTA. The background-music safety rule below applies to the music bed and does not remove the visual/open-mouth presentation rhythm.\n"
        )
    prompt = (
        "Rewrite the product image into a stronger viral-style ad video while preserving product identity, "
        "core benefit, and visible product anchors from the source image.\n"
        f"User-facing language for analysis and brief text: {'English' if _is_en(request) else 'Chinese'}. "
        "This does not override the template spoken-language rule for voiceover templates.\n"
        f"Target audience: {request.target_audience}\n"
        f"Objective: {request.objective}\n"
        f"Product context: {request.product_context or 'same as source image'}\n"
        f"Extra constraints: {constraints}\n"
        f"{hard_template_identity}"
        f"Rewrite strategy: {plan.rewrite_strategy.strategy_summary}\n"
        f"Confirmed analysis brief: {brief_json}\n"
        f"{priority_transfer}"
        f"Detailed storyboard for analysis reference only, not a strict timeline: {storyboard_json}\n"
        f"Soft generation beats to follow in the final video: {generation_beats_json}\n"
        f"Prompt package: {prompt_package_json}\n"
        f"Generation guidance: {original_prompt}\n"
        "Output one cohesive rewritten ad video with a strong first-5-second hook, tighter pacing, clearer product proof, "
        "visible satisfaction moments, and a more explicit action-based visual CTA.\n"
        "Treat all shot durations and storyboard entries as approximate creative beats, not frame-accurate editing instructions. "
        "Do not attempt to reproduce every micro-shot literally. Consolidate small adjacent actions into 4-5 natural visual beats so the product remains stable and recognizable. "
        "Avoid excessive scene changes, prop changes, or complex motion that could destabilize the source product identity.\n"
        "The final video product must stay exactly the same as the product shown in the source image. "
        "Use the source image as the product identity truth: preserve the same object type, shape, packaging, color, label placement, material, and visible design details across every shot. "
        "Do not switch to the viral video's product, ingredients, packaging, flavor, or product story. "
        "Use the viral video only as a creative reference for shot order, pacing, actions, scene function, and satisfaction structure.\n"
        "Forbidden viral carryover: product category, brand, package shape, product color naming, ingredients, flavor, price, claims, captions, shopping UI, and any product-specific semantics from the viral template.\n"
        "Borrow only: structure, pacing, camera rhythm, action sequence, scene function, satisfaction pattern, and non-product-specific proof logic.\n"
        "Never end with blank space, white screen, black screen, a plain-color fade, or a product-free empty shot. The final second must keep the source product visibly present in a complete visual CTA frame.\n"
        "Prefer a 12-15 second result when the model supports it: use the confirmed director-level template analysis, replicate the template framework in the opening, then extend "
        "7-8 seconds with source-product proof, texture/detail shots, before-after change, use-case context, and visual CTA. "
        "If the template is shorter than 5 seconds, preserve its action logic and satisfaction mechanism in the first 5 seconds, then add new source-product proof shots without changing product identity.\n"
        "Do not render any subtitles, captions, on-screen text, labels, price tags, stickers, logos, shopping cart prompts, or any other text overlays.\n"
        f"{voice_note}"
        f"{_music_prompt(request)}"
    )
    if not request.source_image:
        raise ValueError("source_image is required for generation.")
    return GenerationPrompt(prompt=prompt, reference_image_url=request.source_image)


def _create_contact_sheet(video_path: str, *, cache_key: str) -> tuple[str | None, str]:
    ffmpeg = None
    try:
        import imageio_ffmpeg

        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        ffmpeg = shutil.which("ffmpeg")
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    out_path = PREVIEW_DIR / f"contact_sheet_{cache_key}.jpg"
    if ffmpeg:
        cmd = [
            ffmpeg,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            video_path,
            "-vf",
            f"fps={CONTACT_SHEET_SAMPLE_FPS},scale=180:-1,tile=5x3",
            "-frames:v",
            "1",
            str(out_path),
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            if out_path.exists() and out_path.stat().st_size > 0:
                return str(out_path), "ok"
        except Exception:
            pass
    try:
        import imageio.v3 as iio
        from PIL import Image

        metadata = {}
        try:
            metadata = iio.immeta(video_path)
        except Exception:
            metadata = {}
        source_fps = metadata.get("fps") or metadata.get("video_fps") or 30
        try:
            source_fps = float(source_fps)
        except (TypeError, ValueError):
            source_fps = 30.0
        frame_step = max(1, int(round(source_fps / CONTACT_SHEET_SAMPLE_FPS)))

        frames = []
        for index, frame in enumerate(iio.imiter(video_path)):
            if index % frame_step == 0:
                image = Image.fromarray(frame).convert("RGB")
                image.thumbnail((180, 320))
                frames.append(image.copy())
            if len(frames) >= CONTACT_SHEET_MAX_FRAMES:
                break
        if not frames:
            return None, "failed: no frames decoded"
        tile_w = max(frame.width for frame in frames)
        tile_h = max(frame.height for frame in frames)
        sheet = Image.new("RGB", (tile_w * 5, tile_h * 3), "white")
        for idx, frame in enumerate(frames):
            x = (idx % 5) * tile_w + (tile_w - frame.width) // 2
            y = (idx // 5) * tile_h + (tile_h - frame.height) // 2
            sheet.paste(frame, (x, y))
        sheet.save(out_path, quality=90)
    except Exception as exc:
        return None, f"failed: ffmpeg not found and python fallback failed: {exc}"
    if not out_path.exists() or out_path.stat().st_size == 0:
        return None, "failed: contact sheet file missing"
    return str(out_path), "ok"


def _debug_artifacts_enabled() -> bool:
    value = os.environ.get("VIRAL_REWRITE_SHOW_DEBUG_ARTIFACTS") or os.environ.get("VIRAL_REWRITE_CREATE_CONTACT_SHEET") or ""
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def generate_rewritten_video_artifact(request: RewriteRequest, plan: RewritePlan) -> GeneratedVideoArtifact:
    from media_cache import cache_key_for_url, cache_remote_file
    from seedance_runtime import generate_video_with_seedance_result

    _log("generation start")
    final_generation_prompt = plan.generation_prompt
    seedance_result = generate_video_with_seedance_result(
        prompt=final_generation_prompt.prompt,
        duration_sec=sum(shot.duration_sec for shot in plan.rewritten_storyboard.shots),
        ratio=request.output_ratio,
        resolution=request.output_resolution,
        generate_audio=request.generate_audio,
        reference_video_url=final_generation_prompt.reference_video_url,
        reference_image_url=final_generation_prompt.reference_image_url,
        language=_ui_language(request),
    )
    remote_url = str(seedance_result["video_url"])
    task_id = str(seedance_result.get("task_id") or "") or None
    cache_key = cache_key_for_url(remote_url)
    filename_hint = f"rewritten_video_{task_id}" if task_id else "rewritten_video"
    local_path = cache_remote_file(
        remote_url,
        cache_root=CACHE_DIR,
        subdir="videos",
        ext=".mp4",
        filename_hint=filename_hint,
    )
    if _debug_artifacts_enabled():
        contact_sheet_path, contact_sheet_status = _create_contact_sheet(local_path, cache_key=cache_key)
    else:
        contact_sheet_path, contact_sheet_status = None, "skipped: debug artifacts disabled"
    artifact = GeneratedVideoArtifact(
        task_id=task_id,
        generated_at=datetime.now(timezone.utc).isoformat(),
        cache_key=cache_key,
        remote_video_url=remote_url,
        local_video_path=local_path,
        contact_sheet_path=contact_sheet_path,
        contact_sheet_status=contact_sheet_status,
    )
    _log(f"generation done task_id={task_id or 'unknown'} local_path={local_path}")
    if contact_sheet_path:
        _log(f"preview ready contact_sheet={contact_sheet_path}")
    return artifact


def generate_rewritten_video(request: RewriteRequest, plan: RewritePlan) -> tuple[str, str]:
    artifact = generate_rewritten_video_artifact(request, plan)
    return artifact.remote_video_url, artifact.local_video_path


def prepare_rewrite(
    request: RewriteRequest,
    *,
    print_readout: bool = True,
    show_full_prompt: bool = False,
    show_analysis_details: bool = False,
) -> PreparedRewrite:
    _log("prepare start")
    ui_language = _ui_language(request)
    viral_analysis = analyze_video(request.viral_video, video_label="viral_video", media_type=request.viral_media_type, ui_language=ui_language)
    if not request.source_image:
        raise ValueError("source_image is required.")
    source_analysis = analyze_video(request.source_image, video_label="source_image", media_type=request.source_media_type, ui_language=ui_language)
    rewrite_plan = build_rewrite_plan(request, viral_analysis=viral_analysis, source_analysis=source_analysis)
    rewrite_brief = _build_rewrite_brief(request, viral_analysis, source_analysis, rewrite_plan)
    rewrite_plan = apply_rewrite_brief_to_plan(request, rewrite_plan, rewrite_brief)
    prepared = PreparedRewrite(
        request=request,
        viral_analysis=viral_analysis,
        source_analysis=source_analysis,
        rewrite_plan=rewrite_plan,
        rewrite_brief=rewrite_brief,
        prompt_preview=_build_prompt_preview(request, rewrite_plan, rewrite_brief),
    )
    if print_readout:
        print_prepared_readout(
            prepared,
            show_full_prompt=show_full_prompt,
            show_analysis_details=show_analysis_details,
        )
    _log("prepare done")
    return prepared


def apply_rewrite_brief_to_plan(request: RewriteRequest, plan: RewritePlan, brief: RewriteBrief) -> RewritePlan:
    sanitized_shots = []
    english = _is_en(request)
    voice_language = _template_voice_language_prompt_label(brief)
    voice_kind = _spoken_language_kind(voice_language)
    if voice_kind == "en":
        visual_voice_note = (
            ", the presenter speaks to camera in original English, with visible mouth shapes, jaw movement, expression, eye contact, and gestures synchronized to the English audio; do not switch to Chinese"
            if english
            else "，人物使用原创英文口播对镜介绍，可见口型、下颌动作、表情、眼神和手势必须与英文音频同步；不要切换为中文"
        )
        shot_voiceover = "Original English voiceover-style explanatory rhythm with lip sync to the English audio; do not copy the template voice or wording"
    elif voice_kind == "zh":
        visual_voice_note = (
            ", the presenter speaks to camera in original Chinese Mandarin, with visible mouth shapes, jaw movement, expression, eye contact, and gestures synchronized to the Mandarin audio; do not switch to English"
            if english
            else "，人物使用原创中文普通话口播对镜介绍，可见口型、下颌动作、表情、眼神和手势必须与普通话音频同步；不要改成英文口播"
        )
        shot_voiceover = "Original Chinese Mandarin voiceover-style explanatory rhythm with lip sync to the Mandarin audio; do not copy the template voice or wording"
    else:
        visual_voice_note = (
            ", the presenter speaks to camera in the same spoken language as the template, with visible mouth shapes, jaw movement, expression, eye contact, and gestures synchronized; do not choose the language from the UI or target audience"
            if english
            else "，人物使用与模板相同语言的原创口播对镜介绍，可见口型、下颌动作、表情、眼神和手势必须同步；不要根据前台语言或目标人群切换口播语言"
        )
        shot_voiceover = "Original same-language voiceover-style explanatory rhythm with lip sync to the generated audio; do not copy the template voice or wording"
    for shot in plan.rewritten_storyboard.shots:
        visual_instruction = _sanitize_text_for_template_transfer(shot.visual_instruction, request, brief)
        has_sync_instruction = any(token in visual_instruction for token in ["口型", "嘴形", "同步", "mouth", "lip", "sync"])
        if _wants_template_voice(request, brief) and not has_sync_instruction:
            visual_instruction += visual_voice_note
        if shot.role == "cta" and "最后一秒" not in visual_instruction:
            visual_instruction += (
                ", keep the person and product fully visible through the final second; no blank, black, white, or plain-color fade"
                if english
                else "，最后一秒保持人物和商品完整可见，不出现空白、黑屏、白屏或纯色淡出"
            )
        sanitized_shots.append(
            shot.model_copy(
                update={
                    "visual_instruction": visual_instruction,
                    "voiceover": (
                        shot_voiceover
                        if english and _wants_template_voice(request, brief)
                        else (
                            "原创英文口播式讲解节奏，嘴形/口型与英文音频同步，不复刻模板原声或文案"
                            if voice_kind == "en"
                            else "原创中文普通话口播式讲解节奏，嘴形/口型与普通话音频同步，不复刻模板原声或文案"
                            if voice_kind == "zh"
                            else "与模板相同语言的原创口播式讲解节奏，嘴形/口型与生成音频同步，不复刻模板原声或文案"
                        ) if _wants_template_voice(request, brief) else ""
                    ),
                }
            )
        )
    storyboard = plan.rewritten_storyboard.model_copy(update={"shots": sanitized_shots})
    base_risk_controls = [
        _sanitize_text_for_template_transfer(item, request, brief)
        for item in plan.rewrite_strategy.risk_controls
    ]
    if _wants_template_voice(request, brief):
        base_risk_controls = [
            item for item in base_risk_controls if "无任何口播语音" not in item and "纯音乐静默展示" not in item
        ]
    if _wants_template_human_face(request, brief):
        base_risk_controls = [
            item for item in base_risk_controls if "禁止出现可识别真人面部" not in item and "无清晰面部" not in item
        ]
        base_risk_controls.append(
            "Do not copy the specific template person's identity; preserve a newly generated visible front-facing face, natural expression, eye contact, and presenter posture"
            if english
            else "不要复刻模板具体人物身份；可以保留新生成人物的正面脸部、自然表情、眼神交流和对镜展示姿态"
        )
    base_risk_controls.append(
        "Do not end with blank space, black screen, white screen, plain-color fade, or product-free empty shot; the final second must keep the product visible"
        if english
        else "结尾不得留白、黑屏、白屏、纯色淡出或无商品空镜；最后一秒必须仍有商品主体可见"
    )
    prompt_package_data = _sanitize_nested_prompt_value(plan.prompt_package.model_dump(), request, brief)
    prompt_package_data["must_keep"] = list(
        dict.fromkeys(
            [
                *prompt_package_data.get("must_keep", []),
                brief.source_product_identity,
                *brief.source_product_anchors,
                *brief.confirmed_selling_points,
            ]
        )
    )
    prompt_package = PromptPackage.model_validate(prompt_package_data)
    strategy = plan.rewrite_strategy.model_copy(
        update={
            "strategy_summary": brief.rewrite_strategy or plan.rewrite_strategy.strategy_summary,
            "risk_controls": list(
                dict.fromkeys(
                    [
                        *base_risk_controls,
                        *brief.forbidden_template_elements,
                        *brief.uncertain_or_unproven_points,
                        *brief.risks,
                    ]
                )
            ),
        }
    )
    updated_plan = plan.model_copy(update={"rewrite_strategy": strategy, "prompt_package": prompt_package, "rewritten_storyboard": storyboard})
    final_prompt = _finalize_generation_prompt(request, updated_plan, brief)
    return updated_plan.model_copy(update={"generation_prompt": final_prompt})


def _backfill_template_fields(prepared: PreparedRewrite, brief: RewriteBrief) -> RewriteBrief:
    updates = {}
    profile = _resolved_template_profile(prepared.viral_analysis)
    spoken_language = _infer_template_spoken_language(prepared.viral_analysis, brief)
    if not brief.template_profile:
        updates["template_profile"] = profile.profile
    if not brief.template_profile_slots:
        updates["template_profile_slots"] = profile.primary_transfer_slots
    if profile.should_preserve_person_context and prepared.viral_analysis.person_appearance_context:
        current_context = brief.template_person_appearance_context
        analysis_context = prepared.viral_analysis.person_appearance_context
        if (
            not current_context
            or (
                _person_context_is_target_audience_drift(current_context, prepared.request, brief)
                and _usable_template_person_context(analysis_context, prepared.request, brief)
            )
        ):
            updates["template_person_appearance_context"] = analysis_context
    elif not brief.template_person_appearance_context and profile.should_preserve_person_context and prepared.viral_analysis.person_appearance_context:
        updates["template_person_appearance_context"] = prepared.viral_analysis.person_appearance_context
    if profile.should_preserve_voice_language:
        current_kind = _spoken_language_kind(brief.template_spoken_language)
        inferred_kind = _spoken_language_kind(spoken_language)
        if spoken_language and (current_kind == "unknown" or (current_kind == "zh" and inferred_kind == "en")):
            updates["template_spoken_language"] = spoken_language
        elif not brief.template_spoken_language:
            updates["template_spoken_language"] = ""
    if not brief.template_subtitle_state and prepared.viral_analysis.subtitle_state:
        updates["template_subtitle_state"] = prepared.viral_analysis.subtitle_state
    if not updates:
        return brief
    template_cues, transfer_risks = _template_transfer_cues(prepared.viral_analysis)
    updates["borrowable_elements"] = list(dict.fromkeys([*brief.borrowable_elements, *template_cues]))
    updates["risks"] = list(dict.fromkeys([*brief.risks, *transfer_risks]))
    return brief.model_copy(update=updates)


def normalize_prepared_for_generation(prepared: PreparedRewrite) -> PreparedRewrite:
    """Refresh prepared artifacts so stale/manual fields cannot bypass current prompt guards."""
    profile = _resolved_template_profile(prepared.viral_analysis)
    spoken_language = _infer_template_spoken_language(prepared.viral_analysis, prepared.rewrite_brief)
    analysis_updates = {}
    if profile.should_preserve_voice_language and spoken_language:
        current_analysis_kind = _spoken_language_kind(prepared.viral_analysis.spoken_language)
        inferred_kind = _spoken_language_kind(spoken_language)
        if current_analysis_kind == "unknown" or (current_analysis_kind == "zh" and inferred_kind == "en"):
            analysis_updates["spoken_language"] = spoken_language
    viral_analysis = (
        prepared.viral_analysis.model_copy(update=analysis_updates)
        if analysis_updates
        else prepared.viral_analysis
    )
    refreshed = prepared.model_copy(update={"viral_analysis": viral_analysis})
    return refresh_prepared_with_brief(refreshed, refreshed.rewrite_brief)


def refresh_prepared_with_brief(prepared: PreparedRewrite, brief: RewriteBrief) -> PreparedRewrite:
    brief = _backfill_template_fields(prepared, brief)
    rewrite_plan = apply_rewrite_brief_to_plan(prepared.request, prepared.rewrite_plan, brief)
    return prepared.model_copy(
        update={
            "rewrite_brief": brief,
            "rewrite_plan": rewrite_plan,
            "prompt_preview": _build_prompt_preview(prepared.request, rewrite_plan, brief),
        }
    )


def execute_rewrite(prepared: PreparedRewrite) -> RewriteVideoResponse:
    _log("execute start")
    request = prepared.request
    rewrite_plan = prepared.rewrite_plan
    artifact = generate_rewritten_video_artifact(request, rewrite_plan)
    result = RewriteVideoResponse(
        request=request,
        viral_analysis=prepared.viral_analysis,
        source_analysis=prepared.source_analysis,
        rewrite_plan=rewrite_plan,
        rewritten_video_url=artifact.remote_video_url,
        rewritten_video_remote_url=artifact.remote_video_url,
        rewritten_video_local_path=artifact.local_video_path,
        seedance_task_id=artifact.task_id,
        generated_at=artifact.generated_at,
        cache_key=artifact.cache_key,
        contact_sheet_path=artifact.contact_sheet_path,
        artifact=artifact,
    )
    _log("execute done")
    return result


def rewrite_video(request: RewriteRequest) -> RewriteVideoResponse:
    _log("workflow start")
    prepared = prepare_rewrite(request)
    result = execute_rewrite(prepared)
    _log("workflow done")
    return result
