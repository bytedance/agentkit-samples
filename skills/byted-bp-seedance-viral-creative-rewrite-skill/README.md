# Viral Creative Rewrite Skill

This package helps create a new ad video from:

- a template video, provided by the user as a local path or accessible URL
- a product image, using the included example image unless the user provides one

The template video is a structure reference: hook, pacing, shot order, camera language, satisfaction points, and CTA style. Its product, brand, packaging, claims, ingredients, and text should not be inherited.

The product image is the product truth for the generated video: product identity, appearance, packaging, visible ingredients, and confirmed selling points. The final video should be about this product.

For best results, keep the template video and product image in a similar category or use scene. For example, drinks work best with drinks or food templates, and beauty products work best with beauty or skincare templates. Cross-category rewrites can still borrow pacing and shot structure, but product consistency and scene fit may be less stable.

For product images, prefer product-only shots, packaging shots, hands, or non-identifiable body parts. Avoid uploading product images with recognizable real human faces, because they can trigger provider safety review or make generated faces/person shots unstable.

This product-image warning should not erase important template-video signals. If the template relies on a visible presenter face, eye contact, a real shop/home background, or voiceover-style explanation, the rewrite should preserve those as a new non-specific person, real-scene structure, and original presentation rhythm unless the user asks to remove them.

For people and voice templates, the brief should call out the template person's broad appearance/market visual context, the template spoken language, and whether the template contains captions, watermarks, or platform UI. The rewrite keeps the same broad context and same spoken language with new wording, while defaulting to no subtitles, no automatic captions, and no on-screen text.

Template profile routing is required before planning. Drink, food, and product-texture templates should route to `visual_product_texture` and transfer shot order, product state, texture, satisfaction, camera rhythm, and scene mood without forcing voiceover, lip sync, or person appearance matching. Human try-on or use-demo templates route to `human_demo`. Presenter videos with speech route to `human_voiceover` and preserve the template's broad person context and spoken language with original new wording. Platform/account/search endings route to `platform_cta`, borrowing only the closing function and replacing it with a product-visible ending.

Chinese and English user flows are both supported. Set `ui_language` to `zh`, `en`, or `auto` in the request. The UI language controls runner messages, analysis language, brief text, setup/missing-key guidance, prompt-preview labels, and music constraint wording. It does not override template spoken language: a Chinese UI can still preserve an English template voiceover, and an English UI can still preserve a Chinese template voiceover.

## User Flow

1. Choose a template video.
   - Provide a custom template video path or URL.
   - This repository package intentionally excludes bundled `.mp4` example videos.
2. Choose the product image.
   - Use the included example image for rehearsal.
   - Or provide the user's own local product image or image URL.
   - Avoid product images with recognizable real human faces; product-only images, packaging shots, hands, or non-identifiable body parts are safer.
3. Describe what must stay true about the product.
4. Add audience, goal, output style, and safety constraints.
5. Use the host agent to inspect the template video and product image, then create the prepared brief. Do not use ModelArk/Seed for video understanding.
6. Review the compact template-understanding summary first, then the concise rewrite plan, product-image anchors, forbidden carryover, key risks, 12-15 second extension direction, and plain-language prompt preview. Detailed analysis is saved to prepared JSON or shown in debug mode; the user should be explicitly offered "查看详细分析" or "show detailed analysis" before generation confirmation.
   - If there is a conflict, show the evidence from the template analysis and product-image analysis before asking the user to choose a direction.
   - Confirm the template profile and active transfer slots. A watermelon/drink case should stay focused on product texture and shot mechanics; a clothing presenter/voiceover case should preserve broad person context, real scene, spoken language, mouth/gesture rhythm, and no-subtitle defaults.
7. Offer to expand the detailed analysis before generation confirmation. If the user says yes, show it and then continue the same generation flow.
8. Rehearse the full flow with built-in example artifacts, if desired. This shows the brief, detailed-analysis option, confirmation gate, and example result without keys or provider calls.
9. Confirm `ARK_API_KEY` and Seedance 2.0 resource package or equivalent entitlement only before final generation.
10. Confirm the prepared brief before real generation. Saying "real generation" starts this confirmation path; it does not submit Seedance immediately.
11. Review the generated video first, then the task ID and manual review checklist. Debug artifacts are hidden by default.

## Useful Links

- BytePlus registration: <https://console.byteplus.com/auth/signup?redirectURI=https%3A%2F%2Fwww.byteplus.com%2Fen&skipAccountProfile=true&utm_source=tiktok&utm_medium=lead-generation&utm_campaign=BP_TikTok_Agentic_Hub_FY26&utm_term=tiktok&utm_content=20260624>
- ModelArk API Key management: <https://console.byteplus.com/ark/region:ark+ap-southeast-1/apikey>
- ModelArk quick start: <https://docs.byteplus.com/zh-CN/docs/ModelArk/1399008>

Note: when surfacing these links, output each URL complete and verbatim. Do not shorten them or strip query / UTM parameters (e.g. `utm_campaign`) — they carry channel attribution and registration benefits and must reach the user intact.

Formal generation requires purchasing a Seedance 2.0 prepaid resource package and confirming video-generation permissions. Template/product understanding is done by the host agent and does not require `ARK_API_KEY`.

In a platform agent environment, users provide API keys to the agent or secure secret input. In local CLI runs, get `ARK_API_KEY` from ModelArk API Key management, copy `.env.example` to `.env` in the skill root, and fill `ARK_API_KEY=...` there instead of shared docs.

If `ARK_API_KEY` is missing, complete the setup in this order:

1. Register a BytePlus account: <https://console.byteplus.com/auth/signup?redirectURI=https%3A%2F%2Fwww.byteplus.com%2Fen&skipAccountProfile=true&utm_source=tiktok&utm_medium=lead-generation&utm_campaign=BP_TikTok_Agentic_Hub_FY26&utm_term=tiktok&utm_content=20260624>
2. Follow the ModelArk / Seedance flow to get the API key, buy the prepaid resource package, and activate the Seedance video generation model: <https://docs.byteplus.com/zh-CN/docs/ModelArk/2291680>
3. Enable Doubao Seed 2.0 Pro model permission: <https://console.byteplus.com/ark/region:ark+ap-southeast-1/openManagement?LLM=%7B%7D>
4. For local testing, copy `.env.example` to `.env` in the skill root and fill `ARK_API_KEY=...`.

When the user has already chosen real generation and the key is missing, do not stop before analysis. First finish agent-led video understanding, detailed analysis, and the prepared brief. Then summarize Seedance 2.0 advantages, show playable production example videos, and only after that show the complete setup order above.

## Important Behavior

- BytePlus Assets/material library is not used.
- Local template files should be analyzed by the host agent in the conversation.
- If the product image is already an accessible HTTPS URL, it can be used directly for generation.
- Final generation sends the confirmed prompt and product image reference to BytePlus Seedance.
- The template video guides creative structure through the prepared brief.
- The product image is used as the main Seedance reference and product truth.
- The generation direction adapts to the user's product description, audience, goal, and constraints.
- Real generation requires an explicit prepared-brief confirmation before Seedance is called.
- If real generation is about to use the included example product image, the agent must ask for a second confirmation before generation.
- Generated videos are downloaded with unique cache keys, and the normal user-facing result shows the video, task ID, and manual review checklist. For local testing, set `OUTPUT_DIR` outside the skill folder so generated files do not pollute the package source.
- Audio generation is enabled by default with original, non-identifiable, no-vocal music constraints. If Seedance rejects generated audio with `OutputAudioSensitiveContentDetected`, the runner retries once with stricter abstract ambient instrumental constraints.

## First Run

Prepare the skill-local runtime before the first opening or test run:

```bash
python3 scripts/ensure_runtime.py --ui-language zh --print-python
```

Use the printed `.venv/bin/python` for later skill commands. The bootstrap creates or reuses `.venv` and installs `requirements.txt` there when needed, so the workflow does not depend on system Python, Codex bundled Python, or Claude Code's runtime.

Create local config:

```bash
cp .env.example .env
```

Fill `.env` locally for real generation. Keep it in the skill root directory. For test runs, point `OUTPUT_DIR` to a workspace-level artifact folder rather than the skill folder.

Create a request JSON from the chat choices. Use `assets/examples/request.example.json` as the shape if needed, but write the actual request outside the skill folder during tests.

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

Show detailed analysis from a prepared JSON (canonical DETAIL view):

```bash
OUTPUT_DIR=/abs/path/out python3 scripts/render_detailed_analysis.py \
  --prepared-input-json /abs/path/to/prepared.json
```

Real generation:

```bash
OUTPUT_DIR=/abs/path/out python3 scripts/run_rewrite_video.py \
  --env-file .env \
  --prepared-input-json /abs/path/to/prepared.json \
  --output-json /abs/path/to/output.json \
  --confirmed-brief
```

Small adjustment after preview:

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

Real generation is intentionally guarded. Create or load the prepared JSON first, review the prepared brief, then continue from `--prepared-input-json` with `--confirmed-brief` only after the user has explicitly approved the brief. Use `--patch-json` for small prompt/brief adjustments without re-analyzing the media.


## Included Examples

- bundled `.mp4` example videos are intentionally excluded from this repository package
- `assets/examples/source_product.jpg`: example product image
- `assets/examples/request.example.json`: example request for batch mode
- `assets/examples/rehearsal_prepared.example.json`: built-in no-cost rehearsal brief
- `assets/examples/rehearsal_result.example.json`: built-in no-cost rehearsal result
- `assets/examples/README.md`: note explaining why videos are excluded and how to provide runtime media
