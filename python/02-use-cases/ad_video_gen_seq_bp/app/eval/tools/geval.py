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

import asyncio
import json
import os
from typing import Any

from json_repair import repair_json
from openai import AsyncOpenAI
from veadk.auth.veauth.ark_veauth import get_ark_token
from veadk.consts import DEFAULT_MODEL_AGENT_API_BASE
from veadk.utils.logger import get_logger

from app.eval.prompt import PROMPT_EVALUATE_ITEM_AGENT
from app.eval.schema import EvaluationList, ScoredImageList, ScoredVideoList
from app.utils import url_shortener

logger = get_logger(__name__)

evaluate_agent_instruction = PROMPT_EVALUATE_ITEM_AGENT


def resolve_code2url(code: str) -> str:
    # return media_url
    return url_shortener.code2url(code)


async def repair_evaluate_input(
    media_list: list[dict[str, Any]], media_type: str = "image"
) -> list[list[dict[str, Any]]]:
    if media_type == "image":
        MEDIA_URL_FIELD = "image_url"
        MEDIA_TYPE_FIELD = "input_image"
        MEDIA = "image"
    else:
        MEDIA_URL_FIELD = "video_url"
        MEDIA_TYPE_FIELD = "input_video"
        MEDIA = "video"
    result = []
    for shot in media_list:
        shot_id = shot.get("shot_id", "")
        reference_media_list = shot.get("reference", [])
        if isinstance(reference_media_list, str):
            reference_media_list = [reference_media_list]
        media_url_list = [image["code"] for image in shot.get("media", [])]
        # First, construct the reference, which is common within the same shot
        reference_part_list = []
        for reference_media in reference_media_list:
            if len(reference_media.strip()) == 0:
                continue

            # At the video stage the reference is a shortened ⌥code, not a URL;
            # sending it raw makes Ark reject the request with
            # InvalidParameter "invalid scheme" on param `url`.
            resolved_reference = resolve_code2url(reference_media.strip())
            if not resolved_reference.lower().startswith(("http://", "https://")):
                logger.warning(
                    f"Skipping reference that did not resolve to a URL for shot_id={shot_id}: {reference_media!r}"
                )
                continue

            reference_part = {
                "type": "input_image",
                "image_url": resolved_reference,
            }  # Only images will be referenced
            reference_part_list.append(reference_part)

        for i, media_url in enumerate(media_url_list):
            resolved_media_url = resolve_code2url(media_url)
            if not resolved_media_url.lower().startswith(("http://", "https://")):
                logger.warning(
                    f"Skipping media that did not resolve to a URL for shot_id={shot_id}, media_id={i}: {media_url!r}"
                )
                continue

            text_part = {
                "type": "input_text",
                "text": (
                    f"This {MEDIA} has shot_id={shot_id}, media_id={i}. You received {len(reference_part_list) + 1} media items in total; the first {MEDIA} is the {MEDIA} you need to evaluate"
                    + f", and the remaining {len(reference_part_list)} images are all reference images."
                    if len(reference_part_list) > 0
                    else ""
                    + "Please evaluate the media item as required and output a result in the required format."
                ),
            }

            user_prompt = {"role": "user", "content": []}
            media_part = {"type": MEDIA_TYPE_FIELD, MEDIA_URL_FIELD: resolved_media_url}
            user_prompt["content"] = [text_part] + [media_part] + reference_part_list

            result.append(user_prompt)

    return result


async def evaluate_media(
    media_list: list[dict[str, Any]], media_type: str = "image"
) -> dict:
    """
    Evaluate a list of storyboard shots, each containing multiple generated media items,
    and return a score list and reasoning for each shot.

    This tool is designed to perform qualitative or model-based evaluation of
    storyboard media (e.g., generated images or videos from prompts or diffusion models)
    based on visual quality, temporal consistency, and coherence with reference materials.

    Each element in `media_list` represents one storyboard shot and includes its
    metadata, descriptive text, and a list of generated media for evaluation.

    Args:
        media_list (List[Dict[str, Any]]):
            A list of storyboard shot data. Each shot should include:

            - **shot_id** (str): The unique identifier for the storyboard shot.
            - **prompt** (str): A detailed text description used to generate the media.
            - **action** (str): The visual or narrative action happening in this shot.
            - **reference** (str): A reference media URL (optional), used as visual guidance.
            - **media** (List[Dict[str, Any]]): The list of generated media items for this shot,
              each containing:
                - **id** (int): The media ID.
                - **code** (str): The code of the generated media (image or video), eg ⌥00001.
        media_type (str): The type of media to be evaluated. Defaults to "image", only in ["image", "video"].
    Returns:
        List[Dict[str, Any]]: A list of evaluation results, one per shot.
        Each result includes the shot list:
            - **shot_id** (str): The ID of the evaluated shot.
            - **scores** (List[float]): A list of evaluation scores (one per media item)
              indicating visual or semantic quality.
            - **reason** (str): A textual explanation summarizing the evaluation,
              such as prompt alignment, visual coherence, or artistic quality.
    Example:
        evaluate_media([
        ...     {
        ...         "shot_id": "shot_1",
        ...         "prompt": "A samurai walking through cherry blossoms at sunset",
        ...         "action": "Character slowly moves from left to right",
        ...         "reference": "https://example.com/ref1.png",
        ...         "media": [
        ...             {"id": 1, "code": "⌥00001"},
        ...             {"id": 2, "code": "⌥00001"}
        ...         ]
        ...     }
        ... ])
    """
    logger.debug(f"Start to evaluate {media_type} list: items={len(media_list)}")
    m_content = await repair_evaluate_input(media_list, media_type=media_type)
    logger.debug(f"Repaired {media_type} list: messages={len(m_content)}")
    logger.info(f"media_list: \n\n {media_list} \n\n")
    client = AsyncOpenAI(
        base_url=os.getenv("MODEL_AGENT_API_BASE") or DEFAULT_MODEL_AGENT_API_BASE,
        api_key=os.getenv("MODEL_AGENT_API_KEY") or get_ark_token(),
    )

    async def process_message(msg):
        response = await client.responses.create(
            model=os.getenv("MODEL_EVALUATE_NAME", "dola-seed-2-1-turbo-260628"),
            instructions=evaluate_agent_instruction,
            input=[msg],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "EvaluationList",
                    "schema": EvaluationList.model_json_schema(),
                    "strict": True,
                }
            },
            extra_body={"thinking": {"type": "disabled"}},
        )
        # strict=False allows raw control characters (e.g. literal newlines) that
        # the evaluation model sometimes emits inside JSON string values; fall
        # back to json-repair for anything strict=False cannot handle (e.g. an
        # unescaped quote), logging the raw payload for diagnosis.
        try:
            parsed = json.loads(response.output_text, strict=False)
        except json.JSONDecodeError:
            logger.warning(
                "Evaluation model returned malformed JSON, attempting repair: %r",
                response.output_text,
            )
            parsed = repair_json(response.output_text, return_objects=True)
            if not isinstance(parsed, dict):
                raise
        return parsed.get("evaluation", {})

    # Use asyncio.gather to process all messages concurrently
    result = await asyncio.gather(*(process_message(msg) for msg in m_content))

    logger.debug(f"Finish to evaluate {media_type} list: result_items={len(result)}")
    # Post-processing: Merge results by shot_id and ensure the order of media_id
    merged_result = {}
    for item in result:
        shot_id = item.get("shot_id")
        media_id = int(item.get("media_id", 0))

        if shot_id not in merged_result:
            merged_result[shot_id] = {
                "shot_id": shot_id,
                "items": [],
            }
        merged_result[shot_id]["items"].append(
            (media_id, item.get("scores"), item.get("reason"))
        )

    final_result = []
    for shot_id, data in merged_result.items():
        sorted_items = sorted(data["items"], key=lambda x: x[0])

        scores = [item[1] for item in sorted_items]
        reason = [item[2] for item in sorted_items]

        final_result.append({"shot_id": shot_id, "scores": scores, "reason": reason})

    logger.debug(
        f"Finish to evaluate {media_type} list: final_result_items={len(final_result)}"
    )

    # Processing return values: directly construct ScoredImageList / ScoredVideoList and convert to a dictionary
    # Index the original input by shot_id to facilitate supplementing metadata
    shot_index = {shot.get("shot_id", ""): shot for shot in media_list}

    def normalize_reference(ref_val):
        if isinstance(ref_val, list):
            return ",".join(ref_val)
        return ref_val or ""

    # Assemble the corresponding output structure according to the media type
    if media_type == "image":
        scored_image_list = []
        for shot_id, data in merged_result.items():
            shot = shot_index.get(shot_id, {})
            media_entries = shot.get("media", [])
            # Map the evaluation results to {media_id: (score, reason)}
            eval_map = {mi: (score, reason) for mi, score, reason in data["items"]}

            images_items = []
            for idx, media in enumerate(media_entries):
                if idx not in eval_map:
                    continue
                score, reason = eval_map[idx]
                images_items.append(
                    {
                        "id": media.get("id", idx),
                        "code": media.get("code", ""),
                        "score": float(score) if score is not None else 0.0,
                        "reason": reason or "",
                    }
                )

            image_obj = {
                "shot_id": shot_id,
                "prompt": shot.get("prompt", ""),
                "action": shot.get("action", ""),
                "reference": normalize_reference(shot.get("reference")),
                "images": images_items,
            }
            scored_image_list.append(image_obj)

        output = {
            "scored_image_list": scored_image_list,
            "status": {"success": True, "message": ""},
        }
        try:
            model = ScoredImageList.model_validate(output)
            return model.model_dump()
        except Exception:
            return output

    else:
        scored_video_list = []
        for shot_id, data in merged_result.items():
            shot = shot_index.get(shot_id, {})
            media_entries = shot.get("media", [])
            eval_map = {mi: (score, reason) for mi, score, reason in data["items"]}

            videos_items = []
            for idx, media in enumerate(media_entries):
                if idx not in eval_map:
                    continue
                score, reason = eval_map[idx]
                videos_items.append(
                    {
                        "id": int(media.get("id", idx)),
                        "code": media.get("code", ""),
                        "score": float(score) if score is not None else 0.0,
                        "reason": reason or "",
                    }
                )

            video_obj = {
                "shot_id": shot_id,
                "prompt": shot.get("prompt", ""),
                "action": shot.get("action", ""),
                "reference": normalize_reference(shot.get("reference")),
                "videos": videos_items,
            }
            scored_video_list.append(video_obj)

        output = {
            "scored_video_list": scored_video_list,
            "status": {"success": True, "message": ""},
        }
        try:
            model = ScoredVideoList.model_validate(output)
            return model.model_dump()
        except Exception:
            return output
