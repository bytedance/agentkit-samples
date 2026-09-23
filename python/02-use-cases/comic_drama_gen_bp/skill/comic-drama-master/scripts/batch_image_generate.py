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
Batch parallel image generation tool.

Submits multiple prompts to the AI image generation API in parallel,
significantly speeding up multi-image generation.
Supports specifying an output directory and a custom filename prefix.

Environment variables:
    MODEL_IMAGE_API_KEY or ARK_API_KEY or MODEL_AGENT_API_KEY: Ark API key (required)
    MODEL_IMAGE_NAME: Image model name (optional, default: dola-seedream-5-0-pro-260628)

Usage:
    # Read a list of prompts from a JSON file and generate in parallel
    python scripts/batch_image_generate.py --prompts-file prompts.json --output-dir <dir> [--prefix scene_] [--max-workers 3]

    # Pass the prompt list directly (suitable for a small number of tasks)
    python scripts/batch_image_generate.py --prompts "prompt1" "prompt2" "prompt3" --output-dir <dir>
"""

import argparse
import base64
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from volcenginesdkarkruntime import Ark

# Default model
DEFAULT_MODEL = "dola-seedream-5-0-pro-260628"

# Maximum parallelism (to avoid API rate limits)
DEFAULT_MAX_WORKERS = 3


def _get_client() -> Ark:
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
    # MODEL_IMAGE_API_BASE overrides the endpoint; default is BytePlus
    # (the Ark SDK's own default is the Volcano Engine cn-beijing endpoint).
    base_url = os.getenv(
        "MODEL_IMAGE_API_BASE", "https://ark.ap-southeast.bytepluses.com/api/v3"
    )
    return Ark(api_key=api_key, base_url=base_url)


def _generate_single(
    client: Ark,
    model: str,
    prompt: str,
    output_dir: str,
    filename: str,
    index: int,
    max_retries: int = 3,
) -> dict:
    """Generate a single image, with automatic retry support.

    Args:
        client: Ark client
        model: Model name
        prompt: Prompt text
        output_dir: Output directory
        filename: Target filename (e.g. scene_01.jpg)
        index: Image index (used for logging)
        max_retries: Maximum number of retries

    Returns:
        dict: {"index": int, "status": "success"|"failed", "filepath": str, "filename": str, "error": str}
    """
    filepath = os.path.join(output_dir, filename)

    for attempt in range(1, max_retries + 1):
        try:
            response = client.images.generate(
                model=model,
                prompt=prompt,
                # 1024x1024 is the smallest size Seedream supports; the default
                # (2048x2048) quadruples pixel count for no benefit in previews.
                size="1024x1024",
                response_format="b64_json",
            )

            if response.data and response.data[0].b64_json:
                img_bytes = base64.b64decode(response.data[0].b64_json)
                with open(filepath, "wb") as f:
                    f.write(img_bytes)
                print(f"[{index + 1}] ✅ Generated successfully: {filename}")
                return {
                    "index": index,
                    "status": "success",
                    "filepath": filepath,
                    "filename": filename,
                    "error": None,
                }
            elif response.data and response.data[0].url:
                # Fallback: download from URL
                import urllib.request

                urllib.request.urlretrieve(response.data[0].url, filepath)
                print(
                    f"[{index + 1}] ✅ Generated successfully (URL download): {filename}"
                )
                return {
                    "index": index,
                    "status": "success",
                    "filepath": filepath,
                    "filename": filename,
                    "error": None,
                }
            else:
                raise ValueError("No b64_json or url in response")

        except Exception as e:
            error_msg = str(e)
            print(
                f"[{index + 1}] ⚠️ Attempt {attempt}/{max_retries} failed: {filename} - {error_msg}"
            )
            if attempt < max_retries:
                # Exponential backoff wait
                wait_time = 2**attempt
                print(f"[{index + 1}] Waiting {wait_time}s before retrying...")
                time.sleep(wait_time)

    # All retries failed
    print(f"[{index + 1}] ❌ All attempts failed: {filename}")
    return {
        "index": index,
        "status": "failed",
        "filepath": filepath,
        "filename": filename,
        "error": error_msg,
    }


def _simplify_prompt(prompt: str) -> str:
    """Simplify the prompt by removing high-risk terms that may trigger content-safety rejections."""
    replacements = {
        "blood": "spiritual energy",
        "bloody": "intense",
        "bleeding": "glowing with energy",
        "sword piercing": "sword energy clash",
        "killing": "defeating",
        "dead body": "fallen warrior",
        "corpse": "motionless figure",
        "explosion": "energy eruption",
        "war": "confrontation",
        "battle": "encounter",
    }
    simplified = prompt
    for old, new in replacements.items():
        simplified = simplified.replace(old, new)
    return simplified


def batch_image_generate(
    prompts: list[str],
    output_dir: str,
    prefix: str = "scene_",
    ext: str = ".jpg",
    max_workers: int = DEFAULT_MAX_WORKERS,
    max_retries: int = 3,
    filenames: Optional[list[str]] = None,
) -> dict:
    """Generate images in parallel in batch.

    Args:
        prompts: List of prompts
        output_dir: Output directory
        prefix: Filename prefix (default: scene_)
        ext: File extension (default: .jpg)
        max_workers: Maximum parallelism
        max_retries: Maximum retries per image
        filenames: Custom filename list (e.g. ["scene_01.jpg", "scene_02.jpg"]);
                   if provided, prefix and ext are ignored

    Returns:
        dict: Batch generation results
    """
    if not prompts:
        return {"status": "error", "message": "prompts list is empty", "results": []}

    os.makedirs(output_dir, exist_ok=True)

    # Determine the filename list
    if filenames and len(filenames) == len(prompts):
        names = filenames
    else:
        names = [f"{prefix}{i + 1:02d}{ext}" for i in range(len(prompts))]

    client = _get_client()
    model = os.getenv("MODEL_IMAGE_NAME", DEFAULT_MODEL)

    print(
        f"🎨 Starting batch generation of {len(prompts)} images (parallelism: {max_workers})..."
    )
    start_time = time.time()

    results = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for i, (prompt, name) in enumerate(zip(prompts, names)):
            future = executor.submit(
                _generate_single,
                client,
                model,
                prompt,
                output_dir,
                name,
                i,
                max_retries,
            )
            futures[future] = i

        for future in as_completed(futures):
            result = future.result()
            results.append(result)

    # Sort by index
    results.sort(key=lambda x: x["index"])

    elapsed = time.time() - start_time
    succeeded = [r for r in results if r["status"] == "success"]
    failed = [r for r in results if r["status"] == "failed"]

    # For failed tasks, retry generation with simplified prompts
    if failed:
        print(f"\n🔄 Retrying {len(failed)} failed tasks with simplified prompts...")
        retry_results = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            retry_futures = {}
            for r in failed:
                idx = r["index"]
                simplified = _simplify_prompt(prompts[idx])
                future = executor.submit(
                    _generate_single,
                    client,
                    model,
                    simplified,
                    output_dir,
                    r["filename"],
                    idx,
                    2,  # Simplified prompts get only 2 retries
                )
                retry_futures[future] = idx

            for future in as_completed(retry_futures):
                result = future.result()
                retry_results.append(result)

        # Update results
        for retry_r in retry_results:
            if retry_r["status"] == "success":
                # Replace the original failed result
                for i, r in enumerate(results):
                    if r["index"] == retry_r["index"]:
                        results[i] = retry_r
                        break

    # Recompute statistics
    succeeded = [r for r in results if r["status"] == "success"]
    failed = [r for r in results if r["status"] == "failed"]

    summary = {
        "status": "success" if not failed else "partial" if succeeded else "failed",
        "total": len(prompts),
        "succeeded": len(succeeded),
        "failed": len(failed),
        "elapsed_seconds": round(elapsed, 1),
        "results": results,
        "saved_files": [r["filepath"] for r in succeeded],
        "failed_indices": [r["index"] for r in failed],
    }

    print(
        f"\n📊 Batch generation complete: {len(succeeded)}/{len(prompts)} succeeded, took {elapsed:.1f}s"
    )

    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Batch parallel image generation")
    parser.add_argument(
        "--prompts-file",
        help="Path to a JSON file containing an array of prompt strings",
    )
    parser.add_argument(
        "--prompts",
        nargs="+",
        help="Pass the prompt list directly (mutually exclusive with --prompts-file)",
    )
    parser.add_argument("--output-dir", required=True, help="Directory to save images")
    parser.add_argument(
        "--prefix", default="scene_", help="Filename prefix (default: scene_)"
    )
    parser.add_argument("--ext", default=".jpg", help="File extension (default: .jpg)")
    parser.add_argument(
        "--max-workers",
        type=int,
        default=DEFAULT_MAX_WORKERS,
        help=f"Maximum parallelism (default: {DEFAULT_MAX_WORKERS})",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Maximum retries per image (default: 3)",
    )
    parser.add_argument(
        "--filenames-file",
        help="Path to a JSON file containing a custom filename list (optional)",
    )
    args = parser.parse_args()

    # Read prompts
    if args.prompts_file:
        with open(args.prompts_file, "r", encoding="utf-8") as f:
            prompts = json.load(f)
    elif args.prompts:
        prompts = args.prompts
    else:
        print("Error: either --prompts-file or --prompts must be provided")
        sys.exit(1)

    # Read custom filenames
    filenames = None
    if args.filenames_file:
        with open(args.filenames_file, "r", encoding="utf-8") as f:
            filenames = json.load(f)

    result = batch_image_generate(
        prompts=prompts,
        output_dir=args.output_dir,
        prefix=args.prefix,
        ext=args.ext,
        max_workers=args.max_workers,
        max_retries=args.max_retries,
        filenames=filenames,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if result["status"] == "failed":
        sys.exit(1)
