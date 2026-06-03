# MIT License
#
# Copyright (c) 2026 ByteDance
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import os
import click
import logging
import sys
import time
import json
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

from core import Result
from core.api.iccp.service import IccpService
from core.api.meida.media import SimpleMediaService

def download_image(url: str, save_path: str):
    """下载图片并保存为PNG格式"""
    response = requests.get(url, stream=True)
    response.raise_for_status()
    
    with open(save_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)


def process_single_image(media_id: str) -> dict:
    """处理单张图片的抠图任务"""
    try:
        media_service = SimpleMediaService()
        image_info = media_service.get_media(media_id)

        body = json.dumps({"image_url": image_info["url"]}, ensure_ascii=False)

        iccp_service = IccpService()
        submit_res = iccp_service.submit(175170562, body)

        if submit_res.code != "0":
            return {"media_id": media_id, "success": False, "error": submit_res.message}

        task_id = submit_res.data

        for _ in range(2 * 10):
            time.sleep(30)
            poll_res = iccp_service.query(task_id)  # type: ignore

            if poll_res.code == "1000":
                continue
            if poll_res.code != "0":
                return {
                    "media_id": media_id,
                    "success": False,
                    "error": poll_res.message,
                }

            # 解析返回的JSON数据
            result_data = poll_res.data
            if isinstance(result_data, str):
                result_data = json.loads(result_data)

            # 保存到文件空间
            output_dir = os.path.expanduser(f"~/.openclaw/media/outbound/{task_id}/")
            os.makedirs(output_dir, exist_ok=True)

            # 下载subject图片
            subject_url = result_data["subject"] # type: ignore
            subject_path = os.path.join(output_dir, "subject.png")
            download_image(subject_url, subject_path)

            # 下载mask图片
            mask_url = result_data["mask"] # type: ignore
            mask_path = os.path.join(output_dir, "mask.png")
            download_image(mask_url, mask_path)

            return {"media_id": media_id, "success": True, "subject_path": subject_path, "mask_path": mask_path, "subject_url": subject_url, "mask_url": mask_url}  # type: ignore

        return {
            "media_id": media_id,
            "success": False,
            "error": f"任务正在执行中，请通过任务ID:{task_id}查询任务状态",
        }
    except Exception as e:
        return {"media_id": media_id, "success": False, "error": str(e)}


@click.command()
@click.option(
    "--media-ids", required=True, type=str, help="图片对应的媒资ID，多个ID用逗号分隔"
)
def main(media_ids):
    """智能抠图工具（支持多张图片并发处理）"""
    logging.info(f"[tool] >>> python3 {' '.join(sys.argv)}")

    # 解析媒资ID列表
    media_id_list = [mid.strip() for mid in media_ids.split(",") if mid.strip()]

    if not media_id_list:
        click.echo(
            Result(code="-1", message="未提供有效的媒资ID").model_dump_json(), err=True
        )
        exit(1)

    click.echo(f"开始处理 {len(media_id_list)} 张图片...")

    # 并发处理多张图片
    results = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        # 提交所有任务
        futures = {
            executor.submit(process_single_image, mid): mid for mid in media_id_list
        }

        # 收集结果
        for future in as_completed(futures):
            media_id = futures[future]
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                results.append(
                    {"media_id": media_id, "success": False, "error": str(e)}
                )

    # 输出汇总结果
    filename = (
        f"/tmp/openclaw/byted-kickart-saliency-segmenter/output/{int(time.time())}.json"
    )
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    with open(filename, "w") as f:
        json.dump(results, f, ensure_ascii=False, indent=4)

    click.echo(f"处理完成，结果已保存到 {filename}")


if __name__ == "__main__":
    main()