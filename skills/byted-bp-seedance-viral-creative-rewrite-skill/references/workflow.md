# Workflow

## Purpose

Rewrite a user's product image into a new ad video by borrowing the creative pattern from a template video.

The repository submission package intentionally excludes bundled `.mp4` example videos. Users provide a template video as a local path or accessible URL at runtime.

The full frontstage state contract lives in `references/state_machine.md`. Cross-layer prepared/prompt/execution requirements live in `references/chain_contract.md`. This workflow must not contradict either contract. When there is any mismatch, the state-machine and chain contracts win.

## Conversational Flow

0. Before any user-facing opening, prepare the skill runtime from the skill root:
   - Chinese flow: `python3 scripts/ensure_runtime.py --ui-language zh --print-python`
   - English flow: `python3 scripts/ensure_runtime.py --ui-language en --print-python`
   - Use the printed `.venv/bin/python` path for all later skill commands, including `scripts/run_rewrite_video.py` and `scripts/extract_video_frames.py`.
   - Do not assume Codex, Claude Code, system Python, or the bundled runtime already has the needed packages.
   - If bootstrap succeeds, keep it silent in the user-facing opening. Do not mention runtime bootstrap, `.venv`, Python paths, or dependency setup unless the user asks for debugging details.
   - If dependency download is blocked by network or sandbox restrictions, request permission and rerun this same startup bootstrap before continuing.
1. Open by running `scripts/render_opening.py --ui-language zh|en` after runtime bootstrap and sending its complete stdout. The opening explains in plain language that this skill rewrites an ad by borrowing creative structure from a reference/template video and applying it to the user's product image.
   - Use the user's language for user-facing messages and prepared readouts. Support Chinese and English. Set `ui_language` to `zh` or `en` when explicit; otherwise infer from the user's request.
   - For conversation language selection, use the latest user turn, not earlier thread history. If the latest invocation is English, including `/path/to/skill use this skill`, the opening flow, labels, choices, setup guidance, and prompt-preview text must be English even inside a previously Chinese thread.
   - Keep UI language separate from template spoken language. UI language controls conversation, setup guidance, brief text, and prompt preview. Template spoken language controls generated voiceover only for `human_voiceover`.
   - Treat this opening as the `START_OPENING` state. In this state, do not expose final-generation action words such as "确认生成" or "confirm generation", do not mention `--confirmed-brief`, and do not ask the user to approve generation. Those actions are only allowed after the prepared brief exists.
2. Explain the two input roles before showing defaults:
   - Template video: structure reference for hook, pacing, shot order, camera language, satisfaction points, and CTA style; do not inherit its product, brand, packaging, claims, ingredients, or text.
   - Product image: product truth for the generated video; preserve product identity, appearance, packaging, visible ingredients, and confirmed selling points.
3. Bundle BytePlus registration, API key setup, Seedance 2.0 resource package readiness, and rehearsal/real-generation choice into one opening message.
   - The opening must ask for grouped reply information, not only offer three buttons/options.
   - Do not replace the grouped reply sections with one or two example sentences.
   - In Chinese, include the sections "先走哪种流程", "媒体选择", and "商品和生成方向", and mention the default output as `9:16、720p、带原创不可识别无歌词背景音乐`.
   - In English, include the matching sections "Flow", "Media", and "Product and generation direction", and mention the default output as `9:16, 720p, with original unrecognizable instrumental background music`.
   - Say in the opening that real generation requires a ModelArk API Key and Seedance 2.0 resource package or entitlement, and that the user will first see the brief, strategy, forbidden carryover, and risk controls before the Seedance submission step. Do not include the final confirmation phrase in the opening.
4. Tell the user that template videos and product images work best when they are from a similar category or use scene; cross-category rewrites can still try to borrow structure but may be less stable.
5. Tell the user early that uploaded product images should avoid recognizable real human faces. Recommend product-only images, packaging shots, hands, or non-identifiable body parts, because recognizable faces may trigger provider safety review or destabilize generated faces.
6. Ask for both media choices together: local-path/URL template video and example/custom product image.
   - Render the selected template video and default/selected product image as visible media when the chat surface supports it.
   - Do not print raw local paths in user-facing messages; provide paths only when the user asks for debugging or local CLI details.
7. Ask for product identity, audience, goal, output preferences, and constraints in one grouped prompt.
8. If the user chooses no-cost rehearsal, run the built-in full-flow replay. It shows example template understanding, product anchors, rewrite plan, prompt preview, detailed-analysis option, confirmation gate, and example result step without keys or provider calls. Do not use setup-only as the user-facing rehearsal.
9. If previewing analysis or preparing real generation, the host agent should inspect the template video and product image directly, then create the prepared brief/prompt preview. For local template videos, use the startup-bootstrapped skill-local Python to run `scripts/extract_video_frames.py` and default to 1fps visual evidence sampling internally: one timestamped frame observation per second, then aggregate those observations into the original every-5-second analysis windows. Increase density only for fast cuts, text flashes, small hand motions, or mouth movement that 1fps may miss. Do not use browser screenshots or GUI playback as the default extraction path. Do not expose a raw per-second evidence section by default; keep the user-facing detailed analysis in the original structure. The runner no longer calls ModelArk/Seed for media understanding.
   - During `REAL_ANALYSIS_REQUESTED`, keep progress updates short. Do not expose template conclusions, detailed analysis, raw frame observations, request/prepared JSON, Python heredocs, full prompt text, or large command payloads before `BRIEF_READY`.
   - If you need to validate a hand-authored prepared artifact, write the artifact outside the skill source and run a small reusable validator/renderer command. Do not put the full prepared payload inside a shell command where Codex may display it in the transcript.
10. Classify the template into one primary template profile before writing the plan. The profile controls which template facts become hard constraints:
   - `visual_product_texture`: product/food/drink/static-material ads. Transfer shot order, camera pacing, product state, texture/satisfaction, scene mood, music mood, first-five-second hook, and product proof. Do not add voiceover, lip sync, person ethnicity/appearance constraints, or subtitle logic unless the user asks.
   - `human_demo`: human try-on, product handling, use demo, or presenter action without strong speech. Transfer person framing, action sequence, broad expression/eye-contact if central, product-human relationship, and real scene context. Do not invent voiceover.
   - `human_voiceover`: creator/presenter with spoken explanation. Transfer broad person appearance/market visual context, template spoken language, voiceover rhythm, mouth/gesture synchronization, real scene, and action order. Use a new non-identical person and original wording.
   - `platform_cta`: search/account/platform/CTA page. Transfer only the CTA function and replace it with a product-visible ending. Never inherit platform UI, account, watermark, captions, or blank ending.
   - `mixed`: only when several mechanisms are equally central; expose the active transfer slots before asking for user confirmation.
11. Show a short decision brief first by running `scripts/render_brief.py --prepared-input-json <prepared>` and sending its complete stdout. The brief is not the detailed analysis. It should stay close to 8-10 user-facing lines: status, brief summary, template structure, product anchors, generation direction, output defaults, forbidden carryover, risk controls, a one-line natural-beat prompt preview, and the options to view detailed analysis, edit, or confirm generation. Save detailed video facts, full camera/editing analysis, every-five-second windows, full product analysis, full shot script, risk controls, and full prompt to prepared JSON; show them only in `DETAIL_VIEW`, debug mode, or when the user explicitly asks.
   - Keep the no-cost rehearsal and real prepare frontstage shape aligned: status, brief summary, template structure, product anchors, output defaults, forbidden carryover, risk controls, detailed-analysis option, confirmation option, and edit options.
   - In Chinese, use labels such as "本次 brief 摘要", "查看详细分析", and "确认生成". In English, use parallel labels such as "Brief summary", "show detailed analysis", and "confirm generation".
   - The brief must not print detailed-section headings such as "模板视频理解摘要", "生成前复刻方案", "每 5 秒摘要", "镜头脚本", "生成提示词预览", "Template Video Understanding Summary", "Pre-generation Rewrite Plan", "Every-5-second summary", or "Shot script". Those belong in detailed analysis.
   - If there is a conflict, ask the user to choose a direction, but only after showing the evidence from both sides: template analysis, product-image analysis, conflicting elements, and the practical effect of each option.
   - Treat visible creator face, front-facing presenter posture, real background, and voiceover-style presentation as high-priority template structure signals only for `human_demo` and `human_voiceover`. Do not drop them just because product images should avoid human faces or because the source product image has a white background.
   - If a `human_demo` or `human_voiceover` template has a visible person, expose and preserve the broad person appearance / market visual context while avoiding exact identity or face copying.
   - If a `human_voiceover` template has voiceover, expose the template spoken language and preserve that same language with original wording, voiceover-style rhythm, mouth movement, or explaining gestures while avoiding copied voice, wording, account handles, and platform CTAs.
   - If a `visual_product_texture` template has incidental people or lifestyle scenes, keep them as soft scene/use-context options rather than hard person-identity or language constraints. Drink/product texture cases should preserve liquid, ingredient, product-state, camera, and satisfaction mechanics first.
   - Do not make `visual_product_texture` detailed analysis shallow just because the route is simpler. Keep the original detailed-analysis structure and still cover shot language, borrowable mechanics, forbidden carryover, product-drift risks, text/UI risks, weak-hook risks, and ending risks inside the existing brief/risk-control fields.
   - If a template has watermarks, burned-in text, captions, or platform UI, expose that state as forbidden carryover. Generated videos default to no subtitles, no automatic captions, no lower-thirds, no watermarks, no prices, and no platform UI even when voiceover is present.
   - If a template ends on a platform/search/account page, borrow only the CTA closing function and replace it with a product-visible ending; never use blank, white, black, pure-color, or product-free ending frames.
   - This is the `BRIEF_READY` state. Only in this state may the user-facing options include "确认生成" / "confirm generation".
12. Always offer the detailed analysis before generation confirmation using plain wording such as "如果你想先看详细分析，可以回复‘查看详细分析’；看完后再继续确认是否生成。" or "If you want to review the detailed analysis first, reply 'show detailed analysis'; then continue to generation confirmation." If yes, run `scripts/render_detailed_analysis.py --prepared-input-json <prepared>` with the bootstrapped skill-local Python and use the command's complete stdout as the final user-facing response. Do not hand-write a recap. The detailed analysis must use the same section shape in rehearsal and real prepare: template video, product image analysis, proposed generation script, generation constraints, then return to the same edit/confirm/generate flow.
   - Never answer a detailed-analysis request with only "详细分析已展开", "shown above", "same prepared brief", "the key decision is unchanged", or a one-paragraph route recap.
   - The detailed-analysis body must include: template basic facts, profile reason, audio/subtitle/voiceover state, camera/editing, every-5-second windows, borrowable elements, forbidden carryover, product-image anchors, confirmed/unproven claims, proposed script, constraints, and next edit/confirm options.
13. Generate the video script using the original rewrite logic from the detailed analysis: preserve the template framework, replace the template product with the user's product, use the first 5 seconds as the hook, and extend the next 7-8 seconds with proof/detail/use-case/visual CTA. Before submitting to the video model, keep these as natural visual beats rather than frame-accurate per-second commands, so product identity remains stable.
14. Ask the user to confirm the prepared brief or request edits. This confirmation is mandatory even if the user already said "正式生成" or accepted defaults.
   - If the user edits only generation direction, constraints, tone, audience, claims, output settings, or a small selling-point emphasis, patch the prepared JSON and refresh the generation prompt. Do not re-analyze media.
   - For this patch path, run `scripts/apply_brief_patch.py --prepared-input-json <prepared> --patch-json <patch> --prepared-json <patched>` and send its complete stdout.
   - Do not switch UI/analysis language through a patch on an existing prepared JSON. A prepared artifact keeps the language used when it was created. If the user wants the other language, create a fresh request with `ui_language` set to `zh` or `en` and run prepare again.
   - Re-run agent-led media analysis only when the template video or product image changes, or when the user explicitly asks to re-understand the source media.
15. If `ARK_API_KEY` is missing, do not stop before analysis. First finish agent-led video understanding, detailed analysis, and brief confirmation. When the user confirms generation, always run `scripts/confirm_generation.py --prepared-input-json <prepared> --env-file .env --ui-language zh|en` with the bootstrapped skill-local Python. This is the only frontstage entrypoint for the confirmed-generation gate; do not call `scripts/run_rewrite_video.py --confirmed-brief` directly from the frontstage and do not hand-write the result. Do not manually inspect `.env`. If the key is missing, `confirm_generation.py` prints the full missing-key guidance. The final user-facing response must be the command's complete stdout. If the user has already confirmed generation, do not answer with only `.env` or local setup instructions. The required order is: say the confirmed prepared brief is reusable, say Seedance was not called and no resources were consumed, show the confirmed brief snapshot, summarize Seedance 2.0 advantages, show playable production example videos, then show account/key setup and tell the user to continue generation after configuring the key. This applies equally to Chinese and English.
   - Seedance advantages must use this product-facing summary, not a short technical placeholder: it supports mixed text/image/video/audio inputs; carries over material traits from references; keeps character/style consistency across shots and multi-shot narrative continuity; has native audio-video synchronization and AI-director-style generation; has strong physical realism and complex-instruction following; supports video editing and three performance tiers; fits ecommerce/commercial scenarios with stronger compliance, efficiency, and cost benefits.
   - Playable example videos must be embedded before account/key setup.
16. Before real generation, collect or confirm `ARK_API_KEY` and Seedance 2.0 resource package or equivalent entitlement.
17. Before real generation, say in the user's language that BytePlus Seedance will be called, the product image will be used as the main reference, and Seedance generation may take several minutes.
18. Generate the output only after the prepared brief is confirmed. If Seedance fails with `OutputAudioSensitiveContentDetected`, retry once with stricter abstract ambient instrumental constraints.
19. Show the generated video first as visible media by running `scripts/render_generation_result.py --result-json <result>` and sending its complete stdout. Then show the task ID and a short manual review checklist. Show local paths, result JSON, remote URL, and contact sheet only in debug mode or when the user asks.
20. Review the result for product identity, template leakage, unwanted text, first-five-second hook, extended proof/satisfaction shots, audio safety, and ad quality.

## Roles Of The Videos

- Template video: gives creative structure, pacing, hook style, visual rhythm, and CTA pattern.
- Product image: gives product identity, packaging, visual anchors, core selling points, and the main generation reference.

The final video should not inherit the template video's product, packaging, brand, flavor, or claims.

## Implementation Notes

These notes are for maintainers and agents, not for end-user-facing explanations unless asked.

- BytePlus Assets/material library is not used.
- Do not mention object storage, bucket setup, or TOS in the default user flow; explain only if the user asks.
- Local product images are encoded as base64 data URLs for Seedance reference images.
- The skill is conversation-first. Collect choices in chat and use the non-interactive runner; do not drive a terminal questionnaire or stdin-based wizard.
- Rehearsal mode (`--rehearsal`) requires no keys and replays bundled example prepared/result artifacts through the later confirmation flow.
- Rehearsal mode must honor `ui_language` end to end. With `--ui-language en`, do not wrap Chinese example content in English headings; use English frontstage text, detailed-analysis content, prompt-preview labels, music constraint, confirmation gate, and result checklist.
- Setup-only mode is only an internal request/schema smoke test. Do not present it as the user-facing rehearsal.
- Prepare-only mode is for showing an existing prepared JSON or rehearsal. Real media understanding is done by the host agent before invoking the runner.
- After approval, continue with `--prepared-input-json ... --confirmed-brief` so the existing prepared analysis is reused.
- Use `--patch-json` with `--prepared-input-json` for small generation-direction edits. This refreshes the prompt without sending the template or product image back through analysis.
- Write request, prepared, result, cache, and test artifacts outside the skill folder. The source package must not gain an `output/` directory during testing.
- Audio generation is on by default. The base music constraint requires original, non-identifiable, no-vocal music. If the provider rejects generated audio with `OutputAudioSensitiveContentDetected`, retry once with: `Audio safety retry: use only sparse abstract ambient instrumental bed, no melody, no motif, no rhythm hook, no vocals, no lyrics, no speech-like phonemes, no samples, no artist/style imitation.`
- Chinese and English are both supported. `ui_language` controls runner/frontstage language, analysis language, prompt-preview labels, setup/missing-key messages, and the music constraint wording. It must not override `spoken_language` for voiceover templates.
- Choose `ui_language` before prepare. Prepared reuse is not a translation workflow.
