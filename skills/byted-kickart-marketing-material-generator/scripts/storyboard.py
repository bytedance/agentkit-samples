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

import sys
import json
import time
import logging
import click

from .base import Result
from .service import api_submit, api_query


@click.command()
@click.option("--input", required=True, type=str, help="创意分析结果JSON文件路径")
@click.option("--output", required=True, type=str, help="输出结果所在的json文件路径")
def main(input, output):
    """抖音营销视频故事板工具，参考[故事板指南](references/故事板指南.md)"""
    logging.info(f"[tool] >>> python3 {' '.join(sys.argv)}")

    with open(input, "r") as f:
        creative = f.read()
    submit_res = api_submit(4337201517621323, creative)
    click.echo(submit_res.model_dump_json())
    if submit_res.code != "0":
        exit(1)
    click.echo(f"提交任务成功，任务ID: {submit_res.message}")

    for _ in range(2 * 3):
        time.sleep(30)
        poll_res = api_query(submit_res.message)
        if poll_res.code == "1000":
            continue

        if poll_res.code != "0":
            click.echo(poll_res.model_dump_json(), err=True)
            exit(1)

        with open(output, "w") as f:
            result = json.loads(poll_res.message)
            json.dump(result, f, ensure_ascii=False, indent=2)
        click.echo(Result(code="0", message=output).model_dump_json())
        click.echo(f"任务完成，结果已保存到 {output}")
        return

    click.echo(f"任务正在执行中，请通过任务ID:{submit_res.message}查询任务状态")


if __name__ == "__main__":
    main()
