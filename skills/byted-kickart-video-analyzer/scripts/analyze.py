# MIT License
# 
# Copyright (c) 2026 ByteDance
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import click
import logging
import sys
import time
import json

import math

import jsonpath
from typing import Any
from core import Result
from core.api.iccp.service import IccpService
from core.api.meida.media import SimpleMediaService

def format_for_origin(data: dict) -> dict:
    """
    格式化数据为原始格式，仅保留指定字段
    
    保留字段：
    1. 视频链接、视频时长
    2. 商品名称、商品描述
    3. 分镜编号、开始/结束时间，镜头语言、镜头主体、营销意图、口播、旁白、BGM、花字&字幕
    
    Args:
        data: 输入的字典数据
        
    Returns:
        格式化后的字典数据
    """
    result = {}
    
    # 使用jsonpath提取字段，提取成功时返回列表，失败返回None
    def extract_field(path: str) -> Any:
        """使用jsonpath提取字段值"""
        value = jsonpath.jsonpath(data, path)
        return value[0] if (value and len(value) > 0) else None
    
    # 提取video_info，仅保留video_duration
    video_info = extract_field('$.video_info')
    video_info_copy = {}
    if video_info and isinstance(video_info, dict):
        video_info_copy['video_duration'] = video_info.get('video_duration', '')
    
    # 提取并清理shot_breakdown，只保留需要的字段
    shot_breakdown = extract_field('$.video_info.shot_breakdown')
    cleaned_shots = []
    if isinstance(shot_breakdown, list):
        for shot in shot_breakdown:
            if isinstance(shot, dict):
                cleaned_shot = {
                    'shot_number': shot.get('shot_number', ''),
                    'start_time': shot.get('start_time', ''),
                    'end_time': shot.get('end_time', ''),
                    'camera_language': shot.get('camera_language', ''),
                    'main_subject': shot.get('main_subject', ''),
                    'marketing_intent': shot.get('marketing_intent', ''),
                    'on_camera_speech': shot.get('on_camera_speech', ''),
                    'voiceover_text': shot.get('voiceover_text', ''),
                    'bgm': shot.get('bgm', ''),
                    'stickers': shot.get('stickers', ''),
                    'text_style': shot.get('text_style', '')
                }
                cleaned_shots.append(cleaned_shot)
    
    video_info_copy['shot_breakdown'] = cleaned_shots
    result['video_info'] = video_info_copy
    
    # 提取product_info，仅保留product_title和product_description
    product_info = extract_field('$.product_info')
    product_info_copy = {}
    if product_info and isinstance(product_info, dict):
        product_info_copy['product_title'] = product_info.get('product_title', '')
        product_info_copy['product_description'] = product_info.get('product_description', '')
    result['product_info'] = product_info_copy
    
    return result

def format_for_seedance(data: dict) -> dict:
    """
    格式化数据为Seedance格式，仅保留指定字段
    
    保留字段：
    1. 视频链接、视频时长
    2. 商品名称、商品描述
    3. 分镜编号、开始/结束时间，镜头语言、镜头主体、营销意图、口播、旁白、BGM、花字&字幕
    4. 全片级音频基调
    
    格式规范：
    - 台词: 需用 {} 包裹
    - 画外音、字幕语义: 可用 【】
    - 音乐: 需用 () 包裹
    - 音效: 需用 <> 包裹
    - 字幕: 需用 【】 包裹
    
    Args:
        data: 输入的字典数据
        
    Returns:
        格式化后的字典数据
    """
    result = {}
    
    # 使用jsonpath提取字段
    def extract_field(path: str) -> Any:
        """使用jsonpath提取字段值"""
        value = jsonpath.jsonpath(data, path)
        return value[0] if (value and len(value) > 0) else None
    
    # ===== 视频信息 =====
    result['video_duration'] = extract_field('$.video_info.video_duration') or ''
    
    # ===== 商品信息 =====
    product_info = extract_field('$.product_info')
    if product_info and isinstance(product_info, dict):
        result['product_title'] = product_info.get('product_title', '')
        result['product_description'] = product_info.get('product_description', '')
    
    # ===== 分镜信息 =====
    shot_breakdown = extract_field('$.video_info.shot_breakdown')
    shots = []
    
    if isinstance(shot_breakdown, list):
        for shot in shot_breakdown:
            if isinstance(shot, dict):
                # 按照Seedance格式规范格式化字段
                on_camera_speech = shot.get('on_camera_speech', '')
                voiceover_text = shot.get('voiceover_text', '')
                bgm = shot.get('bgm', '')
                stickers = shot.get('stickers', '')
                
                shots.append({
                    'shot_number': shot.get('shot_number', ''),
                    'start_time': shot.get('start_time', ''),
                    'end_time': shot.get('end_time', ''),
                    'camera_language': shot.get('camera_language', ''),
                    'main_subject': shot.get('main_subject', ''),
                    'marketing_intent': shot.get('marketing_intent', ''),
                    # 台词用 {} 包裹
                    'on_camera_speech': "{" + on_camera_speech + "}",
                    # 画外音用 【】 包裹
                    'voiceover_text': "【" + voiceover_text + "】",
                    # 音乐用 () 包裹
                    'bgm_music': "(" + bgm + ")",
                    # 音效用 <> 包裹
                    'bgm_sound_effect': "<" + bgm + ">",
                    # 字幕用 【】 包裹
                    'stickers': "【" + stickers + "】"
                })
    
    result['shots'] = shots
    
    # ===== 全片级音频基调 =====
    result['audio_tone'] = extract_field('$.video_info.audio_tone') or ''

    # ===== 音色参数 =====
    role_list = extract_field('$.scene_info.role_list')
    if role_list and isinstance(role_list, list):
        result['role_list'] = list(zip([role.get('id', '') for role in role_list], [role.get('vocal_attributes', '') for role in role_list]))
    
    return result

@click.command()
@click.option("--media-id", required=True, type=str, help="输入视频的媒资ID")
@click.option("--output", required=True, type=str, help="输出结果所在的json文件路径")
def main(media_id, output):
    """本地视频文件解析工具，提取视频文件的元数据信息"""
    logging.info(f"[tool] >>> python3 {' '.join(sys.argv)}")

    try:

        media_service = SimpleMediaService()
        material = media_service.get_media(media_id)

        body = json.dumps({
            "video_url": material["url"],
            "video_duration": 1 + math.floor(material["duration"])
        }, ensure_ascii=False)

        iccp_service = IccpService()
        submit_res = iccp_service.submit(115997442, body)
        click.echo(submit_res.model_dump_json())
        if submit_res.code != "0": exit(1)
        click.echo(f"提交任务成功，任务ID: {submit_res.data}")

        for _ in range(2 * 5):
            time.sleep(30)
            poll_res = iccp_service.query(submit_res.data) # type: ignore

            if poll_res.code == "1000": 
                continue
            if poll_res.code != "0": 
                click.echo(poll_res.model_dump_json(), err=True)
                exit(1)
            
            result = json.loads(poll_res.data) # type: ignore
            
            # 输出格式化后的JSON文件（原始格式）
            with open(output, "w") as f:
                cleaned_result = format_for_origin(result)
                json.dump(cleaned_result, f, ensure_ascii=False, indent=2)
            
            # 输出符合seedance格式的JSON文件
            seedance_output = output.replace('.json', '_seedance.json')
            with open(seedance_output, "w") as f:
                seedance_result = format_for_seedance(result)
                json.dump(seedance_result, f, ensure_ascii=False, indent=2)
            
            click.echo(Result(code="0", message="success", data={"output": output, "seedance_output": seedance_output}).model_dump_json())
            click.echo(f"任务完成，结果已保存到 {output} 和 {seedance_output}")
            return
        
        click.echo(f"任务正在执行中，请通过任务ID:{submit_res.data}查询任务状态")
    except Exception as e:
        click.echo(Result(code="-1", message=str(e)), err=True)
        exit(1)

if __name__ == "__main__":
    # main()
    with open("input/1.json", "r") as f:
        data = json.load(f)
        result = format_for_seedance(data)
        with open("output/1_seedance.json", "w") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)