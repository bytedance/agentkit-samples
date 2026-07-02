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
TOS media upload — aligned with the official VodService.upload_tob behaviour.

Handles the binary upload step between ApplyUploadInfo and CommitUploadInfo:
  1. VPC pre-signed path  (vpc direct / vpc part)
  2. Candidate upload addresses  (main → backup → fallback)
  3. Default UploadAddress fallback

Small files (< chunk_size) use direct PUT; larger files use chunked upload
(init → upload parts → merge).
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Callable, Dict, List, Optional, Tuple
from zlib import crc32

import requests

MIN_CHUNK_SIZE = 1024 * 1024 * 20  # 20 MiB
DEFAULT_CONNECT_TIMEOUT = float(os.environ.get("TOS_UPLOAD_CONNECT_TIMEOUT", "5"))
DEFAULT_READ_TIMEOUT = float(os.environ.get("TOS_UPLOAD_READ_TIMEOUT", "600"))


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

class _FileSectionReader:
    """Readable wrapper over a slice of a file object (for chunked PUT)."""

    def __init__(self, fobj, size: int, init_offset: Optional[int] = None):
        self.fobj = fobj
        self.size = size
        self.offset = 0
        if init_offset is not None:
            self.fobj.seek(init_offset, os.SEEK_SET)

    def read(self, amt=None):
        if self.offset >= self.size:
            return b""
        if amt is None or amt < 0 or amt + self.offset >= self.size:
            data = self.fobj.read(self.size - self.offset)
            self.offset = self.size
            return data
        self.offset += amt
        return self.fobj.read(amt)

    @property
    def len(self) -> int:
        return self.size


def _norm_headers(raw: Any) -> Dict[str, str]:
    if isinstance(raw, dict):
        return {str(k): str(v) for k, v in raw.items()}
    return {}


def _retry(fn: Callable[[], Any], tries: int = 3, delay: float = 1.0, backoff: float = 2.0) -> Any:
    last_err: Optional[BaseException] = None
    d = delay
    for attempt in range(tries):
        try:
            return fn()
        except Exception as exc:
            last_err = exc
            if attempt == tries - 1:
                break
            time.sleep(d)
            d *= backoff
    assert last_err is not None
    raise last_err


# ---------------------------------------------------------------------------
# TOS uploader
# ---------------------------------------------------------------------------

class TosUploader:
    """PUT files to the TOS gateway using credentials returned by ApplyUploadInfo."""

    def __init__(
        self,
        session: Optional[requests.Session] = None,
        timeout: Tuple[float, float] = (DEFAULT_CONNECT_TIMEOUT, DEFAULT_READ_TIMEOUT),
    ):
        self._s = session or requests.Session()
        self._timeout = timeout

    # -- low-level helpers --------------------------------------------------

    def _put_file(self, url: str, path: str, headers: Dict[str, str]) -> Tuple[bool, bytes]:
        with open(path, "rb") as f:
            r = self._s.put(url, headers=headers, data=f, timeout=self._timeout)
        headers["X-Tt-Logid"] = r.headers.get("X-Tt-Logid", "")
        return r.status_code == 200, r.content

    def _put_data(self, url: str, data: Optional[bytes], headers: Dict[str, str]) -> Tuple[bool, bytes]:
        r = self._s.put(url, headers=headers, data=data, timeout=self._timeout)
        headers["X-Tt-Logid"] = r.headers.get("X-Tt-Logid", "")
        return r.status_code == 200, r.content

    def _storage_headers(self, headers: Dict[str, str], sc: int) -> None:
        if sc == 2:
            headers["X-Upload-Storage-Class"] = "archive"
        elif sc == 3:
            headers["X-Upload-Storage-Class"] = "ia"

    # -- direct upload (small files) ----------------------------------------

    def direct_upload(self, host: str, oid: str, auth: str, path: str, sc: int) -> None:
        def _once():
            with open(path, "rb") as f:
                data = f.read()
            crc = "%08x" % (crc32(data) & 0xFFFFFFFF)
            url = f"https://{host}/{oid}"
            hdrs: Dict[str, str] = {"Content-CRC32": crc, "Authorization": auth}
            self._storage_headers(hdrs, sc)
            ok, body = self._put_file(url, path, hdrs)
            text = body.decode()
            if not ok:
                raise RuntimeError(f"direct upload error: {text}, logid: {hdrs.get('X-Tt-Logid', '')}")
            j = json.loads(text)
            if j.get("success") not in (0,):
                raise RuntimeError(f"direct upload error: {text}, logid: {hdrs.get('X-Tt-Logid', '')}")
        _retry(_once)

    # -- chunked upload (large files) ---------------------------------------

    def _init_part(self, host: str, oid: str, auth: str, large: bool, sc: int) -> str:
        def _once():
            url = f"https://{host}/{oid}?uploads"
            hdrs: Dict[str, str] = {"Authorization": auth}
            if large:
                hdrs["X-Storage-Mode"] = "gateway"
            self._storage_headers(hdrs, sc)
            ok, body = self._put_data(url, None, hdrs)
            text = body.decode()
            if not ok:
                raise RuntimeError(f"init upload error: {text}")
            return json.loads(text)["payload"]["uploadID"]
        return _retry(_once)

    def _upload_part(self, host: str, oid: str, auth: str, uid: str,
                     pn: int, data: bytes, large: bool, sc: int) -> Tuple[str, Any]:
        def _once():
            url = f"https://{host}/{oid}?partNumber={pn}&uploadID={uid}"
            crc = "%08x" % (crc32(data) & 0xFFFFFFFF)
            hdrs: Dict[str, str] = {"Content-CRC32": crc, "Authorization": auth}
            if large:
                hdrs["X-Storage-Mode"] = "gateway"
            self._storage_headers(hdrs, sc)
            ok, body = self._put_data(url, data, hdrs)
            text = body.decode()
            if not ok:
                raise RuntimeError(f"upload part error: {text}")
            j = json.loads(text)
            if j.get("success") not in (0,):
                raise RuntimeError(f"upload part error: {text}")
            return crc, j["payload"]
        return _retry(_once)

    def _merge_parts(self, host: str, oid: str, auth: str, uid: str,
                     crcs: List[str], large: bool, sc: int, meta: Optional[Dict]) -> None:
        def _once():
            occ = ""
            if meta and meta.get("ObjectContentType"):
                occ = meta["ObjectContentType"]
            url = f"https://{host}/{oid}?uploadID={uid}&ObjectContentType={occ}"
            merge = ",".join(f"{i}:{crcs[i]}" for i in range(len(crcs)))
            hdrs: Dict[str, str] = {"Authorization": auth}
            if large:
                hdrs["X-Storage-Mode"] = "gateway"
            self._storage_headers(hdrs, sc)
            ok, body = self._put_data(url, merge.encode(), hdrs)
            text = body.decode()
            if not ok:
                raise RuntimeError(f"merge upload error: {text}")
            j = json.loads(text)
            if j.get("success") not in (0,):
                raise RuntimeError(f"merge upload error: {text}")
        _retry(_once)

    def chunk_upload(self, path: str, host: str, oid: str, auth: str,
                     size: int, large: bool, sc: int, chunk: int) -> None:
        uid = self._init_part(host, oid, auth, large, sc)
        n = size // chunk
        last = n - 1
        crcs: List[str] = []
        meta: Dict[str, Any] = {}
        with open(path, "rb") as f:
            for i in range(last):
                pn = i + 1 if large else i
                c, payload = self._upload_part(host, oid, auth, uid, pn, f.read(chunk), large, sc)
                if pn == 1:
                    meta = payload.get("meta") or {}
                crcs.append(c)
            if large:
                last = last + 1
            c, payload = self._upload_part(host, oid, auth, uid, last, f.read(), large, sc)
            if last == 1:
                meta = payload.get("meta") or {}
            crcs.append(c)
        self._merge_parts(host, oid, auth, uid, crcs, large, sc, meta)

    # -- VPC pre-signed paths -----------------------------------------------

    def vpc_upload(self, addr: Dict[str, Any], path: str, size: int) -> None:
        if addr.get("QuickCompleteMode") == "enable":
            return
        mode = addr.get("UploadMode") or ""
        if mode == "direct":
            put_url = addr.get("PutUrl") or ""
            put_hdrs = _norm_headers(addr.get("PutUrlHeaders"))
            with open(path, "rb") as f:
                r = self._s.put(put_url, headers=put_hdrs, data=f, timeout=self._timeout)
            if r.status_code != 200:
                raise RuntimeError(f"vpc put error, logId: {r.headers.get('x-tos-request-id', '')}")
        elif mode == "part":
            self._vpc_part_upload(addr.get("PartUploadInfo") or {}, path, size)

    def _vpc_part_upload(self, info: Dict[str, Any], path: str, size: int) -> None:
        chunk = int(info.get("PartSize") or 0)
        if chunk <= 0:
            raise RuntimeError("invalid PartSize for vpc part upload")
        urls = info.get("PartPutUrls") or []
        total = size // chunk
        if size % chunk == 0:
            total -= 1
        if len(urls) != total + 1:
            raise RuntimeError("mismatch part upload")
        offset = 0
        etags: List[str] = []
        with open(path, "rb") as f:
            for i in range(total):
                sr = _FileSectionReader(f, chunk, init_offset=offset)
                r = self._s.put(urls[i], data=sr, timeout=self._timeout)
                if r.status_code != 200:
                    raise RuntimeError(f"vpc part put error, logId: {r.headers.get('x-tos-request-id', '')}")
                etags.append(r.headers.get("ETag", ""))
                offset += chunk
            sr = _FileSectionReader(f, size - offset, init_offset=offset)
            r = self._s.put(urls[total], data=sr, timeout=self._timeout)
            if r.status_code != 200:
                raise RuntimeError(f"vpc part put error, logId: {r.headers.get('x-tos-request-id', '')}")
            etags.append(r.headers.get("ETag", ""))
        parts = ",".join(
            '{' + f'"PartNumber": {i + 1}, "ETag": {etags[i]}' + '}'
            for i in range(len(etags))
        )
        body = f'{{"Parts":[{parts}]}}'.encode()
        comp_url = info.get("CompletePartUrl") or ""
        comp_hdrs = _norm_headers(info.get("CompleteUrlHeaders"))
        r = self._s.post(comp_url, data=body, headers=comp_hdrs, timeout=self._timeout)
        if r.status_code != 200:
            raise RuntimeError(f"vpc post error, logId: {r.headers.get('x-tos-request-id', '')}")


# ---------------------------------------------------------------------------
# High-level: pick the best upload path from ApplyUploadInfo data
# ---------------------------------------------------------------------------

def upload_to_tos(
    data: Dict[str, Any],
    file_path: str,
    storage_class: int = 1,
    chunk_size: int = 0,
    log_fn: Callable[[str], None] = print,
) -> str:
    """
    Given the Result.Data from ApplyUploadInfo, upload *file_path* to TOS and
    return the SessionKey needed for CommitUploadInfo.
    """
    if not os.path.isfile(file_path):
        raise RuntimeError(f"file not found: {file_path}")
    if chunk_size < MIN_CHUNK_SIZE:
        chunk_size = MIN_CHUNK_SIZE
    fsize = os.path.getsize(file_path)
    uploader = TosUploader()

    # 1) VPC pre-signed
    vpc = data.get("VpcTosUploadAddress")
    if vpc and (vpc.get("UploadMode") or ""):
        sk = (data.get("UploadAddress") or {}).get("SessionKey") or ""
        uploader.vpc_upload(vpc, file_path, fsize)
        return sk

    # 2) Candidate addresses (main → backup → fallback)
    cand = data.get("CandidateUploadAddresses")
    addrs: List[Dict[str, Any]] = []
    if cand:
        addrs.extend(cand.get("MainUploadAddresses") or [])
        addrs.extend(cand.get("BackupUploadAddresses") or [])
        addrs.extend(cand.get("FallbackUploadAddresses") or [])
    if addrs:
        for addr in addrs:
            hosts = addr.get("UploadHosts") or []
            stores = addr.get("StoreInfos") or []
            if not hosts or not stores or not stores[0]:
                continue
            host = hosts[0]
            sk = addr.get("SessionKey") or ""
            auth = stores[0].get("Auth") or ""
            oid = stores[0].get("StoreUri") or ""
            try:
                if fsize < chunk_size:
                    uploader.direct_upload(host, oid, auth, file_path, storage_class)
                else:
                    uploader.chunk_upload(file_path, host, oid, auth, fsize, True, storage_class, chunk_size)
            except Exception as exc:
                log_fn(f"upload failed on {host}, switching host… ({exc})")
                continue
            return sk
        raise RuntimeError("upload failed on all candidate hosts")

    # 3) Default UploadAddress
    ua = data.get("UploadAddress") or {}
    stores = ua.get("StoreInfos") or []
    hosts = ua.get("UploadHosts") or []
    if not stores or not hosts:
        raise RuntimeError("ApplyUploadInfo: UploadAddress missing StoreInfos or UploadHosts")
    oid = stores[0].get("StoreUri") or ""
    sk = ua.get("SessionKey") or ""
    auth = stores[0].get("Auth") or ""
    host = hosts[0]
    if fsize < chunk_size:
        uploader.direct_upload(host, oid, auth, file_path, storage_class)
    else:
        uploader.chunk_upload(file_path, host, oid, auth, fsize, True, storage_class, chunk_size)
    return sk
