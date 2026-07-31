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
import click
import requests
import collections
from typing import Optional, List, Any
from pydantic import BaseModel, Field
from metadata import MetadataExtractorFactory
from core import initialize, token, Metadata, SkillException

logger = initialize()


@click.group()
def main():
    logger.info(f"[tool] >>> python3 {' '.join(sys.argv)}")


class UploadData(BaseModel):
    app_id: str
    created_at: str
    created_by: str
    etag: str
    expires: str
    file_name: str
    id: str
    last_consume_rec_id: str
    name: str
    remote_name: str
    resource_set_name: str
    scene: str
    size: int
    status: str
    tenant_id: str
    updated_at: str
    updated_by: str


class UploadResponse(BaseModel):
    code: int
    data: UploadData
    message: str
    request_id: str


@main.command()
@click.option(
    "--file",
    required=True,
    type=str,
    help="Material absolute path, must be image or video file, and must be in local file system!",
)
def upload(file: str) -> UploadData:
    """Upload material"""

    # ======= Check file ========
    if not os.path.exists(file):
        SkillException.throw(
            "90400", f"File [{file}] not found! Please check the file path."
        )
    if not os.path.isfile(file):
        SkillException.throw(
            "90401", f"File [{file}] is not a file! Please check the file type."
        )

    try:
        metadata = MetadataExtractorFactory().extract(file)
        if "image" in metadata.mimetype:
            if metadata.mimetype not in ["image/jpeg", "image/png"]:
                SkillException.throw(
                    "90403",
                    f"Image file [{file}] is not a valid image file! File type must be jpeg or png. Current file type is {metadata.mimetype}.",
                )
            if metadata.size > 1024 * 1024 * 8:
                SkillException.throw(
                    "90404",
                    f"Image file [{file}] size must be less than or equal to 8MB. Current size is {metadata.size / 1024 / 1024} MB.",
                )
            if metadata.width < 480 or metadata.height < 480:
                SkillException.throw(
                    "90406",
                    f"Image file [{file}] resolution must be at least 480x480p. Current resolution is {metadata.width}x{metadata.height}.",
                )
            if metadata.width * metadata.height < 300 * 300:
                SkillException.throw(
                    "90408",
                    f"Image file [{file}] pixel count must be at least 300x300. Current pixel count is {metadata.width * metadata.height}.",
                )
            if metadata.width * metadata.height > 36000000:
                SkillException.throw(
                    "90409",
                    f"Image file [{file}] pixel count must be less than or equal to 36000000. Current pixel count is {metadata.width * metadata.height}.",
                )
            if min(metadata.width, metadata.height) < 300:
                SkillException.throw(
                    "90410",
                    f"Image file [{file}] minimum length  must be at least 300 pixels.",
                )
            if max(metadata.width, metadata.height) > 6000:
                SkillException.throw(
                    "90411",
                    f"Image file [{file}] maximum length  must be at most 6000 pixels.",
                )

        if "video" in metadata.mimetype:
            # Note: video/quicktime is the container format for both MP4 and MOV files
            # The filetype library detects the container format, so MP4 files may be identified as video/quicktime
            if metadata.mimetype not in ["video/mp4", "video/mov", "video/quicktime"]:
                SkillException.throw(
                    "90403",
                    f"Video file [{file}] is not a valid video file! File type must be mp4 or mov. Current file type is {metadata.mimetype}.",
                )
            if metadata.size > 50 * 1024 * 1024:
                SkillException.throw(
                    "90404",
                    f"Video file [{file}] size must be less than or equal to 50MB. Current size is {metadata.size / 1024 / 1024} MB.",
                )
            if metadata.duration < 5 or metadata.duration > 60:
                SkillException.throw(
                    "90405",
                    f"Video file [{file}] duration must be between 5 and 60 seconds. Current duration is {metadata.duration} seconds.",
                )
            if metadata.width < 480 or metadata.height < 480:
                SkillException.throw(
                    "90406",
                    f"Video file [{file}] resolution must be at least 480p. Current resolution is {metadata.width}x{metadata.height}.",
                )
            if metadata.width / metadata.height not in [
                9 / 16,
                16 / 9,
                3 / 4,
                4 / 3,
                1 / 1,
            ]:
                SkillException.throw(
                    "90407",
                    f"Video file [{file}] aspect ratio must be 9:16, 16:9, 3:4, 4:3, 1:1. Current aspect ratio is {metadata.width / metadata.height:.2f}",
                )
    finally:
        pass

    # ======= Upload file ========
    url = "https://kickart.bytepluses.com/api/storage/objects/-"

    query = collections.defaultdict(str)
    query["scene"] = "upload-material-cc"
    query["fast_upload"] = "false"
    query["file_name"] = os.path.basename(file)

    with open(file, "rb") as f:
        payload = f.read()

    headers = collections.defaultdict(str)
    headers["Content-Type"] = "application/octet-stream"
    headers["x-muse-token"] = token()
    if ppe_env := os.getenv("X_VOLC_ENV"):
        headers["X-TT-Env"] = "ppe_volcengine"
        headers["X-Volc-Env"] = ppe_env
        headers["X-Use-Ppe"] = "1"

    logger.info(f"[request] >>> {url} {query}")
    response = requests.request("PUT", url, headers=headers, data=payload, params=query)
    logger.info(
        f"[response] <<< {response.headers['X-Tt-Logid']} {response.status_code} {response.text}"
    )
    response.raise_for_status()

    response = UploadResponse(**response.json())
    if response.code != 0:
        SkillException.throw(str(response.code), response.message)
    return response.data


class CreateData(BaseModel):
    media_id: str = Field(alias="MediaId")
    media_store_id: str = Field(alias="MediaStoreID")


class CreateResponse(BaseModel):
    response_metadata: Metadata = Field(alias="ResponseMetadata")
    result: Optional[CreateData] = Field(default=None, alias="Result")


@main.command()
@click.option(
    "--type",
    required=True,
    type=click.Choice(["image", "video"]),
    help="Material type, must be image or video",
)
@click.option(
    "--data",
    required=True,
    type=json.loads,
    help="Material data, must be in JSON format, and must contain file_name, id, etag, size fields",
)
def create(type: str, data: dict) -> Optional[CreateData]:
    """Create material"""
    url = "http://ai.byteplus.com/api/kickart/asset/create_media"
    payload = json.dumps(
        {
            "MediaExtension": data["file_name"].split(".")[-1],
            "ResourceItem": {
                "StoreId": data["id"],
                "Md5": data["etag"],
                "Size": data["size"],
            },
            "ResourceType": type,
            "Title": data["file_name"],
            "Lang": "en",
        }
    )

    headers = collections.defaultdict(str)
    headers["x-muse-token"] = token()
    headers["x-muse-extra"] = '{"biz_id":"100000001"}'
    headers["Content-Type"] = "application/json"
    logger.info(f"[request] >>> {url} {payload}")
    response = requests.request("POST", url, headers=headers, data=payload)
    logger.info(
        f"[response] <<< {response.headers['X-Tt-Logid']}{response.status_code} {response.text}"
    )
    response.raise_for_status()

    response = CreateResponse(**response.json())
    if (
        response.response_metadata.error is not None
        and response.response_metadata.error.code_n != 0
    ):
        SkillException.throw(
            str(response.response_metadata.error.code_n),
            response.response_metadata.error.message,
        )

    return response.result


class CoverDownloadURL(BaseModel):
    key: str = Field(alias="Key")
    url: str = Field(alias="Url")


class DownloadURL(BaseModel):
    key: str = Field(alias="Key")
    url: str = Field(alias="Url")


class SourceInfo(BaseModel):
    width: Optional[int] = Field(default=None, alias="Width")
    height: Optional[int] = Field(default=None, alias="Height")
    md5: Optional[str] = Field(default=None, alias="Md5")
    size: Optional[int] = Field(default=None, alias="Size")


class TranscodeVideo(BaseModel):
    source_info: Optional[SourceInfo] = Field(default=None, alias="SourceInfo")


class StoreInfo(BaseModel):
    download_urls: Optional[List[DownloadURL]] = Field(
        default=None, alias="DownloadUrls"
    )
    format: Optional[str] = Field(default=None, alias="Format")
    width: Optional[int] = Field(default=None, alias="Width")
    height: Optional[int] = Field(default=None, alias="Height")
    md5: Optional[str] = Field(default=None, alias="Md5")
    mime: Optional[str] = Field(default=None, alias="Mime")
    size: Optional[int] = Field(default=None, alias="Size")
    source_path: Optional[str] = Field(default=None, alias="SourcePath")
    store_id: Optional[str] = Field(default=None, alias="StoreId")
    transcode_video: Optional[TranscodeVideo] = Field(
        default=None, alias="TranscodeVideo"
    )


class Media(BaseModel):
    aspect_ratio: Optional[str] = Field(default=None, alias="AspectRatio")
    cover: Optional[str] = Field(default=None, alias="Cover")
    cover_download_urls: Optional[List[CoverDownloadURL]] = Field(
        default=None, alias="CoverDownloadUrls"
    )
    create_account_id: Optional[str] = Field(default=None, alias="CreateAccountId")
    create_time: Optional[int] = Field(default=None, alias="CreateTime")
    create_user_id: Optional[str] = Field(default=None, alias="CreateUserId")
    extension: Optional[str] = Field(default=None, alias="Extension")
    media_id: Optional[str] = Field(default=None, alias="MediaId")
    modify_time: Optional[int] = Field(default=None, alias="ModifyTime")
    source_from: Optional[str] = Field(default=None, alias="SourceFrom")
    status: Optional[int] = Field(default=None, alias="Status")
    store_id: Optional[str] = Field(default=None, alias="StoreId")
    store_info: Optional[StoreInfo] = Field(default=None, alias="StoreInfo")
    title: Optional[str] = Field(default=None, alias="Title")
    type: Optional[str] = Field(default=None, alias="Type")


class SearchData(BaseModel):
    medias: List[Media] = Field(alias="Medias")


class SearchResponse(BaseModel):
    response_metadata: Metadata = Field(alias="ResponseMetadata")
    result: SearchData = Field(alias="Result")


@main.command()
@click.option(
    "--ids", required=True, type=str, help="Material media ids, from create command"
)
def search(ids: str):
    """Search material"""
    url = "http://ai.byteplus.com/api/kickart/asset/get_media"

    payload = json.dumps({"MediaIds": ids.split(","), "Lang": "en"})

    headers = collections.defaultdict(str)
    headers["x-muse-token"] = token()
    headers["x-muse-extra"] = '{"biz_id":"100000001"}'
    headers["Content-Type"] = "application/json"
    if ppe_env := os.getenv("X_VOLC_ENV"):
        headers["X-TT-Env"] = "ppe_volcengine"
        headers["X-Volc-Env"] = ppe_env
        headers["X-Use-Ppe"] = "1"

    logger.info(f"[request] >>> {url} {payload}")
    response = requests.request("POST", url, headers=headers, data=payload)
    logger.info(
        f"[response] <<< {response.headers['X-Tt-Logid']} {response.status_code} {response.text}"
    )
    response.raise_for_status()

    response = SearchResponse(**response.json())
    if (
        response.response_metadata.error is not None
        and response.response_metadata.error.code_n != 0
    ):
        SkillException.throw(
            response.response_metadata.error.code,
            response.response_metadata.error.message,
        )

    media = response.result.medias[0] if response.result.medias else None
    if not media or not media.store_info or not media.store_info.download_urls:
        raise ValueError("Media not found in response!")

    filtered_urls = filter(lambda x: x.key == "origin", media.store_info.download_urls)
    return next(filtered_urls).url if filtered_urls else None


@main.command()
@click.pass_context
@click.option(
    "--names",
    required=True,
    type=str,
    help="Commands, must be upload, create, search, and could be combined with comma",
)
@click.option(
    "--type",
    required=True,
    type=click.Choice(["video", "image"]),
    help="Material type, must be video or image",
)
@click.option(
    "--file",
    required=True,
    type=str,
    help="Material file path, must be video or image file, and must be a local file",
)
def pipeline(ctx: click.Context, names: str, type: str, file: str) -> Any:
    """Pipeline"""
    lastest = None
    for name in names.split(","):
        if name == "upload":
            lastest = ctx.invoke(upload, file=file)
        if name == "create":
            lastest = ctx.invoke(
                create, type=type, data=lastest and lastest.model_dump()
            )
        if name == "search":
            lastest = ctx.invoke(search, ids=lastest and lastest.media_id)

    return lastest


if __name__ == "__main__":
    main()
