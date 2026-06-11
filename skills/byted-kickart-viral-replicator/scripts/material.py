# Copyright 2026 ByteDance
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

import os
import sys
import json
import time
import click
import logging
import requests
from urllib.parse import urlparse, parse_qs, urlencode

from core import Result
from core.api.iccp.service import IccpService
from core.utils.downloader import ParallelDownloader
import jsonpath
from core.utils.downloader import MagicFilenameGenerator


def simplify(url: str, keys: list) -> Result:
    try:
        # 校验域名
        parsed_original = urlparse(url)
        original_domain = parsed_original.netloc
        allowed_domains = ["haohuo.jinritemai.com", "v.douyin.com"]

        if original_domain not in allowed_domains:
            return Result(
                code="-1",
                message=f"URL域名不支持，仅支持以下域名：{', '.join(allowed_domains)}",
            )

        response = requests.head(url, allow_redirects=True)
        parsed = urlparse(response.url)
        query = {k: v for k, v in parse_qs(parsed.query).items() if k in keys}
        simplified_url = parsed._replace(query=urlencode(query, doseq=True)).geturl()
        return Result(code="0", message=simplified_url)
    except Exception as e:
        return Result(code="-1", message=f"简化URL失败：{str(e)}")


def poll(iccp_service, task_id: str, output: str) -> dict:
    """
    轮询查询任务状态

    Args:
        iccp_service: ICCP服务实例
        task_id: 任务ID
        output: 输出文件路径

    Returns:
        解析后的任务结果字典
    """

    for _ in range(2 * 5):
        time.sleep(30)
        poll_res = iccp_service.query(task_id)
        if poll_res.code == "1000":
            continue
        if poll_res.code != "0":
            click.echo(poll_res.model_dump_json(), err=True)
            exit(1)
        result = json.loads(poll_res.data)  # type: ignore
        with open(output, "w") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        click.echo(Result(code="0", message=output).model_dump_json())
        click.echo(f"任务完成，结果已保存到 {output}")
        return result

    click.echo(f"任务正在执行中，请通过任务ID:{task_id}查询任务状态")
    exit(1)


@click.command()
@click.option("--url", required=True, type=str, help="抖店商品链接")
@click.option("--output", required=True, type=str, help="输出结果所在的json文件路径")
def main(url, output):
    """抖店链接解析工具，提取链接中的图片和视频素材"""
    logging.info(f"[tool] >>> python3 {' '.join(sys.argv)}")

    simplify_res = simplify(url, ["id"])
    click.echo(simplify_res.model_dump_json())
    if simplify_res.code != "0":
        exit(1)

    try:
        iccp_service = IccpService()
        submit_res = iccp_service.submit(
            59317506, json.dumps({"url": simplify_res.message}, ensure_ascii=False)
        )
        click.echo(submit_res.model_dump_json())
        if submit_res.code != "0":
            exit(1)
        click.echo(f"提交任务成功，任务ID: {submit_res.data}")

        res = poll(iccp_service, submit_res.data, output)  # type: ignore

        # 使用jsonpath表达式提取所有URL
        urls = jsonpath.jsonpath(res, "$..url")
        if not urls:
            result = Result(
                code="0",
                message="success",
                data={
                    "task": submit_res.data,
                    "result": output,
                },
            )
            click.echo(result.model_dump_json())
            exit(0)

        # 创建下载目录（在openclaw/media/outbound目录下创建任务文件夹）
        download_dir = f"media/outbound/{submit_res.data}"
        dir = os.path.expanduser(os.path.join("~/.openclaw", download_dir))
        downloader = ParallelDownloader(
            output=dir, filename_generator=MagicFilenameGenerator()
        )
        success_count = downloader.download(urls)
        click.echo(f"素材下载完成，成功 {success_count}/{len(urls)} 个文件")
        click.echo(f"素材已保存到: {download_dir}")
        result = Result(
            code="0",
            message="success",
            data={
                "task": submit_res.data,
                "result": output,
                "total": len(urls),
                "downloaded": success_count,
                "path": download_dir,
            },
        )
        click.echo(result.model_dump_json())
        exit(0)

    except Exception as e:
        click.echo(Result(code="-1", message=str(e)), err=True)
        exit(1)


if __name__ == "__main__":
    main()
