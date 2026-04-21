import sys
import json
import logging
import click
from collections import defaultdict

from media import media_list
from base import Result, perror
from task import submit, poll


def concat(input=None, session_id=None, duration=15, prompt="无人物出镜") -> dict:
    material = defaultdict()
    if input:
        with open(input, "r") as f:
            material = json.load(f)
    material["video_duration"] = duration
    material["user_prompt"] = prompt

    if session_id:
        # Create a namespace-like object for media.list
        materials = media_list(session_id)
        material["user_images"] = [m for m in materials if m["type"] == "image"]
        material["user_videos"] = [m for m in materials if m["type"] == "video"]
    return material


def check(duration) -> Result:
    if duration < 0 or duration > 60:
        return Result(code="-1", message="视频时长必须在0-60秒之间", data=None)
    return Result(code="0", message="success", data=None)


@click.command()
@click.option("--input", type=str, help="素材分析结果JSON文件路径")
@click.option("--session-id", type=str, help="已上传的远程素材列表对应的会话ID")
@click.option("--duration", default=15, type=int, help="自定义时长，默认15秒")
@click.option(
    "--prompt", default="无人物出镜", type=str, help="自定义提示，默认无人物出镜"
)
@click.option("--output", required=True, type=str, help="输出结果所在的json文件路径")
def main(input, session_id, duration, prompt, output):
    """创意分析服务"""
    logging.info(f"[tool] >>> python3 {' '.join(sys.argv)}")

    material = json.dumps(
        concat(input, session_id, duration, prompt), ensure_ascii=False
    )

    check_res = check(duration)
    if check_res.code != "0":
        perror(check_res)

    submit_res = submit(3339986037439799, material)
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
