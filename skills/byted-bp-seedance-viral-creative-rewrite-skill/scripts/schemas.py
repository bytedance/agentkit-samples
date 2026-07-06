# Copyright (c) 2026 BytePlus. All rights reserved.
# SPDX-License-Identifier: Proprietary
from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class RewriteRequest(BaseModel):
    viral_video: str
    viral_media_type: Literal["video", "image", "url"] = "video"
    source_media_type: Literal["image"] = "image"
    source_image: Optional[str] = None
    ui_language: Literal["auto", "zh", "en"] = "auto"
    target_audience: str = "broad_ecommerce"
    objective: str = "improve_ctr"
    product_context: str = ""
    extra_constraints: List[str] = Field(default_factory=list)
    output_ratio: str = "9:16"
    output_resolution: str = "720p"
    generate_audio: bool = True


class VlmSummary(BaseModel):
    creative_type: str
    product_category: str
    main_value_prop: str
    target_persona_guess: str


class VlmStyle(BaseModel):
    visual_style: str
    pacing: str
    emotion_tone: str
    subtitle_style: str


class VlmStructure(BaseModel):
    hook_type: str
    product_exposure_timing: str
    cta_type: str
    trust_signals: List[str]


class VlmSegment(BaseModel):
    start_sec: float
    end_sec: float
    role: str
    summary: str
    product_visible: bool
    emotion: str


class VlmEditablePoint(BaseModel):
    segment_role: str
    editable: bool
    reason: str


class FiveSecondWindow(BaseModel):
    window_index: int
    start_sec: float
    end_sec: float
    material_type: str = ""
    shot_type: str = ""
    composition: str = ""
    scene: str = ""
    scene_details: List[str] = Field(default_factory=list)
    camera: str = ""
    camera_position: str = ""
    camera_movement: str = ""
    materials_to_capture: List[str] = Field(default_factory=list)
    action_sequence: List[str] = Field(default_factory=list)
    product_presence: str = ""
    product_selling_points: List[str] = Field(default_factory=list)
    product_satisfaction_points: List[str] = Field(default_factory=list)
    subtitle_text: str = ""
    voiceover_text: str = ""
    audio_state: str = ""
    borrowable_function: List[str] = Field(default_factory=list)
    forbidden_carryover: List[str] = Field(default_factory=list)
    replication_notes: List[str] = Field(default_factory=list)


class TemplateProfile(BaseModel):
    profile: Literal["unknown", "visual_product_texture", "human_demo", "human_voiceover", "platform_cta", "mixed"] = "unknown"
    has_human: bool = False
    has_voiceover: bool = False
    has_visible_face: bool = False
    audio_track_confirmed: bool = False
    has_real_scene: bool = False
    has_platform_cta: bool = False
    has_subtitles_or_text: bool = False
    should_preserve_person_context: bool = False
    should_preserve_voice_language: bool = False
    should_preserve_scene_context: bool = False
    should_preserve_visual_product_texture: bool = True
    primary_transfer_slots: List[str] = Field(default_factory=list)


class VideoAnalysis(BaseModel):
    model_config = ConfigDict(extra="ignore")

    video_label: str
    duration_sec: Optional[float] = None
    fps: Optional[float] = None
    total_frames: Optional[int] = None
    basic_info: str = ""
    audio_facts: str = ""
    camera_and_editing: str = ""
    material_type: str = ""
    scene_and_people: List[str] = Field(default_factory=list)
    scene_details: List[str] = Field(default_factory=list)
    subject_framing: str = ""
    person_appearance_context: str = ""
    spoken_language: str = ""
    subtitle_state: str = ""
    template_profile: TemplateProfile = Field(default_factory=TemplateProfile)
    summary: VlmSummary
    style: VlmStyle
    structure: VlmStructure
    segments: List[VlmSegment]
    five_second_windows: List[FiveSecondWindow] = Field(default_factory=list)
    shot_sequence: List[str] = Field(default_factory=list)
    product_selling_points: List[str] = Field(default_factory=list)
    product_satisfaction_points: List[str] = Field(default_factory=list)
    subtitle_messages: List[str] = Field(default_factory=list)
    core_satisfaction_mechanism: str = ""
    replication_script: str = ""
    replication_framework: str = ""
    extend_to_15s_plan: str = ""
    editable_points: List[VlmEditablePoint]


class RewriteStrategy(BaseModel):
    strategy_summary: str
    keep_from_source: List[str]
    borrow_from_viral: List[str]
    replace_in_source: List[str]
    risk_controls: List[str]


class RewrittenStoryboardShot(BaseModel):
    shot_index: int
    role: str
    duration_sec: float
    visual_instruction: str
    text_overlay: str
    voiceover: str
    keep_from_source: bool


class RewrittenStoryboard(BaseModel):
    base_video_label: str
    shots: List[RewrittenStoryboardShot]


class PromptPackage(BaseModel):
    base_reference_summary: str
    style_constraints: dict
    structure_constraints: dict
    scene_instructions: List[str]
    must_keep: List[str]
    editable_goals: List[str]
    target_audience: str


class GenerationPrompt(BaseModel):
    prompt: str
    reference_video_url: Optional[str] = None
    reference_image_url: Optional[str] = None


class RewritePlan(BaseModel):
    rewrite_strategy: RewriteStrategy
    rewritten_storyboard: RewrittenStoryboard
    prompt_package: PromptPackage
    generation_prompt: GenerationPrompt


class PromptPreview(BaseModel):
    user_summary: str
    full_prompt: str


class RewriteBrief(BaseModel):
    template_structure: List[str] = Field(default_factory=list)
    template_five_second_summary: List[str] = Field(default_factory=list)
    template_director_analysis: List[str] = Field(default_factory=list)
    template_core_satisfaction_mechanism: str = ""
    template_extend_to_15s_plan: str = ""
    template_person_appearance_context: str = ""
    template_spoken_language: str = ""
    template_subtitle_state: str = ""
    template_profile: str = ""
    template_profile_slots: List[str] = Field(default_factory=list)
    borrowable_elements: List[str] = Field(default_factory=list)
    forbidden_template_elements: List[str] = Field(default_factory=list)
    source_product_identity: str = ""
    source_product_anchors: List[str] = Field(default_factory=list)
    confirmed_selling_points: List[str] = Field(default_factory=list)
    uncertain_or_unproven_points: List[str] = Field(default_factory=list)
    rewrite_strategy: str = ""
    risks: List[str] = Field(default_factory=list)


class PreparedRewrite(BaseModel):
    request: RewriteRequest
    viral_analysis: VideoAnalysis
    source_analysis: VideoAnalysis
    rewrite_plan: RewritePlan
    rewrite_brief: RewriteBrief
    prompt_preview: PromptPreview


class GeneratedVideoArtifact(BaseModel):
    task_id: Optional[str] = None
    generated_at: str
    cache_key: str
    remote_video_url: str
    local_video_path: str
    contact_sheet_path: Optional[str] = None
    contact_sheet_status: str = ""


class RewriteVideoResponse(BaseModel):
    request: RewriteRequest
    viral_analysis: VideoAnalysis
    source_analysis: VideoAnalysis
    rewrite_plan: RewritePlan
    rewritten_video_url: str
    rewritten_video_remote_url: Optional[str] = None
    rewritten_video_local_path: Optional[str] = None
    seedance_task_id: Optional[str] = None
    generated_at: Optional[str] = None
    cache_key: Optional[str] = None
    contact_sheet_path: Optional[str] = None
    artifact: Optional[GeneratedVideoArtifact] = None
