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
import uuid
import json
import time
import click
import logging
import subprocess
from subprocess import DEVNULL

from .base import Result
from .service import api_submit, api_query


@click.group()
def main():
    """消费成片工具，参考[消费成片指南](references/消费成片指南.md)"""
    logging.info(f"[tool] >>> {' '.join(sys.argv)}")


def check(session, metadata):
    jsession = json.loads(session)
    jmetadata = json.loads(metadata)
    if "sessionId" not in jsession:
        result = Result(code="A0101", message="会话元数据中缺少sessionId字段")
        click.echo(result.model_dump_json(), err=True)
        exit(1)
    try:
        # 尝试将输入字符串转换为UUID对象
        uuid_obj = uuid.UUID(jsession["sessionId"])  # type: ignore
        if str(uuid_obj) != jsession["sessionId"].lower():  # type: ignore
            result = Result(code="A0101", message="会话元数据中sessionId字段格式错误")
            click.echo(result.model_dump_json(), err=True)
            exit(1)
    except ValueError:
        result = Result(code="A0101", message="会话元数据中sessionId字段格式错误")
        click.echo(result.model_dump_json(), err=True)
        exit(1)

    if "chat_id" not in jmetadata:
        result = Result(code="A0102", message="消息元数据中缺少chat_id字段")
        click.echo(result.model_dump_json(), err=True)
        exit(1)
    if "channel" not in jmetadata:
        result = Result(code="A0102", message="消息元数据中缺少channel字段")
        click.echo(result.model_dump_json(), err=True)
        exit(1)
    return jsession, jmetadata


@main.command()
@click.option("--storyboard", default=0, type=int, help="用于成片任务的故事板编号")
@click.option("--input", required=True, type=str, help="故事板创作结果JSON文件路径")
@click.option("--output", "-o", required=True, help="输出文件路径")
@click.option(
    "--session", required=True, type=str, help="当前会话的完整元数据（JSON格式）"
)
@click.option(
    "--metadata", required=True, type=str, help="当前消息的完整未修改元信息（JSON格式）"
)
def submit(storyboard, input, output, session, metadata):
    with open(input, "r") as f:
        data = json.load(f)

    storyboards = data["storyboards"]
    if storyboard >= len(storyboards):
        msg = f"故事板编号超出范围，总故事板数为{len(storyboards)}, 请指定一个有效的故事板编号（1-{len(storyboards)}）"
        result = Result(code="-1", message=msg)
        click.echo(result.model_dump_json(), err=True)
        exit(1)

    data["storyboard"] = storyboards[storyboard]
    data["storyboards"] = None

    mock = os.getenv("SKILL_MOCK")
    if not mock:
        submit_res = api_submit(2935355633875543, json.dumps(data, ensure_ascii=False))
    else:
        submit_res = Result(code="0", message="7631484346175782975")
    click.echo(submit_res.model_dump_json(), err=True)
    click.echo(f"提交任务成功，任务ID: {submit_res.message}")

    ### 提交后台轮询任务
    script_dir = os.path.dirname(os.path.abspath(__file__))
    command = [
        sys.executable,
        os.path.join(script_dir, "consumption.py"),
        "poll",
        "--task-id",
        submit_res.message,
        "--output",
        output,
        "--session",
        session,
        "--metadata",
        metadata,
    ]
    logging.info(f"[tool] >>> {' '.join(command)}")
    subprocess.Popen(
        command,
        text=True,
        start_new_session=True,
        stdin=DEVNULL,
        stdout=DEVNULL,
        stderr=DEVNULL,
    )
    logging.info(f"轮询任务提交成功，任务 ID: {submit_res.message}")


def notice(jsession: dict, jmetadata: dict, msg: str):
    """通知成片任务完成"""
    command = [
        "openclaw",
        "agent",
        "--session-id",
        jsession["sessionId"],
        "-m",
        msg,
        "--deliver",
    ]  # type: ignore
    logging.info(f"[tool] >>> {' '.join(command)}")
    retcode = subprocess.call(command)
    logging.info(f"[tool] >>> retcode: {retcode}")


@main.command()
@click.option("--task-id", type=str, required=True, help="任务ID")
@click.option("--output", "-o", required=True, help="输出文件路径")
@click.option(
    "--session", required=True, type=str, help="当前会话的完整元数据（JSON格式）"
)
@click.option(
    "--metadata", required=True, type=str, help="当前消息的完整未修改元信息（JSON格式）"
)
def poll(task_id: str, output: str, session: str, metadata: str):
    jsession, jmetadata = check(session, metadata)
    for _ in range(2 * 60):
        time.sleep(30)
        result = api_query(task_id)
        if result.code == "1000":
            continue

        # 任务异常
        if result.code != "0":
            notice(
                jsession,
                jmetadata,
                f"任务{task_id}异常，错误码：{result.code}，错误信息：{result.message}。请根据SKILL的错误处理规范，建议用户下一步操作。",
            )
            return

        # success
        with open(output, "w") as f:
            f.write(result.message)
        notice(
            jsession,
            jmetadata,
            f"任务{task_id}完成，输出结果已保存到{output}。根据[消费成片指南](references/消费成片指南.md)，告知用户成片结果。",
        )
        return

    notice(
        jsession,
        jmetadata,
        f"任务{task_id}轮询时间超过最大限制，建议稍后主动查询任务状态～",
    )


if __name__ == "__main__":
    main()