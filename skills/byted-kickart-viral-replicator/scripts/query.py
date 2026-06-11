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

# 添加当前目录到Python路径，支持直接运行脚本
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import click
from core.api.iccp.service import IccpService
from core.api.meida.media import KickartUploader


@click.command()
@click.option("--task-id", type=str, required=True, help="任务ID")
@click.option("--output", "-o", required=True, help="输出文件路径")
def main(task_id: str, output: str):
    iccp_service = IccpService()
    result = iccp_service.query(task_id)

    if result.code == "1000":
        click.echo(result.model_dump_json(), err=True)
        return

    # 任务异常
    if result.code != "0":
        click.echo(result.model_dump_json(), err=True)
        return

    # 产物同步Saas平台
    kickart_uploader = KickartUploader(source="ad_variations")
    data = json.loads(str(result.data))
    kickart_uploader.upload(data.get("video_url"))

    # success
    with open(output, "w") as f:
        f.write(json.dumps(data, ensure_ascii=False))  # type: ignore

    click.echo(f"任务{task_id}完成，输出结果已保存到{output}")


if __name__ == "__main__":
    main()
