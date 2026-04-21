#!/usr/bin/env python3
# Copyright (c) 2025 Beijing Volcano Engine Technology Co., Ltd. and/or its affiliates.
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

"""
VOD 本地上传 — 字节落 TOS 与官方 VodService.upload_tob 行为对齐。

模块结构（自上而下）：
  1. 常量（MIN_CHUNK_SIZE、存贮类型枚举）
  2. OpenAPI 响应 JSON：`raise_for_vod_response` / `result_data`
  3. `FileSectionReader`：VPC 场景分片读流
  4. `_retry` / `_normalize_headers`：与 SDK 一致的重试与 Header 映射
  5. `TosMediaUploader`：直传、分片（init/part/merge）、VPC direct/part/complete
  6. `upload_tob_from_apply_data`：VPC → 候选地址轮询 → 默认 UploadAddress

`ApplyUploadInfo` / `CommitUploadInfo` 仍由 `ApiManage` 经 `vod_transport`（SkillHub Bearer 或火山 HMAC）请求。
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

import requests
from zlib import crc32

# ---------------------------------------------------------------------------
# 与 VodService 对齐的常量
# ---------------------------------------------------------------------------

MIN_CHUNK_SIZE = 1024 * 1024 * 20

# volcengine.vod.models.business.vod_upload_pb2.StorageClassType
STORAGE_STANDARD = 1
STORAGE_ARCHIVE = 2
STORAGE_IA = 3

# ---------------------------------------------------------------------------
# OpenAPI JSON 辅助
# ---------------------------------------------------------------------------


def raise_for_vod_response(resp: Dict[str, Any]) -> None:
    meta = resp.get("ResponseMetadata") or {}
    err = meta.get("Error") or {}
    code = err.get("Code", "") or err.get("code", "")
    if code not in ("", None, 0, "0"):
        rid = meta.get("RequestId", "")
        raise RuntimeError(f"VOD API error: {err} request_id={rid}")


def result_data(resp: Dict[str, Any]) -> Dict[str, Any]:
    return (resp.get("Result") or {}).get("Data") or {}


# ---------------------------------------------------------------------------
# 与 VodService.helper.FileSectionReader 等价（VPC 分片上传读流）
# ---------------------------------------------------------------------------


class FileSectionReader:
    def __init__(
        self,
        file_object,
        size: int,
        init_offset: Optional[int] = None,
        can_reset: bool = False,
    ):
        self.file_object = file_object
        self.size = size
        self.offset = 0
        self.init_offset = init_offset
        self.can_reset = can_reset
        if init_offset is not None:
            self.file_object.seek(init_offset, os.SEEK_SET)

    def read(self, amt=None):
        if self.offset >= self.size:
            return b""

        if (amt is None or amt < 0) or (amt + self.offset >= self.size):
            data = self.file_object.read(self.size - self.offset)
            self.offset = self.size
            return data

        self.offset += amt
        return self.file_object.read(amt)

    @property
    def len(self) -> int:
        return self.size


def _normalize_headers(raw: Any) -> Dict[str, str]:
    if not raw:
        return {}
    if isinstance(raw, dict):
        return {str(k): str(v) for k, v in raw.items()}
    return {}


def _retry(
    fn: Callable[[], Any], tries: int = 3, delay: float = 1.0, backoff: float = 2.0
) -> Any:
    last_err: Optional[BaseException] = None
    d = delay
    for attempt in range(tries):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001 — 与 SDK retry 语义一致
            last_err = e
            if attempt == tries - 1:
                break
            time.sleep(d)
            d *= backoff
    assert last_err is not None
    raise last_err


# ---------------------------------------------------------------------------
# TOS 上传（对齐 VodService.direct_upload / chunk_upload / vpc_*）
# ---------------------------------------------------------------------------


class TosMediaUploader:
    """对 TOS 网关发起 PUT，使用 Apply 返回的 host / StoreUri / Auth 或 VPC 预签名 URL。"""

    def __init__(self, session: Optional[requests.Session] = None):
        self._session = session or requests.Session()

    def _put_file(
        self, url: str, file_path: str, headers: Dict[str, str]
    ) -> Tuple[bool, bytes]:
        with open(file_path, "rb") as f:
            resp = self._session.put(url, headers=headers, data=f)
        headers["X-Tt-Logid"] = resp.headers.get("X-Tt-Logid", "")
        if resp.status_code == 200:
            return True, resp.content
        return False, resp.content

    def _put_data(
        self, url: str, data: Optional[bytes], headers: Dict[str, str]
    ) -> Tuple[bool, bytes]:
        resp = self._session.put(url, headers=headers, data=data)
        headers["X-Tt-Logid"] = resp.headers.get("X-Tt-Logid", "")
        if resp.status_code == 200:
            return True, resp.content
        return False, resp.content

    def _storage_headers(self, headers: Dict[str, str], storage_class: int) -> None:
        if storage_class == STORAGE_ARCHIVE:
            headers["X-Upload-Storage-Class"] = "archive"
        if storage_class == STORAGE_IA:
            headers["X-Upload-Storage-Class"] = "ia"

    def direct_upload(
        self, host: str, oid: str, auth: str, file_path: str, storage_class: int
    ) -> None:
        def _once():
            with open(file_path, "rb") as f:
                data = f.read()
            check_sum = "%08x" % (crc32(data) & 0xFFFFFFFF)
            url = "https://{}/{}".format(host, oid)
            headers = {"Content-CRC32": check_sum, "Authorization": auth}
            self._storage_headers(headers, storage_class)
            upload_status, resp = self._put_file(url, file_path, headers)
            resp_text = resp.decode("utf-8")
            if not upload_status:
                raise RuntimeError(
                    "direct upload error: {}, logid: {}".format(
                        resp_text, headers.get("X-Tt-Logid", "")
                    )
                )
            body = json.loads(resp_text)
            if body.get("success") is None or body["success"] != 0:
                raise RuntimeError(
                    "direct upload error: {}, logid: {}".format(
                        resp_text, headers.get("X-Tt-Logid", "")
                    )
                )

        _retry(_once)

    def init_upload_part(
        self, host: str, oid: str, auth: str, is_large_file: bool, storage_class: int
    ) -> str:
        def _once():
            url = "https://{}/{}?uploads".format(host, oid)
            headers = {"Authorization": auth}
            if is_large_file:
                headers["X-Storage-Mode"] = "gateway"
            self._storage_headers(headers, storage_class)
            upload_status, resp = self._put_data(url, None, headers)
            resp_text = resp.decode("utf-8")
            if not upload_status:
                raise RuntimeError(
                    "init upload error: {}, logid: {}".format(
                        resp_text, headers.get("X-Tt-Logid", "")
                    )
                )
            body = json.loads(resp_text)
            if body.get("success") is None or body["success"] != 0:
                raise RuntimeError(
                    "init upload error: {}, logid: {}".format(
                        resp_text, headers.get("X-Tt-Logid", "")
                    )
                )
            return body["payload"]["uploadID"]

        return _retry(_once)

    def upload_part(
        self,
        host: str,
        oid: str,
        auth: str,
        upload_id: str,
        part_number: int,
        data: bytes,
        is_large_file: bool,
        storage_class: int,
    ) -> Tuple[str, Any]:
        def _once():
            url = "https://{}/{}?partNumber={}&uploadID={}".format(
                host, oid, part_number, upload_id
            )
            check_sum = "%08x" % (crc32(data) & 0xFFFFFFFF)
            headers = {"Content-CRC32": check_sum, "Authorization": auth}
            if is_large_file:
                headers["X-Storage-Mode"] = "gateway"
            self._storage_headers(headers, storage_class)
            upload_status, resp = self._put_data(url, data, headers)
            resp_text = resp.decode("utf-8")
            if not upload_status:
                raise RuntimeError(
                    "upload part error: {}, logid: {}".format(
                        resp_text, headers.get("X-Tt-Logid", "")
                    )
                )
            body = json.loads(resp_text)
            if body.get("success") is None or body["success"] != 0:
                raise RuntimeError(
                    "upload part error: {}, logid: {}".format(
                        resp_text, headers.get("X-Tt-Logid", "")
                    )
                )
            return check_sum, body["payload"]

        return _retry(_once)

    @staticmethod
    def generate_merge_body(check_sum_list: List[str]) -> str:
        if len(check_sum_list) == 0:
            raise RuntimeError("crc32 list empty")
        parts = [
            "{}:{}".format(i, check_sum_list[i]) for i in range(len(check_sum_list))
        ]
        return ",".join(parts)

    def upload_merge_part(
        self,
        host: str,
        oid: str,
        auth: str,
        upload_id: str,
        check_sum_list: List[str],
        is_large_file: bool,
        storage_class: int,
        meta: Optional[Dict[str, Any]],
    ) -> None:
        def _once():
            object_content_type = ""
            if meta is not None and meta.get("ObjectContentType") is not None:
                object_content_type = meta["ObjectContentType"]
            url = "https://{}/{}?uploadID={}&ObjectContentType={}".format(
                host, oid, upload_id, object_content_type
            )
            data = self.generate_merge_body(check_sum_list).encode("utf-8")
            headers = {"Authorization": auth}
            if is_large_file:
                headers["X-Storage-Mode"] = "gateway"
            self._storage_headers(headers, storage_class)
            upload_status, resp = self._put_data(url, data, headers)
            resp_text = resp.decode("utf-8")
            if not upload_status:
                raise RuntimeError(
                    "commit upload part error: {}, logid: {}".format(
                        resp_text, headers.get("X-Tt-Logid", "")
                    )
                )
            body = json.loads(resp_text)
            if body.get("success") is None or body["success"] != 0:
                raise RuntimeError(
                    "commit upload part error: {}, logid: {}".format(
                        resp_text, headers.get("X-Tt-Logid", "")
                    )
                )

        _retry(_once)

    def chunk_upload(
        self,
        file_path: str,
        host: str,
        oid: str,
        auth: str,
        size: int,
        is_large_file: bool,
        storage_class: int,
        chunk_size: int,
    ) -> None:
        upload_id = self.init_upload_part(host, oid, auth, is_large_file, storage_class)
        n = size // chunk_size
        last_num = n - 1
        parts: List[str] = []
        meta: Dict[str, Any] = {}
        with open(file_path, "rb") as f:
            for i in range(0, last_num):
                data = f.read(chunk_size)
                part_number = i
                if is_large_file:
                    part_number = i + 1
                part, payload = self.upload_part(
                    host,
                    oid,
                    auth,
                    upload_id,
                    part_number,
                    data,
                    is_large_file,
                    storage_class,
                )
                if part_number == 1:
                    meta = payload["meta"]
                parts.append(part)
            data = f.read()
            if is_large_file:
                last_num = last_num + 1
            part, payload = self.upload_part(
                host, oid, auth, upload_id, last_num, data, is_large_file, storage_class
            )
            if last_num == 1:
                meta = payload["meta"]
            parts.append(part)
        self.upload_merge_part(
            host, oid, auth, upload_id, parts, is_large_file, storage_class, meta
        )

    # --- VPC 预签名路径（对齐 VodService.vpc_*） ---

    def vpc_upload(
        self, vpc_upload_address: Dict[str, Any], file_path: str, file_size: int
    ) -> None:
        if vpc_upload_address.get("QuickCompleteMode") == "enable":
            return
        mode = vpc_upload_address.get("UploadMode") or ""
        if mode == "direct":
            put_url = vpc_upload_address.get("PutUrl") or ""
            put_headers = _normalize_headers(vpc_upload_address.get("PutUrlHeaders"))
            self.vpc_put(put_url, put_headers, file_path)
        elif mode == "part":
            self.vpc_part_upload(
                vpc_upload_address.get("PartUploadInfo") or {}, file_path, file_size
            )

    def vpc_put(
        self, put_url: str, put_headers: Dict[str, str], file_path: str
    ) -> None:
        with open(file_path, "rb") as f:
            resp = self._session.put(put_url, headers=put_headers, data=f)
        if resp.status_code != 200:
            log_id = resp.headers.get("x-tos-request-id", "")
            raise RuntimeError("vpc put error, logId: {}".format(log_id))

    def vpc_part_put(self, put_url: str, content) -> str:
        resp = self._session.put(put_url, data=content)
        if resp.status_code != 200:
            log_id = resp.headers.get("x-tos-request-id", "")
            raise RuntimeError("vpc part put error, logId: {}".format(log_id))
        return resp.headers.get("ETag", "")

    def vpc_post(self, post_url: str, data: bytes, headers: Dict[str, str]) -> None:
        resp = self._session.post(post_url, data=data, headers=headers)
        if resp.status_code != 200:
            log_id = resp.headers.get("x-tos-request-id", "")
            raise RuntimeError("vpc post error, logId: {}".format(log_id))

    def vpc_generate_body(self, etag_list: List[str]) -> str:
        if len(etag_list) == 0:
            raise RuntimeError("etag list empty")
        s = []
        for i in range(len(etag_list)):
            s.append(
                "{" + '"PartNumber": {}, "ETag": {}'.format(i + 1, etag_list[i]) + "}"
            )
        return '{"Parts":[' + ",".join(s) + "]}"

    def vpc_part_upload(
        self, part_upload_info: Dict[str, Any], file_path: str, file_size: int
    ) -> None:
        chunk_sz = int(part_upload_info.get("PartSize") or 0)
        part_put_urls = part_upload_info.get("PartPutUrls") or []
        total_num = file_size // chunk_sz
        if file_size % chunk_sz == 0:
            total_num -= 1
        if len(part_put_urls) != total_num + 1:
            raise RuntimeError("mismatch part upload")

        offset = 0
        etag_list: List[str] = []
        with open(file_path, "rb") as f:
            for i in range(0, total_num):
                put_url = part_put_urls[i]
                sr = FileSectionReader(f, chunk_sz, init_offset=offset, can_reset=True)
                etag = self.vpc_part_put(put_url, sr)
                etag_list.append(etag)
                offset += chunk_sz
            last_chunk_size = file_size - offset
            put_url = part_put_urls[total_num]
            sr = FileSectionReader(
                f, last_chunk_size, init_offset=offset, can_reset=True
            )
            etag = self.vpc_part_put(put_url, sr)
            etag_list.append(etag)

        post_data = self.vpc_generate_body(etag_list).encode("utf-8")
        complete_headers = _normalize_headers(
            part_upload_info.get("CompleteUrlHeaders")
        )
        complete_url = part_upload_info.get("CompletePartUrl") or ""
        self.vpc_post(complete_url, post_data, complete_headers)


# ---------------------------------------------------------------------------
# upload_tob：根据 ApplyUploadInfo 的 Data 选择线路并上传（对齐 VodService.upload_tob）
# ---------------------------------------------------------------------------


def upload_tob_from_apply_data(
    uploader: TosMediaUploader,
    data: Dict[str, Any],
    file_path: str,
    storage_class: int,
    chunk_size: int,
    log_print: Callable[[str], None] = print,
) -> str:
    if not os.path.isfile(file_path):
        raise RuntimeError("no such file on file path")
    if chunk_size < MIN_CHUNK_SIZE:
        chunk_size = MIN_CHUNK_SIZE
    file_size = os.path.getsize(file_path)

    vpc_upload_address = data.get("VpcTosUploadAddress")
    if vpc_upload_address:
        upload_address = data.get("UploadAddress") or {}
        session_key = upload_address.get("SessionKey") or ""
        if (vpc_upload_address.get("UploadMode") or "") != "":
            uploader.vpc_upload(vpc_upload_address, file_path, file_size)
            return session_key

    cand = data.get("CandidateUploadAddresses")
    all_addrs: List[Dict[str, Any]] = []
    if cand:
        all_addrs.extend(cand.get("MainUploadAddresses") or [])
        all_addrs.extend(cand.get("BackupUploadAddresses") or [])
        all_addrs.extend(cand.get("FallbackUploadAddresses") or [])

    if len(all_addrs) > 0:
        file_size = os.path.getsize(file_path)
        for upload_address in all_addrs:
            hosts = upload_address.get("UploadHosts") or []
            store_infos = upload_address.get("StoreInfos") or []
            if len(hosts) == 0 or len(store_infos) == 0 or not store_infos[0]:
                continue
            tos_host = hosts[0]
            session_key = upload_address.get("SessionKey") or ""
            auth = store_infos[0].get("Auth") or ""
            oid = store_infos[0].get("StoreUri") or ""
            try:
                if file_size < chunk_size:
                    uploader.direct_upload(
                        tos_host, oid, auth, file_path, storage_class
                    )
                else:
                    uploader.chunk_upload(
                        file_path,
                        tos_host,
                        oid,
                        auth,
                        file_size,
                        True,
                        storage_class,
                        chunk_size,
                    )
            except Exception as e:  # noqa: BLE001
                log_print("upload failed, switch host to retry.. reason: {}".format(e))
                continue
            return session_key
        raise RuntimeError("upload failed")

    upload_address = data.get("UploadAddress") or {}
    store_infos = upload_address.get("StoreInfos") or []
    hosts = upload_address.get("UploadHosts") or []
    if not store_infos or not hosts:
        raise RuntimeError(
            "ApplyUploadInfo: UploadAddress missing StoreInfos or UploadHosts"
        )
    oid = store_infos[0].get("StoreUri") or ""
    session_key = upload_address.get("SessionKey") or ""
    auth = store_infos[0].get("Auth") or ""
    host = hosts[0]
    file_size = os.path.getsize(file_path)
    if file_size < chunk_size:
        uploader.direct_upload(host, oid, auth, file_path, storage_class)
    else:
        uploader.chunk_upload(
            file_path, host, oid, auth, file_size, True, storage_class, chunk_size
        )
    return session_key
