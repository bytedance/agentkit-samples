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
import json
import time
import logging
import click

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.api.meida.media import SimpleMediaService, KickartUploader
from core import Result
from core.core import token, TokenException


VALID_TEMPLATE_IDS = {
    "604911874": "专业模式（2.0、720p）",
    "463631106": "进阶模式（2.0fast、720p）",
}


def build_request_body(
    ref_video_material: dict,
    role_images: list,
    location_images: list,
    language: str,
    game_name: str,
    prompt: str,
    template_id: str,
) -> dict:
    payload = {
        "ref_video": ref_video_material["url"],
        "role_images": [m["url"] for m in role_images],
        "language": language,
        "game_name": game_name,
    }

    if location_images:
        payload["location_images"] = [m["url"] for m in location_images]

    if prompt:
        payload["prompt"] = prompt

    return {
        "template_id": template_id,
        "payload": payload,
        "watermark": False,
    }


@click.group()
def main():
    logging.info(f"[tool] >>> {' '.join(sys.argv)}")


@main.command()
@click.option(
    "--ref-video",
    required=True,
    type=str,
    help="参考视频素材ID（MP4/MOV，>5s 且 ≤60s，≤50MB，≥480p）",
)
@click.option(
    "--role-images",
    required=True,
    type=str,
    help="角色图素材ID，逗号分隔（1-10张，JPEG/PNG，单张≤8MB，≥480p）",
)
@click.option(
    "--location-images",
    required=False,
    type=str,
    default="",
    help="场景参考图素材ID，逗号分隔（0-3张，JPEG/PNG，单张≤8MB，≥480p）",
)
@click.option(
    "--language",
    required=False,
    type=click.Choice(["zh", "en", "en-us", "pt-br", "ja", "es-mx", "id", "ms", "tl"]),
    default="zh",
    help="成片语种（zh, en, en-us, pt-br, ja, es-mx, id, ms, tl），默认 zh",
)
@click.option("--game-name", required=True, type=str, help="游戏名称，≤500 字符")
@click.option(
    "--prompt",
    required=False,
    type=str,
    default="",
    help="自定义创意策略/爆点描述，≤5000 字符（可选）",
)
@click.option(
    "--template-id",
    required=True,
    type=click.Choice(list(VALID_TEMPLATE_IDS.keys())),
    help="本次提交使用的模板ID，必须由用户明确输入。可选：604911874=专业模式（2.0、720p），463631106=进阶模式（2.0fast、720p）",
)
@click.option("--output", required=True, type=str, help="输出结果路径")
def replication(
    ref_video,
    role_images,
    location_images,
    language,
    game_name,
    prompt,
    template_id,
    output,
):
    media_service = SimpleMediaService()

    click.echo(f"正在处理参考视频: {ref_video}")
    video_mat = media_service.get_media(ref_video)
    if not video_mat:
        click.echo(
            Result(
                code="-1", message=f"未找到参考视频素材ID: {ref_video}"
            ).model_dump_json(),
            err=True,
        )
        exit(1)

    click.echo(f"正在处理角色图: {role_images}")
    role_image_sources = [src.strip() for src in role_images.split(",") if src.strip()]
    if len(role_image_sources) < 1 or len(role_image_sources) > 10:
        click.echo(
            Result(
                code="-1",
                message=f"角色图数量必须在 1-10 张之间，当前提供 {len(role_image_sources)} 张。",
            ).model_dump_json(),
            err=True,
        )
        exit(1)
    role_images_list = []
    for image_source in role_image_sources:
        img_mat = media_service.get_media(image_source)
        if not img_mat:
            click.echo(
                Result(
                    code="-1", message=f"未找到角色图素材ID: {image_source}"
                ).model_dump_json(),
                err=True,
            )
            exit(1)
        role_images_list.append(img_mat)
    click.echo(
        f"角色图处理成功，媒资IDs: {','.join([m['id'] for m in role_images_list])}"
    )

    location_images_list = []
    if location_images:
        click.echo(f"正在处理场景参考图: {location_images}")
        location_image_sources = [
            src.strip() for src in location_images.split(",") if src.strip()
        ]
        if len(location_image_sources) > 3:
            click.echo(
                Result(
                    code="-1",
                    message=f"场景参考图数量必须在 0-3 张之间，当前提供 {len(location_image_sources)} 张。",
                ).model_dump_json(),
                err=True,
            )
            exit(1)
        for image_source in location_image_sources:
            img_mat = media_service.get_media(image_source)
            if not img_mat:
                click.echo(
                    Result(
                        code="-1", message=f"未找到场景参考图素材ID: {image_source}"
                    ).model_dump_json(),
                    err=True,
                )
                exit(1)
            location_images_list.append(img_mat)
        click.echo(
            f"场景参考图处理成功，媒资IDs: {','.join([m['id'] for m in location_images_list])}"
        )

    if len(game_name) > 500:
        click.echo(
            Result(
                code="-1",
                message=f"game_name 长度不能超过 500 字符，当前 {len(game_name)}。",
            ).model_dump_json(),
            err=True,
        )
        exit(1)

    if prompt and len(prompt) > 5000:
        click.echo(
            Result(
                code="-1",
                message=f"prompt 长度不能超过 5000 字符，当前 {len(prompt)}。",
            ).model_dump_json(),
            err=True,
        )
        exit(1)

    click.echo("正在获取 x-muse-token...")
    try:
        x_muse_token = token()
    except TokenException as e:
        click.echo(
            Result(
                code="x01401", message=f"获取 x-muse-token 失败: {str(e)}"
            ).model_dump_json(),
            err=True,
        )
        exit(1)

    click.echo("正在构造请求体...")
    request_body = build_request_body(
        video_mat,
        role_images_list,
        location_images_list,
        language,
        game_name,
        prompt,
        template_id,
    )

    body_file = f"/tmp/kickart/request_body_{int(time.time())}.json"
    os.makedirs(os.path.dirname(body_file), exist_ok=True)
    with open(body_file, "w", encoding="utf-8") as f:
        json.dump(request_body, f, ensure_ascii=False, indent=2)

    click.echo(f"正在提交游戏视频复刻任务（template_id={template_id}）...")

    from core.api.call_api import ViralReplicator, TaskStatus, KickartException

    os.environ["X_MUSE_TOKEN"] = x_muse_token
    replicator = ViralReplicator(template_id=template_id)

    try:
        task_info = replicator.submit(request_body["payload"])
        click.echo(
            f"提交成功，task_id = {task_info.task_id}，本次调用的 template_id = {template_id}"
        )
    except KickartException as e:
        click.echo(
            Result(code=e.code, message=f"提交任务失败: {e.message}").model_dump_json(),
            err=True,
        )
        exit(1)
    except Exception as e:
        click.echo(
            Result(code="-1", message=f"提交任务异常: {str(e)}").model_dump_json(),
            err=True,
        )
        exit(1)

    click.echo("正在轮询任务结果...")
    poll_interval = 30
    max_wait = 3600
    deadline = time.time() + max_wait

    while time.time() < deadline:
        time.sleep(poll_interval)
        try:
            task_info = replicator.query(task_info)
        except KickartException as e:
            click.echo(
                Result(code=e.code, message=f"轮询失败: {e.message}").model_dump_json(),
                err=True,
            )
            exit(1)
        except Exception as e:
            click.echo(f"轮询异常: {str(e)}", err=True)
            continue

        if task_info.task_status == TaskStatus.SUCCESS:
            result_json = json.dumps(task_info.payload, ensure_ascii=False, indent=2)
            click.echo(f"任务成功，最终结果:\n{result_json}")

            import re

            match = re.search(r'"result_url":\s*"([^"]+)"', result_json)
            if match:
                video_url = match.group(1)
                click.echo(f"成片视频URL: {video_url}")

                kickart_uploader = KickartUploader(source="ad_variations")
                kickart_uploader.upload(video_url)

                os.makedirs(os.path.dirname(output), exist_ok=True)
                with open(output, "w", encoding="utf-8") as f:
                    json.dump(task_info.payload, f, ensure_ascii=False, indent=2)

                click.echo(
                    json.dumps(
                        {
                            "code": "0",
                            "message": output,
                            "task_id": task_info.task_id,
                            "template_id": template_id,
                        },
                        ensure_ascii=False,
                    )
                )
            else:
                click.echo(
                    Result(code="-1", message="未找到结果视频URL").model_dump_json(),
                    err=True,
                )
                exit(1)
            return

        if task_info.task_status == TaskStatus.FAILED:
            click.echo(
                Result(code="-1", message="任务执行失败").model_dump_json(), err=True
            )
            exit(1)

    click.echo(
        Result(
            code="-1",
            message=f"轮询超时（超过 {max_wait}s），任务ID: {task_info.task_id}，template_id: {template_id}",
        ).model_dump_json(),
        err=True,
    )
    exit(1)


if __name__ == "__main__":
    main()
