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

from typing import Dict

from google.adk.tools import ToolContext
from veadk.tools.builtin_tools.video_generate import (
    video_generate as video_generate_builtin,
)


async def video_generate(
    params: list,
    tool_context: ToolContext,
    batch_size: int = 10,
    max_wait_seconds: int = 1200,
) -> Dict:
    """
    Generate videos in **batch** from text prompts, optionally guided by a first/last frame,
    and fine-tuned via *model text commands* (a.k.a. `parameters` appended to the prompt).

    This API creates video-generation tasks. Each item in `params` describes a single video.
    The function submits all items in one call and returns task metadata for tracking.

    Args:
        params (list[dict]):
            A list of video generation requests. Each item supports the fields below.
        batch_size (int):
            The number of videos to generate in a batch. Defaults to 10.
        max_wait_seconds (int):
            Maximum time in seconds to wait for all video tasks in each batch.
            Default is 20 minutes (1200 seconds). When the timeout is reached,
            unfinished tasks will be marked as timeout errors.

            Required per item:
                - video_name (str):
                    Name/identifier of the output video file.

                - prompt (str):
                    Text describing the video to generate. Supports zh/EN.
                    You may append **model text commands** after the prompt to control resolution,
                    aspect ratio, duration, fps, watermark, seed, camera lock, etc.
                    Format: `... --rs <resolution> --rt <ratio> --dur <seconds> --fps <fps> --wm <bool> --seed <int> --cf <bool>`
                    Example:
                        "小猫骑着滑板穿过公园。 --rs 720p --rt 16:9 --dur 5 --fps 24 --wm true --seed 11 --cf false"

            Optional per item:
                - first_frame (str | None):
                    Code (⌥code格式) or Base64 string (data URL) for the **first frame** (role = `first_frame`).
                    Use when you want the clip to start from a specific image.

                - last_frame (str | None):
                    Code (⌥code格式) or Base64 string (data URL) for the **last frame** (role = `last_frame`).
                    Use when you want the clip to end on a specific image.

                - generate_audio (bool | None):
                    Boolean value, used to determine whether the generated video should have sound.
                    If this field is not configured (None) or its value is `False`, no sound will be generated.
                    If it is configured as `True`, sound can be generated.
                    If you want to describe the sound content in detail, you can do so in the `prompt` field.

            Notes on first/last frame:
                * When both frames are provided, **match width/height** to avoid cropping; if they differ,
                  the tail frame may be auto-cropped to fit.
                * If you only need one guided frame, provide either `first_frame` or `last_frame` (not both).

            Image input constraints (for first/last frame):
                - Formats: jpeg, png, webp, bmp, tiff, gif
                - Aspect ratio (宽:高): 0.4–2.5
                - Width/Height (px): 300–6000
                - Size: < 30 MB
                - Base64 data URL example: `data:image/png;base64,<BASE64>`

    Model text commands (append after the prompt; unsupported keys are ignored by some models):
        --rs / --resolution <value>       Video resolution. Common values: 480p, 720p, 1080p.
                                          Default depends on model (e.g., doubao-seedance-1-0-pro: 1080p,
                                          some others default 720p).

        --rt / --ratio <value>            Aspect ratio. Typical: 16:9 (default), 9:16, 4:3, 3:4, 1:1, 2:1, 21:9.
                                          Some models support `keep_ratio` (keep source image ratio) or `adaptive`
                                          (auto choose suitable ratio).

        --dur / --duration <seconds>      Clip length in seconds. Seedance supports **3–12 s**;
                                          Wan2.1 仅支持 5 s。Default varies by model.

        --fps / --framespersecond <int>   Frame rate. Common: 16 or 24 (model-dependent; e.g., seaweed=24, wan2.1=16).

        --wm / --watermark <true|false>   Whether to add watermark. Default: **false** (per doc).

        --seed <int>                      Random seed in [-1, 2^32-1]. Default **-1** = auto seed.
                                          Same seed may yield similar (not guaranteed identical) results across runs.

        --cf / --camerafixed <true|false> Lock camera movement. Some models support this flag.
                                          true: try to keep camera fixed; false: allow movement. Default: **false**.

    Returns:
        Dict:
            API response containing task creation results for each input item. A typical shape is:
            {
                "status": "success",
                "success_list": [{"video_name": "video_url"}],
                "error_list": []
            }

    Constraints & Tips:
        - Keep prompt concise and focused (建议 ≤ 500 字); too many details may distract the model.
        - If using first/last frames, ensure their **aspect ratio matches** your chosen `--rt` to minimize cropping.
        - If you must reproduce results, specify an explicit `--seed`.
        - Unsupported parameters are ignored silently or may cause validation errors (model-specific).

    Minimal examples:
        1) Text-only batch of two 5-second clips at 720p, 16:9, 24 fps:
            params = [
                {
                    "video_name": "cat_park.mp4",
                    "prompt": "小猫骑着滑板穿过公园。 --rs 720p --rt 16:9 --dur 5 --fps 24 --wm false"
                },
                {
                    "video_name": "city_night.mp4",
                    "prompt": "霓虹灯下的城市延时摄影风。 --rs 720p --rt 16:9 --dur 5 --fps 24 --seed 7"
                },
            ]

        2) With guided first/last frame (square, 6 s, camera fixed):
            params = [
                {
                    "video_name": "logo_reveal.mp4",
                    "first_frame": "⌥abc12",
                    "last_frame": "⌥xyz34",
                    "prompt": "品牌 Logo 从线稿到上色的变化。 --rs 1080p --rt 1:1 --dur 6 --fps 24 --cf true"
                }
            ]
    """
    for item in params:
        if "prompt" in item:
            item["prompt"] = (
                f"（可以有极其轻度的动作音，但禁止任何人声，禁止背景音乐，禁止音效，禁止旁白，禁止解说）{item['prompt']}"
            )
    return await video_generate_builtin(
        params, tool_context, batch_size, max_wait_seconds
    )
