import os
import sys
import json
import logging
import subprocess
from subprocess import DEVNULL
import click
from base import Result, perror
from task import submit


@click.command()
@click.option("--storyboard", default=0, type=int, help="用于成片任务的故事板编号")
@click.option(
    "--session",
    required=True,
    type=str,
    help="当前Session的UUID，可用于openclaw agent指令的--session-id参数",
)
@click.option("--metadata", required=True, type=str, help="当前消息的完整未修改元信息")
@click.option("--input", required=True, type=str, help="故事板创作结果JSON文件路径")
@click.option("--output", required=True, type=str, help="输出结果所在的json文件路径")
def main(storyboard, session, metadata, input, output):
    """消费成片任务"""
    logging.info(f"[tool] >>> python3 {' '.join(sys.argv)}")

    with open(input, "r") as f:
        data = json.load(f)

    storyboards = data["storyboards"]
    if storyboard >= len(storyboards):
        perror(
            Result(
                code="-1",
                message=f"故事板编号超出范围，总故事板数为{len(storyboards)}, 请指定一个有效的故事板编号（1-{len(storyboards)}）",
            )
        )

    data["storyboard"] = storyboards[storyboard]
    data["storyboards"] = None

    submit_res = submit(2935355633875543, json.dumps(data, ensure_ascii=False))
    if submit_res.code != "0":
        perror(submit_res)
    print(submit_res.model_dump_json(), flush=True)

    ### 创建后台轮询任务
    workspace = os.path.dirname(os.path.abspath(__file__))
    metadata = json.loads(metadata)
    cmd = [
        "bash",
        "poll.sh",
        submit_res.message,
        output,
        session,
        metadata["channel"],
        metadata["chat_id"],
    ]
    process = subprocess.Popen(
        cmd,
        cwd=workspace,
        text=True,
        start_new_session=True,
        stdin=DEVNULL,
        stdout=DEVNULL,
        stderr=DEVNULL,
    )
    logging.info(f"[cron] >>> {submit_res.message} to {process.pid}")


if __name__ == "__main__":
    main()
