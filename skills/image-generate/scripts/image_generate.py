import argparse
import asyncio
import json
import os
import sys
from typing import Dict

import httpx

API_KEY = os.getenv("MODEL_IMAGE_API_KEY") or os.getenv("MODEL_AGENT_API_KEY")
API_BASE = os.getenv(
    "MODEL_IMAGE_API_BASE", "https://ark.cn-beijing.volces.com/api/v3"
).rstrip("/")
DEFAULT_MODEL = "doubao-seedream-5-0-260128"


def _get_headers() -> dict:
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}",
    }


def _build_request_body(item: dict, model_name: str) -> dict:
    body = {
        "model": model_name,
        "prompt": item.get("prompt", ""),
    }

    optional_fields = [
        "size",
        "response_format",
        "watermark",
        "image",
        "sequential_image_generation",
        "tools",
        "output_format",
    ]
    for field in optional_fields:
        if field in item and item[field] is not None:
            body[field] = item[field]

    if "max_images" in item and item.get("sequential_image_generation") == "auto":
        body["sequential_image_generation_options"] = {"max_images": item["max_images"]}

    return body


async def _call_image_api(item: dict, model_name: str, timeout: int) -> dict:
    url = f"{API_BASE}/images/generations"
    body = _build_request_body(item, model_name)

    async with httpx.AsyncClient(timeout=float(timeout)) as client:
        response = await client.post(url, headers=_get_headers(), json=body)
        response.raise_for_status()
        return response.json()


async def handle_single_task(
    idx: int,
    item: dict,
    timeout: int,
    model_name: str,
) -> tuple[list[dict], list[str], list[dict]]:
    success_list = []
    error_list = []
    error_detail_list = []

    try:
        response = await _call_image_api(item, model_name, timeout)

        if "error" not in response:
            data_list = response.get("data", [])
            for i, image_data in enumerate(data_list):
                image_name = f"task_{idx}_image_{i}"

                if "error" in image_data:
                    error_list.append(image_name)
                    error_detail_list.append(
                        {
                            "task_idx": idx,
                            "image_name": image_name,
                            "error": image_data.get("error"),
                        }
                    )
                    continue

                image_url = image_data.get("url")
                if image_url:
                    success_list.append({image_name: image_url})
                else:
                    b64 = image_data.get("b64_json")
                    if b64:
                        success_list.append(
                            {image_name: f"data:image/png;base64,{b64}"}
                        )
                    else:
                        error_list.append(image_name)
                        error_detail_list.append(
                            {
                                "task_idx": idx,
                                "image_name": image_name,
                                "error": "missing data (no url/b64)",
                            }
                        )
        else:
            error_info = response.get("error", {})
            error_list.append(f"task_{idx}")
            error_detail_list.append({"task_idx": idx, "error": error_info})

    except Exception as e:
        error_list.append(f"task_{idx}")
        error_detail_list.append({"task_idx": idx, "error": str(e)})

    return success_list, error_list, error_detail_list


async def image_generate(
    tasks: list[dict],
    timeout: int = 600,
    model_name: str = None,
) -> Dict:
    model = model_name or os.getenv("MODEL_IMAGE_NAME", DEFAULT_MODEL)

    if model.startswith("doubao-seedream-3-0"):
        return {
            "status": "failed",
            "success_list": [],
            "error_list": ["Seedream 3.0 is deprecated. Use Seedream 4.0+ instead."],
            "error_detail_list": [{"error": "Model deprecated"}],
        }

    success_list = []
    error_list = []
    error_detail_list = []

    coroutines = [
        handle_single_task(idx, item, timeout, model) for idx, item in enumerate(tasks)
    ]

    results = await asyncio.gather(*coroutines, return_exceptions=True)

    for res in results:
        if isinstance(res, Exception):
            error_list.append("unknown_task_exception")
            error_detail_list.append({"error": str(res)})
            continue
        s, e, ed = res
        success_list.extend(s)
        error_list.extend(e)
        error_detail_list.extend(ed)

    return {
        "status": "success" if success_list else "error",
        "success_list": success_list,
        "error_list": error_list,
        "error_detail_list": error_detail_list,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Generate images using Seedream models"
    )
    parser.add_argument(
        "--prompt", "-p", required=True, help="Text description of the desired image(s)"
    )
    parser.add_argument(
        "--size", "-s", default="2048x2048", help="Image size (e.g., 2048x2048, 2K, 4K)"
    )
    parser.add_argument(
        "--model",
        "-m",
        default=None,
        help="Model name (default: doubao-seedream-4-0-250828)",
    )
    parser.add_argument(
        "--image",
        "-i",
        default=None,
        help="Reference image URL or path (for image-to-image)",
    )
    parser.add_argument(
        "--images",
        nargs="+",
        default=None,
        help="Multiple reference images (for multi-image tasks)",
    )
    parser.add_argument(
        "--group", "-g", action="store_true", help="Generate group of images"
    )
    parser.add_argument(
        "--max-images",
        type=int,
        default=15,
        help="Max images for group generation (default: 15)",
    )
    parser.add_argument(
        "--output-format", choices=["png", "jpeg"], default="jpeg", help="Output format"
    )
    parser.add_argument(
        "--timeout",
        "-t",
        type=int,
        default=600,
        help="Timeout in seconds (default: 600)",
    )
    parser.add_argument("--no-watermark", action="store_true", help="Disable watermark")

    args = parser.parse_args()

    if not API_KEY:
        print(
            "Error: MODEL_IMAGE_API_KEY or MODEL_AGENT_API_KEY environment variable is required"
        )
        sys.exit(1)

    task = {
        "prompt": args.prompt,
        "size": args.size,
        "output_format": args.output_format,
        "watermark": not args.no_watermark,
    }

    if args.images:
        task["image"] = args.images
    elif args.image:
        task["image"] = args.image

    if args.group:
        task["sequential_image_generation"] = "auto"
        task["max_images"] = args.max_images

    result = asyncio.run(
        image_generate([task], timeout=args.timeout, model_name=args.model)
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
