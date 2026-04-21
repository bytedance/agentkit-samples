# Copyright (c) 2025 Beijing Volcano Engine Technology Co., Ltd. and/or its affiliates.
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
import jsonpath

from base import Result, perror
from service import do_request


__all__ = ["submit", "query"]


# 发起请求 获取 TaskID
def submit(service_id: int, params: str) -> Result:
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
        response = do_request(
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
def query(task_id: str) -> Result:
    params = json.dumps({"TaskId": task_id}, ensure_ascii=False).encode("utf-8")
    try:
        resp = do_request("POST", {}, params, action="QueryAiTemplateTaskResult").json()

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


# 轮询任务状态
def poll(
    task_id: str, max_attempts: int = 10 * 10, interval_seconds: int = 6
) -> Result:
    for _ in range(max_attempts):
        time.sleep(interval_seconds)
        result = query(task_id)
        if result.code != "1000":
            return result
    exit(0)


@click.command()
@click.option("--id", required=True, type=str, help="任务ID")
@click.option("--output", required=True, type=str, help="输出结果所在的json文件路径")
def main(id, output):
    """根据任务ID重新查询任务结果"""
    logging.info(f"[tool] >>> python3 {' '.join(sys.argv)}")

    poll_res = query(id)
    if poll_res.code != "0":
        perror(poll_res)
    with open(output, "w") as f:
        result = json.loads(poll_res.message)
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(Result(code="0", message=output).model_dump_json())


if __name__ == "__main__":
    main()
