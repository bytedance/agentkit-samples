import os
import sys
# 添加当前目录到Python路径，支持直接运行脚本
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import click
from core.api.iccp.service import IccpService

@click.command()
@click.option("--task-id", type=str, required=True, help="任务ID")
@click.option("--output", "-o", required=True, help="输出文件路径")
def main(task_id: str, output: str):
    iccp_service = IccpService()
    result = iccp_service.query(task_id)

    if result.code == "1000":
        click.echo(result.model_dump_json(), err=True)
        return

    # 任务异常
    if result.code != "0":
        click.echo(result.model_dump_json(), err=True)
        return

    # success
    with open(output, "w") as f:
        f.write(result.data) # type: ignore
    click.echo(result.model_dump_json())

if __name__ == "__main__":
    main()