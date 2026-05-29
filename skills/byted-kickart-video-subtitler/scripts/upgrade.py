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
        body = json.dumps({"name": "byted-kickart-video-subtitler"}, ensure_ascii=False)
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
