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

import click
import logging
import sys
import time
import json
import os
import math

from core import Result
from core.api.iccp.service import IccpService
from core.api.meida.media import SimpleMediaService
from core.api.meida.media import KickartUploader


@click.command()
@click.option("--media-id", required=True, type=str, help="视频对应的媒资ID")
@click.option(
    "--captions", required=True, type=str, help="视频字幕配置的本地文件路径（JSON格式）"
)
@click.option("--output", required=True, type=str, help="输出结果所在的json文件路径")
def main(media_id, captions, output):
    """本地视频文件字幕添加工具，为视频文件添加字幕"""
    logging.info(f"[tool] >>> python3 {' '.join(sys.argv)}")

    if not os.path.isfile(captions):
        click.echo(
            Result(code="-1", message=f"字幕配置文件不存在: {captions}"), err=True
        )
        exit(1)

    try:
        # 读取字幕配置文件
        with open(captions, "r", encoding="utf-8") as f:
            captions_config = json.load(f)
            if isinstance(captions_config, list):
                captions_config_new = {}
                captions_config_new["text"] = "".join(
                    [item["text"] for item in captions_config]
                )
                captions_config_new["start_time"] = min(
                    item["start_time"] for item in captions_config
                )
                captions_config_new["end_time"] = max(
                    item["end_time"] for item in captions_config
                )
                captions_config_new["words"] = [
                    word for item in captions_config for word in item["words"]
                ]
                captions_config_new["attribute"] = {}
                captions_config = captions_config_new

        if 3000 < len(captions_config["text"]):
            click.echo(
                Result(code="-1", message="字幕文本长度必须小于3000个字符"), err=True
            )
            exit(1)

        media_service = SimpleMediaService()
        video_info = media_service.get_media(media_id)

        body = json.dumps(
            {
                "video_url": video_info["url"],
                "video_duration": 1 + math.floor(video_info["duration"]),
                "aspect_ratio": video_info["closest_ratio"],
                "captions": captions_config,
            },
            ensure_ascii=False,
        )

        iccp_service = IccpService()
        submit_res = iccp_service.submit(29396226, body)
        click.echo(submit_res.model_dump_json())
        if submit_res.code != "0":
            exit(1)
        click.echo(f"提交任务成功，任务ID: {submit_res.data}")

        for _ in range(2 * 5):
            time.sleep(30)
            poll_res = iccp_service.query(submit_res.data)  # type: ignore

            if poll_res.code == "1000":
                continue
            if poll_res.code != "0":
                click.echo(poll_res.model_dump_json(), err=True)
                exit(1)

            # 产物同步Saas平台
            result = json.loads(poll_res.data)  # type: ignore
            kickart_uploader = KickartUploader(source="skills")
            kickart_uploader.upload(result.get("video"))

            with open(output, "w") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            click.echo(Result(code="0", message=output).model_dump_json())
            click.echo(f"任务完成，结果已保存到 {output}")

            return

        click.echo(f"任务正在执行中，请通过任务ID:{submit_res.data}查询任务状态")
    except Exception as e:
        click.echo(Result(code="-1", message=str(e)), err=True)
        exit(1)


if __name__ == "__main__":
    main()
