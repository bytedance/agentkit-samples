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

import re
from typing import Dict

from google.adk.tools import ToolContext
from veadk.tools.builtin_tools.image_generate import (
    image_generate as image_generate_builtin,
)
from veadk.utils.logger import get_logger

logger = get_logger(__name__)


async def image_generate(tasks: list[dict], tool_context: ToolContext) -> Dict:
    """Generate images with Seedream.

    Commit batch image generation requests via tasks.

    Args:
        tasks (list[dict]):
            A list of image-generation tasks. Each task is a dict.
    Per-task schema
    ---------------
    Required:
        - task_type (str):
            One of:
              * "multi_image_to_group"   # multiple images -> image group
              * "single_image_to_group"  # single image -> image group
              * "text_to_group"          # text -> image group
              * "multi_image_to_single"  # multiple images -> single image
              * "single_image_to_single" # single image -> single image
              * "text_to_single"         # text -> single image
        - prompt (str)
            Text description of the desired image(s). Chinese and English are both supported.
            Note: never put descriptions like `generate x images` in the prompt field; use the `max_images` field to control the number of generated images.
    Optional:
        - size (str)
            Size of the generated image:
                    - 1:1   -> 2048x2048
                    - 4:3   -> 2384x1728
                    - 3:4   -> 1728x2304
                    - 16:9  -> 2560x1440
                    - 9:16  -> 1440x2560
            Default: "2048x2048"
        - watermark (bool)
            Add watermark. Default: true.
        - image (str | list[str])   # (**corresponds to the reference field**)
            Reference image(s) as URL or Base64.
            * For "single image" tasks: pass a string (exactly 1 image).
            * For "image group" tasks: pass an array (2-10 images).
        - sequential_image_generation (str)
            Controls whether to generate an "image group". Default: "disabled".
            * To generate an image group: must be set to "auto".
        - max_images (int)
            Only effective when generating an image group. Controls how many images the model can generate.
    Model behavior (how the mode is inferred from parameters)
    ---------------------------------------------------------
    1) Text -> single image: no image provided and (S unset or S="disabled") -> 1 image.
    2) Text -> image group: no image provided and S="auto" -> image group, count controlled by max_images.
    3) Single image -> single image: image=string and (S unset or S="disabled") -> 1 image.
    4) Single image -> image group: image=string and S="auto" -> image group, count <= 14.
    5) Multiple images -> single image: image=array (2-10) and (S unset or S="disabled") -> 1 image.
    6) Multiple images -> image group: image=array (2-10) and S="auto" -> image group, total must be <= 15.
    Returns
    -------
        Dict with generation summary.
        Example:
        {
            "status": "success",
            "success_list": [
                {"image_name": "url"}
            ],
            "error_list": ["image_name"]
        }
    Notes:
    - Image-group tasks require sequential_image_generation="auto".
    - For size, prefer 2048x2048 or the standard ratios in the table above to ensure generation quality.
    """
    logger.debug(f"image_generate_gather tasks: {tasks}")
    new_tasks = []
    task_origin_info = []  # Stores (original_task_index, sub_index_within_group)

    for original_idx, task in enumerate(tasks):
        task_type = task.get("task_type", "")
        is_group_task = task_type in {
            "single_image_to_group",
            "text_to_group",
            "multi_image_to_group",
        }

        if is_group_task:
            num_images = task.get("max_images", 1)
            base_task_type = task_type.replace("_group", "_single")
            for i in range(num_images):
                new_task = task.copy()
                new_task["task_type"] = base_task_type
                new_task.pop("sequential_image_generation", None)
                new_task.pop("max_images", None)
                new_tasks.append(new_task)
                task_origin_info.append((original_idx, i))
        else:
            new_tasks.append(task.copy())
            task_origin_info.append((original_idx, 0))

    for task in new_tasks:
        # Guard against prompts containing phrases like "N张图片" ("N images" in
        # Chinese), which would turn a single image into a 4- or 6-panel grid.
        # The pattern matches both Arabic and Chinese numerals; it is kept in
        # Chinese on purpose because it sanitizes Chinese-language prompts.
        if "prompt" in task and isinstance(task["prompt"], str):
            task["prompt"] = re.sub(
                r"[\d一二三四五六七八九十百千万]+张图片", "图片", task["prompt"]
            )
        task["watermark"] = False

        # Handling the reference field: The model often incorrectly uses reference instead of image
        # Priority: image > reference
        if "reference" in task:
            if "image" not in task or not task.get("image"):
                task["image"] = task["reference"]
            task.pop("reference", None)

        aspect_ratio_map = {
            "1:1": "2048x2048",
            "4:3": "2384x1728",
            "3:4": "1728x2304",
            "16:9": "2560x1440",
            "9:16": "1440x2560",
            "3:2": "2496x1664",
            "2:3": "1664x2496",
            "21:9": "3024x1296",
        }
        if "size" in task and task["size"] in aspect_ratio_map:
            task["size"] = aspect_ratio_map[task["size"]]

    # Call the underlying image_generate function with the flattened list of tasks
    logger.debug(f"image_generate_gather new_tasks: {new_tasks}")
    raw_result = await image_generate_builtin(new_tasks, tool_context)
    logger.debug(f"image_generate_gather raw_result: {raw_result}")

    # Remap the results to match the original task structure
    remapped_success = []
    remapped_errors = set()

    for success_item in raw_result.get("success_list", []):
        for key, url in success_item.items():
            # Key is like 'task_{idx}_image_{i}'
            match = re.match(r"task_(\d+)_image_(\d+)", key)
            if not match:
                continue

            new_task_idx = int(match.group(1))
            if new_task_idx >= len(task_origin_info):
                continue

            original_idx, original_sub_idx = task_origin_info[new_task_idx]
            new_key = f"task_{original_idx}_image_{original_sub_idx}"
            remapped_success.append({new_key: url})

    for error_item in raw_result.get("error_list", []):
        # Error item is like 'task_{idx}'
        match = re.match(r"task_(\d+)", error_item)
        if match:
            new_task_idx = int(match.group(1))
            if new_task_idx < len(task_origin_info):
                original_idx, _ = task_origin_info[new_task_idx]
                remapped_errors.add(f"task_{original_idx}")
            else:
                remapped_errors.add(error_item)  # Keep original error if mapping fails
        else:
            remapped_errors.add(error_item)
    logger.debug(f"image_generate_gather remapped_success: {remapped_success}")
    logger.debug(f"image_generate_gather remapped_errors: {remapped_errors}")

    result = {
        "status": raw_result.get("status"),
        "success_list": remapped_success,
        "error_list": list(remapped_errors),
    }
    return result
