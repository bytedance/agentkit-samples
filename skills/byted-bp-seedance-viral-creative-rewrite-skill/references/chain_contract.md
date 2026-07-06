# Viral Creative Rewrite Chain Contract

This document is the product and engineering contract for the `byted-bp-seedance-viral-creative-rewrite-skill` workflow. It exists because manual testing showed that fixing one badcase at a time is not enough: the skill must keep the same state, prepared artifact, renderer, prompt compiler, and execution gate aligned.

## Core Principle

The user-facing language, the template analysis facts, and the final video-generation constraints are different layers.

- UI language controls chat, opening copy, brief, detailed analysis, setup guidance, and prompt-preview labels.
- Template spoken language controls generated voiceover language for `human_voiceover` templates.
- Template person appearance / market visual context controls generated presenter casting for `human_demo` and `human_voiceover` templates.
- Product image facts control the product identity, appearance, packaging, visible ingredients, and confirmed selling points.
- Target audience controls style, context, and persuasion angle, but must not override template language, template person / market visual context, lip-sync requirements, or factual product anchors.

If any layer conflicts with another layer, the workflow must surface the conflict before Seedance submission instead of guessing.

## State Contract

All frontstage states must be rendered through canonical scripts. The agent must not hand-write shorter replacements.

| State | Canonical renderer or runner | Allowed user-facing content | Forbidden leakage |
| --- | --- | --- | --- |
| `START_OPENING` | `scripts/render_opening.py` | Skill purpose, two media roles, default media, category/face guidance, grouped input request | `确认生成`, `confirm generation`, raw paths, setup-only wording |
| `REAL_ANALYSIS_REQUESTED` | Host-agent analysis plus local artifacts outside skill source | Short progress only | Raw prepared JSON, prompt payloads, Python heredocs, detailed conclusions before brief |
| `BRIEF_READY` | `scripts/render_brief.py` | Compact brief, detail option, edit option, final confirmation option | Full JSON, long detailed sections, debug prompt |
| `DETAIL_VIEW` | `scripts/render_detailed_analysis.py` | Full detailed analysis in the user's language | Short recap such as `关键结论不变` or `shown above` |
| `BRIEF_EDITING` | `scripts/apply_brief_patch.py` | Refreshed brief from patched prepared | Re-analyzing unchanged media |
| `GENERATION_CONFIRMED` | `scripts/confirm_generation.py` | Either real generation or full missing-key guidance | Manual `.env` short answer, direct `run_rewrite_video.py --confirmed-brief` frontstage call |
| `MISSING_KEY_FULL_GUIDANCE` | `scripts/render_missing_key_guidance.py` through `confirm_generation.py` | Reusable brief, no-call state, Seedance advantages, playable examples, account/key setup | A short no-key reply |
| `GENERATION_DONE` | `scripts/render_generation_result.py` | Generated video first, task ID, manual review checklist | Engineering-only result dump as the first screen |

## Prepared Artifact Contract

The prepared artifact is not automatically trusted. Before any display, patch, confirmation, or generation path, it must be normalized.

Required normalized layers:

- `viral_analysis`: observed template facts only.
- `source_analysis`: observed product-image facts only.
- `rewrite_brief`: transfer policy and generation direction derived from facts.
- `rewrite_plan`: storyboard and prompt package after brief policy is applied.
- `prompt_preview`: final user-readable summary plus compiled prompt preview.

Forbidden prepared pollution:

- UI language deciding template voiceover language.
- Target audience deciding template voiceover language.
- Target audience deciding presenter ethnicity, broad appearance, or market visual context for a human-presenter template.
- Product white-background image overwriting a real-scene template.
- Product-image no-face guidance overwriting a visible-face presenter template.
- Platform CTA page becoming a real platform UI ending.
- Unconfirmed product claims becoming hard selling points.
- Old prompt fragments surviving after a patch.

## Template Profile Contract

### `visual_product_texture`

Use for drinks, food, product static shots, material demos, texture/state-change ads.

Must preserve:

- first-five-second hook
- shot order and camera rhythm
- product state and texture changes
- ingredient/product proof
- scene mood and music mood
- visual satisfaction

Must not automatically add:

- voiceover
- lip sync
- person ethnicity/appearance constraints
- subtitle logic

### `human_demo`

Use for visible human demonstrations, try-on, hand-use, or presenter action without strong speech.

Must preserve:

- human framing
- action sequence
- product-human relationship
- broad expression/eye-contact if central
- real scene context

Must not invent voiceover.

### `human_voiceover`

Use for creator/presenter videos with spoken explanation.

Must preserve:

- broad person appearance / market visual context
- template spoken language
- voiceover rhythm
- mouth/gesture synchronization
- real scene
- action order

Must generate:

- a new non-identical person
- original wording
- a new non-identifiable voice

Must not:

- copy the original speaker identity, voice, account, or wording
- translate the template voiceover language because the UI language is different
- add subtitles/captions by default

If template spoken language is unknown, confirmed generation must block before Seedance.

### `platform_cta`

Only the CTA function can transfer. Platform UI, search pages, watermarks, accounts, captions, and blank endings are forbidden carryover.

## Voiceover Language Contract

This contract is mandatory for `human_voiceover`.

- Chinese UI + English template voiceover -> generated video uses English original voiceover.
- English UI + Chinese template voiceover -> generated video uses Chinese Mandarin original voiceover.
- Target audience never overrides template spoken language.
- Target audience never overrides template person appearance / market visual context. For example, an English/TikTok fashion-presenter template inside a Chinese UI and a Chinese target-audience brief must still preserve the template's broad presenter/market visual context while generating a new non-identical person.
- Product category never overrides template spoken language.
- If the spoken language cannot be confidently determined, do not guess. Block confirmed generation and ask for the real template language.
- The compiled prompt must include a hard `VOICEOVER LANGUAGE LOCK`.
- The compiled prompt must include a hard `PERSON CONTEXT LOCK` for `human_demo` and `human_voiceover`.
- The compiled prompt must include a hard `LIP-SYNC LOCK` for `human_voiceover`: visible mouth shapes, jaw movement, expression, eye contact, and gestures must synchronize with the generated same-language audio.

Forbidden prompt contradictions:

- English template language plus `中文口播`, `原创中文短句`, `中文导购式表达`, `Chinese voiceover`, or `original Chinese presenter-style wording`.
- Chinese template language plus `English voiceover`, `English presenter-style wording`, or `英文口播`.
- Any voiceover/lip-sync hard constraint inside a `visual_product_texture` route.

## Prompt Compiler Contract

The final prompt is the only thing Seedance sees, so it must be treated as a compiled artifact, not a loose summary.

Before Seedance submission, the runner must validate:

- template profile and active transfer slots
- no subtitles, captions, platform UI, price tags, stickers, watermarks, or shopping prompts
- product-visible ending
- product identity does not switch to the template product
- `human_voiceover` has a real spoken-language lock
- `human_voiceover` / `human_demo` has a real template person-context lock when a presenter is central
- `human_voiceover` has a real lip-sync lock
- a human-presenter template (`human_demo` / `human_voiceover`) has its audio track confirmed: `template_profile.audio_track_confirmed=true` is required before generation. Set it only after actually listening to the audio (`extract_video_frames.py --with-audio`) or confirming `has_audio_stream=false`. If demo-vs-voiceover is still ambiguous, expose it in the brief for the user to decide instead of guessing.
- prompt does not contain contradictory voiceover-language instructions
- prompt does not let target audience or UI language become the presenter casting rule
- `visual_product_texture` does not contain voiceover/lip-sync hard constraints

If validation fails, the runner must stop before Seedance and print an actionable blocking message.

## Renderer Contract

Brief and detailed analysis must come from the same normalized prepared artifact.

- `render_brief.py` shows compact decision content only.
- `render_detailed_analysis.py` shows full details: template facts, profile reason, audio/subtitle/voiceover state, camera/editing, every-five-second windows, borrowable mechanics, forbidden carryover, product-image analysis, confirmed/unproven claims, proposed generation script, constraints, and next edit/confirm options.
- Chinese rendering must not leak raw schema tokens such as `human_voiceover`, `lip_sync`, `UI`, or English placeholders such as `same as the original template spoken language`.
- English rendering must not wrap Chinese detailed content in English headings.

## Regression Matrix Requirements

Every future badcase must be represented at four layers:

- frontstage transcript/state invariant
- prepared JSON invariant
- compiled prompt invariant
- execution gate invariant

Minimum evergreen cases:

- no-cost rehearsal full flow
- real prepare with compact brief
- detailed-analysis full rendering
- missing-key full guidance in Chinese and English
- visual drink/product texture route with music and no voiceover
- warm office mug visual route with no unsupported claims
- dress presenter voiceover route with real scene, person context, spoken-language lock, no subtitles
- English template voiceover inside Chinese UI must remain English
- English/TikTok presenter template inside Chinese UI must not become Chinese-market casting just because the target audience is Chinese
- human voiceover template must keep mouth/lip movement synchronized to the generated same-language audio
- unknown template voiceover language must block confirmed generation
- source product video must be rejected
- packaged staging must pass release check

## Badcase Handling Rule

Do not patch only the visible symptom. For every new badcase:

1. Identify which state first allowed the bad output.
2. Identify which prepared field carried the wrong fact or policy.
3. Identify whether the renderer or prompt compiler diverged.
4. Add one focused regression case.
5. Fix the shared normalizer, renderer, prompt compiler, or execution gate.
6. Run the changed case and the full suite.
