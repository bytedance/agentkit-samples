#!/usr/bin/env python3
# Copyright (c) 2026 BytePlus. All rights reserved.
# SPDX-License-Identifier: Proprietary
"""Entrypoint for viral creative rewrite workflow."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from dependency_check import ensure_analysis_dependencies, ensure_core_dependencies
from env_loader import load_env_file, missing_env
from media_links import media_markdown
from setup_links import print_base_setup_links, print_local_key_setup_hint, print_real_generation_setup_flow

BASE_DIR = Path(__file__).resolve().parent.parent
ensure_core_dependencies(base_dir=BASE_DIR, include_provider=False)

from schemas import PreparedRewrite, RewriteRequest

REQUIRED_ARK_ENV = ["ARK_API_KEY"]
REHEARSAL_PREPARED_PATH = BASE_DIR / "assets" / "examples" / "rehearsal_prepared.example.json"
REHEARSAL_RESULT_PATH = BASE_DIR / "assets" / "examples" / "rehearsal_result.example.json"
REHEARSAL_PREVIEW_PATH = BASE_DIR / "assets" / "examples" / "rehearsal_result_video.mp4"
SEEDANCE_SHOWCASE_PATHS = [
    REHEARSAL_PREVIEW_PATH,
    BASE_DIR / "assets" / "examples" / "seedance_showcase_lark_203400.mp4",
    BASE_DIR / "assets" / "examples" / "seedance_showcase_lark_203404.mp4",
    BASE_DIR / "assets" / "examples" / "seedance_showcase_rewritten_vqtnl.mp4",
    BASE_DIR / "assets" / "examples" / "seedance_showcase_glowbottle.mp4",
    BASE_DIR / "assets" / "examples" / "seedance_showcase_a2_video_001.mp4",
]


def is_url(value: str) -> bool:
    return value.startswith("http://") or value.startswith("https://")


def is_local_template_video(request: RewriteRequest) -> bool:
    if request.viral_media_type != "video":
        return False
    value = str(request.viral_video or "")
    return bool(value) and not is_url(value)


def guess_media_type(value: str) -> str:
    lower = value.split("?", 1)[0].split("#", 1)[0].lower()
    if lower.endswith((".png", ".jpg", ".jpeg", ".webp", ".heic", ".bmp")):
        return "image"
    if lower.endswith((".mp4", ".mov", ".m4v", ".webm", ".avi", ".mkv")):
        return "video"
    return "url" if is_url(value) else "video"


def is_image_media(value: str) -> bool:
    return is_url(value) or guess_media_type(value) == "image"


def contains_cjk(text: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in text)


def payload_language(payload: dict, override: str = "auto") -> str:
    if override in {"zh", "en"}:
        return override
    explicit = str(payload.get("ui_language") or "auto")
    if explicit in {"zh", "en"}:
        return explicit
    text = "\n".join(
        [
            str(payload.get("product_context") or ""),
            str(payload.get("target_audience") or ""),
            str(payload.get("objective") or ""),
            "\n".join(str(item) for item in payload.get("extra_constraints") or []),
        ]
    )
    return "zh" if contains_cjk(text) else "en"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rewrite an ad video from a template video and source product image.")
    parser.add_argument("--input-json", help="Path to rewrite request JSON")
    parser.add_argument("--prepared-input-json", help="Path to an existing prepared JSON. Reuses previous media analysis.")
    parser.add_argument("--patch-json", help="Optional small generation-direction patch applied to prepared JSON without re-analyzing media")
    parser.add_argument("--rehearsal", action="store_true", help="Replay the built-in full-flow example without API keys or provider calls")
    parser.add_argument("--setup-only", action="store_true", help="Validate and print the request without requiring API keys")
    parser.add_argument("--prepare-only", action="store_true", help="Show an existing prepared brief or rehearsal. Real media understanding is done by the host agent, not ModelArk.")
    parser.add_argument("--prepared-json", help="Optional prepared analysis output JSON path")
    parser.add_argument("--output-json", help="Optional output JSON path")
    parser.add_argument("--env-file", default=".env", help="Optional .env file to load before running")
    parser.add_argument("--show-full-prompt", action="store_true", help="Print the full generation prompt in addition to the user summary")
    parser.add_argument("--show-debug-artifacts", action="store_true", help="Print full JSON and detailed analysis artifacts")
    parser.add_argument("--show-detailed-analysis", action="store_true", help="Show the clean full detailed analysis (DETAIL stage) without the raw JSON debug dump; stops at the same confirmation gate")
    parser.add_argument("--ui-language", choices=["auto", "zh", "en"], default="auto", help="User-facing language override for runner messages and rehearsal")
    parser.add_argument("--media-style", choices=["codex", "link", "both"], default="codex", help="How to render media (video/image) markdown: codex=![](path) inline preview (default); link=[](file:// url) clickable; both")
    parser.add_argument(
        "--confirmed-brief",
        action="store_true",
        help="Allow real generation after the prepared brief has already been reviewed and explicitly confirmed",
    )
    return parser.parse_args()


def write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def output_dir_from_env() -> Path:
    value = os.getenv("OUTPUT_DIR", "").strip()
    if not value:
        return Path.cwd() / "output"
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = BASE_DIR / path
    return path.resolve()


def default_sidecar_path(input_path: Path, suffix: str) -> Path:
    return output_dir_from_env() / f"{input_path.stem}.{suffix}.json"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_media_paths(payload: dict, *, base_path: Path) -> dict:
    payload = dict(payload)
    for key in ("viral_video", "source_image"):
        value = str(payload.get(key) or "")
        if not value or is_url(value):
            continue
        path = Path(value).expanduser()
        candidates = [path]
        if not path.is_absolute():
            candidates = [base_path / path, BASE_DIR / path, Path.cwd() / path]
        for candidate in candidates:
            if candidate.exists():
                payload[key] = str(candidate.resolve())
                break
    return payload


def load_request(input_path: Path) -> RewriteRequest:
    payload = resolve_media_paths(read_json(input_path), base_path=input_path.parent)
    payload.setdefault("viral_media_type", guess_media_type(str(payload.get("viral_video") or "")))
    source_image = str(payload.get("source_image") or "")
    if not source_image or not is_image_media(source_image):
        language = payload_language(payload)
        if payload.get("source_video"):
            if language == "en":
                raise SystemExit("Product videos are not supported as the source input. Please provide a product image in source_image.")
            raise SystemExit("当前流程不支持用商品视频作为 source。请把商品素材改成 source_image 图片。")
        if language == "en":
            raise SystemExit("Please provide source_image in input-json. Product video sources are not supported.")
        raise SystemExit("请在 input-json 中提供 source_image 商品图；当前流程不支持用商品视频作为 source。")
    payload["source_image"] = source_image
    payload.pop("source_video", None)
    payload["source_media_type"] = "image"
    return RewriteRequest.model_validate(payload)


def request_language(request: RewriteRequest | None = None, override: str = "auto") -> str:
    if override in {"zh", "en"}:
        return override
    explicit = request.ui_language if request else "auto"
    if explicit in {"zh", "en"}:
        return explicit
    if request:
        text = "\n".join([request.product_context, request.target_audience, request.objective, *request.extra_constraints])
        return "zh" if contains_cjk(text) else "en"
    return "zh"


def localize_rehearsal_payload_en(payload: dict) -> dict:
    payload = json.loads(json.dumps(payload, ensure_ascii=False))
    payload["request"].update(
        {
            "ui_language": "en",
            "target_audience": "women_20_30",
            "objective": "improve_ctr",
            "product_context": "Watermelon drink ad. Core values: fresh, icy, summery, real fruit pulp. The final video must preserve the same watermelon drink identity as the product image.",
            "extra_constraints": [
                "Keep the product identity from the product image",
                "Do not exaggerate efficacy",
                "Keep the video within 15 seconds",
                "Do not render subtitles or any on-screen text",
                "Do not inherit the template video's grape-drink product identity",
            ],
        }
    )
    payload["viral_analysis"].update(
        {
            "basic_info": "12.1-second 16:9 commercial beverage ad with no subtitles and no dialogue; the story is carried by visuals.",
            "audio_facts": "Light, fresh instrumental background music with subtle pouring, fruit splash, and outdoor ambience; no voiceover.",
            "camera_and_editing": "Hard cuts with no effects, mostly locked-off shots plus slow push-ins, 1-2 seconds per shot, clean commercial lighting.",
            "material_type": "commercial product-beauty ad video",
            "scene_and_people": [
                "backlit grape leaves",
                "studio liquid pour",
                "black-background product still",
                "fresh fruit splash macro",
                "bright product still",
                "indoor woman holding the drink",
                "beach drinking scene",
                "outdoor smiling end shot",
            ],
            "scene_details": [
                "green leaves, blue sky, sun-star highlight",
                "clear glass, saturated purple liquid, white studio surface",
                "black gradient background, reflective tabletop",
                "fresh grapes, wet surface, tiny water splashes",
                "sunny beach and open outdoor greenery",
            ],
            "subject_framing": "The product stays visually central; people shots keep the drink as the anchor.",
            "person_appearance_context": "Young women appear in lifestyle scenes, but their exact identity and face must not be copied.",
            "spoken_language": "none",
            "subtitle_state": "no subtitles or on-screen text",
            "template_profile": {
                "profile": "visual_product_texture",
                "has_human": True,
                "has_voiceover": False,
                "has_visible_face": True,
                "has_real_scene": True,
                "has_platform_cta": False,
                "has_subtitles_or_text": False,
                "should_preserve_person_context": False,
                "should_preserve_voice_language": False,
                "should_preserve_scene_context": True,
                "should_preserve_visual_product_texture": True,
                "primary_transfer_slots": ["shot order", "liquid texture", "ingredient proof", "lifestyle satisfaction", "music mood"],
            },
            "summary": {
                "creative_type": "ingredient-origin product-beauty ad",
                "product_category": "grape-flavored bottled sparkling drink",
                "main_value_prop": "fresh fruit cues, translucent liquid texture, refreshing lifestyle enjoyment",
                "target_persona_guess": "young consumers who like clean, summery beverage visuals",
            },
            "style": {
                "visual_style": "cinematic natural-light product beauty with saturated color and clean contrast",
                "pacing": "brisk hard cuts, each shot about 1-2 seconds",
                "emotion_tone": "bright, clean, relaxed, refreshing",
                "subtitle_style": "no subtitles or text overlays",
            },
            "structure": {
                "hook_type": "backlit natural ingredient sun-star hook",
                "product_exposure_timing": "liquid appears around 1.7s; complete product appears around 2.5s",
                "cta_type": "visual CTA through drinking satisfaction and a smile",
                "trust_signals": ["ingredient close-up", "liquid texture macro", "real drinking action", "multi-scene lifestyle proof"],
            },
            "segments": [
                {"start_sec": 0.0, "end_sec": 1.6, "role": "hook", "summary": "Backlit leaves and sun-star create a fresh natural hook.", "product_visible": False, "emotion": "calm and refreshing"},
                {"start_sec": 1.6, "end_sec": 3.2, "role": "solution_demo", "summary": "Liquid pour and product still introduce the beverage texture.", "product_visible": True, "emotion": "premium texture"},
                {"start_sec": 3.2, "end_sec": 5.0, "role": "proof", "summary": "Fresh fruit splash and product close-up support the ingredient story.", "product_visible": True, "emotion": "fresh and credible"},
                {"start_sec": 5.0, "end_sec": 12.1, "role": "cta", "summary": "People hold, drink, and smile with the product across lifestyle scenes.", "product_visible": True, "emotion": "relaxed satisfaction"},
            ],
            "five_second_windows": [
                {
                    "window_index": 1,
                    "start_sec": 0.0,
                    "end_sec": 5.0,
                    "material_type": "video",
                    "shot_type": "backlit close-up, liquid macro, product still",
                    "composition": "centered product framing and backlit ingredient framing",
                    "scene": "vineyard-like ingredient scene and studio tabletop",
                    "scene_details": ["green leaves with sun-star", "clear glass and flowing liquid", "black reflective product surface", "fresh fruit splash"],
                    "camera": "commercial camera with macro lens",
                    "camera_position": "low angle for leaves, overhead for pour, eye-level for product",
                    "camera_movement": "mostly locked-off with subtle push-ins",
                    "materials_to_capture": ["sun-star through leaves", "liquid ripples", "glossy product silhouette", "fresh fruit splash"],
                    "action_sequence": ["sun passes through leaves", "liquid pours into a glass", "product sits centered on black surface", "fruit splashes on wet tabletop"],
                    "product_presence": "liquid and product appear in the first five seconds",
                    "product_selling_points": ["ingredient freshness", "clean liquid texture", "premium product look"],
                    "product_satisfaction_points": ["sunlit freshness", "smooth flowing liquid", "fresh fruit moisture"],
                    "subtitle_text": "",
                    "voiceover_text": "",
                    "audio_state": "instrumental music with subtle pour and splash sounds",
                    "borrowable_function": ["natural ingredient hook", "ingredient-to-liquid-to-product progression", "macro texture proof"],
                    "forbidden_carryover": ["do not keep the grape product", "do not keep original packaging or brand"],
                    "replication_notes": ["keep the opening sensory and product-led, not text-led"],
                },
                {
                    "window_index": 2,
                    "start_sec": 5.0,
                    "end_sec": 10.0,
                    "material_type": "video",
                    "shot_type": "product still, person close-up, drinking side shot",
                    "composition": "center product framing and thirds for people shots",
                    "scene": "bright studio, indoor lifestyle, beach",
                    "scene_details": ["bright wall and soft shadows", "simple indoor background", "sunny beach and natural side light"],
                    "camera": "locked-off eye-level camera",
                    "camera_position": "eye-level with the product and person",
                    "camera_movement": "minimal movement",
                    "materials_to_capture": ["product in changing light", "hand holding drink", "natural drinking action"],
                    "action_sequence": ["product displayed in bright light", "woman holds product", "woman drinks outdoors", "smiles after drinking"],
                    "product_presence": "the drink stays visible as the lifestyle anchor",
                    "product_selling_points": ["easy to hold", "outdoor friendly", "refreshing drinking experience"],
                    "product_satisfaction_points": ["relaxed drinking expression", "natural smile", "sunny lifestyle mood"],
                    "subtitle_text": "",
                    "voiceover_text": "",
                    "audio_state": "light music and outdoor ambience",
                    "borrowable_function": ["multi-light product comparison", "emotion transfer through drinking"],
                    "forbidden_carryover": ["do not copy the actor identity", "do not copy exact clothing or product bottle"],
                    "replication_notes": ["make the drinking action natural rather than posed"],
                },
                {
                    "window_index": 3,
                    "start_sec": 10.0,
                    "end_sec": 12.1,
                    "material_type": "video",
                    "shot_type": "person medium shot",
                    "composition": "person on thirds with product as visual anchor",
                    "scene": "sunny outdoor greenery",
                    "scene_details": ["green slope, blue sky, natural top light"],
                    "camera": "locked-off eye-level camera",
                    "camera_position": "chest-level medium shot",
                    "camera_movement": "static",
                    "materials_to_capture": ["translucent drink in sunlight", "natural smile while holding product"],
                    "action_sequence": ["woman lifts the drink", "woman smiles to close the ad"],
                    "product_presence": "product remains in hand and visible",
                    "product_selling_points": ["outdoor occasion fit", "photogenic product look"],
                    "product_satisfaction_points": ["sunlit feel-good smile", "relaxed outdoor mood"],
                    "subtitle_text": "",
                    "voiceover_text": "",
                    "audio_state": "light music and breeze ambience",
                    "borrowable_function": ["emotional close", "visual CTA through smile and product hold"],
                    "forbidden_carryover": ["do not copy the actor identity or accessories"],
                    "replication_notes": ["end on product-in-hand satisfaction, not a blank frame"],
                },
            ],
            "shot_sequence": [
                "1. Backlit ingredient leaves with sun-star",
                "2. Colored liquid poured into a glass",
                "3. Product still on black background",
                "4. Fresh fruit splash macro",
                "5. Product close-up",
                "6. Bright product still",
                "7. Woman holds product indoors",
                "8. Woman drinks outdoors",
                "9. Woman smiles after drinking",
                "10. Outdoor product-in-hand smile close",
            ],
            "product_selling_points": ["fresh ingredient cue", "clean liquid texture", "premium product look", "refreshing drinking occasion"],
            "product_satisfaction_points": ["sun-star freshness", "flowing liquid beauty", "fresh fruit moisture", "post-drink relaxed smile"],
            "subtitle_messages": [],
            "core_satisfaction_mechanism": "The template moves from natural ingredient cues to liquid texture proof, then to real drinking satisfaction.",
            "replication_script": "Director script: open with backlit ingredient leaves, cut to liquid pouring, show product texture, add ingredient proof, then use lifestyle drinking and smile to close.",
            "replication_framework": "Natural ingredient hook -> product texture macro -> lifestyle satisfaction close.",
            "extend_to_15s_plan": "Keep the first-5-second ingredient and liquid- texture framework, then extend with product proof, use-case context, and a non-text visual CTA.",
            "editable_points": [
                {"segment_role": "hook", "editable": True, "reason": "Ingredient location can change as long as the backlit natural hook remains."},
                {"segment_role": "product texture", "editable": False, "reason": "Liquid and texture proof are the core of the template."},
                {"segment_role": "lifestyle scene", "editable": True, "reason": "Use context can adapt to the target audience."},
            ],
        }
    )
    payload["source_analysis"].update(
        {
            "basic_info": "Static product image of an icy watermelon drink in a close-up vertical composition.",
            "audio_facts": "Static image with no audio.",
            "camera_and_editing": "Locked still image, shallow depth of field, no cuts or camera movement.",
            "material_type": "static product-beauty image",
            "scene_and_people": ["no person; product-only still life"],
            "scene_details": ["matte light-gray tabletop", "soft blurred indoor greenery", "mint leaf and watermelon pieces at frame edges", "bright natural light"],
            "subject_framing": "Straight glass centered and filling most of the frame; focus on liquid, ice, condensation, and pulp.",
            "person_appearance_context": "",
            "spoken_language": "none",
            "subtitle_state": "no subtitles",
            "template_profile": {
                "profile": "visual_product_texture",
                "has_human": False,
                "has_voiceover": False,
                "has_visible_face": False,
                "has_real_scene": True,
                "has_platform_cta": False,
                "has_subtitles_or_text": False,
                "should_preserve_person_context": False,
                "should_preserve_voice_language": False,
                "should_preserve_scene_context": True,
                "should_preserve_visual_product_texture": True,
                "primary_transfer_slots": ["product appearance", "condensation", "ice", "fruit pulp", "fresh ingredients"],
            },
            "summary": {
                "creative_type": "static beverage product-beauty image",
                "product_category": "fresh icy watermelon drink",
                "main_value_prop": "icy, fresh, real-fruit summer refreshment",
                "target_persona_guess": "young consumers looking for a cool summer drink",
            },
            "style": {
                "visual_style": "fresh natural-light food photography with shallow depth of field",
                "pacing": "static image",
                "emotion_tone": "cool, refreshing, appetizing",
                "subtitle_style": "no subtitles",
            },
            "structure": {
                "hook_type": "direct sensory product close-up",
                "product_exposure_timing": "product is visible for the full image",
                "cta_type": "sensory desire through icy texture",
                "trust_signals": ["condensation on the glass", "visible pulp", "real ice", "fresh fruit garnish"],
            },
            "segments": [
                {"start_sec": 0.0, "end_sec": 5.0, "role": "solution_demo", "summary": "Complete icy watermelon drink still-life with visible product details.", "product_visible": True, "emotion": "cool and refreshing"}
            ],
            "five_second_windows": [
                {
                    "window_index": 1,
                    "start_sec": 0.0,
                    "end_sec": 5.0,
                    "material_type": "static image",
                    "shot_type": "product close-up",
                    "composition": "vertical centered glass, ingredients near frame edges, blurred background",
                    "scene": "bright tabletop beverage scene",
                    "scene_details": ["light-gray tabletop", "soft blurred greenery", "condensation on glass", "red drink with ice and pulp", "mint and watermelon garnish"],
                    "camera": "shallow-depth-of-field product lens",
                    "camera_position": "eye-level, slightly low",
                    "camera_movement": "none",
                    "materials_to_capture": ["straight clear glass", "red watermelon drink", "ice cubes", "mint leaf", "watermelon pieces"],
                    "action_sequence": ["static product arrangement"],
                    "product_presence": "product is centered and fully visible",
                    "product_selling_points": ["real fruit pulp", "plenty of ice", "clean translucent drink", "fresh ingredient look"],
                    "product_satisfaction_points": ["visual coolness", "clean refreshing look", "real ingredient trust"],
                    "subtitle_text": "",
                    "voiceover_text": "",
                    "audio_state": "no audio",
                    "borrowable_function": ["centered drink close-up", "condensation for icy feel", "ingredient garnish cues"],
                    "forbidden_carryover": ["do not add clutter", "do not cover the product"],
                    "replication_notes": ["preserve glass shape, red color, ice, pulp, mint, watermelon pieces, and condensation"],
                }
            ],
            "shot_sequence": ["single static product close-up"],
            "product_selling_points": ["real watermelon pulp", "plenty of ice", "clean translucent drink", "fresh natural ingredient look"],
            "product_satisfaction_points": ["icy cooling visual", "real ingredient trust", "clean refreshing feel"],
            "subtitle_messages": [],
            "core_satisfaction_mechanism": "Condensation, ice, pulp, and fresh fruit cues create an immediate visual cooling sensation.",
            "replication_script": "Use the source image as product truth: centered clear glass, red drink, ice, pulp, mint, watermelon pieces, and condensation.",
            "replication_framework": "Icy drink close-up with ingredient garnish and shallow-depth-of-field freshness.",
            "extend_to_15s_plan": "Extend into slow push-in, liquid movement, fruit splash, lifestyle drinking, and product-in-hand satisfaction without changing product identity.",
            "editable_points": [
                {"segment_role": "background", "editable": True, "reason": "The background can become a patio, cafe table, or outdoor picnic setting."},
                {"segment_role": "icy texture", "editable": False, "reason": "Condensation and ice are core product satisfaction cues."},
            ],
        }
    )
    payload["rewrite_plan"] = {
        "rewrite_strategy": {
            "strategy_summary": "Borrow the template's natural ingredient hook, liquid texture proof, and lifestyle satisfaction close; replace every grape-drink element with the watermelon drink from the product image.",
            "keep_from_source": [
                "straight clear glass",
                "red watermelon drink",
                "condensation on the glass",
                "ice cubes and fruit pulp",
                "mint leaf and watermelon pieces",
                "fresh icy summer feel",
            ],
            "borrow_from_viral": [
                "first-five-second natural ingredient hook",
                "ingredient-to-liquid-to-product progression",
                "hard-cut camera rhythm",
                "lifestyle drinking satisfaction close",
                "clean natural-light commercial look",
                "no-text visual storytelling",
            ],
            "replace_in_source": [
                "turn static product image into moving ad beats",
                "replace grape ingredients with watermelon ingredients",
                "adapt template product scenes to the source drink",
            ],
            "risk_controls": [
                "no subtitles, on-screen text, stickers, UI, or price tags",
                "all shots must keep the watermelon drink identity from the product image",
                "do not inherit grape-drink bottle, color, flavor, brand, or claims",
                "do not make hard health or efficacy claims",
                "keep the result within 15 seconds",
            ],
        },
        "rewritten_storyboard": {
            "base_video_label": "watermelon_drink_14s_ad",
            "shots": [
                {"shot_index": 1, "role": "hook", "duration_sec": 2.0, "visual_instruction": "Backlit watermelon leaves with a soft sun-star, then a clean hard cut.", "text_overlay": "", "voiceover": "", "keep_from_source": False},
                {"shot_index": 2, "role": "texture", "duration_sec": 3.0, "visual_instruction": "Red watermelon drink pours into the same straight clear glass; ice and ripples show icy freshness.", "text_overlay": "", "voiceover": "", "keep_from_source": True},
                {"shot_index": 3, "role": "proof", "duration_sec": 3.0, "visual_instruction": "Watermelon pieces splash lightly, then macro focus on pulp, ice, and condensation on the glass.", "text_overlay": "", "voiceover": "", "keep_from_source": True},
                {"shot_index": 4, "role": "use_context", "duration_sec": 3.0, "visual_instruction": "Sunny patio scene with a young woman naturally holding and drinking the same watermelon drink.", "text_overlay": "", "voiceover": "", "keep_from_source": False},
                {"shot_index": 5, "role": "visual_cta", "duration_sec": 3.0, "visual_instruction": "Outdoor daylight close: the drink catches sunlight while the person smiles naturally; end on product in hand, no blank tail.", "text_overlay": "", "voiceover": "", "keep_from_source": False},
            ],
        },
        "prompt_package": {
            "base_reference_summary": "Create a 12-15 second 9:16 watermelon drink ad from the product image, borrowing the template's ingredient hook, liquid texture proof, and lifestyle satisfaction close.",
            "style_constraints": {
                "visual_style": "fresh natural-light beverage commercial, clean frame, saturated red drink",
                "pacing": "brisk but stable hard cuts",
                "emotion_tone": "cool, fresh, summery, relaxed",
                "subtitle_rule": "no subtitles or on-screen text",
                "subtitle_style": "No subtitles, no on-screen text, no stickers, no labels.",
            },
            "structure_constraints": {
                "hook_duration": "first 2 seconds use a natural ingredient hook",
                "product_first_exposure_sec": 2,
                "total_duration": "within 15 seconds",
                "core_logic": "ingredient hook -> liquid texture -> product proof -> drinking satisfaction -> visual CTA",
            },
            "scene_instructions": ["backlit watermelon leaves", "macro pour into glass", "watermelon ingredient proof", "sunny patio drinking", "outdoor product-in-hand close"],
            "must_keep": ["straight glass", "red watermelon drink", "ice cubes", "fruit pulp", "condensation", "mint and watermelon garnish"],
            "editable_goals": ["adapt scenes to a summer beverage ad", "keep 9:16 vertical composition", "avoid any grape-drink carryover"],
            "target_audience": "women_20_30",
        },
        "generation_prompt": {
            "prompt": "Rewrite the product image into a 12-15 second 9:16 watermelon drink ad. Borrow only the template's shot rhythm, ingredient hook, liquid texture proof, lifestyle drinking satisfaction, and visual CTA. Keep the source image as product truth: straight clear glass, red watermelon drink, ice cubes, fruit pulp, condensation, mint, and watermelon pieces. Do not inherit the template's grape drink, bottle, brand, flavor, claims, subtitles, or shopping UI. No subtitles, no captions, no on-screen text, no stickers, no labels, no price tags. Music: original background score, non-identifiable, no clear hummable melody, no repeated hook, no existing melody/chord/rhythm motif, no artist imitation, no sampling, no vocals.",
            "reference_video_url": None,
            "reference_image_url": "./assets/examples/source_product.jpg",
        },
    }
    payload["rewrite_brief"] = {
        "template_structure": [
            "backlit natural ingredient hook",
            "liquid pouring macro",
            "product still and ingredient proof",
            "lifestyle drinking scene",
            "smiling product-in-hand close",
        ],
        "template_five_second_summary": [
            "0-5s: natural ingredient sun-star, liquid pour, product texture, fresh fruit proof",
            "5-10s: product in clean light, person holds and drinks in lifestyle context",
            "10-12.1s: outdoor smile with product as visual CTA",
        ],
        "template_director_analysis": [
            "12.1-second no-dialogue beverage commercial",
            "light instrumental music and subtle product sound effects",
            "hard cuts, macro texture shots, product-centered framing",
            "natural ingredient hook -> liquid texture proof -> lifestyle satisfaction",
        ],
        "template_core_satisfaction_mechanism": "Fresh ingredient cue plus liquid texture proof creates desire; the drinking smile closes the ad emotionally.",
        "template_extend_to_15s_plan": "Keep the template's first-five-second logic, then extend with product details, use context, and a product-in-hand visual CTA.",
        "template_person_appearance_context": "",
        "template_spoken_language": "",
        "template_subtitle_state": "no subtitles or on-screen text",
        "template_profile": "visual_product_texture",
        "template_profile_slots": ["shot order", "liquid texture", "ingredient proof", "lifestyle satisfaction", "music mood"],
        "borrowable_elements": ["natural ingredient hook", "liquid pour texture", "ingredient proof", "hard-cut rhythm", "lifestyle drinking close", "no-text visual storytelling"],
        "forbidden_template_elements": ["template grape drink category", "template bottle and packaging", "template brand, flavor, claims, subtitles, prices, and shopping prompts"],
        "source_product_identity": "fresh icy watermelon drink",
        "source_product_anchors": ["straight clear glass", "red watermelon drink", "ice cubes", "fruit pulp", "condensation", "mint leaf", "watermelon pieces", "fresh summer drink mood"],
        "confirmed_selling_points": ["real watermelon pulp", "plenty of ice", "clean translucent drink", "fresh ingredient look"],
        "uncertain_or_unproven_points": ["Do not invent health, efficacy, parameter, or brand claims that are not visible in the product image."],
        "rewrite_strategy": "Use the template structure, not its product identity, to create a watermelon drink ad.",
        "risks": ["grape-drink semantics leaking into the result", "invented claims", "generated subtitles or shopping UI", "product appearance drift"],
    }
    payload["prompt_preview"] = {
        "user_summary": "\n".join(
            [
                "Generation prompt preview (user-readable)",
                "- Target audience: women_20_30",
                "- Objective: improve_ctr",
                "- Product identity / must keep: fresh icy watermelon drink in the same straight clear glass with red liquid, ice, pulp, condensation, mint, and watermelon pieces.",
                "- Output: 9:16, 720p",
                "- Generate audio: yes",
                "- Rewrite strategy: borrow the template's natural ingredient hook, liquid texture proof, and lifestyle satisfaction close; replace grape-drink semantics with watermelon drink cues.",
                "- Keep from source image: straight glass; red watermelon drink; ice cubes and pulp; condensation; mint and watermelon garnish.",
                "- Borrow from template: first-five-second ingredient hook; macro pour; hard-cut rhythm; product proof; lifestyle drinking close.",
                "- Risk controls: no grape product, no subtitles, no on-screen text, no price tags, no shopping prompts, no invented claims.",
                "- Shot script:",
                "  1. hook / 2.0s: Backlit watermelon leaves with a soft sun-star.",
                "  2. texture / 3.0s: Red watermelon drink pours into the same straight clear glass with ice and ripples.",
                "  3. proof / 3.0s: Watermelon pieces splash lightly; macro details show pulp, ice, and condensation.",
                "  4. use_context / 3.0s: Sunny patio drinking moment with the same product in hand.",
                "  5. visual_cta / 3.0s: Outdoor product-in-hand smile close, no blank tail.",
                "- Forbidden: subtitles, on-screen text, stickers, price tags, shopping prompts, or template product identity leakage.",
                "- Music: original background score, non-identifiable, no clear hummable melody, no repeated hook, no existing melody/chord/rhythm motif, no artist imitation, no sampling, no vocals.",
            ]
        ),
        "full_prompt": payload["rewrite_plan"]["generation_prompt"]["prompt"],
    }
    return payload


def load_rehearsal_prepared(language: str = "zh") -> PreparedRewrite:
    payload = read_json(REHEARSAL_PREPARED_PATH)
    if language == "en":
        payload = localize_rehearsal_payload_en(payload)
    payload["request"] = resolve_media_paths(payload["request"], base_path=BASE_DIR)
    return PreparedRewrite.model_validate(payload)


def _append_unique(base: list, additions: list) -> list:
    result = list(base)
    for item in additions:
        if item not in result:
            result.append(item)
    return result


def _apply_replace_and_append(model, *, replace=None, append=None, language: str = "zh"):
    data = model.model_dump()
    if replace:
        data.update(replace)
    if append:
        for key, values in append.items():
            current = data.get(key)
            if not isinstance(current, list):
                if language == "en":
                    raise SystemExit(f"Patch field {key} is not a list, so append cannot be applied.")
                raise SystemExit(f"patch 字段 {key} 不是列表，不能 append。")
            if not isinstance(values, list):
                if language == "en":
                    raise SystemExit(f"Patch append value for {key} must be a list.")
                raise SystemExit(f"patch 字段 {key} 的 append 值必须是列表。")
            data[key] = _append_unique(current, values)
    return type(model).model_validate(data)


def apply_prepared_patch(prepared: PreparedRewrite, patch_path: Path | None) -> PreparedRewrite:
    from services import normalize_prepared_for_generation, refresh_prepared_with_brief

    if not patch_path:
        return normalize_prepared_for_generation(prepared)
    patch = read_json(patch_path)
    language = request_language(prepared.request)
    request = _apply_replace_and_append(
        prepared.request,
        replace=patch.get("request"),
        append=patch.get("append_request"),
        language=language,
    )
    brief = _apply_replace_and_append(
        prepared.rewrite_brief,
        replace=patch.get("rewrite_brief"),
        append=patch.get("append_rewrite_brief"),
        language=language,
    )
    return normalize_prepared_for_generation(refresh_prepared_with_brief(prepared.model_copy(update={"request": request}), brief))


def print_request_summary(request: RewriteRequest, *, language: str = "zh") -> None:
    if language == "en":
        print("Request validated.")
        print(f"- Template media type: {request.viral_media_type}")
        print("- Product media type: image")
        print(f"- Target audience: {request.target_audience}")
        print(f"- Objective: {request.objective}")
        print(f"- Output: {request.output_ratio}, {request.output_resolution}")
        print(f"- Original music: {'on' if request.generate_audio else 'off'}")
        return
    print("请求已校验。")
    print(f"- 模板类型：{request.viral_media_type}")
    print("- 商品素材类型：image")
    print(f"- 目标人群：{request.target_audience}")
    print(f"- 目标：{request.objective}")
    print(f"- 输出规格：{request.output_ratio}，{request.output_resolution}")
    print(f"- 原创配乐：{'开启' if request.generate_audio else '关闭'}")


def write_rehearsal_result(path: Path, prepared: PreparedRewrite, *, language: str = "zh") -> None:
    payload = read_json(REHEARSAL_RESULT_PATH)
    if language == "en":
        payload.update(
            {
                "summary": "Example rehearsal result: this is a pre-generated real watermelon-drink sample video for the no-cost confirmation flow. This rehearsal does not call Seedance again.",
                "manual_review_checklist": [
                    "Watch the bundled real watermelon-drink sample video first, then review the task information.",
                    "Confirm the product identity comes from the watermelon drink product image, not the grape-drink template.",
                    "Confirm there are no subtitles, price tags, shopping buttons, stickers, or template brand remnants.",
                    "Confirm the first five seconds have a clear hook and later shots extend texture, use context, and visual close.",
                    "Confirm the music direction is original, non-identifiable, and non-vocal.",
                ],
            }
        )
    payload["request"] = prepared.request.model_dump()
    payload["rewrite_brief"] = prepared.rewrite_brief.model_dump()
    payload["prompt_preview"] = prepared.prompt_preview.model_dump()
    payload["preview_image_path"] = str(REHEARSAL_PREVIEW_PATH) if REHEARSAL_PREVIEW_PATH.exists() else ""
    write_json(path, payload)


def print_rehearsal_result(path: Path, *, language: str = "zh", media_style: str = "codex") -> None:
    payload = read_json(REHEARSAL_RESULT_PATH)
    if language == "en":
        print("\nExample rehearsal result (not a real generation)")
        if REHEARSAL_PREVIEW_PATH.exists():
            print("This is the bundled real watermelon-drink sample video. This rehearsal does not call Seedance and does not incur cost.")
            print(media_markdown("Example result video", REHEARSAL_PREVIEW_PATH, style=media_style))
        else:
            print("This repository package does not include bundled `.mp4` example videos. The rehearsal result metadata is still shown, and no Seedance call or cost is incurred.")
        print(f"Task ID: {payload.get('seedance_task_id', 'rehearsal-example-no-task')}")
        english_checklist = [
            "Watch the bundled real watermelon-drink sample video first, then review the task information.",
            "Confirm the product identity comes from the watermelon drink product image, not the grape-drink template.",
            "Confirm there are no subtitles, price tags, shopping buttons, stickers, or template brand remnants.",
            "Confirm the first five seconds have a clear hook and later shots extend texture, use context, and visual close.",
            "Confirm the music direction is original, non-identifiable, and non-vocal.",
        ]
        for item in english_checklist:
            print(f"- {item}")
        print(f"Example result JSON saved: {path}")
        return
    print("\n示例彩排结果（不是真实生成）")
    if REHEARSAL_PREVIEW_PATH.exists():
        print("这里展示的是 skill 内置的真实西瓜果饮样例视频；本次彩排不调用 Seedance，也不会产生费用。")
        print(media_markdown("示例结果视频", REHEARSAL_PREVIEW_PATH, style=media_style))
    else:
        print("当前仓库提交包不包含内置 `.mp4` 示例视频；这里仍展示彩排结果元信息，不调用 Seedance，也不会产生费用。")
    print(f"任务 ID：{payload.get('seedance_task_id', 'rehearsal-example-no-task')}")
    for item in payload.get("manual_review_checklist", []):
        print(f"- {item}")
    print(f"示例结果 JSON 已保存：{path}")


def _seedance_example_paths() -> list[str]:
    paths = [str(path) for path in SEEDANCE_SHOWCASE_PATHS if path.exists()]
    extra = os.getenv("SEEDANCE_EXAMPLE_VIDEOS", "").strip()
    if extra:
        for item in extra.split(os.pathsep):
            item = item.strip()
            if item:
                paths.append(item)
    return paths


def print_seedance_advantages_and_examples(*, language: str = "zh", media_style: str = "codex") -> None:
    if language == "en":
        print("\nWhy Seedance 2.0 is useful for the final production step")
        print(
            "It supports mixed text, image, video, and audio inputs; accurately preserves material traits from references; "
            "maintains character and style consistency across shots with coherent multi-shot storytelling; native audio-video synchronization "
            "and AI-director-style generation lower the creation barrier; strong physical realism and accurate complex-instruction following; "
            "supports video editing and offers three performance tiers for different needs; well suited for ecommerce and other commercial scenarios, "
            "with stronger compliance, significant efficiency gains, and lower production costs."
        )
        print("\nProduction example videos")
        for index, path in enumerate(_seedance_example_paths(), start=1):
            print(media_markdown(f"Seedance example {index}", path, style=media_style))
        return
    print("\nSeedance 2.0 作为最终视频生产步骤的优势")
    print(
        "支持文本、图片、视频、音频四模态混合输入，能精准复刻素材特征，实现跨镜头角色风格统一与多镜头连贯叙事；"
        "原生音画同步，AI 导演降低创作门槛；物理真实度高、复杂指令遵循准；支持视频编辑，提供三档性能版本适配不同需求，"
        "适配电商等商业场景，合规有保障，提效降本显著。"
    )
    print("\n生产视频示例")
    for index, path in enumerate(_seedance_example_paths(), start=1):
        print(media_markdown(f"Seedance 示例视频 {index}", path, style=media_style))


def _brief_items(items: list[str], limit: int = 4, *, language: str = "zh") -> str:
    cleaned = [item.strip() for item in items if item and item.strip()]
    if not cleaned:
        return ""
    separator = "; " if language == "en" else "；"
    return separator.join(cleaned[:limit])


def print_confirmed_missing_key_snapshot(prepared: PreparedRewrite, *, language: str = "zh") -> None:
    brief = prepared.rewrite_brief
    request = prepared.request
    product = brief.source_product_identity or request.product_context or "the product image"
    anchors = _brief_items(brief.source_product_anchors, language=language)
    strategy = brief.rewrite_strategy or prepared.prompt_preview.user_summary
    output = f"{request.output_ratio} / {request.output_resolution}"
    audio = "on" if request.generate_audio else "off"
    if language == "en":
        print("\nConfirmed brief snapshot")
        print(f"- Product: {product}")
        if anchors:
            print(f"- Product anchors: {anchors}")
        print(f"- Rewrite direction: {strategy}")
        print(f"- Output: {output}, audio {audio}")
        print("- This confirmed prepared brief can be sent to Seedance after ARK_API_KEY is configured; media analysis will not be repeated.")
        return

    print("\n已确认 brief 摘要")
    print(f"- 商品：{product}")
    if anchors:
        print(f"- 商品锚点：{anchors}")
    print(f"- 生成方向：{strategy}")
    print(f"- 输出：{output}，音频{'开启' if request.generate_audio else '关闭'}")
    print("- 配好 ARK_API_KEY 后会直接用这份 confirmed prepared brief 提交 Seedance，不重新分析素材。")


def print_agent_preparation_required(request: RewriteRequest, *, language: str = "zh") -> None:
    if language == "en":
        print("\nAgent analysis required before running this script.")
        print("Video understanding and rewrite planning are no longer performed by ModelArk/Seed inside the runner.")
        print("Use the current agent to inspect the template video and product image, write the prepared JSON, then rerun with --prepared-input-json.")
        print("This keeps template understanding in the agent and uses Seedance only for final video generation.")
        return
    print("\n需要先由 Agent 完成分析。")
    print("runner 已不再用 ModelArk/Seed 做视频理解和改写规划。")
    print("请先由当前 Agent 理解模板视频和商品图，写出 prepared JSON，再用 --prepared-input-json 交给 runner。")
    print("这样大语言模型/视频理解都留在当前 Agent，Seedance 只负责最终视频生成。")


def main() -> None:
    args = parse_args()
    load_env_file(args.env_file)
    if args.rehearsal and (args.input_json or args.prepared_input_json):
        raise SystemExit("--rehearsal 使用 skill 内置示例，不需要 --input-json 或 --prepared-input-json。")
    if not args.rehearsal and not args.input_json and not args.prepared_input_json:
        raise SystemExit("请提供 --input-json 或 --prepared-input-json。")
    if args.setup_only and args.prepared_input_json:
        raise SystemExit("--setup-only 需要 --input-json，不使用 prepared JSON。")
    input_path = Path(args.input_json).expanduser().resolve() if args.input_json else None
    prepared_input_path = Path(args.prepared_input_json).expanduser().resolve() if args.prepared_input_json else None
    patch_path = Path(args.patch_json).expanduser().resolve() if args.patch_json else None

    if args.rehearsal:
        language = request_language(None, args.ui_language)
        prepared = apply_prepared_patch(load_rehearsal_prepared(language), patch_path)
        language = request_language(prepared.request, args.ui_language)
        show_detail_stage = args.show_detailed_analysis or args.show_debug_artifacts
        show_prepared_stage = args.prepare_only or show_detail_stage or not args.confirmed_brief
        if show_prepared_stage:
            if language == "en":
                print("No-cost full-flow rehearsal: replaying bundled prepared/result artifacts without calling ModelArk or Seedance.")
            else:
                print("无成本完整彩排：使用 skill 内置示例 prepared/result 回放，不调用 ModelArk 或 Seedance。")
            from services import print_analysis_details, print_prepared_readout

            if show_detail_stage:
                print_analysis_details(prepared, show_full_prompt=args.show_full_prompt)
            else:
                print_prepared_readout(prepared, show_full_prompt=args.show_full_prompt)
        else:
            print("No-cost full-flow rehearsal: reusing the bundled prepared artifact and showing the confirmed example result." if language == "en" else "无成本完整彩排：复用 skill 内置示例 prepared，继续展示确认后的示例结果。")
        prepared_path = (
            Path(args.prepared_json).expanduser().resolve()
            if args.prepared_json
            else output_dir_from_env() / "rehearsal.prepared.json"
        )
        write_json(prepared_path, prepared.model_dump())
        print(f"Example prepared JSON saved: {prepared_path}" if language == "en" else f"示例 prepared JSON 已保存：{prepared_path}")
        if args.prepare_only or not args.confirmed_brief:
            if show_detail_stage:
                print(
                    "Detailed analysis shown above. Reply \"confirm generation\" to continue to the example result, or tell me what to change; no external model will be called."
                    if language == "en"
                    else "以上为完整详细分析。回复“确认生成”继续看示例结果，或直接说要改哪里；仍然不会调用外部模型。"
                )
            else:
                print(
                    "The example rehearsal has reached the pre-generation confirmation gate. Reply \"show detailed analysis\" or \"confirm generation\" to continue to the example result; no external model will be called."
                    if language == "en"
                    else "示例彩排已到生成确认前。可以回复“查看详细分析”，或回复“确认生成”继续看示例结果；仍然不会调用外部模型。"
                )
            if args.show_debug_artifacts:
                print(json.dumps(prepared.model_dump(), ensure_ascii=False, indent=2))
            return
        out_path = (
            Path(args.output_json).expanduser().resolve()
            if args.output_json
            else output_dir_from_env() / "rehearsal.result.json"
        )
        write_rehearsal_result(out_path, prepared, language=language)
        print_rehearsal_result(out_path, language=language, media_style=args.media_style)
        if args.show_debug_artifacts:
            print(json.dumps(read_json(out_path), ensure_ascii=False, indent=2))
        return

    prepared = None
    if prepared_input_path:
        prepared = PreparedRewrite.model_validate(read_json(prepared_input_path))
        prepared = apply_prepared_patch(prepared, patch_path)
        request = prepared.request
    else:
        request = load_request(input_path)
    language = request_language(request, args.ui_language)

    missing_key = missing_env(REQUIRED_ARK_ENV)
    can_preview_prepared_without_key = prepared_input_path and args.prepare_only
    if missing_key and prepared is None and not args.setup_only and is_local_template_video(request):
        ensure_analysis_dependencies(base_dir=BASE_DIR, language=language)
    if args.setup_only or (missing_key and not can_preview_prepared_without_key):
        print_request_summary(request, language=language)
        if prepared is not None and missing_key:
            from services import print_analysis_details, print_prepared_readout

            if args.show_debug_artifacts:
                print_analysis_details(prepared, show_full_prompt=args.show_full_prompt)
            else:
                print_prepared_readout(prepared, show_full_prompt=args.show_full_prompt)
        if args.show_debug_artifacts:
            print(json.dumps(request.model_dump(), ensure_ascii=False, indent=2))
        if missing_key:
            if prepared is None:
                print_agent_preparation_required(request, language=language)
            else:
                print_confirmed_missing_key_snapshot(prepared, language=language)
            print(
                "ARK_API_KEY is not configured: the confirmed prepared brief is reusable; Seedance generation was not called, no resources were consumed, and no new video was generated."
                if language == "en"
                else "ARK_API_KEY 未配置：当前已确认的 prepared brief 可以复用；未调用 Seedance、未消耗资源、也未生成新视频。"
            )
            print_seedance_advantages_and_examples(language=language, media_style=args.media_style)
            env_path = Path(args.env_file).expanduser()
            if not env_path.is_absolute():
                env_path = Path.cwd() / env_path
            print_real_generation_setup_flow(language)
            print_local_key_setup_hint(str(env_path), language)
        return

    from services import execute_rewrite

    if prepared is None:
        if is_local_template_video(request):
            ensure_analysis_dependencies(base_dir=BASE_DIR, language=language)
        print_request_summary(request, language=language)
        print_agent_preparation_required(request, language=language)
        return
    else:
        print("Loaded prepared JSON from agent analysis; no ModelArk/Seed media analysis will be called." if language == "en" else "已读取由 Agent 分析得到的 prepared JSON；不会调用 ModelArk/Seed 做素材理解。")
        if patch_path:
            print(f"Applied pre-generation patch: {patch_path}" if language == "en" else f"已应用生成前 patch：{patch_path}")
        if args.show_debug_artifacts:
            from services import print_analysis_details

            print_analysis_details(prepared, show_full_prompt=args.show_full_prompt)
    prepared_path = (
        Path(args.prepared_json).expanduser().resolve()
        if args.prepared_json
        else default_sidecar_path(input_path or prepared_input_path, "prepared")
    )
    write_json(prepared_path, prepared.model_dump())
    print(f"prepared JSON saved: {prepared_path}" if language == "en" else f"prepared JSON 已保存：{prepared_path}")
    if args.prepare_only:
        if args.show_debug_artifacts:
            print(json.dumps(prepared.model_dump(), ensure_ascii=False, indent=2))
        return
    if not args.confirmed_brief:
        if language == "en":
            raise SystemExit(
                "Analysis and prompt preview are complete, but generation was not executed.\n"
                f"prepared JSON: {prepared_path}\n"
                "Ask the user to confirm the prepared brief first; after confirmation rerun with --confirmed-brief for real generation."
            )
        raise SystemExit(
            "已完成模板/商品图分析和提示词预览，但未执行生成。\n"
            f"prepared JSON：{prepared_path}\n"
            "请先让用户确认 prepared brief；确认后再加 --confirmed-brief 执行真实生成。"
        )
    from services import generation_contract_blocking_message

    contract_issue = generation_contract_blocking_message(prepared, language=language)
    if contract_issue:
        raise SystemExit(contract_issue)
    ensure_core_dependencies(base_dir=BASE_DIR, include_provider=True)
    response = execute_rewrite(prepared)
    out_path = (
        Path(args.output_json).expanduser().resolve()
        if args.output_json
        else default_sidecar_path(input_path or prepared_input_path, "result")
    )
    write_json(out_path, response.model_dump())
    print("\nGeneration complete." if language == "en" else "\n生成完成。")
    video_alt = "Generated video" if language == "en" else "生成视频"
    if response.rewritten_video_local_path:
        print(media_markdown(video_alt, response.rewritten_video_local_path, style=args.media_style))
    elif response.rewritten_video_url:
        print(media_markdown(video_alt, response.rewritten_video_url, style=args.media_style))
    if response.seedance_task_id:
        print(f"Task ID: {response.seedance_task_id}" if language == "en" else f"任务 ID：{response.seedance_task_id}")
    print(f"Result JSON saved: {out_path}" if language == "en" else f"结果 JSON 已保存：{out_path}")
    if args.show_debug_artifacts:
        print(json.dumps(response.model_dump(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
