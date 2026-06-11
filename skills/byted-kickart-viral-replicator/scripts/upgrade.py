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


import time
import json
import click
from core import Result
from core.api.iccp.service import IccpService


@click.command()
def main() -> None:
    """获取技能最新版本"""
    try:
        iccp_service = IccpService()
        body = json.dumps(
            {"name": "byted-kickart-viral-replicator"}, ensure_ascii=False
        )
        submit_res = iccp_service.submit(175169026, body)
        click.echo(submit_res.model_dump_json())
        if submit_res.code != "0":
            exit(1)
        click.echo(f"提交任务成功，任务ID: {submit_res.data}")

        for _ in range(2 * 2):
            time.sleep(30)
            poll_res = iccp_service.query(submit_res.data)  # type: ignore

            if poll_res.code == "1000":
                continue
            if poll_res.code != "0":
                click.echo(poll_res.model_dump_json(), err=True)
                exit(1)

            click.echo(poll_res.model_dump_json())
            return

        click.echo(f"任务正在执行中，请通过任务ID:{submit_res.data}查询任务状态")
    except Exception as e:
        click.echo(Result(code="-1", message=str(e)), err=True)


if __name__ == "__main__":
    main()
