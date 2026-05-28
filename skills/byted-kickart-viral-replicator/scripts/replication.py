import os
import sys
# 添加当前目录到Python路径，支持直接运行脚本
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import json
import time
import subprocess
from subprocess import DEVNULL
import logging
import click
import math
import uuid
import jsonpath
import collections
from core.api.meida.media import SimpleMediaService, KickartUploader
from core import Result
from core.api.iccp.service import IccpService

def concat(analysis: str, ref_video_material: dict, character_image_materials: list, language: str) -> dict:
    material = collections.defaultdict()
    if analysis and os.path.exists(analysis):
        with open(analysis, "r", encoding="utf-8") as f:
            material["product_info"] = json.load(f)
    # import pdb; pdb.set_trace()
    material["language"] = language
    material["video_url"] = ref_video_material['url']
    material["video_duration"] = 1 + math.floor(ref_video_material['duration'])
    material["aspect_ratio"] = ref_video_material['closest_ratio']
    material["role_urls"] = [m["url"] for m in character_image_materials]
    # import pdb; pdb.set_trace()
    return material

@click.group()
def main():
    logging.info(f"[tool] >>> {' '.join(sys.argv)}")

@main.command()
@click.option("--ref-video", required=True, type=str, help="参考视频素材ID")
@click.option("--character-images", required=False, type=str, help="角色图素材ID，逗号分隔")
@click.option("--input", required=True, type=str, help="创意分析的输出文件")
@click.option("--output", required=True, type=str, help="输出结果路径")
@click.option("--session",required=True,type=str,help="当前会话的完整元数据（JSON格式）")
@click.option("--metadata", required=True, type=str, help="当前消息的完整未修改元信息（JSON格式）")
@click.option("--language", required=False, type=click.Choice(["zh", "en", "pt-br"]), default="zh", help="成片语种（如 zh, en, pt 等），默认 zh")
def replication(input, ref_video, character_images, output, session, metadata, language):
    """爆款裂变脚本入口"""
    media_service = SimpleMediaService()

    # 2. 处理参考视频
    click.echo(f"正在处理参考视频: {ref_video}")
    video_mat = media_service.get_media(ref_video)
    if not video_mat:
        click.echo(Result(code="-1", message=f"未找到参考视频素材ID: {ref_video}").model_dump_json(), err=True)
        exit(1)

    # 3. 处理角色图（可选）
    image_res_list = []
    if character_images:
        click.echo(f"正在处理角色图: {character_images}")

        image_sources = [src.strip() for src in character_images.split(',') if src.strip()]
        if len(image_sources) < 1 or len(image_sources) > 3:
            click.echo(Result(code="-1", message=f"角色图数量必须在 1-3 张之间，当前提供 {len(image_sources)} 张。").model_dump_json(), err=True)
            exit(1)
            
        for image_source in image_sources:
            img_mat = media_service.get_media(image_source)
            if not img_mat:
                click.echo(Result(code="-1", message=f"未找到角色图素材ID: {image_source}").model_dump_json(), err=True)
                exit(1)
            image_res_list.append(img_mat)
        
        image_id_str = ",".join([m["id"] for m in image_res_list])
        click.echo(f"角色图处理成功，媒资IDs: {image_id_str}")
        
    # 4. 调用后端服务，获取爆款裂变结果
    click.echo("正在提交裂变任务...")
    material = json.dumps(concat(input, video_mat, image_res_list, language), ensure_ascii=False)
    iccp_service = IccpService()
    submit_res = iccp_service.submit(126296066, material)
    # submit_res = Result(code="0", message="success", data="7644093348403249194")
    click.echo(submit_res.model_dump_json())
    if submit_res.code != "0": 
        exit(1)
    click.echo(f"提交任务成功，任务ID: {submit_res.data}")

    ### 提交后台轮询任务
    # 使用绝对路径确保后台进程能正确找到脚本
    script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), __file__))    
    command = ["python3", script_path, "poll", "--task-id", submit_res.data, "--output", output, "--session", session, "--metadata", metadata]
    logging.info(f"[tool] >>> {' '.join(command)}")
    subprocess.Popen(command, text=True, start_new_session=True, stdin=DEVNULL, stdout=DEVNULL, stderr=DEVNULL)
    click.echo(f"轮询任务提交成功，任务ID: {submit_res.data}")
 
def notice(jsession: dict, jmetadata: dict, msg: str):
    """通知成片任务完成"""
    command = ["openclaw", "agent", "--session-id", jsession["sessionId"], "-m", msg, "--deliver"] # type: ignore
    logging.info(f"[tool] >>> {' '.join(command)}")
    retcode = subprocess.call(command)
    logging.info(f"[tool] >>> retcode: {retcode}")


def check(session, metadata):
    jsession = json.loads(session)
    jmetadata = json.loads(metadata)
    if "sessionId" not in jsession:
        result = Result(code="A0101", message="会话元数据中缺少sessionId字段")
        click.echo(result.model_dump_json(), err=True); exit(1)
    try:
        # 尝试将输入字符串转换为UUID对象
        uuid_obj = uuid.UUID(jsession["sessionId"]) # type: ignore
        if str(uuid_obj) != jsession["sessionId"].lower(): # type: ignore
            result = Result(code="A0101", message="会话元数据中sessionId字段格式错误")
            click.echo(result.model_dump_json(), err=True); exit(1)
    except ValueError:
        result = Result(code="A0101", message="会话元数据中sessionId字段格式错误")
        click.echo(result.model_dump_json(), err=True); exit(1)

    if "chat_id" not in jmetadata:
        result = Result(code="A0102", message="消息元数据中缺少chat_id字段")
        click.echo(result.model_dump_json(), err=True); exit(1)
    if "channel" not in jmetadata:
        result = Result(code="A0102", message="消息元数据中缺少channel字段")
        click.echo(result.model_dump_json(), err=True); exit(1)
    return jsession, jmetadata

@main.command()
@click.option("--task-id", type=str, required=True, help="任务ID")
@click.option("--output", "-o", required=True, help="输出文件路径")
@click.option("--session",required=True,type=str,help="当前会话的完整元数据（JSON格式）")
@click.option("--metadata", required=True, type=str, help="当前消息的完整未修改元信息（JSON格式）")
def poll(task_id: str, output: str, session: str, metadata: str):
    try:
        os.makedirs(os.path.dirname(output), exist_ok=True)
        jsession, jmetadata = check(session, metadata)
        iccp_service = IccpService()
        kickart_uploader = KickartUploader(source="ad_variations")
        for _ in range(2 * 60):
            time.sleep(30)
            result = iccp_service.query(task_id)

            if result.code == "1000":
                continue

            # 任务异常
            if result.code != "0":
                notice(jsession, jmetadata, f"任务{task_id}异常，错误码：{result.code}，错误信息：{result.message}。请根据SKILL的错误处理规范，建议用户下一步操作。")
                return
            
            # 产物同步Saas平台
            data = json.loads(result.data) # type: ignore
            material = kickart_uploader.upload(data.get("video_url")) # type: ignore
            data["video_url"] = material.url

            # success
            with open(output, "w") as f:
                f.write(json.dumps(data, ensure_ascii=False)) # type: ignore

            notice(jsession, jmetadata, f"任务{task_id}完成，输出结果已保存到{output}。根据[爆款裂变指南](references/爆款裂变指南.md)，告知用户成片结果。")
            return
        
        notice(jsession, jmetadata, f"任务{task_id}轮询时间超过最大限制，建议稍后主动查询任务状态～")
    except Exception as e:
        logging.error(f"[tool] >>> poll task: {task_id} error: {str(e)}")
        
if __name__ == "__main__":
    main()