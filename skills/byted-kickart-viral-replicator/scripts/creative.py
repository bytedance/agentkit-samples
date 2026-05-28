import sys
import os
# 添加当前目录到Python路径，支持直接运行脚本
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import json
import time
import logging
import click
from collections import defaultdict
from core import Result
from core.api.meida.media import SimpleMediaService
from core.api.iccp.service import IccpService

media_service = SimpleMediaService()
def concat(input, ids) -> dict:
    material = defaultdict()
    if input:
        with open(input, "r") as f:
            material = json.load(f)
    
    if ids:
        materials = [media_service.get_media(id.strip()) for id in ids.split(",")]
        material["user_images"] = [m for m in materials if m["type"] == "image"] # type: ignore
        material["user_videos"] = [m for m in materials if m["type"] == "video"] # type: ignore
    return material

@click.command()
@click.option("--input", type=str, help="素材分析结果JSON文件路径")
@click.option("--ids", type=str, help="参与分析的素材ID列表，多个ID用逗号分隔")
@click.option("--output", required=True, type=str, help="输出结果所在的json文件路径")
def main(input, ids, output):
    """创意分析工具，参考[创意分析指南](references/创意分析指南.md)"""
    logging.info(f"[tool] >>> python3 {' '.join(sys.argv)}")

    material = json.dumps(concat(input, ids), ensure_ascii=False)
    iccp_service = IccpService()
    submit_res = iccp_service.submit(13891330, material)
    click.echo(submit_res.model_dump_json())
    if submit_res.code != "0": exit(1)
    click.echo(f"提交任务成功，任务ID: {submit_res.data}")

    for _ in range(2 * 3):
        time.sleep(30)
        poll_res = iccp_service.query(submit_res.data) # type: ignore
        
        if poll_res.code == "1000":
            continue

        if poll_res.code != "0":
            click.echo(poll_res.model_dump_json(), err=True)
            exit(1)

        with open(output, "w") as f:
            result = json.loads(poll_res.data) # type: ignore
            result.pop("duration", None)
            result.pop("aspect_ratio", None)
            json.dump(result, f, ensure_ascii=False, indent=2)
        click.echo(Result(code="0", message=output).model_dump_json())
        click.echo(f"任务完成，结果已保存到 {output}")
        return

    click.echo(f"任务正在执行中，请通过任务ID:{submit_res.data}查询任务状态")

if __name__ == "__main__":
    main()