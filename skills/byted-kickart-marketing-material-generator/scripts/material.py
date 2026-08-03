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
import click
import logging
import requests
from urllib.parse import urlparse, parse_qs, urlencode
from .base import Result
from .service import api_submit, api_query


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


@click.command()
@click.option("--url", required=True, type=str, help="抖店商品链接")
@click.option("--output", required=True, type=str, help="输出结果所在的json文件路径")
def main(url, output):
    """抖音营销素材分析工具，参考[素材分析指南](references/素材分析指南.md)"""
    logging.info(f"[tool] >>> python3 {' '.join(sys.argv)}")

    simplify_res = simplify(url, ["id"])
    click.echo(simplify_res.model_dump_json())
    if simplify_res.code != "0":
        exit(1)

    submit_res = api_submit(
        3296206833079096, json.dumps({"url": simplify_res.message}, ensure_ascii=False)
    )
    click.echo(submit_res.model_dump_json)
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
