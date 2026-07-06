# Frontstage State Machine

This file is the source of truth for the conversational state machine. It applies to Chinese and English flows equally. `SKILL.md`, `references/workflow.md`, `references/chain_contract.md`, and regression transcripts must not contradict it.

## Core Rules

- The latest user turn selects the frontstage language. English invocations stay English; Chinese invocations stay Chinese.
- UI language and template spoken language are separate. UI language controls the conversation; template spoken language controls generated voiceover only for `human_voiceover`.
- The agent must never jump from opening directly to final generation confirmation.
- The agent must never answer detailed-analysis requests with a short recap.
- If the final generation runner finds no `ARK_API_KEY`, the answer must still be the complete missing-key guidance state, not a short `.env` instruction.
- State-specific rules apply before style preferences. If wording would violate the current state, do not print it.

## States

### START_OPENING

Entry condition:
- The skill has just been invoked and the user has not yet chosen flow, media, and product direction.

Required output:
- Explain that the skill recreates an ad template for a new product.
- Explain the two inputs: template video and product image.
- Render the selected template video and default/selected product image when the surface supports media. The repository submission package intentionally excludes bundled `.mp4` example videos.
- Explain category/use-case similarity.
- Warn that product images should avoid recognizable real human faces.
- Ask for grouped inputs:
  - Chinese: `先走哪种流程`, `媒体选择`, `商品和生成方向`
  - English: `Flow`, `Media`, `Product and generation direction`
- Mention that real generation requires ModelArk API Key and Seedance 2.0 resources, and that a brief/strategy/risk-control preview comes before Seedance submission.

Required behavior:
- Run `scripts/render_opening.py --ui-language zh|en` with the bootstrapped skill-local Python and use the complete stdout as the opening response.
- Do not hand-write a shorter opening from memory.

Forbidden output:
- `确认生成`
- `confirm generation`
- `--confirmed-brief`
- `等你回复`
- `wait for you to reply`
- Any instruction asking the user to approve final generation.
- Any short answer that only shows media without explaining what the skill does.

Allowed transitions:
- `REHEARSAL_PREVIEW_REQUESTED`
- `REAL_ANALYSIS_REQUESTED`

### REHEARSAL_PREVIEW_REQUESTED

Entry condition:
- The user chooses no-cost rehearsal.

Required output:
- Use bundled example prepared/result artifacts.
- Walk through the same structure as real prepare: status, brief summary, detailed-analysis option, edit option, confirmation option, and example result expectation.
- Do not call Seedance or consume resources.

Allowed transitions:
- `BRIEF_READY`
- `DETAIL_VIEW`
- `REHEARSAL_RESULT`

### REAL_ANALYSIS_REQUESTED

Entry condition:
- The user chooses real analysis or real generation, with template/product choices.

Allowed user-facing progress:
- One short sentence that says analysis/preparation is in progress.
- One short sentence when local evidence extraction or prepared validation completes.
- No final brief content until `BRIEF_READY`.

Required behavior:
- Run or perform local runtime bootstrap before analysis if not already done.
- Use 1fps local visual evidence for template-video understanding by default.
- Use the host agent for video understanding and rewrite planning.
- Do not call ModelArk/Seed/ARK Responses for analysis.
- Write request/prepared artifacts outside the skill source folder.
- If a script is needed to validate or transform prepared artifacts, run a small reusable script or short command. Do not embed the full prepared JSON, schema dump, prompt, or Python payload in the shell command where it can be surfaced to the user.

Forbidden user-facing output:
- Detailed template/product analysis before `BRIEF_READY`.
- Raw prepared JSON, request JSON, `source_analysis`, `rewrite_plan`, `rewrite_brief`, `prompt_preview`, or `generation_prompt` blocks.
- Python heredocs or command payloads containing media analysis, full JSON, or full prompts.
- Tool-operation narration such as `已运行 python`, `已读取`, `Searched for`, `Read schemas.py`, or full ffmpeg command details.

Allowed transitions:
- `BRIEF_READY`

### BRIEF_READY

Entry condition:
- A prepared brief exists or has just been created.

Required output:
- Status: analysis/brief is ready, Seedance has not been called.
- Compact brief summary:
  - template structure
  - product-image anchors
  - generation direction
  - output defaults
  - forbidden carryover
  - risk controls
  - one-line natural-beat prompt preview
- Offer:
  - detailed analysis
  - edits
  - final generation confirmation

Required behavior:
- Run `scripts/render_brief.py --prepared-input-json <prepared>` with the bootstrapped skill-local Python and use the complete stdout as the brief response.
- Do not hand-write a shorter brief.

Allowed final-confirmation wording:
- Chinese: `确认生成`
- English: `confirm generation`

Forbidden output:
- Full debug JSON by default.
- Provider setup as the only next step before the user confirms generation.
- Detailed-analysis headings or long sections such as `模板视频理解摘要`, `生成前复刻方案`, `每 5 秒摘要`, `镜头脚本`, `生成提示词预览`, `Template Video Understanding Summary`, `Pre-generation Rewrite Plan`, `Every-5-second summary`, or `Shot script`.

Allowed transitions:
- `DETAIL_VIEW`
- `BRIEF_EDITING`
- `GENERATION_CONFIRMED`

### DETAIL_VIEW

Entry condition:
- The user asks `查看详细分析` or `show detailed analysis`.

Required behavior:
- Run `scripts/render_detailed_analysis.py --prepared-input-json <prepared>` with the bootstrapped skill-local Python.
- The final user-facing response for this state must be the complete stdout from `scripts/render_detailed_analysis.py`.
- Do not hand-write a recap, do not say the key conclusion is unchanged, and do not summarize only the profile route.

Required output:
- Print the full detailed-analysis body in the user's language.
- Required sections:
  - template video facts
  - template profile reason
  - audio/subtitle/voiceover state
  - camera/editing facts
  - every-5-second breakdown
  - borrowable mechanics
  - forbidden carryover
  - product-image analysis
  - confirmed and unproven claims
  - proposed generation script
  - generation constraints
  - next edit/confirm options

Forbidden output:
- `详细分析已展开`
- `关键结论不变`
- `Detailed analysis is shown above`
- `shown above`
- `same prepared brief remains validated`
- `the key decision is unchanged`
- A short answer beginning with only "这条模板应按" or "this should be handled as".
- A one-paragraph route recap.

Allowed transitions:
- `BRIEF_READY`
- `BRIEF_EDITING`
- `GENERATION_CONFIRMED`

### BRIEF_EDITING

Entry condition:
- The user edits tone, audience, claims, constraints, output settings, or a small selling-point emphasis after preview.

Required behavior:
- If media is unchanged, patch the prepared JSON and refresh prompt direction.
- Run `scripts/apply_brief_patch.py --prepared-input-json <prepared> --patch-json <patch> --prepared-json <patched>` with the bootstrapped skill-local Python and use the complete stdout as the patched-brief response.
- Do not re-analyze template video or product image unless media changed or the user explicitly asks.
- Do not patch a prepared artifact only to switch UI language; create a fresh request in that language.

Allowed transitions:
- `BRIEF_READY`

### GENERATION_CONFIRMED

Entry condition:
- The user confirms the prepared brief from `BRIEF_READY` or after `DETAIL_VIEW`.

Required behavior:
- Run `scripts/confirm_generation.py --prepared-input-json <prepared> --env-file .env --ui-language zh|en` with the bootstrapped skill-local Python. This is the only allowed frontstage entrypoint after the user says `确认生成` / `confirm generation`.
- `scripts/confirm_generation.py` internally chooses the path: if `ARK_API_KEY` exists, it submits the confirmed prepared brief; if `ARK_API_KEY` is missing, it renders the complete canonical missing-key guidance.
- The confirmed runner blocks before Seedance when a human-presenter template (`human_demo` / `human_voiceover`) has not confirmed its audio track: `template_profile.audio_track_confirmed` must be `true`, set only after listening to the audio (`extract_video_frames.py --with-audio`) or confirming `has_audio_stream=false`. If still ambiguous, expose demo-vs-voiceover in the brief for the user to decide.
- Do not manually inspect `.env`.
- Do not write a short missing-key answer yourself.
- The final user-facing response for this state must be the complete stdout from `scripts/confirm_generation.py`. Do not summarize, paraphrase, translate, shorten, or merge it with memory/context.

Allowed transitions:
- `MISSING_KEY_FULL_GUIDANCE`
- `GENERATION_RUNNING`
- `GENERATION_DONE`

### MISSING_KEY_FULL_GUIDANCE

Entry condition:
- The confirmed runner path finds no usable `ARK_API_KEY`.

Rendering rule:
- The frontstage response must be produced by `scripts/confirm_generation.py`, which calls the canonical renderer when the key is missing.
- Paste or faithfully reproduce the complete rendered output. Do not summarize it.

Required output order:
- Say the confirmed prepared brief is reusable.
- Say Seedance was not called, no resources were consumed, and no new video was generated.
- Show a compact confirmed brief snapshot.
- Explain Seedance 2.0 advantages. Chinese output must include this exact summary sentence:
  `支持文本、图片、视频、音频四模态混合输入，能精准复刻素材特征，实现跨镜头角色风格统一与多镜头连贯叙事；原生音画同步，AI 导演降低创作门槛；物理真实度高、复杂指令遵循准；支持视频编辑，提供三档性能版本适配不同需求，适配电商等商业场景，合规有保障，提效降本显著。`
  English output must include this exact summary sentence:
  `It supports mixed text, image, video, and audio inputs; accurately preserves material traits from references; maintains character and style consistency across shots with coherent multi-shot storytelling; native audio-video synchronization and AI-director-style generation lower the creation barrier; strong physical realism and accurate complex-instruction following; supports video editing and offers three performance tiers for different needs; well suited for ecommerce and other commercial scenarios, with stronger compliance, significant efficiency gains, and lower production costs.`
- Show playable production example videos.
- Then show account/key setup:
  - BytePlus registration
  - ModelArk/Seedance setup for API key, prepaid resource package, and model activation
  - Doubao Seed 2.0 Pro permission page
  - local `.env` with only `ARK_API_KEY=...`
- Tell the user to continue generation after configuring the key.

Forbidden output:
- A short answer that only says no key was found.
- A short answer that only points to `.env`, a prepared file, or setup links.
- A response that omits Seedance advantages or playable example videos.
- Any paraphrase that drops the rendered examples or account/key setup.
- TOS, bucket, or object-storage setup in the default flow.

Allowed transitions:
- `GENERATION_CONFIRMED` after key setup.

### GENERATION_DONE

Entry condition:
- Seedance generation succeeds.

Required output:
- Show the generated video first as playable/visible media.
- Then show task ID.
- Then show a short manual checklist.
- Keep result JSON, raw paths, remote URL, or contact sheet in debug-only wording unless the user asks.

Required behavior:
- Run `scripts/render_generation_result.py --result-json <result>` with the bootstrapped skill-local Python and use the complete stdout as the result response.
- Do not hand-write a shorter generation-complete message.

## Transcript Regression Invariants

Regression tests should include good and bad frontstage transcripts.

Good transcript coverage:
- Chinese and English opening in `START_OPENING` without final confirmation wording.
- Chinese and English `BRIEF_READY` with detailed-analysis and confirmation options.
- Chinese and English `DETAIL_VIEW` with full sections, not a recap.
- Chinese and English `MISSING_KEY_FULL_GUIDANCE` with Seedance advantages, example videos, and setup links after confirmed brief state.
- Patched brief and generation result renderer paths.

Bad transcript coverage:
- Opening that contains `确认生成` or `confirm generation`.
- Detailed-analysis response that says only `shown above` or `same prepared brief`.
- Missing-key response that only asks the user to add `.env`.
