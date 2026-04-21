import sys
import json
import logging
import click

from base import Result, perror
from task import submit, poll


@click.command()
@click.option("--input", required=True, type=str, help="创意分析结果JSON文件路径")
@click.option("--output", required=True, type=str, help="输出结果所在的json文件路径")
def main(input, output):
    """故事板创作"""
    logging.info(f"[tool] >>> python3 {' '.join(sys.argv)}")

    with open(input, "r") as f:
        creative = f.read()
    submit_res = submit(4337201517621323, creative)
    if submit_res.code != "0":
        perror(submit_res)
    print(f"提交任务成功，任务ID: {submit_res.message}", flush=True)

    poll_res = poll(submit_res.message)
    if poll_res.code != "0":
        perror(poll_res)
    with open(output, "w") as f:
        result = json.loads(poll_res.message)
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(Result(code="0", message=output).model_dump_json())


if __name__ == "__main__":
    main()
