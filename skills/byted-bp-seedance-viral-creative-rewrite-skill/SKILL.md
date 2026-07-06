---
name: byted-bp-seedance-viral-creative-rewrite-skill
description: Guide a user conversationally through generating a new ad video from a template video and a user-provided product image. The host agent performs video understanding, detailed analysis, and rewrite planning; BytePlus Seedance is used only for final video generation with local product images as generation references.
---

# Viral Creative Rewrite Skill

## What This Skill Does

This skill helps a user create a stronger ad video from:

- a template video, provided by the user as a local path or accessible URL
- a user-provided product image, defaulting to `./assets/examples/source_product.jpg`

The template video provides creative structure: hook, pacing, visual rhythm, CTA style. The product image provides the product identity, packaging, visual anchors, and confirmed selling points. The final video should keep the product image identity and borrow only the template's creative pattern.

## Reference Loading

- Read `references/state_machine.md` when changing or auditing frontstage state transitions, opening prompts, detailed-analysis behavior, confirmation gates, missing-key behavior, bilingual parity, or transcript regressions.
- Read `references/workflow.md` when changing or auditing the user flow, confirmation gates, setup/prepare/execute behavior, review outputs, or local product image handling.
- Read `references/prompt_alignment.md` when changing analysis schemas, rewrite-planning prompts, prompt-package structure, or compatibility with earlier creative rewrite prompt patterns.
- Read `references/chain_contract.md` when changing or auditing cross-layer behavior: state, prepared artifacts, renderers, prompt compiler, execution gate, bilingual parity, and badcase regression coverage.

## Hard Gates

- Treat "正式生成", "直接生成", or similar user wording as intent to enter the real-generation path, not permission to submit Seedance immediately.
- Always run or present the analysis/brief confirmation gate before real generation. The user must see the template logic, product-image anchors, rewrite strategy, forbidden carryover, prompt preview, audio setting, and cost/time warning before Seedance is called.
- Treat the conversation as a state machine. `references/state_machine.md` is the source of truth for frontstage state transitions, allowed output, forbidden output, and transcript regression invariants. Do not expose later-state actions in earlier-state messages:
  - `START_OPENING`: explain the skill, two media roles, default assets, category/face guidance, and ask for grouped inputs. Forbidden in this state: "确认生成", "confirm generation", `--confirmed-brief`, or any instruction that asks the user to approve final generation.
  - `BRIEF_READY`: after analysis/brief exists, show the compact brief, detailed-analysis option, edit option, and only then expose the generation-confirmation action.
  - `DETAIL_VIEW`: when the user asks for detailed analysis, print the full detailed-analysis sections and return to edit/confirm options.
  - `GENERATION_CONFIRMED`: after the user confirms the prepared brief, run `scripts/confirm_generation.py`; do not hand-write the result.
  - `MISSING_KEY_FULL_GUIDANCE`: if the confirmed runner path lacks `ARK_API_KEY`, show the reusable brief state, no-cost/no-call state, Seedance advantages, playable examples, and account/key setup.
- Support both Chinese and English user flows. Keep user-facing messages, compact brief text, detailed-analysis text, setup/missing-key guidance, and prompt preview in the user's language. Use `ui_language: "zh"` or `ui_language: "en"` when the language is explicit; use `auto` only when it is safe to infer from the user's request. This UI language is separate from the template spoken-language rule.
- For conversation language selection, the latest user turn wins. If the latest invocation/request is in English, including a local-path invocation such as `/path/to/byted-bp-seedance-viral-creative-rewrite-skill use this skill`, start and continue the frontstage flow in English even if earlier thread history is Chinese. If the latest invocation/request is in Chinese, use Chinese. Do not let old thread context override the language of the current invocation.
- Before planning the rewrite, classify the template into a template profile. This profile decides which signals are allowed to become hard generation constraints:
  - `visual_product_texture`: drinks, food, product static shots, material/texture demos, ingredient/product-state ads. Borrow shot order, camera pacing, product state changes, texture/satisfaction points, scene mood, and music mood. Do not add voiceover, lip sync, person ethnicity/appearance constraints, or subtitle logic unless the user explicitly asks.
  - `human_demo`: visible human demonstration, try-on, hand-use, or presenter action without a strong voiceover. Borrow human framing, action sequence, expression/eye-contact when structurally important, product-human relationship, and real scene context. Do not invent voiceover.
  - `human_voiceover`: presenter/creator video with spoken explanation. Borrow broad person appearance/market visual context, original template spoken language, voiceover rhythm, mouth/gesture synchronization, real scene, and action order. Generate a new non-identical person and original wording.
  - `platform_cta`: platform/account/search/CTA pages. Borrow only the closing function; do not inherit platform UI, account, watermark, search page, captions, or blank ending.
  - `mixed`: use only when several mechanisms are equally central, then expose the active transfer slots in the brief before asking for confirmation.
- Keep no-cost rehearsal and real prepare frontstage readouts aligned. They may differ in provider/cost wording, but they must use the same user-facing structure: status, brief summary, detailed-analysis option, edit option, confirmation option, and result-display expectation.
- Do not call Seedance until the user explicitly confirms the prepared brief.
- Video understanding and rewrite planning must be done by the host agent in the conversation. Do not call ModelArk/Seed/ARK Responses for template or product-image understanding.
- For local template-video understanding, inspect visual evidence at 1fps by default, meaning one timestamped frame per second. Use these per-second observations as evidence, then summarize them into every-5-second windows. If the video has very fast cuts, text flashes, or hand motions that may be missed, increase density for the relevant interval instead of lowering detail.
- When the template shows a person whose mouth is visibly moving, increasing frame density is not enough — frames cannot tell whether there is voiceover. You must also inspect the audio track (listen for spoken voiceover vs music/ambient only) before classifying the profile. Run `scripts/extract_video_frames.py --with-audio`, which exports `audio_track.m4a` and records `has_audio_stream` in the manifest, then actually listen. Do not infer `human_demo` vs `human_voiceover` from visual frames alone; screen-recording sources especially must have their original audio checked.
- If the user has chosen real generation and `ARK_API_KEY` is missing, still continue through agent-led video understanding, detailed analysis, and brief confirmation. Then show Seedance 2.0 advantages, playable production examples, and only after that show the account/key setup block: BytePlus registration, ModelArk/Seedance setup document for API key plus prepaid resource package activation, Doubao Seed 2.0 Pro permission page, and local `.env` placement.
- When the user asks "查看详细分析" / "show detailed analysis", never answer with a short recap such as "详细分析已展开", "shown above", "same prepared brief", or "the key decision is unchanged". You must print the full detailed-analysis body in the user's language: template video facts, every-5-second breakdown, product-image analysis, proposed generation script, generation constraints, and the next edit/confirm gate.
- When the user asks "查看详细分析" / "show detailed analysis", always execute `scripts/render_detailed_analysis.py --prepared-input-json <prepared>` with the bootstrapped skill-local Python. The final chat reply must be the complete stdout from this command. Do not hand-write "关键结论不变", "核心要复刻的是...", or any short profile recap.
- This applies to the real generation flow too, not just rehearsal. For every brief / detailed-analysis / confirmation step (`render_brief.py`, `render_detailed_analysis.py`, `confirm_generation.py`), the visible chat reply must reproduce the command's complete stdout. Leaving the output collapsed inside a tool-call box and replying only with a pointer like "以上是完整详细分析" / "shown above" does NOT count as forwarding — the analysis body must be in the visible reply. The brief and detailed-analysis stdout already end with the next-step gate (confirm / view detailed analysis / tell me what to change); do not strip those options, do not replace them with a binary "confirm only" AskUserQuestion widget, and re-offer them whenever the brief is edited and re-confirmed.
- When opening the skill, use `scripts/render_opening.py --ui-language zh|en` after runtime bootstrap and send the complete stdout. Do not hand-write a shorter opening.
- When showing a prepared brief, use `scripts/render_brief.py --prepared-input-json <prepared>` and send the complete stdout. Do not hand-write a shorter brief.
- When applying a user edit to an existing brief, use `scripts/apply_brief_patch.py --prepared-input-json <prepared> --patch-json <patch> --prepared-json <patched>` and send the complete stdout. Do not hand-write "已修改" without the refreshed brief.
- When showing a final generation result, use `scripts/render_generation_result.py --result-json <result>` and send the complete stdout. The generated video must be shown first.
- Always output setup, registration, and account URLs (BytePlus signup, ModelArk, API-key, model-management, docs links, etc.) complete and verbatim, exactly as the scripts print them. Never shorten a URL, drop its query string, or strip UTM / tracking parameters such as `utm_source`, `utm_medium`, or `utm_campaign` "for tidiness" — these carry channel attribution and registration benefits and must reach the user intact. If you show a shortened display text, the underlying link target must still be the full URL.
- Media markdown style: the scripts that print video/image links (`run_rewrite_video.py`, `render_opening.py`, `render_generation_result.py`) accept `--media-style codex|link|both`, default `codex`. Keep the default `codex` in Codex Desktop, where `![](absolute path)` renders an inline preview. In a client that shows `![](path)` as plain text but linkifies markdown links (e.g. Claude Code), pass `--media-style link` to emit clickable `[label](file:///… )` links instead (or `both` if unsure). The link is only clickable once it is in your visible reply — forwarding the script stdout into the chat (not leaving it collapsed in a tool box) still applies. Local `file://` links open only on the machine that ran the skill; for cross-machine sharing a public URL is required.
- To make media clickable, re-run the script with `--media-style link` (or `both`) and forward that output. Do NOT hand-convert `![alt](path)` into `[alt](path)` yourself: a bare absolute path like `C:/Users/...` or `/Users/...` is not a valid URL, so the result renders as a link that does nothing when clicked. Only the `--media-style link` flag produces the correct `file://` form (with proper percent-encoding); use it instead of editing the URL by hand.
- At skill startup, before showing the opening prompt or starting analysis, run `scripts/ensure_runtime.py --ui-language zh|en --print-python` from the skill root. This creates/reuses the skill-local `.venv`, installs `requirements.txt` there when needed, verifies `imageio`, `imageio-ffmpeg`, `pillow`, `pydantic`, `httpx`, and an ffmpeg executable, and prints the Python path to use. Do not assume Codex, Claude Code, system Python, or the bundled runtime already has these dependencies.
- Use the Python path printed by `ensure_runtime.py` for `scripts/run_rewrite_video.py`, `scripts/extract_video_frames.py`, and other skill scripts. Do not use the Codex bundled Python or system Python for this skill after startup bootstrap.
- If `ensure_runtime.py` fails because network or sandbox access is blocked, request permission and rerun the same startup bootstrap with network access. Do not wait until the user has chosen real generation to discover missing dependencies.
- Do not ask for object storage, material library, TOS, or bucket setup in the default flow. Explain local product-image handling only if the user asks.
- Use `scripts/run_rewrite_video.py` as the only runner. This skill is conversation-first: collect choices in chat, write a request JSON, then execute the non-interactive runner.
- Never drive a terminal wizard or stdin-based questionnaire from the agent. The package intentionally has no interactive runner.
- Use the host agent to create the prepared brief before generation. After the user reviews and confirms it, continue from `--prepared-input-json`; do not run any provider media-analysis step.
- For local template videos, use the bootstrapped skill-local Python to run `scripts/extract_video_frames.py` and extract 1fps timestamped frames for evidence before writing the prepared brief. Do not use browser screenshots or GUI playback as the default extraction path.
- During the real-analysis preparation state, keep user-facing progress terse. Do not print template conclusions, detailed analysis, raw request/prepared JSON, `source_analysis`, `rewrite_plan`, `rewrite_brief`, `prompt_preview`, full prompts, Python heredocs, or large shell command payloads before `scripts/render_brief.py` has rendered `BRIEF_READY`.
- If a prepared artifact must be hand-authored or patched, write it outside the skill source and validate/render it with a reusable script. Do not embed the full prepared JSON inside a shell command that can appear in the transcript.
- If the user changes only generation direction after preview, such as audience, claims, tone, constraints, output settings, or "add this lightly", apply a small `--patch-json` to the prepared JSON and refresh the prompt. Do not re-analyze the template video or product image unless those media changed. Do not use a patch to switch a prepared artifact from Chinese to English or English to Chinese; the saved analysis stays in its original language. If the user wants a different UI/analysis language, create a fresh request with the desired `ui_language` and run prepare again.
- Always write request, prepared, output, cache, and test artifacts outside the skill folder. Do not create an `output/` directory inside the skill source.

## Default Invocation Behavior

When the user says "use byted-bp-seedance-viral-creative-rewrite-skill" or otherwise invokes this skill by name without extra details:

- First run the startup runtime bootstrap from the skill root, before the opening message:
  - Chinese flow: `python3 scripts/ensure_runtime.py --ui-language zh --print-python`
  - English flow: `python3 scripts/ensure_runtime.py --ui-language en --print-python`
  - Keep the printed `PYTHON=.../.venv/bin/python` path and use it for all later skill commands.
  - If bootstrap succeeds, do not mention runtime bootstrap, `.venv`, Python paths, or dependency setup in the user-facing opening. This is internal preparation.
  - If the command fails because dependency download is blocked, request network approval and rerun it. The user-facing opening should not proceed until the runtime is ready.
- Start the conversational flow immediately. Do not ask the user for the skill path, script names, or raw JSON.
- Choose the frontstage language from the latest user invocation text, not from earlier thread context. English invocations must receive English opening copy, English labels, and English option text.
- First explain what the skill does in one short paragraph before showing media: it uses a reference ad video as a creative template and a product image as the product truth to generate a new short ad video.
- Immediately explain the two media roles in plain language:
  - Template video: the reference ad to borrow hook, pacing, shot order, camera language, satisfaction points, and CTA structure from. Its product, brand, claims, packaging, ingredients, and text must not be inherited.
  - Product image: the user's product source of truth for identity, appearance, packaging, visible ingredients, and confirmed selling points. The generated video should be about this product.
- Offer a no-cost full-flow rehearsal first, then a real agent-led analysis + Seedance generation path. The rehearsal uses built-in example prepared/result artifacts to walk through the later brief, detailed-analysis option, review step, and example result without calling Seedance.
- Tell the user early that similar product categories or use scenes give more stable results.
- Tell the user early that uploaded product images should avoid recognizable real human faces. Recommend product-only images, packaging shots, hands, or non-identifiable body parts instead, because face-containing product images can trigger provider safety review or make the generated person/face unstable.
- Ask the user to provide a template video path or accessible video URL. The repository submission package intentionally excludes bundled `.mp4` example videos.
- Show the default or selected template video and product image as visible media when the chat surface supports media rendering. Use Markdown media syntax with absolute paths internally, but do not print the raw local paths as user-facing text.
- Ask for the minimum grouped inputs in the user-facing wording, not just three option buttons or two example sentences: flow choice, media choice, product/generation direction, default output settings, and the real-generation key/brief-preview gate. The Chinese opening must explicitly show the section labels "先走哪种流程", "媒体选择", and "商品和生成方向".
- If the user chooses real generation, still run the prepared-brief confirmation gate before any Seedance call.
- For local execution, run commands from the installed skill directory so relative assets and `.env` resolve correctly.

Chinese invocation opening template:

```markdown
这个 skill 做的是广告模板复刻：我会先理解一个参考广告视频的开头钩子、镜头节奏、产品爽点和收尾方式，再用你的商品图作为产品真相，生成一条新的商品广告视频。

这里有两个输入：模板视频和商品图。

- 模板视频：只提供广告结构参考，比如节奏、镜头顺序、动作、爽点和 CTA 结构；不会继承里面的商品、品牌、包装、字幕或卖点。
- 商品图：提供最终视频里的商品身份、外观、包装、可见成分和确认卖点；生成结果要围绕这张图里的商品。

模板视频（结构参考）：
当前仓库提交包不包含内置 `.mp4` 示例视频。运行时请提供本地模板视频路径，或提供可访问的视频 URL。

默认商品图（产品真相/彩排示例）：
![默认商品图](/absolute/path/to/assets/examples/source_product.jpg)

更稳定的组合通常是同品类或相近使用场景，比如饮品配饮品/食品广告模板，美妆配美妆/护肤模板。跨品类也能借节奏和镜头结构，但商品一致性和场景贴合度会弱一些。

另外，真实生成时上传的商品图尽量不要包含可识别真人脸。更推荐商品本体、包装图、手持局部或不可识别身体局部；清晰真人脸可能触发模型风控，也可能让后续人物/脸部生成不稳定。

你可以直接回复下面这些信息，我就继续：

先走哪种流程：
无成本彩排 或 真实分析预览/正式生成

媒体选择：
模板视频用本地路径还是视频 URL？商品图用默认示例还是你自己的商品图？

商品和生成方向：
商品身份/必须保留卖点、目标人群、目标，比如提高点击率/强化开头；默认输出为 9:16、720p、带原创不可识别无歌词背景音乐。

正式生成需要 ModelArk API Key，并且账号需要有 Seedance 2.0 可用资源包或权益。进入真实分析/生成流程后，我会先给你看 brief、策略、禁止继承项和风险控制；你确认方向后，才会进入提交 Seedance 的下一步。
```

English invocation opening template:

```markdown
I’m using this local `byted-bp-seedance-viral-creative-rewrite-skill`.

This skill recreates an ad template for a new product: I first understand a reference ad video’s hook, shot rhythm, satisfaction moments, and ending structure, then use your product image as the product truth to generate a new short ad video.

There are two inputs: a template video and a product image.

- Template video: the reference ad structure. I borrow pacing, shot order, camera language, actions, satisfaction points, and CTA function. I do not inherit its product, brand, packaging, claims, subtitles, or selling points.
- Product image: the source of truth for the generated product identity, appearance, packaging, visible ingredients, and confirmed selling points.

I recommend starting with a no-cost full-flow rehearsal. It replays the built-in example through template understanding, brief summary, detailed analysis, review, and example result without calling Seedance or consuming resources.

For better results, keep the template video and product image close in category or use case. For example, drinks work best with drink/food ad templates, and beauty products work best with beauty/skincare templates. Cross-category rewrites can still borrow pacing and shot structure, but product consistency and scene fit may be weaker.

Also avoid product images with recognizable real human faces for real generation. Product-only shots, packaging, hands, or non-identifiable body parts are more stable.

You can reply with these details and I will continue:

Flow:
No-cost rehearsal, or real analysis preview / real generation.

Media:
Provide a local template video path or accessible video URL. Use the default example product image or your own product image?

Product and generation direction:
Product identity / must-keep selling points, target audience, and goal, such as improving click-through rate or strengthening the opening hook. Default output is 9:16, 720p, with original unrecognizable instrumental background music.

Real generation requires a ModelArk API Key and a Seedance 2.0 prepaid resource package or entitlement. In the real analysis/generation flow, I will first show you the brief, strategy, forbidden carryover, and risk controls; after you approve the direction, we move to the Seedance submission step.
```

## Agent Conversation Style

Guide the user like a product assistant, not like a developer tool.

Do:

- Use friendly, plain-language prompts.
- Respond in the latest user's language, Chinese or English. If the latest user turn is English, do not show Chinese frontstage headings, setup guidance, prompt-preview labels, or option text, even if earlier turns in the same thread were Chinese. If the latest user turn is Chinese, keep the Chinese flow.
- Proactively lead the user through each step. Do not wait for the user to ask what comes next.
- Avoid opening with only media labels. Always say what the skill does and what each input controls before asking the user to choose.
- Ask the user to provide/upload their own template video path or accessible video URL.
- Let the user provide/upload their own product image.
- Do not ask the user to provide a product video for the source side.
- Show the selected template video and default/selected product image in the conversation when the surface supports media rendering.
- Do not list raw local filesystem paths in user-facing messages unless the user asks for debugging or local CLI details.
- Tell the user early that template videos and product images work best when they are from a similar category or usage scene. If they are far apart, explain that the workflow can still try to borrow pacing and shot structure, but product stability and scene fit may be weaker.
- Tell the user early that their uploaded product image should not contain a recognizable real human face. Product-only images, packaging shots, hands, or non-identifiable body parts are safer; recognizable faces in the product image can trigger model safety review or make generated faces unstable.
- Do not confuse the product-image face warning with template-video understanding. If the template video relies on a creator's visible face, expressions, eye contact, real background, or voiceover-style presentation, those are template structure signals. Preserve them as a newly generated non-specific person, real-scene structure, and original presentation rhythm unless the user explicitly removes them.
- When the template has people or voiceover, first decide whether it is `human_demo` or `human_voiceover`. The brief must expose the template person's broad appearance/market visual context, the template voiceover language when present, and the template subtitle/text state. The generated person should be new and non-identical but keep the same broad visual context; generated voiceover must use the same language with original wording; subtitles/captions remain off by default.
- If you cannot confirm whether a human-presenter template is `human_demo` or `human_voiceover` (for example, a person's mouth is moving but the audio track was not independently confirmed, or a screen-recording source means the original audio could be either voiceover or background music), do not silently pick one and generate. Expose the unresolved ambiguity in the brief with the observed evidence and an explicit A/B choice for the user, for example: "模板 profile 判定：human_demo 或 human_voiceover 待定 / 证据：女主嘴部多帧有张合动作，但音轨未独立确认 / 你来定：A. 当无口播试穿走 demo；B. 当 <语言> 口播走 voiceover". Treat this as a blocking decision: do not confirm generation until the user picks. Once you have actually listened to the audio track (or confirmed `has_audio_stream=false`), set `template_profile.audio_track_confirmed=true` in the prepared JSON; the runner blocks generation on a human-presenter template while this is unconfirmed.
- Do not confuse UI language with template voiceover language. An English user can rewrite a Chinese voiceover template and still get Chinese voiceover in the generated video; a Chinese user can rewrite an English voiceover template and still get English voiceover. The user's language controls the conversation and brief; the template controls voiceover language for `human_voiceover`.
- For `visual_product_texture` templates, do not turn incidental lifestyle shots into hard person/voice constraints. A drink case like watermelon/pineapple juice should primarily preserve product texture, ingredient-to-product progression, camera rhythm, first-five-second hook, and visual satisfaction, not force voiceover, lip sync, or person appearance matching.
- Explain that `ARK_API_KEY` is collected only for final Seedance video generation. Agent-led analysis can happen before a key is configured.
- Say that a full-flow example rehearsal can be completed before real generation.
- Before generation, summarize the concise rewrite brief in natural language and let the user revise it.
- Adapt the generation direction from the user's product, audience, goal, and constraints.
- Before generation, ask for explicit confirmation and mention possible cost/time.
- After generation, show the generated video first as a playable/visible media item. Then show the task ID and a short manual review checklist.
- If Seedance rejects generated audio with `OutputAudioSensitiveContentDetected`, retry once automatically with stricter abstract-instrumental audio constraints before reporting failure.

Avoid unless the user asks:

- Raw script names.
- JSON terminology.
- Internal data URL details or raw prompts.
- Request payloads or low-level implementation details.
- Asking for secrets before the user chooses real generation.

When the user asks whether TOS is needed, answer plainly:

- BytePlus material library is not needed.
- TOS is not required or used by this skill.
- If the product image is already an accessible HTTPS URL, it can be passed directly as a reference image.
- If the user uploads a local product image, the runner encodes it as a base64 data URL for Seedance reference image input.
- Full-flow rehearsal does not require keys, upload files, or call model APIs. It replays built-in example analysis and example result artifacts.
- Real template/product-image understanding is performed by the host agent, then saved as prepared JSON. The runner no longer calls ModelArk/Seed for analysis.

## User-Facing Flow

### 1. Account And Key Setup

Bundle account, API key, Seedance resource package, and rehearsal choice into one message. Do not split setup across many turns.

Useful links:

- BytePlus registration: `https://console.byteplus.com/auth/signup?redirectURI=https%3A%2F%2Fwww.byteplus.com%2Fen&skipAccountProfile=true&utm_source=tiktok&utm_medium=lead-generation&utm_campaign=BP_TikTok_Agentic_Hub_FY26&utm_term=tiktok&utm_content=20260624`
- ModelArk API Key management: `https://console.byteplus.com/ark/region:ark+ap-southeast-1/apikey`
- ModelArk quick start: `https://docs.byteplus.com/zh-CN/docs/ModelArk/1399008`

Tell the user in text, not as extra default links, that formal generation also requires purchasing a Seedance 2.0 prepaid resource package and confirming video-generation permissions.
Tell the user what to prepare and provide to the agent or the platform's secure secret form before real generation:

- `ARK_API_KEY` from ModelArk API Key management.
- Seedance 2.0 prepaid resource package or equivalent available entitlement.

Platform-facing wording:

"正式生成视频需要 ARK_API_KEY，并且账号需要有 Seedance 2.0 可用资源包或权益；视频理解和详细分析会先由我在当前对话里完成。"

When `ARK_API_KEY` is missing, show the complete setup flow:

1. Register a BytePlus account: `https://console.byteplus.com/auth/signup?redirectURI=https%3A%2F%2Fwww.byteplus.com%2Fen&skipAccountProfile=true&utm_source=tiktok&utm_medium=lead-generation&utm_campaign=BP_TikTok_Agentic_Hub_FY26&utm_term=tiktok&utm_content=20260624`
2. Follow the ModelArk / Seedance flow to get the API key, buy the prepaid resource package, and activate the Seedance video generation model: `https://docs.byteplus.com/zh-CN/docs/ModelArk/2291680`
3. Open the model management page and enable Doubao Seed 2.0 Pro model permission: `https://console.byteplus.com/ark/region:ark+ap-southeast-1/openManagement?LLM=%7B%7D`
4. For local testing, copy `.env.example` to `.env` in the skill root and fill `ARK_API_KEY=...`.

Required missing-key response shape after the user already asked for real generation:

```markdown
当前没有读到 `ARK_API_KEY`，所以还不能提交 Seedance 生成视频。当前 prepared brief 已经确认并可复用；还没有调用 Seedance、没有消耗资源、也没有生成新视频。

这版会继续保留已经确认的模板理解、商品图分析、详细 brief 和生成方向。配好 key 后，我会直接用这份 prepared brief 提交 Seedance，不重新分析素材。

Seedance 2.0 适合作为最终视频生产步骤的原因：
支持文本、图片、视频、音频四模态混合输入，能精准复刻素材特征，实现跨镜头角色风格统一与多镜头连贯叙事；原生音画同步，AI 导演降低创作门槛；物理真实度高、复杂指令遵循准；支持视频编辑，提供三档性能版本适配不同需求，适配电商等商业场景，合规有保障，提效降本显著。

可以先看这些生产视频示例：

![Seedance 示例视频 1](<bundled example video path>)
![Seedance 示例视频 2](<bundled example video path>)

请先按这个顺序准备：
1. 注册 BytePlus 账号：<registration URL>
2. 按 ModelArk / Seedance 文档获取 API Key、购买预付费资源包，并激活 Seedance 视频生成模型：<ModelArk/Seedance setup URL>
3. 到模型开通管理页开启 Doubao Seed 2.0 Pro 权限：<model permission URL>
4. 本地测试时，在这个 skill 根目录创建 `.env`，从 `.env.example` 复制，只填写 `ARK_API_KEY=...`。保持 `OUTPUT_DIR` 指到 skill 目录外，避免生成结果污染交付包。

配好后回复“继续”，我会基于已经确认的 prepared brief 提交 Seedance 生成。
```

Required English missing-key response shape after the user already asked for real generation:

```markdown
`ARK_API_KEY` is not configured, so I cannot submit the Seedance generation yet. The confirmed prepared brief is reusable; Seedance has not been called, no resources were consumed, and no new video has been generated.

This version will keep the confirmed template understanding, product-image analysis, detailed brief, and generation direction. After the key is configured, I will submit this same prepared brief to Seedance without re-analyzing the media.

Confirmed brief snapshot:
- Product: <product identity from prepared brief>
- Product anchors: <must-keep visual anchors>
- Rewrite direction: <confirmed rewrite direction>
- Output: <ratio/resolution/audio>

Why Seedance 2.0 is useful for the final production step:
It supports mixed text, image, video, and audio inputs; accurately preserves material traits from references; maintains character and style consistency across shots with coherent multi-shot storytelling; native audio-video synchronization and AI-director-style generation lower the creation barrier; strong physical realism and accurate complex-instruction following; supports video editing and offers three performance tiers for different needs; well suited for ecommerce and other commercial scenarios, with stronger compliance, significant efficiency gains, and lower production costs.

Production example videos:

![Seedance example 1](<bundled example video path>)
![Seedance example 2](<bundled example video path>)

Please prepare these in order:
1. Register a BytePlus account: <registration URL>
2. Follow the ModelArk / Seedance document to get an API key, buy the prepaid resource package, and activate the Seedance video generation model: <ModelArk/Seedance setup URL>
3. Open the model management page and enable Doubao Seed 2.0 Pro permission: <model permission URL>
4. For local testing, create `.env` in the skill root from `.env.example`, and fill only `ARK_API_KEY=...`. Keep `OUTPUT_DIR` outside the skill folder to avoid polluting the release package.

After setup, reply "continue generation" and I will submit the already-confirmed prepared brief to Seedance.
```

When the user replies "确认生成" / "confirm generation", always execute `scripts/confirm_generation.py --prepared-input-json <prepared> --env-file .env --ui-language zh|en` with the bootstrapped skill-local Python. This is the only frontstage entrypoint for the confirmed-generation gate. It either submits Seedance when `ARK_API_KEY` is available or prints the complete missing-key guidance when the key is absent. The final chat reply must be the complete stdout from this command. Do not manually inspect `.env`, do not call `run_rewrite_video.py --confirmed-brief` directly from the frontstage, and do not write a short missing-key answer yourself. If the command output is unavailable, rerun `scripts/confirm_generation.py`; do not reconstruct the answer from memory.

Do not replace the Chinese or English block with a shorter "本地最短路径", "add ARK_API_KEY=... to .env", "Prepared brief remains here", "Setup links from the runner", or "To continue, add ARK_API_KEY=..." message in the real-generation missing-key branch. If the agent detects the missing key in chat instead of through the runner, it must still run the canonical renderer and keep this same order in the user's language: confirmed reusable brief -> no Seedance/no cost state -> confirmed brief snapshot -> Seedance 2.0 advantages -> playable example videos -> account/key setup -> "continue generation" instruction. In Chinese, the Seedance advantages section must include the exact sentence: "支持文本、图片、视频、音频四模态混合输入，能精准复刻素材特征，实现跨镜头角色风格统一与多镜头连贯叙事；原生音画同步，AI 导演降低创作门槛；物理真实度高、复杂指令遵循准；支持视频编辑，提供三档性能版本适配不同需求，适配电商等商业场景，合规有保障，提效降本显著。" In English, it must include the exact sentence: "It supports mixed text, image, video, and audio inputs; accurately preserves material traits from references; maintains character and style consistency across shots with coherent multi-shot storytelling; native audio-video synchronization and AI-director-style generation lower the creation barrier; strong physical realism and accurate complex-instruction following; supports video editing and offers three performance tiers for different needs; well suited for ecommerce and other commercial scenarios, with stronger compliance, significant efficiency gains, and lower production costs."

Local-runner wording:

"如果你是在本地命令行运行：进入 skill 根目录，执行 `cp .env.example .env`，打开 `.env`，把 `ARK_API_KEY=...` 填成你在 ModelArk API Key 管理页面拿到的 key。不要把 key 写进共享文档或聊天记录。测试时建议保持 `OUTPUT_DIR` 指到 skill 目录外，避免生成结果污染交付包。"

Also ask whether they want to run the no-cost full-flow rehearsal first or start real generation after setup.

### 2. Template Video And Product Image

Before showing default media, explain:

```markdown
这个 skill 做的是广告模板复刻：我会先理解一个参考广告视频的开头钩子、镜头节奏、产品爽点和收尾方式，再用你的商品图作为产品真相，生成一条新的商品广告视频。

这里有两个输入：模板视频和商品图。
- 模板视频：只提供广告结构参考，比如节奏、镜头顺序、动作和爽点；不会继承里面的商品、品牌、包装、字幕或卖点。
- 商品图：提供最终视频里的商品身份和外观锚点；生成结果要围绕这张图里的商品。
```

Default behavior:

- Provide a local template video path or accessible template video URL
- Use `./assets/examples/source_product.jpg`

User option:

- They can provide their own local template video path or video URL.
- They can provide their own local product image path or image URL.
- They should not provide a product video as the source.

User-facing wording:

"For the template video, provide a local video path or an accessible URL. For the product image, use the included example only for the built-in rehearsal, or provide your own product image for real generation."

When using media in Codex Desktop, render existing local media directly:

```markdown
模板视频（结构参考）：
当前仓库提交包不包含内置 `.mp4` 示例视频。运行时请提供本地模板视频路径，或提供可访问的视频 URL。

默认商品图（产品真相/彩排示例）：
![默认商品图](/absolute/path/to/assets/examples/source_product.jpg)
```

Do not show lines like `模板视频：/absolute/path/...` or `商品图：/absolute/path/...` unless the user asks for paths.

Also say:

"For more stable results, choose a template video and product image from a similar product category or use scene. For example, drinks work best with drinks or food templates, and beauty products work best with beauty or skincare templates. Cross-category rewrites can still borrow pacing and shot structure, but product consistency and scene fit may be less stable."

Also warn:

"为了降低风控和生成不稳定风险，上传的商品图尽量不要包含可识别真人脸。建议用商品本体、包装图、手持局部或不可识别身体局部；如果商品图里有清晰真人脸，可能触发模型风控，或让后续人物/脸部生成不稳定。"

Collect both video choices together:

- template video: default or custom
- product image: default example image, custom local image, or image URL

If the user asks how local product images are passed, explain that the runner encodes them as base64 reference images.

### 3. Product And Generation Requirements

Collect product and generation requirements in one grouped prompt, not as many tiny questions:

- product identity and must-keep selling points
- target audience
- goal, such as improving click-through or making the opening stronger
- output ratio and quality
- whether to generate original, non-identifiable background music
- extra constraints, such as no exaggerated claims, no price tags, no subtitles, no shopping prompts

If the user omits details, use defaults:

- audience: broad ecommerce
- goal: improve click-through
- ratio: 9:16
- quality: 720p
- audio: on by default, using original non-identifiable background music
- audio safety fallback: if the first Seedance task fails with `OutputAudioSensitiveContentDetected`, retry once by appending `Audio safety retry: use only sparse abstract ambient instrumental bed, no melody, no motif, no rhythm hook, no vocals, no lyrics, no speech-like phonemes, no samples, no artist/style imitation.`

Language defaults:

- Chinese user flow: use Chinese labels and the Chinese music constraint.
- English user flow: use English labels and the English music constraint.
- For `human_voiceover`, keep the generated voiceover in the template's spoken language, regardless of UI language.
- Language must be chosen before prepare. Existing prepared JSON should keep its original analysis language; switching `ui_language` by patch is only for small prompt-label experiments and is not a full translation path.

### 4. Creative Brief Confirmation

This gate is mandatory. It still applies when the user has already said "正式生成" or "其余默认".

Before generation, show a simple natural-language summary. Use the same frontstage section shape for both no-cost rehearsal and real prepare:

```markdown
{彩排/真实分析预览}已完成，当前还没有调用 Seedance，也还没有生成新视频。

本次 brief 摘要：
- 模板结构：...
- 商品锚点：...
- 输出默认：...
- 禁止继承：...
- 风险控制：...

如果你要继续，请回复：确认生成。
如果想先看完整详细分析，回复：查看详细分析。
也可以直接告诉我要改哪里，例如：...
```

English users should receive the same structure in English, for example:

```markdown
{No-cost rehearsal / real analysis preview} is complete. Seedance has not been called yet, and no new video has been generated.

Brief summary:
- Template structure: ...
- Product anchors: ...
- Output defaults: ...
- Forbidden carryover: ...
- Risk controls: ...

To continue, reply: confirm generation.
To review the full detailed analysis first, reply: show detailed analysis.
You can also tell me what to adjust, for example: ...
```

For real prepare, add the upload/provider/cost sentence where appropriate:

- The host agent should inspect the selected media and create the prepared brief before any provider video-generation call.
- After the real brief is prepared, say that confirming generation will call BytePlus Seedance, may take several minutes, and may consume the resource package.

For no-cost rehearsal, use parallel wording without provider calls:

- Say it replays the built-in real watermelon-juice sample prepared/result assets.
- Say it did not call Seedance and will not consume resources.
- When the user confirms, show the built-in real watermelon-juice sample video, not a template contact sheet or placeholder.

The compact summary is a decision brief, not the detailed analysis. Keep it short, close to 8-10 user-facing lines. It must include:

- chosen template
- chosen product image and media type
- product identity to preserve
- audience
- goal
- output style
- important constraints
- compact template structure and product anchors
- concise generation direction, forbidden carryover, key risks, and one-line natural-beat prompt preview
- a clear offer to expand the detailed analysis before generation confirmation. Use wording like: "如果你想先看详细分析，可以回复‘查看详细分析’；看完后再继续确认是否生成。"
- for English users, use the parallel wording: "If you want to review the detailed analysis first, reply 'show detailed analysis'; then continue to generation confirmation."

The compact brief must not print detailed-section headings such as "模板视频理解摘要", "生成前复刻方案", "每 5 秒摘要", "镜头脚本", "生成提示词预览", "Template Video Understanding Summary", "Pre-generation Rewrite Plan", "Every-5-second summary", or "Shot script". Those belong in detailed analysis.

The detailed analysis saved to prepared JSON or shown in debug mode should keep the original analysis shape below. Use 1fps timestamped frame observations as internal evidence for template videos, but do not add a separate per-second evidence section to the user-facing detailed analysis unless the user asks for raw frame evidence.

For local files, get those observations by running:

```bash
python3 scripts/extract_video_frames.py /path/to/template.mp4 --output-dir /path/to/workdir/frames --fps 1 --max-frames 15
```

1. 视频基础信息：duration, frames/fps when available, ratio, audio state, voiceover/music/environment sound, and whether the video is one-take or edited.
2. 模板流程与核心爽点：start state -> product/action intervention -> visible change -> result display -> CTA/ending, plus why the satisfaction works.
3. 场景、人物与画面重点：real scene type, background elements, light, props, camera position, framing, and product focus.
4. 每 5 秒窗口精细拆解：material type, shot/composition, camera, scene, action, product presence, selling points, satisfaction points, subtitles/voice/audio, borrowable elements, and forbidden carryover.
5. 复刻成新商品视频的生成脚本：how to keep the template framework, replace it with the user's product, use the first 5 seconds as hook, and extend the next 7-8 seconds with proof/detail/use-case/visual CTA. The generated script should follow this original template-rewrite logic; do not replace it with a generic summary or a raw per-second frame list.

For human/scene/voice templates:

- If the template has a visible creator face, eye contact, expression, or front-facing presenter posture, treat it as a trust mechanism. The generated person must be new and non-specific, but should not automatically become faceless or only a cropped body.
- Preserve the template person's broad appearance / market visual context when it is visible. This means keeping the same broad demographic and styling context while avoiding any exact identity or face copy.
- If the template uses a real shop/home/studio background, preserve the background function and major scene cues. Do not let a white-background product image overwrite the template's real scene unless the user asks for a studio look.
- If the template has voiceover or spoken presentation, preserve the template language and presentation rhythm as original voiceover-style delivery, mouth movement, or clear explaining gestures. Do not copy the original speaker, voice, wording, account handle, or platform CTA.
- If the template ends with a platform page, search page, or account CTA, borrow only the closing function. Do not inherit platform UI, and do not replace it with a blank/white/black/pure-color ending. The last second should keep the source product visibly present.
- Even when a voiceover is generated, subtitles, automatic captions, watermarks, lower-thirds, platform text, prices, and shopping UI are off by default unless the user explicitly asks otherwise.

For the actual generation prompt, convert detailed analysis into soft generation beats. Do not ask the video model to follow frame-accurate timing or many 0.5-1 second micro-shots. Keep 4-5 natural visual beats by default, preserve the template's function and satisfaction structure, and avoid excessive scene/action changes that could destabilize product identity.

Ask whether the user wants to generate from this brief or adjust anything. Do not call Seedance if the user has not confirmed.
After showing the concise readout, ask whether the user wants to see the detailed analysis. If yes, show the detailed analysis and then continue back to the same edit/confirm/generate flow.
Use the same detailed-analysis section shape for both no-cost rehearsal and real prepare:
Do not replace this with a one-paragraph recap. Do not say "详细分析见上面", "Detailed analysis is shown above", "the key decision is unchanged", or only repeat the route/profile. The user asked to inspect the evidence, so print the actual detailed sections.

```markdown
详细分析

模板视频
- 基础信息：时长、帧率、画幅、素材类型、是否静音/口播/字幕。
- 模板 profile：visual_product_texture / human_demo / human_voiceover / platform_cta / mixed，以及为什么这么判。
- 音频/字幕/口播：音乐、人声、口播语言、字幕/屏幕文字状态。
- 镜头/剪辑：剪辑节奏、镜头类型、机位、运动、转场。
- 每 5 秒窗口：素材类型、镜头顺序、动作、场景、可抓取素材、产品卖点、产品爽点、字幕/口播输出、可复刻元素、禁止继承元素。
- 可借用结构：hook、证明镜头、动作机制、情绪/CTA 功能。
- 禁止继承：模板商品、品牌、包装、平台 UI、字幕、价格、人物身份等。

{商品名}商品图分析
- 商品身份和外观锚点。
- 可确认卖点。
- 不可脑补/不能强宣称的点。
- 与模板的冲突或风险。

拟生成脚本
- 用自然镜头 beat 写 4-5 段生成脚本，保留模板框架、替换成用户商品。
- 前 5 秒必须说明 hook 怎么复刻，后 7-8 秒说明证明/使用场景/视觉 CTA 怎么延展。

生成约束
- 输出规格、音频策略、无字幕/无价格/无购物 UI/无水印、禁止模板商品泄漏、产品一致性、结尾不能留白。

现在可以回复 确认生成 ... 也可以直接说要改哪里...
```

For English users, keep the same section shape in English:

```markdown
Detailed analysis

Template video
- Basic facts: duration, fps, aspect ratio, material type, whether it has silence, voiceover, subtitles, or music.
- Template profile: visual_product_texture / human_demo / human_voiceover / platform_cta / mixed, and why.
- Audio/subtitle/voiceover: music, human voice, spoken language, subtitles/on-screen text state.
- Camera/editing: pacing, shot types, camera position, movement, transitions.
- Every-5-second windows: material type, shot order, actions, scene, materials to capture, product selling points, satisfaction points, subtitle/voiceover output, borrowable elements, forbidden carryover.
- Borrowable structure: hook, proof shots, action mechanism, emotion/CTA function.
- Forbidden carryover: template product, brand, packaging, platform UI, subtitles, prices, exact person identity, and similar elements.

{Product name} product image analysis
- Product identity and visual anchors.
- Confirmed selling points.
- Unproven points that must not become hard claims.
- Conflicts or risks against the template.

Proposed generation script
- Write 4-5 natural visual beats that preserve the template framework while replacing the template product with the user's product.
- Explain how the first 5 seconds replicate the hook, then how the next 7-8 seconds extend proof/use context/visual CTA.

Generation constraints
- Output settings, audio strategy, no subtitles/prices/shopping UI/watermarks, no template-product leakage, product consistency, and no blank ending.

You can now reply confirm generation ... or tell me what to adjust...
```

If the analysis reveals a conflict, it is correct to ask the user to choose a direction, but first show the evidence: what the template analysis says, what the product image analysis says, which elements conflict, and what each option changes.
Ask in user language what should change, for example product appearance, selling points, forbidden elements, or shot direction. Internally this can update:

- source product identity
- product image appearance anchors
- confirmed selling points
- forbidden template elements
- uncertain or unproven points
- rewrite strategy
- risks

Do not show the raw model prompt or full director-level analysis unless the user explicitly asks or debug mode is enabled.

### 5. Rehearsal Or Real Generation

If the user wants a no-cost rehearsal, run the built-in full-flow rehearsal. It is a three-stage state machine that must show the later workflow shape, not just validate a request. Walk the stages in order and gate between them; never collapse or skip a stage:

1. BRIEF — `--rehearsal --prepare-only`. Shows the example template understanding, product anchors, rewrite strategy, prompt preview, and the "查看详细分析 / 确认生成" or "show detailed analysis / confirm generation" gate. Forward its complete stdout verbatim. Do not compress it into your own bullet summary.
2. DETAIL — only when the user replies "查看详细分析" / "show detailed analysis". Run `--rehearsal --prepare-only --show-detailed-analysis` (clean detailed analysis, no raw JSON dump) and forward its complete stdout verbatim. Always offer this stage before generation confirmation; do not jump from BRIEF straight to the confirmed result.
3. RESULT — only after the user replies "确认生成" / "confirm generation". Run `--rehearsal --confirmed-brief` to show the example result step.

Use `--show-detailed-analysis`, not `--show-debug-artifacts`, for the user-facing DETAIL stage. `--show-debug-artifacts` additionally dumps the raw prepared JSON and is for debugging only, not for forwarding to the user.

This rehearsal uses only bundled example files and must clearly say it is an example replay, not a real generation.
When `--ui-language en` is used, the built-in rehearsal frontstage, detailed-analysis headings/content, prompt-preview labels, music constraint, confirmation gate, and example result checklist must be in English. Do not load a Chinese prepared artifact and merely print English wrapper text.

Use `--setup-only` only as an internal request/schema smoke test. Do not use setup-only as the user-facing no-cost rehearsal.

If the user wants real analysis and prompt preview, collect choices in chat, use the host agent to inspect the media and write a prepared JSON outside the skill folder. The runner does not call ModelArk/Seed for real template/product-image understanding.

User-facing wording:

"We can do a no-cost full-flow rehearsal first. It uses the built-in example to show the template understanding, rewrite brief, detailed-analysis option, confirmation gate, and example result step. It does not call Seedance. For your real materials, I will do the analysis first; once the API key is ready, the confirmed brief can be sent to Seedance for generation."

Before calling Seedance, clearly say:

- Real generation sends the final prompt and product image reference to BytePlus Seedance.
- The template video guides the creative pattern.
- The product image is used as the main generation reference and source of product truth.
- Seedance generation may take several minutes and may incur model usage costs.
- If generated audio is rejected by provider safety checks, the runner will automatically retry once with stricter abstract ambient instrumental constraints while keeping original, non-identifiable, no-vocal music intent.

Ask for explicit confirmation.

### 6. Review

After generation, put the result media first:

- Show a direct generated-video preview first. In Codex Desktop, prefer `![生成视频](/absolute/path/to/video.mp4)`.
- Then show the returned task ID and a short manual review checklist.
- Show the contact sheet, saved local video path, remote URL, and result JSON only in debug mode or when the user asks.

Help the user review:

- The returned task ID belongs to this generation.
- The user reviews the video directly with the checklist.
- The output product is still the source product.
- The template product/brand did not leak into the output.
- The output avoids unwanted text, stickers, price labels, shopping prompts, or exaggerated claims.
- The first 5 seconds have a clear hook.
- The extended 7-8 seconds contain product proof, texture/detail, use-case context, or visual CTA.
- If audio was requested, the output has audio and it remains original, non-identifiable, no-vocal, with no clear hummable melody or repeated hook.
- The pacing, opening, CTA, ratio, and quality are acceptable.

## Commands For Agents

Prefer not to show these commands to end users unless needed. Use them internally or when the user asks how to run locally.

No-cost full-flow rehearsal:

```bash
OUTPUT_DIR=/abs/path/out python3 scripts/run_rewrite_video.py \
  --rehearsal \
  --prepare-only
```

English no-cost full-flow rehearsal:

```bash
OUTPUT_DIR=/abs/path/out python3 scripts/run_rewrite_video.py \
  --rehearsal \
  --prepare-only \
  --ui-language en
```

Show detailed rehearsal analysis (clean DETAIL stage, no raw JSON dump):

```bash
OUTPUT_DIR=/abs/path/out python3 scripts/run_rewrite_video.py \
  --rehearsal \
  --prepare-only \
  --show-detailed-analysis
```

Continue rehearsal after confirmation:

```bash
OUTPUT_DIR=/abs/path/out python3 scripts/run_rewrite_video.py \
  --rehearsal \
  --confirmed-brief
```

Internal request smoke test:

```bash
OUTPUT_DIR=/abs/path/out python3 scripts/run_rewrite_video.py \
  --env-file .env \
  --input-json /abs/path/to/request.json \
  --setup-only
```

Prepared brief and prompt preview from agent analysis:

```bash
OUTPUT_DIR=/abs/path/out python3 scripts/run_rewrite_video.py \
  --env-file .env \
  --prepared-input-json /abs/path/to/prepared.json \
  --prepare-only
```

Show detailed analysis from an existing prepared JSON:

```bash
OUTPUT_DIR=/abs/path/out python3 scripts/run_rewrite_video.py \
  --env-file .env \
  --prepared-input-json /abs/path/to/prepared.json \
  --prepare-only \
  --show-debug-artifacts
```

Real generation:

```bash
OUTPUT_DIR=/abs/path/out python3 scripts/run_rewrite_video.py \
  --env-file .env \
  --prepared-input-json /abs/path/to/prepared.json \
  --output-json /abs/path/to/output.json \
  --confirmed-brief
```

Small generation-direction adjustment after preview:

```bash
OUTPUT_DIR=/abs/path/out python3 scripts/run_rewrite_video.py \
  --env-file .env \
  --prepared-input-json /abs/path/to/prepared.json \
  --patch-json /abs/path/to/patch.json \
  --prepared-json /abs/path/to/prepared.adjusted.json \
  --output-json /abs/path/to/output.json \
  --confirmed-brief
```

Patch JSON shape:

```json
{
  "request": {
    "product_context": "updated product direction or must-keep context"
  },
  "append_request": {
    "extra_constraints": ["new generation constraint"]
  },
  "append_rewrite_brief": {
    "confirmed_selling_points": ["new light selling-point emphasis"],
    "risks": ["new risk control"]
  }
}
```

Create or load the prepared JSON first, show the prepared brief to the user, and only then run real generation from `--prepared-input-json` with `--confirmed-brief`.
