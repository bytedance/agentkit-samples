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
import time
import json
import click
import logging
import jsonpath

from .base import Result

__all__ = ["api_submit"]


### 判断使用那种鉴权方式
def authentication():
    ACCESS_KEY_ID = os.getenv("ACCESS_KEY_ID")
    SECRET_ACCESS_KEY = os.getenv("SECRET_ACCESS_KEY")
    if ACCESS_KEY_ID is not None and SECRET_ACCESS_KEY is not None:
        from .servicev1 import _do_request

        return _do_request

    click.echo(Result(code="10010", message="AK/SK 未配置"), err=True)
    exit(1)


def api_submit(service_id: int, params: str) -> Result:
    try:
        payload = {
            "ResourceList": [
                "https://lf3-static.bytednsdoc.com/obj/eden-cn/jhteh7uhpxnult/test_image/woman/woman_4.png"
            ],
            "TemplateId": "2000620034",
            "Resolution": "1080p",
            "Extra": params,
        }

        # 图生图 样例
        submit_body = {
            "ServerId": service_id,
            "PayloadJson": json.dumps(payload, ensure_ascii=False),
        }
        submit_bytes = json.dumps(submit_body, ensure_ascii=False).encode("utf-8")
        response = authentication()(
            "POST", {}, submit_bytes, action="SubmitAiTemplateTaskAsync"
        ).json()

        code = jsonpath.jsonpath(response, "$.ResponseMetadata.Code")
        if not code:
            return Result(code="-1", message="提交任务失败, 响应内容为空")

        if code[0] != 0:
            return Result(code=str(code[0]), message=f"提交任务失败, Code: {code[0]}")

        task_id = jsonpath.jsonpath(response, "$.Result.TaskId")
        if not task_id or not task_id[0]:
            return Result(code="-1", message=f"解析TaskId失败, 响应内容: {response.c}")
        return Result(code="0", message=task_id[0])
    except Exception as e:
        return Result(code="-1", message=f"提交任务失败, 错误信息: {str(e)}")


# 查询任务状态
def api_query(task_id: str) -> Result:
    params = json.dumps({"TaskId": task_id}, ensure_ascii=False).encode("utf-8")
    try:
        resp = authentication()(
            "POST", {}, params, action="QueryAiTemplateTaskResult"
        ).json()

        code = jsonpath.jsonpath(resp, "$.ResponseMetadata.Code")
        if not code:
            return Result(code="-1", message="提交任务失败, 响应内容为空")
        if code[0] != 0:
            return Result(
                code=str(code[0]), message=f"查询任务状态失败, Code: {code[0]}"
            )

        result_code = jsonpath.jsonpath(resp, "$.Result.Code")
        if not result_code:
            return Result(code="-1", message="提交任务失败, 响应内容为空")

        # 继续轮询
        if result_code[0] in [1000, 1600]:
            return Result(code="1000", message="任务正在执行中")

        # 任务异常
        if result_code[0] != 0:
            msg = jsonpath.jsonpath(resp, "$.Result.Message")
            return Result(
                code=str(result_code[0]), message=msg[0] if msg else "任务异常"
            )

        # 任务成功
        progress = jsonpath.jsonpath(resp, "$.Result.Progress")
        if not progress or progress[0] != 100:
            return Result(code="1000", message="任务正在执行中")

        result = jsonpath.jsonpath(resp, "$.Result.ResultExtra")
        if not result or not result[0]:
            return Result(code="-1", message="未获取到任务结果")

        return Result(code="0", message=result[0])

    except Exception as e:
        return Result(code="-1", message=f"查询任务状态失败: {str(e)}")


@click.group()
def main():
    logging.info(f"[tool] >>> {' '.join(sys.argv)}")


# 查询&注册免费的Ark Claw 套餐
@main.command()
def combo() -> None:
    """查询&注册免费的Ark Claw 套餐"""
    try:
        resp = authentication()("POST", {}, b"", action="RegisterArkClawCombo").json()
        # >>> [火山OpenTop错误] >>> #
        open_top_code = jsonpath.jsonpath(resp, "$.ResponseMetadata.Error.CodeN")
        if open_top_code and open_top_code[0] != 0:
            click.echo(Result(code=str(open_top_code), message=""), err=True)
            exit(1)

        # >>> [创作云错误] >>> #
        code = jsonpath.jsonpath(resp, "$.ResponseMetadata.Code")
        if code and code[0] != 0:
            click.echo(Result(code=str(code), message=""), err=True)
            exit(1)

        # >>> [创作云成功] >>> #
        if code and code[0] == 0:
            result = jsonpath.jsonpath(resp, "$.Result")
            if not result or not result[0]:
                click.echo(Result(code="-1", message="接口返回值解析错误"), err=True)
                exit(1)
            expire = jsonpath.jsonpath(resp, "$.Result.expire_time")
            click.echo(Result(code="0", message=str(expire and expire[0])))
            exit(0)

        click.echo(Result(code="-1", message="接口返回值解析错误"), err=True)
    except Exception as e:
        click.echo(Result(code="-1", message=str(e)), err=True)


# 发起请求 获取 TaskID
@main.command()
@click.option("--service-id", type=int, required=True, help="服务ID")
@click.option("--params", type=str, required=True, help="请求参数")
def submit(service_id: int, params: str):
    result = api_submit(service_id, params)
    click.echo(result)


@main.command()
@click.option("--task-id", type=str, required=True, help="任务ID")
@click.option("--output", "-o", required=True, help="输出文件路径")
def query(task_id: str, output: str):
    result = api_query(task_id)
    click.echo(result)
    if result.code != "0":
        exit(1)

    with open(output, "w") as f:
        f.write(result.message)
    click.echo(Result(code="0", message=output))


@main.command()
@click.option("--task-id", type=str, required=True, help="任务ID")
@click.option("--output", "-o", required=True, help="输出文件路径")
def poll(task_id: str, output: str):
    """轮询查询任务进度"""
    for _ in range(2 * 60):
        time.sleep(30)
        result = api_query(task_id)
        if result.code == "1000":
            continue

        # 任务异常
        if result.code != "0":
            click.echo(result, err=True)
            return

        # success
        with open(output, "w") as f:
            f.write(result.message)
        click.echo(Result(code="0", message=output))
        return

    click.echo("轮询时间超过最大限制，建议稍后主动查询任务状态～", err=True)


if __name__ == "__main__":
    combo()