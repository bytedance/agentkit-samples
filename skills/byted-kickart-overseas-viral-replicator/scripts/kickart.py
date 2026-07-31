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
import time
import json
import click
import requests
import collections
import subprocess
from enum import Enum
from typing import List
from pydantic import BaseModel, Field, model_validator, field_validator
from collections import defaultdict
from core import SkillException
import metrial as metrial

from core import initialize, token

logger = initialize()


class TaskStatus(Enum):
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class KickartException(SkillException):
    pass


class ViralReplicationReq(BaseModel):
    ref_video: str = Field(
        ..., description="Reference video URL, supports mp4/mov format"
    )
    product_url: str = Field(
        default="", description="Product URL, supports http/https format"
    )
    product_images: list = Field(
        default=[],
        description="Product image URL list, supports http/https format, maximum 10 images",
    )
    model_images: list = Field(
        default=[],
        description="Model image URL list, supports http/https format, maximum 3 images",
    )
    language: str = Field(
        default="en",
        description="Video language, affects voiceover, subtitles, etc. Supported values: zh (Chinese), en (English - British), en-us (English - American), pt-br (Portuguese - Brazil), ja (Japanese), es-mx (Spanish - Mexico), id (Indonesian), ms (Malay), tl (Filipino)",
    )
    ai_product_analysis: bool = Field(
        default=False, description="Enable AI product analysis, default False"
    )


class TaskInfo(BaseModel):
    task_id: str = Field(..., description="Task ID, Kickart task ID")
    task_status: TaskStatus = Field(
        default=TaskStatus.RUNNING,
        description="Task status, Kickart task status, default RUNNING",
    )
    payload: dict = Field(default={}, description="Task result, Kickart task result")


class TaskSaveReq(BaseModel):
    title: str = Field(..., description="Video/Image title, for kickart saas display")
    full_path: List[str] = Field(default=["3"])
    material_url: str = Field(
        ..., description="Material URL, must be http/https format"
    )
    media_first_category: str = Field(
        default="video", description="Media first category, default video"
    )
    media_type: int = Field(default=3, description="Media type, default 3")
    source_from: str = Field(
        default="ad_variations", description="Source from, default ad_variations"
    )


class TaskSaveResp(BaseModel):
    media_id: str = Field(..., description="Media ID, Kickart media ID")


class ViralReplicator:
    HOST = "https://kickart.bytepluses.com"

    def __init__(self, template_id: str):
        self.template_id = template_id

    def submit(self, params: ViralReplicationReq) -> TaskInfo:
        body = defaultdict()
        body["template_id"] = self.template_id
        body["payload"] = params.model_dump()

        headers = defaultdict()
        headers["x-muse-token"] = token()
        if ppe_env := os.getenv("X_VOLC_ENV"):
            headers["X-TT-Env"] = ppe_env
            headers["X-Use-Ppe"] = "1"

        url = self.HOST + "/openapi/ai_effect/submit/v2"

        logger.info(f"[request] >>> {url} {body}")
        response = requests.post(url, json=body, headers=headers)
        logger.info(
            f"[response] <<< {response.headers['X-Tt-Logid']} {response.status_code} {response.text}"
        )
        response.raise_for_status()

        response_data = response.json()
        if response_data["code"] != 0:
            KickartException.throw(str(response_data["code"]), response_data["message"])
        task_info = TaskInfo(task_id=response_data["data"]["task_id"])

        script_path = os.path.abspath(__file__)
        subprocess.Popen(
            [sys.executable, script_path, "watch", "--task-id", task_info.task_id],
            start_new_session=True,
            stdout=open(os.devnull, "w"),
            stderr=open(os.devnull, "w"),
            close_fds=True,
            cwd=os.path.dirname(script_path),
        )

        return task_info

    def monitor(self, task_info: TaskInfo) -> None:
        logger.info(f"[monitor] Start monitoring task: {task_info.task_id}")

        result = task_info
        for _ in range(120):
            time.sleep(30.0)
            result = self.query(task_info)
            if result.task_status == TaskStatus.RUNNING:
                continue
            if result.task_status == TaskStatus.SUCCESS:
                logger.info(
                    f"[monitor] Task {task_info.task_id} completed successfully"
                )
                break
            if result.task_status == TaskStatus.FAILED:
                logger.error(f"[monitor] Task {task_info.task_id} failed")
                sys.exit(1)

        self.save(
            TaskSaveReq(
                title=task_info.task_id,
                material_url=result.payload["result_url"],  # pyright: ignore[reportPossiblyUnboundVariable]
            )
        )

    def query(self, task_info: TaskInfo) -> TaskInfo:
        headers = defaultdict()
        headers["x-muse-token"] = token()
        if ppe_env := os.getenv("X_VOLC_ENV"):
            headers["X-TT-Env"] = ppe_env
            headers["X-Use-Ppe"] = "1"

        url = self.HOST + "/openapi/ai_effect/query/v2"
        body = task_info.model_dump(exclude=set(["task_status"]))

        logger.info(f"[request] >>> {url} {body}")
        response = requests.post(url, json=body, headers=headers)
        logger.info(f"[response] <<< {response.status_code} {response.text}")
        response.raise_for_status()

        response = response.json()

        if response["code"] == 1000:
            return TaskInfo(task_id=task_info.task_id, task_status=TaskStatus.RUNNING)
        if response["code"] != 0:
            KickartException.throw(str(response["code"]), response["message"])

        return TaskInfo(
            task_id=task_info.task_id,
            task_status=TaskStatus.SUCCESS,
            payload=response["data"]["payload"],
        )

    def save(self, params: TaskSaveReq) -> None:
        headers = defaultdict()
        headers["x-muse-token"] = token()
        if ppe_env := os.getenv("X_VOLC_ENV"):
            headers["X-TT-Env"] = ppe_env
            headers["X-Use-Ppe"] = "1"

        url = self.HOST + "/openapi/ai_effect/media/save_url"
        body = params.model_dump()
        logger.info(f"[request] >>> {url} {body}")
        response = requests.post(url, json=body, headers=headers)
        logger.info(
            f"[response] <<< {response.headers['X-Tt-Logid']} {response.status_code} {response.text}"
        )
        response.raise_for_status()

        response = response.json()
        if response["code"] != 0:
            KickartException.throw(str(response["code"]), response["message"])


@click.group()
def main():
    logger.info(f"[tool] >>> python3 {' '.join(sys.argv)}")


class KickartSubmitTask(BaseModel):
    ref_video: str = Field(
        ...,
        description="Reference video file path, supports mp4/mov format, must be a local file",
    )
    product_url: str = Field(
        default="", description="Product URL, supports http/https format"
    )
    product_images: list[str] = Field(
        default=[],
        max_length=10,
        description="Product image path list, must be local files, maximum 10 images",
    )
    model_images: list[str] = Field(
        default=[],
        max_length=3,
        description="Model image path list, must be local files, maximum 3 images",
    )
    language: str = Field(
        default="en",
        description="Video language, affects voiceover, subtitles, etc. Supported values: zh (Chinese), en (English - British), en-us (English - American), pt-br (Portuguese - Brazil), ja (Japanese), es-mx (Spanish - Mexico), id (Indonesian), ms (Malay), tl (Filipino)",
    )

    @field_validator("language")
    @classmethod
    def validate_language(cls, v):
        allowed_languages = {
            "zh",
            "en",
            "en-us",
            "pt-br",
            "ja",
            "es-mx",
            "id",
            "ms",
            "tl",
        }
        if v not in allowed_languages:
            raise ValueError(
                f"Invalid language value: {v}. Allowed values: {', '.join(sorted(allowed_languages))}"
            )
        return v

    @model_validator(mode="after")
    def check_product_info(self):
        if not self.product_url and not self.product_images:
            raise ValueError("Either product_url or product_images must be provided!")
        return self


@main.command()
@click.option("--params", type=json.loads, required=True)
def submit(params: dict):
    """Submit a replication task"""
    try:
        task = KickartSubmitTask(**params)
        body = collections.defaultdict()

        ctx = click.Context(metrial.main)
        body["ref_video"] = ctx.invoke(
            metrial.main.commands["pipeline"],
            names="upload,create,search",
            type="video",
            file=task.ref_video,
        )
        body["product_url"] = task.product_url
        body["product_images"] = [
            ctx.invoke(
                metrial.main.commands["pipeline"],
                names="upload,create,search",
                type="image",
                file=image,
            )
            for image in task.product_images
        ]
        body["model_images"] = [
            ctx.invoke(
                metrial.main.commands["pipeline"],
                names="upload,create,search",
                type="image",
                file=image,
            )
            for image in task.model_images
        ]
        body["language"] = task.language

        viral_replicator = ViralReplicator("247820305")
        response = viral_replicator.submit(ViralReplicationReq(**body))
        click.echo(response.model_dump_json())
        return response
    except SkillException as e:
        logger.error(f"[submit] Exception: {e}")
        click.echo(json.dumps({"code": e.code, "msg": str(e)}), err=True)
    except Exception as e:
        logger.error(f"[submit] Exception: {e}")
        click.echo(json.dumps({"code": "90999", "msg": str(e)}), err=True)
    sys.exit(1)


@main.command()
@click.option("--task-id", "--task_id", required=True, type=str, help="Task ID")
def query(task_id: str) -> TaskInfo:
    """Single query task status"""
    try:
        replicator = ViralReplicator("247820305")
        task_info = TaskInfo(task_id=task_id)
        response = replicator.query(task_info)
        click.echo(response.model_dump_json())
        return response
    except SkillException as e:
        logger.error(f"[query] Exception: {e}")
        click.echo(json.dumps({"code": e.code, "msg": str(e)}), err=True)
    except Exception as e:
        logger.error(f"[query] Exception: {e}")
        click.echo(json.dumps({"code": "90999", "msg": str(e)}), err=True)
    sys.exit(1)


@main.command("watch", hidden=True)
@click.option(
    "--task-id", "--task_id", required=True, type=str, help="Internal use only"
)
def watch(task_id: str) -> None:
    """Background watch task status until completion"""
    try:
        replicator = ViralReplicator("247820305")
        task_info = TaskInfo(task_id=task_id)
        replicator.monitor(task_info)
    except Exception:
        logger.error(
            f"[watch] Background watch failed for task {task_id}", exc_info=True
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
