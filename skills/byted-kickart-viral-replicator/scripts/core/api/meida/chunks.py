# Copyright 2026 ByteDance
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


import json
import logging
import os
import sys
import time
import collections
from typing import Optional
from abc import ABC, abstractmethod
from typing import Dict, List, TypedDict
from urllib.parse import urlencode, urlparse

import jsonpath
import requests

# 动态加载项目根目录，以便于引入 utils
sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
from utils.hash import HashUtils
from utils.matriel import Matriel, ImageMatriel, VideoMatriel
from auth.strategy import AuthType, AuthStrategy


# ─── 类型定义 ──────────────────────────────────────────


class RangeDict(TypedDict):
    Start: int
    End: int


class UploadStateResult(TypedDict):
    SkipDataComplete: bool
    PartSize: int
    Ranges: List[RangeDict]


# ─── 配置管理 ──────────────────────────────────────────


class AppConfig:
    """全局配置管理"""

    REGION = "cn-north"
    VERSION = "2022-02-01"

    SERVICE_MUSE = "iccloud_muse"
    SERVICE_IAM = "ic_iam"

    POLL_MAX_ATTEMPTS = 60
    POLL_INTERVAL = 5

    IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "bmp", "webp", "tiff", "tif"}
    VIDEO_EXTENSIONS = {"mp4", "avi", "mov", "wmv", "flv", "mkv", "webm", "m4v", "3gp"}


# ─── API 客户端 ────────────────────────────────────────


class ApiClient(ABC):
    """处理与后端的 HTTP 交互"""

    def __init__(self, host: str):
        self.host = host

    def _check_resp(self, resp: dict, action: str):
        meta = resp.get("ResponseMetadata", {})
        error_obj = meta.get("Error")
        if error_obj:
            code = error_obj.get("Code") or error_obj.get("CodeN")
            msg = error_obj.get("Message", "")
            print(f"❌ {action} 失败: code={code}, msg={msg}")
            sys.exit(1)

        code = meta.get("Code")
        if code is not None and str(code) not in ("0", "Success", "200"):
            msg = meta.get("Message") or ""
            print(f"❌ {action} 失败: code={code}, msg={msg}")
            sys.exit(1)

    def request(
        self,
        action: str,
        service: str,
        body: Optional[dict] = None,
        extra_query: Optional[dict] = None,
    ) -> dict:
        extra_query = extra_query or {}
        body_bytes = json.dumps(body or {}, ensure_ascii=False).encode()
        payload_hash = HashUtils.hash_sha256(body_bytes).hex()

        url = self.build_url(self.host, action, extra_query)
        query_string = urlparse(url).query
        headers = self.build_headers(
            service, self.host, query_string, payload_hash, is_binary=False
        )

        logging.info(
            f"[http] <<< {headers} {json.dumps(body or {}, ensure_ascii=False)}"
        )
        resp = requests.post(url, data=body_bytes, headers=headers, timeout=30)
        logging.info(f"[http] <<< {resp.headers} {resp.text}")

        try:
            result = resp.json()
        except Exception:
            print(f"json parse error, resp is {resp.text}")
            sys.exit(1)

        self._check_resp(result, action)
        return result

    def request_binary(
        self, action: str, service: str, extra_query: dict, data: bytes
    ) -> dict:
        payload_hash = HashUtils.hash_sha256(data).hex()
        url = self.build_url(self.host, action, extra_query)
        query_string = urlparse(url).query
        headers = self.build_headers(
            service, self.host, query_string, payload_hash, is_binary=True
        )

        resp = requests.post(url, data=data, headers=headers, timeout=60)
        try:
            result = resp.json()
        except Exception:
            print(f"json parse error, resp is {resp.text}")
            sys.exit(1)

        self._check_resp(result, action)
        return result

    @abstractmethod
    def build_headers(
        self,
        service: str,
        host: str,
        query_string: str,
        payload_hash: str,
        is_binary: bool,
    ) -> Dict[str, str]:
        pass

    @abstractmethod
    def build_url(self, host: str, action: str, extra_query: dict) -> str:
        pass


class ArkClawApiClient(ApiClient):
    def __init__(self):
        super().__init__(os.getenv("ARK_SKILL_API_BASE", ""))
        self.token = os.getenv("ARK_SKILL_API_KEY", "")

    def build_headers(
        self,
        service: str,
        host: str,
        query_string: str,
        payload_hash: str,
        is_binary: bool,
    ) -> Dict[str, str]:
        headers = collections.defaultdict(str)
        headers["ServiceName"] = service
        headers["Authorization"] = f"Bearer {self.token}"
        headers["Content-Type"] = (
            "application/octet-stream" if is_binary else "application/json"
        )

        if ppe_env := os.getenv("X_VOLC_ENV"):
            headers.update(
                {"X-TT-Env": "ppe_volcengine", "X-Volc-Env": ppe_env, "X-Use-Ppe": "1"}
            )
        return headers

    def build_url(self, host: str, action: str, extra_query: dict) -> str:
        url = f"{host}/?Action={action}&Version={AppConfig.VERSION}"
        if extra_query:
            url += "&" + urlencode(extra_query)
        return url


class AkSkApiClient(ApiClient):
    def __init__(self):
        super().__init__("https://icp.volcengineapi.com")
        self.ak = os.getenv("ACCESS_KEY_ID", "")
        self.sk = os.getenv("SECRET_ACCESS_KEY", "")

    def build_headers(
        self,
        service: str,
        host: str,
        query_string: str,
        payload_hash: str,
        is_binary: bool,
    ) -> Dict[str, str]:
        date = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(time.time()))
        auth_date = date[:8]

        content_type = "application/octet-stream" if is_binary else "application/json"
        signed_headers = ["host", "x-date", "x-content-sha256", "content-type"]

        parsed_url = urlparse(host)
        host_name = parsed_url.netloc

        header_list = [
            f"host:{host_name}",
            f"x-date:{date}",
            f"x-content-sha256:{payload_hash}",
            f"content-type:{content_type}",
        ]
        header_string = "\n".join(header_list)

        canonical_string = "\n".join(
            [
                "POST",
                "/",
                query_string,
                f"{header_string}\n",
                ";".join(signed_headers),
                payload_hash,
            ]
        )
        hashed_canonical_string = HashUtils.hash_sha256(
            canonical_string.encode("utf-8")
        ).hex()

        credential_scope = f"{auth_date}/{AppConfig.REGION}/{service}/request"
        sign_string = "\n".join(
            ["HMAC-SHA256", date, credential_scope, hashed_canonical_string]
        )

        k_date = HashUtils.hmac_sha256(self.sk.encode("utf-8"), auth_date)
        k_region = HashUtils.hmac_sha256(k_date, AppConfig.REGION)
        k_service = HashUtils.hmac_sha256(k_region, service)
        signed_key = HashUtils.hmac_sha256(k_service, "request")

        signature = HashUtils.hmac_sha256(signed_key, sign_string).hex()
        authorization = (
            f"HMAC-SHA256 Credential={self.ak}/{credential_scope},"
            f" SignedHeaders={';'.join(signed_headers)},"
            f" Signature={signature}"
        )

        headers = collections.defaultdict(str)
        headers["X-Date"] = date
        headers["X-Content-Sha256"] = payload_hash
        headers["Content-Type"] = content_type
        headers["Authorization"] = authorization
        if ppe_env := os.getenv("X_VOLC_ENV"):
            headers.update(
                {"X-TT-Env": "ppe_volcengine", "X-Volc-Env": ppe_env, "X-Use-Ppe": "1"}
            )
        return headers

    def build_url(self, host: str, action: str, extra_query: dict) -> str:
        queries = extra_query.copy()
        queries["Action"] = action
        queries["Version"] = AppConfig.VERSION
        query_string = urlencode(sorted(queries.items())).replace("+", "%20")
        return f"{host}?{query_string}"


class ApiClientFactory:
    @staticmethod
    def create(strategy: AuthStrategy) -> ApiClient:
        if strategy.strategy == AuthType.API_KEY:
            return ArkClawApiClient()
        if strategy.strategy == AuthType.AK_SK:
            return AkSkApiClient()
        raise ValueError(f"不支持的认证策略类型: {strategy.strategy}")


# ─── 业务服务层 ────────────────────────────────────────


class IamService:
    def __init__(self, client: ApiClient):
        self.client = client

    def get_admin_user_id(self) -> int:
        result = self.client.request(
            action="ListUsers", service=AppConfig.SERVICE_IAM, body={"UserType": "All"}
        )
        users = result.get("Result", {}).get("Users", [])
        if not users:
            print("❌ 未获取到任何用户信息")
            sys.exit(1)

        for user in users:
            if user.get("IsAdmin") and user.get("Id"):
                return user.get("Id")
        return users[0].get("Id")


class MuseService:
    def __init__(self, client: ApiClient):
        self.client = client

    def get_upload_state(
        self, file_md5: str, file_size: int, file_crc32: int, owner_id: int
    ) -> UploadStateResult:
        body = {
            "Owner": {"Id": owner_id, "Type": "PERSON"},
            "Md5": file_md5,
            "Size": file_size,
            "Start": 0,
            "End": file_size - 1,
            "Crc": file_crc32,
        }
        result = self.client.request(
            action="GetUploadState", service=AppConfig.SERVICE_MUSE, body=body
        )
        raw_state = result.get("Result", {})
        return {
            "SkipDataComplete": bool(raw_state.get("SkipDataComplete", False)),
            "PartSize": int(raw_state.get("PartSize", 0)),
            "Ranges": raw_state.get("Ranges", []),
        }

    def upload_part(
        self, owner_id: int, chunk: bytes, offset: int, part_size: int, chunk_md5: str
    ) -> dict:
        query = {
            "Md5": chunk_md5,
            "Size": part_size,
            "Offset": offset,
            "OwnerId": owner_id,
            "OwnerType": "PERSON",
        }
        return self.client.request_binary(
            "StreamUploadData", AppConfig.SERVICE_MUSE, query, chunk
        )

    def create_material(
        self,
        file_md5: str,
        file_size: int,
        file_name: str,
        file_ext: str,
        skip_data_complete: bool,
        owner_id: int,
        owner_type: str,
        title: str,
        category: str,
    ) -> str:
        body = {
            "Owner": {"Id": owner_id, "Type": "PERSON"},
            "StoreItem": {
                "Md5": file_md5,
                "Size": file_size,
                "SkipDataComplete": skip_data_complete,
                "Filename": file_name,
                "FileExtension": file_ext,
            },
            "CreateMaterialInfo": {
                "Visibility": 0,
                "Title": title,
                "MediaType": 1,
                "MediaFirstCategory": category,
                "Tags": [],
                "MediaExtension": file_ext,
            },
        }
        result = self.client.request(
            action="CreateMaterial", service=AppConfig.SERVICE_MUSE, body=body
        )
        return result.get("Result", {}).get("MediaId")

    def poll_media_info(self, media_id: str, owner_id: int, owner_type: str) -> dict:
        for _ in range(AppConfig.POLL_MAX_ATTEMPTS):
            result = self.client.request(
                action="GetMediaInfo",
                service=AppConfig.SERVICE_MUSE,
                body={"MediaIds": [media_id], "MediaType": 1},
            )
            media_infos = result.get("Result", {}).get("MediaInfos", [])
            if media_infos:
                media_info = media_infos[0]
                status = media_info.get("BasicInfo", {}).get("MediaStatus")
                if status >= 2:
                    return media_info
                if status in (1, 5):
                    print("❌ 处理失败")
                    sys.exit(1)
            time.sleep(AppConfig.POLL_INTERVAL)
        sys.exit(1)


class KickartMuseService:
    def __init__(self, client: ApiClient):
        self.client = client

    def poll_media_info(self, media_id: str, owner_id: int, owner_type: str) -> dict:
        for _ in range(AppConfig.POLL_MAX_ATTEMPTS):
            time.sleep(AppConfig.POLL_INTERVAL)
            result = self.client.request(
                action="GetMediaInfo",
                service=AppConfig.SERVICE_MUSE,
                body={"MediaIds": [media_id], "MediaType": 3},
            )
            media_infos = result.get("Result", {}).get("MediaInfos", [])
            if not media_infos:
                continue

            media_info = media_infos[0]
            status = media_info.get("BasicInfo", {}).get("MediaStatus")

            if status == 4:
                return media_info

            elif status == 5 or status == 1:
                print("❌ 处理失败")
                sys.exit(1)

        sys.exit(1)


# ─── 编排与格式化层 ────────────────────────────────────


class MaterialUploader:
    def __init__(self, client: ApiClient):
        self.iam = IamService(client)
        self.muse = MuseService(client)

    def stream_upload(
        self,
        file_path: str,
        file_md5: str,
        file_size: int,
        file_crc32: int,
        owner_id: int,
        state: UploadStateResult,
    ) -> UploadStateResult:
        if state["SkipDataComplete"]:
            return state

        with open(file_path, "rb") as f:
            data = f.read()

        offset = 0
        for _ in range(1000):
            if state["SkipDataComplete"]:
                break
            part_size = state.get("PartSize", 0)

            if part_size == 0:
                chunk, chunk_size = data, file_size
            else:
                chunk_size = (
                    part_size
                    if offset + part_size * 2 <= file_size
                    else file_size - offset
                )
                chunk = data[offset : offset + chunk_size]

            self.muse.upload_part(owner_id, chunk, offset, chunk_size, file_md5)
            offset += chunk_size
            state = self.muse.get_upload_state(
                file_md5, file_size, file_crc32, owner_id
            )

            if state["SkipDataComplete"] or not state["Ranges"] or offset >= file_size:
                return state
        return state


class MediaFormatter:
    @staticmethod
    def extract_url(media_info: dict) -> str:
        cat = media_info.get("BasicInfo", {}).get("MediaFirstCategory", "")
        if cat == "image":
            image_media = media_info.get("ImageMedia", {})
            if dl := image_media.get("DownloadUrl"):
                return dl
            for q in ["origin", "jpeg_1080p", "jpeg_480p"]:
                if url := image_media.get("TranscodeDownloadUrls", {}).get(q):
                    return url
        elif cat in ("video", "audio"):
            media = media_info.get("VideoMedia" if cat == "video" else "AudioMedia", {})
            if dl := media.get("DownloadUrl"):
                return dl
            if play := media.get("PlayInfo", []):
                return play[0].get("Url", "")
        return ""

    @staticmethod
    def simplify(media_info: dict) -> dict:
        # 保持原逻辑的 simplify
        cat = media_info.get("BasicInfo", {}).get("MediaFirstCategory", "")
        if cat == "image":
            im = media_info.get("ImageMedia", {})
            if dl := im.get("DownloadUrl"):
                im["DownloadUrl"] = dl
            for q in ["origin", "jpeg_1080p", "jpeg_480p"]:
                if url := im.get("TranscodeDownloadUrls", {}).get(q):
                    im["TranscodeDownloadUrls"][q] = url
        elif cat in ("video", "audio"):
            vm = media_info.get("VideoMedia" if cat == "video" else "AudioMedia", {})
            if dl := vm.get("DownloadUrl"):
                vm["DownloadUrl"] = dl
            if play := vm.get("PlayInfo", []):
                play[0]["Url"] = play[0].get("Url")
        return media_info

    @staticmethod
    def format(media_info: dict) -> Matriel:
        if jsonpath.jsonpath(media_info, "$.ImageMedia"):
            m = ImageMatriel(id="", type="image", url="", size=0, height=0, width=0)
            if v := jsonpath.jsonpath(media_info, "$.BasicInfo.MediaId"):
                m.id = v[0]
            if v := jsonpath.jsonpath(media_info, "$.ImageMedia.DownloadUrl"):
                m.url = v[0]
            if v := jsonpath.jsonpath(media_info, "$.ImageMedia.Width"):
                m.width = v[0]
            if v := jsonpath.jsonpath(media_info, "$.ImageMedia.Height"):
                m.height = v[0]
            return m
        elif jsonpath.jsonpath(media_info, "$.VideoMedia"):
            m = VideoMatriel(
                id="", type="video", url="", size=0, height=0, width=0, duration=0
            )
            if v := jsonpath.jsonpath(media_info, "$.BasicInfo.MediaId"):
                m.id = v[0]
            if v := jsonpath.jsonpath(media_info, "$.VideoMedia.DownloadUrl"):
                m.url = v[0]
            if v := jsonpath.jsonpath(media_info, "$.VideoMedia.MediaMetaInfo.Width"):
                m.width = v[0]
            if v := jsonpath.jsonpath(media_info, "$.VideoMedia.MediaMetaInfo.Height"):
                m.height = v[0]
            if v := jsonpath.jsonpath(
                media_info, "$.VideoMedia.MediaMetaInfo.Duration"
            ):
                m.duration = v[0] / 1000
            return m
        return Matriel(id="", type="", url="", size=0, height=0, width=0)
