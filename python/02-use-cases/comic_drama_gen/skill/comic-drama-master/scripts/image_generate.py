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

"""
Image generation tool for comic-drama-master skill.

Uses the VolcEngine Ark SDK to generate images from text prompts.

Environment variables:
    MODEL_IMAGE_API_KEY or ARK_API_KEY or MODEL_AGENT_API_KEY: Ark API key (required)
    MODEL_IMAGE_NAME: Image model name (optional, default: doubao-seedream-4-5-251128)
    IMAGE_DOWNLOAD_DIR: Directory to save generated images (optional, default: ./)

Usage:
    python scripts/image_generate.py <prompt> [--output-dir <dir>]
"""

import argparse
import base64
import json
import os
import sys
import time

from volcenginesdkarkruntime import Ark

# Default model
DEFAULT_MODEL = "doubao-seedream-4-5-251128"


def image_generate(prompt: str, output_dir: str = None) -> list[str]:
    """Generate image based on prompt.

    Args:
        prompt: The prompt to generate image.
        output_dir: Directory to save the generated image. Defaults to IMAGE_DOWNLOAD_DIR env
                    or current directory.

    Returns:
        A list of local file paths of generated images.
    """
    if not prompt:
        print("Prompt is empty.")
        return []

    api_key = (
        os.getenv("MODEL_IMAGE_API_KEY")
        or os.getenv("ARK_API_KEY")
        or os.getenv("MODEL_AGENT_API_KEY")
    )
    if not api_key:
        print(
            "Error: MODEL_IMAGE_API_KEY, ARK_API_KEY or MODEL_AGENT_API_KEY environment variable is required."
        )
        sys.exit(1)

    client = Ark(api_key=api_key)

    model = os.getenv("MODEL_IMAGE_NAME", DEFAULT_MODEL)

    if output_dir is None:
        output_dir = os.getenv("IMAGE_DOWNLOAD_DIR", os.path.expanduser("./"))

    if not os.path.exists(output_dir):
        try:
            os.makedirs(output_dir, exist_ok=True)
        except Exception as e:
            print(f"Failed to create directory {output_dir}: {e}")
            return []

    saved_paths = []
    try:
        response = client.images.generate(
            model=model,
            prompt=prompt,
            response_format="b64_json",
        )

        for i, image in enumerate(response.data):
            timestamp = int(time.time())
            filename = f"generated_image_{timestamp}_{i}.png"
            filepath = os.path.join(output_dir, filename)

            if image.b64_json:
                # Decode base64 and save directly — avoids TOS URL access issues
                try:
                    img_bytes = base64.b64decode(image.b64_json)
                    with open(filepath, "wb") as f:
                        f.write(img_bytes)
                    print(f"Saved to: {filepath}")
                    saved_paths.append(filepath)
                except Exception as e:
                    print(f"Failed to save b64 image: {e}")
            elif image.url:
                # Fallback: try downloading from URL (may fail if TOS URL is not pre-signed)
                try:
                    import urllib.request

                    urllib.request.urlretrieve(image.url, filepath)
                    print(f"Downloaded to: {filepath}")
                    saved_paths.append(filepath)
                except Exception as e:
                    print(f"Failed to download image from {image.url}: {e}")
            else:
                print(f"Image {i}: no b64_json or url available.")

    except Exception as e:
        print(f"Error generating image: {e}")

    return saved_paths


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate image from prompt using Ark SDK"
    )
    parser.add_argument("prompt", help="Text prompt for image generation")
    parser.add_argument(
        "--output-dir", default=None, help="Directory to save generated images"
    )
    args = parser.parse_args()

    paths = image_generate(args.prompt, args.output_dir)
    print(json.dumps({"saved_files": paths}, ensure_ascii=False, indent=2))
