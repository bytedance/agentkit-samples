# Copyright (c) 2026 ByteDance Ltd. and/or its affiliates
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
import re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import click
from core.api.meida.media import KickartUploader
from core.api.call_api import ViralReplicator, TaskInfo, TaskStatus, KickartException
from core.core import token, TokenException
from core import Result


POLL_INTERVAL = 30
MAX_WAIT = 3600

VALID_TEMPLATE_IDS = {
    "604911874": "专业模式（2.0、720p）",
    "463631106": "进阶模式（2.0fast、720p）",
}


@click.command()
@click.option("--task-id", type=str, required=True, help="任务ID")
@click.option(
    "--template-id",
    type=click.Choice(list(VALID_TEMPLATE_IDS.keys())),
    required=True,
    help="提交任务时使用的模板ID，必须与本次任务提交时一致。可选：604911874=专业模式（2.0、720p），463631106=进阶模式（2.0fast、720p）",
)
@click.option("--output", "-o", required=True, help="输出文件路径")
def main(task_id: str, template_id: str, output: str):
    click.echo("正在获取 x-muse-token...")
    try:
        x_muse_token = token()
    except TokenException as e:
        click.echo(
            Result(
                code="x01401", message=f"获取 x-muse-token 失败: {str(e)}"
            ).model_dump_json(),
            err=True,
        )
        exit(1)

    os.environ["X_MUSE_TOKEN"] = x_muse_token

    click.echo(f"正在查询任务状态: {task_id}（template_id={template_id}）")

    replicator = ViralReplicator(template_id=template_id)
    task_info = TaskInfo(task_id=task_id)

    deadline = time.time() + MAX_WAIT
    attempt = 0

    while time.time() < deadline:
        attempt += 1
        click.echo("任务执行中，请不要中断任务...")

        try:
            task_info = replicator.query(task_info)
        except KickartException as e:
            click.echo(
                json.dumps({"code": e.code, "message": e.message}, ensure_ascii=False),
                err=True,
            )
            exit(1)
        except Exception as e:
            click.echo(f"轮询异常: {str(e)}", err=True)
            time.sleep(POLL_INTERVAL)
            continue

        if task_info.task_status == TaskStatus.SUCCESS:
            result_json = json.dumps(task_info.payload, ensure_ascii=False, indent=2)
            click.echo(f"任务成功，最终结果:\n{result_json}")

            match = re.search(r'"result_url":\s*"([^"]+)"', result_json)
            if match:
                video_url = match.group(1)
                click.echo(f"成片视频URL: {video_url}")

                kickart_uploader = KickartUploader(source="ad_variations")
                kickart_uploader.upload(video_url)

            os.makedirs(os.path.dirname(output), exist_ok=True)
            with open(output, "w", encoding="utf-8") as f:
                json.dump(task_info.payload, f, ensure_ascii=False, indent=2)

            click.echo(
                json.dumps(
                    {
                        "code": "0",
                        "message": output,
                        "task_id": task_id,
                        "template_id": template_id,
                    },
                    ensure_ascii=False,
                )
            )
            exit(0)

        if task_info.task_status == TaskStatus.FAILED:
            click.echo(
                json.dumps(
                    {"code": "-1", "message": "任务执行失败"}, ensure_ascii=False
                ),
                err=True,
            )
            exit(1)

        time.sleep(POLL_INTERVAL)

    click.echo(
        json.dumps(
            {
                "code": "-1",
                "message": f"轮询超时（超过 {MAX_WAIT}s 仍未拿到终态），template_id: {template_id}",
            },
            ensure_ascii=False,
        ),
        err=True,
    )
    exit(1)


if __name__ == "__main__":
    main()
