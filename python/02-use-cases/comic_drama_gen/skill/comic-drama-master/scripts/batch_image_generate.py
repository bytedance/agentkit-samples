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
批量并行图片生成工具。

将多个 prompt 并行提交给 AI 图片生成 API，显著提升多张图片生成速度。
支持指定输出目录和自定义文件名前缀。

环境变量:
    MODEL_IMAGE_API_KEY or ARK_API_KEY or MODEL_AGENT_API_KEY: Ark API key (required)
    MODEL_IMAGE_NAME: Image model name (optional, default: doubao-seedream-4-5-251128)

用法:
    # 从 JSON 文件读取 prompts 列表，并行生成
    python scripts/batch_image_generate.py --prompts-file prompts.json --output-dir <dir> [--prefix scene_] [--max-workers 3]

    # 直接传入 prompt 列表（适合少量任务）
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
DEFAULT_MODEL = "doubao-seedream-4-5-251128"

# 最大并行数（避免 API rate limit）
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
    return Ark(api_key=api_key)


def _generate_single(
    client: Ark,
    model: str,
    prompt: str,
    output_dir: str,
    filename: str,
    index: int,
    max_retries: int = 3,
) -> dict:
    """生成单张图片，支持自动重试。

    Args:
        client: Ark client
        model: 模型名称
        prompt: 提示词
        output_dir: 输出目录
        filename: 目标文件名（如 scene_01.jpg）
        index: 图片索引（用于日志）
        max_retries: 最大重试次数

    Returns:
        dict: {"index": int, "status": "success"|"failed", "filepath": str, "filename": str, "error": str}
    """
    filepath = os.path.join(output_dir, filename)

    for attempt in range(1, max_retries + 1):
        try:
            response = client.images.generate(
                model=model,
                prompt=prompt,
                response_format="b64_json",
            )

            if response.data and response.data[0].b64_json:
                img_bytes = base64.b64decode(response.data[0].b64_json)
                with open(filepath, "wb") as f:
                    f.write(img_bytes)
                print(f"[{index + 1}] ✅ 生成成功: {filename}")
                return {
                    "index": index,
                    "status": "success",
                    "filepath": filepath,
                    "filename": filename,
                    "error": None,
                }
            elif response.data and response.data[0].url:
                # Fallback: 下载 URL
                import urllib.request

                urllib.request.urlretrieve(response.data[0].url, filepath)
                print(f"[{index + 1}] ✅ 生成成功（URL 下载）: {filename}")
                return {
                    "index": index,
                    "status": "success",
                    "filepath": filepath,
                    "filename": filename,
                    "error": None,
                }
            else:
                raise ValueError("响应中无 b64_json 或 url")

        except Exception as e:
            error_msg = str(e)
            print(
                f"[{index + 1}] ⚠️ 第 {attempt}/{max_retries} 次尝试失败: {filename} - {error_msg}"
            )
            if attempt < max_retries:
                # 指数退避等待
                wait_time = 2**attempt
                print(f"[{index + 1}] 等待 {wait_time}s 后重试...")
                time.sleep(wait_time)

    # 所有重试都失败
    print(f"[{index + 1}] ❌ 全部失败: {filename}")
    return {
        "index": index,
        "status": "failed",
        "filepath": filepath,
        "filename": filename,
        "error": error_msg,
    }


def _simplify_prompt(prompt: str) -> str:
    """简化 prompt，移除可能导致内容安全拒绝的高风险词汇。"""
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
    """批量并行生成图片。

    Args:
        prompts: 提示词列表
        output_dir: 输出目录
        prefix: 文件名前缀（默认 scene_）
        ext: 文件扩展名（默认 .jpg）
        max_workers: 最大并行数
        max_retries: 每张图片最大重试次数
        filenames: 自定义文件名列表（如 ["scene_01.jpg", "scene_02.jpg"]），
                   如果提供则忽略 prefix 和 ext

    Returns:
        dict: 批量生成结果
    """
    if not prompts:
        return {"status": "error", "message": "prompts 列表为空", "results": []}

    os.makedirs(output_dir, exist_ok=True)

    # 确定文件名列表
    if filenames and len(filenames) == len(prompts):
        names = filenames
    else:
        names = [f"{prefix}{i + 1:02d}{ext}" for i in range(len(prompts))]

    client = _get_client()
    model = os.getenv("MODEL_IMAGE_NAME", DEFAULT_MODEL)

    print(f"🎨 开始批量生成 {len(prompts)} 张图片（并行度: {max_workers}）...")
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

    # 按 index 排序
    results.sort(key=lambda x: x["index"])

    elapsed = time.time() - start_time
    succeeded = [r for r in results if r["status"] == "success"]
    failed = [r for r in results if r["status"] == "failed"]

    # 对失败的任务，尝试用简化 prompt 再次生成
    if failed:
        print(f"\n🔄 尝试对 {len(failed)} 个失败任务使用简化 prompt 重试...")
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
                    2,  # 简化 prompt 只重试 2 次
                )
                retry_futures[future] = idx

            for future in as_completed(retry_futures):
                result = future.result()
                retry_results.append(result)

        # 更新结果
        for retry_r in retry_results:
            if retry_r["status"] == "success":
                # 替换原失败结果
                for i, r in enumerate(results):
                    if r["index"] == retry_r["index"]:
                        results[i] = retry_r
                        break

    # 重新统计
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
        f"\n📊 批量生成完成: {len(succeeded)}/{len(prompts)} 成功，耗时 {elapsed:.1f}s"
    )

    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="批量并行图片生成")
    parser.add_argument("--prompts-file", help="JSON 文件路径，包含 prompts 字符串数组")
    parser.add_argument(
        "--prompts", nargs="+", help="直接传入 prompt 列表（与 --prompts-file 二选一）"
    )
    parser.add_argument("--output-dir", required=True, help="图片保存目录")
    parser.add_argument("--prefix", default="scene_", help="文件名前缀（默认 scene_）")
    parser.add_argument("--ext", default=".jpg", help="文件扩展名（默认 .jpg）")
    parser.add_argument(
        "--max-workers",
        type=int,
        default=DEFAULT_MAX_WORKERS,
        help=f"最大并行数（默认 {DEFAULT_MAX_WORKERS}）",
    )
    parser.add_argument(
        "--max-retries", type=int, default=3, help="每张图片最大重试次数（默认 3）"
    )
    parser.add_argument(
        "--filenames-file",
        help="JSON 文件路径，包含自定义文件名列表（可选）",
    )
    args = parser.parse_args()

    # 读取 prompts
    if args.prompts_file:
        with open(args.prompts_file, "r", encoding="utf-8") as f:
            prompts = json.load(f)
    elif args.prompts:
        prompts = args.prompts
    else:
        print("Error: 必须提供 --prompts-file 或 --prompts")
        sys.exit(1)

    # 读取自定义文件名
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
