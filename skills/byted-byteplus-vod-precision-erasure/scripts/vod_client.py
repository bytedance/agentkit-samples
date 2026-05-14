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
vod_client.py — shared VOD transport layer and utility helpers

Authentication:
  - Direct OpenAPI HMAC-SHA256
    - Preferred env: BYTEPLUS_ACCESSKEY + BYTEPLUS_SECRETKEY
    - Backward-compatible env: VOLCENGINE_ACCESS_KEY + VOLCENGINE_SECRET_KEY
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import sys
import time
from datetime import datetime, timedelta, timezone
from functools import reduce
from pathlib import Path
from typing import NoReturn
from urllib.parse import quote, urlencode

import requests
from dotenv import load_dotenv

# ── .env loading ───────────────────────────────────────────────────────────
# Look for .env in the current working directory first, then in the script's
# own directory (so the skill still works when invoked from elsewhere).
_SCRIPT_DIR = Path(__file__).resolve().parent
for _base in (Path.cwd(), _SCRIPT_DIR):
    _env = _base / ".env"
    if _env.is_file():
        load_dotenv(_env, override=False)
        break

# ── VOD host ───────────────────────────────────────────────────────────────
# Defaults to the BytePlus (overseas) endpoint. Set VOD_HOST to override,
# e.g. "vod.volcengineapi.com" for the Volcengine (mainland China) endpoint.
_VOD_HOST = (os.environ.get("VOD_HOST") or "vod.byteplusapi.com").strip()

_HTTP_TIMEOUT = float(os.environ.get("VOD_HTTP_TIMEOUT", "20"))


# ══════════════════════════════════════════════════════════════════════════
# Output helpers
# ══════════════════════════════════════════════════════════════════════════

def out(data: dict):
    """Print the result as JSON to stdout."""
    print(json.dumps(data, ensure_ascii=False), flush=True)


def log(msg: str):
    """Write a debug message to stderr."""
    print(f"[byted-byteplus-vod-precision-erasure] {msg}", file=sys.stderr, flush=True)


def bail(msg: str) -> NoReturn:
    """Print an error JSON and exit."""
    out({"error": msg})
    sys.exit(1)


# ══════════════════════════════════════════════════════════════════════════
# Volcengine OpenAPI client (HMAC-SHA256 signing)
# ══════════════════════════════════════════════════════════════════════════

class VolcClient:
    _REGION = (os.environ.get("VOD_REGION") or "ap-southeast-1").strip()
    _SERVICE = "vod"

    def __init__(self, ak: str, sk: str):
        self._ak = ak
        self._sk = sk

    def post(self, action: str, version: str, body: dict) -> dict:
        body_str = json.dumps(body, ensure_ascii=False)
        url, headers = self._sign("POST", action, version, {}, body_str)
        r = requests.post(url, headers=headers, data=body_str.encode(), timeout=_HTTP_TIMEOUT)
        self._check(r)
        return r.json()

    def get(self, action: str, version: str, params: dict) -> dict:
        url, headers = self._sign("GET", action, version, params or {}, "")
        r = requests.get(url, headers=headers, timeout=_HTTP_TIMEOUT)
        self._check(r)
        return r.json()

    def _sign(self, method: str, action: str, version: str,
              query_extra: dict, body_str: str) -> tuple[str, dict]:
        qp = {"Action": action, "Version": version}
        qp.update(query_extra)
        canonical_query = urlencode(sorted(qp.items()), quote_via=quote, safe="-_.~")
        url = f"https://{_VOD_HOST}/?{canonical_query}"

        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        body_hash = hashlib.sha256(body_str.encode()).hexdigest()

        h = {
            "content-type": "application/json; charset=utf-8",
            "host": _VOD_HOST,
            "x-content-sha256": body_hash,
            "x-date": ts,
        }
        signed_keys = sorted(h.keys())
        canonical_headers = "".join(f"{k}:{h[k]}\n" for k in signed_keys)
        signed_headers_str = ";".join(signed_keys)
        canonical_request = (
            f"{method}\n/\n{canonical_query}\n"
            f"{canonical_headers}\n{signed_headers_str}\n{body_hash}"
        )

        credential_scope = f"{ts[:8]}/{self._REGION}/{self._SERVICE}/request"
        string_to_sign = (
            f"HMAC-SHA256\n{ts}\n{credential_scope}\n"
            f"{hashlib.sha256(canonical_request.encode()).hexdigest()}"
        )
        signing_key = reduce(
            lambda k, v: hmac.new(k, v.encode(), hashlib.sha256).digest(),
            [ts[:8], self._REGION, self._SERVICE, "request"],
            self._sk.encode(),
        )
        signature = hmac.new(signing_key, string_to_sign.encode(),
                             hashlib.sha256).hexdigest()

        headers = {k.title().replace("X-C", "X-c"): v for k, v in h.items()}
        headers["Authorization"] = (
            f"HMAC-SHA256 Credential={self._ak}/{credential_scope}, "
            f"SignedHeaders={signed_headers_str}, Signature={signature}"
        )
        return url, headers

    @staticmethod
    def _check(r):
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code}: {r.text}")


# ══════════════════════════════════════════════════════════════════════════
# Factory: pick a client based on environment variables
# ══════════════════════════════════════════════════════════════════════════

def get_client() -> VolcClient:
    """Build a direct OpenAPI client from environment variables."""
    ak = (os.environ.get("BYTEPLUS_ACCESSKEY") or "").strip() or (os.environ.get("VOLCENGINE_ACCESS_KEY") or "").strip()
    sk = (os.environ.get("BYTEPLUS_SECRETKEY") or "").strip() or (os.environ.get("VOLCENGINE_SECRET_KEY") or "").strip()
    if not (ak and sk):
        bail(
            "Missing credentials. Set BYTEPLUS_ACCESSKEY and BYTEPLUS_SECRETKEY "
            "(preferred) or VOLCENGINE_ACCESS_KEY and VOLCENGINE_SECRET_KEY "
            "(legacy) in the environment or in .env."
        )
    return VolcClient(ak, sk)


# ══════════════════════════════════════════════════════════════════════════
# Space name resolution
# ══════════════════════════════════════════════════════════════════════════

def get_space_name(argv_pos: int = 2) -> str:
    """Resolve space_name with priority: CLI argument > VOD_SPACE_NAME env."""
    if len(sys.argv) > argv_pos:
        v = sys.argv[argv_pos].strip()
        if v:
            return v
    sp = (os.environ.get("VOD_SPACE_NAME") or "").strip()
    if sp:
        return sp
    bail("VOD space name not specified: pass it as a CLI argument or set VOD_SPACE_NAME.")


# ══════════════════════════════════════════════════════════════════════════
# Media input builder (used by StartExecution)
# ══════════════════════════════════════════════════════════════════════════

def build_media_input(asset_type: str, asset_value: str, space_name: str) -> dict:
    """
    Build the Input field for StartExecution.

    asset_type: "Vid" or "DirectUrl"
    asset_value: the vid value (without the vid:// prefix) or the VOD FileName
    """
    if asset_type not in ("Vid", "DirectUrl"):
        bail(f"type must be Vid or DirectUrl, got: {asset_type!r}")
    if not asset_value:
        bail("media asset value must not be empty")
    if not space_name:
        bail("space_name must not be empty")

    # Strip protocol prefix
    value = asset_value
    if value.startswith("vid://"):
        value = value[len("vid://"):]
    elif value.startswith("directurl://"):
        value = value[len("directurl://"):]

    media_input: dict = {"Type": asset_type}
    if asset_type == "Vid":
        media_input["Vid"] = value
    else:
        media_input["DirectUrl"] = {"FileName": value, "SpaceName": space_name}
    return media_input


# ══════════════════════════════════════════════════════════════════════════
# Playback URL signing (turn a DirectUrl/FileName into an accessible URL)
# Reference: vod-media-kit/volcengine-ai-mediakit/scripts/api_manage.py
# ══════════════════════════════════════════════════════════════════════════

_VOD_ACTION_APPLY_UPLOAD_INFO = "ApplyUploadInfo"
_VOD_ACTION_COMMIT_UPLOAD_INFO = "CommitUploadInfo"
_VOD_ACTION_LIST_DOMAIN = "ListDomain"
_VOD_ACTION_DESCRIBE_DOMAIN_CONFIG = "DescribeDomainConfig"
_VOD_ACTION_GET_STORAGE_CONFIG = "GetStorageConfig"
_VOD_ACTION_GET_PLAY_INFO = "GetPlayInfo"
_VOD_ACTION_UPDATE_MEDIA_PUBLISH_STATUS = "UpdateMediaPublishStatus"

_VOD_VERSION = "2023-01-01"

_CACHE: dict = {"available_domains": {}, "storage_config": {}}


def _encode_path_str(s: str = "") -> str:
    return quote(s, safe="-_.~$&+,/:;=@")


def _encode_rfc3986_uri_component(s: str) -> str:
    return quote(s, safe=":/?&=%-_.~")


def _random_string(length: int) -> str:
    alphabet = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _parse_time(value):
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        except Exception:
            return None
    if isinstance(value, str):
        try:
            v = value.replace("Z", "+00:00") if "Z" in value else value
            return datetime.fromisoformat(v)
        except Exception:
            return None
    return None


def _is_https_available(certificate: dict) -> bool:
    if certificate and certificate.get("HttpsStatus") == "enable":
        exp = _parse_time(certificate.get("ExpiredAt"))
        if exp:
            return exp > datetime.now(timezone.utc)
    return False


def _get_domain_config(client: VolcClient, domain: str, space_name: str, domain_type: str = "play") -> dict:
    detail = client.get(
        _VOD_ACTION_DESCRIBE_DOMAIN_CONFIG,
        _VOD_VERSION,
        {"SpaceName": space_name, "Domain": domain, "DomainType": domain_type},
    )
    result = detail.get("Result", {}) if isinstance(detail, dict) else {}
    cdn_config = result.get("Config") or {}
    signed_url_auth_control = cdn_config.get("SignedUrlAuthControl") or {}
    signed_url_auth_rules = (signed_url_auth_control.get("SignedUrlAuth") or {}).get("SignedUrlAuthRules", [])
    if not signed_url_auth_rules:
        return {}
    signed_url_auth_action = (signed_url_auth_rules[0] or {}).get("SignedUrlAuthAction", {}) or {}
    base_domain = result.get("Domain", {}) or {}
    status = "enable" if base_domain.get("ConfigStatus") == "online" else base_domain.get("ConfigStatus")
    return {
        "AuthType": signed_url_auth_action.get("URLAuthType"),
        "AuthKey": signed_url_auth_action.get("MasterSecretKey")
        or signed_url_auth_action.get("BackupSecretKey")
        or "",
        "Status": status,
        "Domain": base_domain.get("Domain", ""),
    }


def _get_available_domain(client: VolcClient, space_name: str) -> list[dict]:
    cached = (_CACHE.get("available_domains") or {}).get(space_name) or []
    if cached:
        return cached

    offset = 0
    total = 1
    domain_list: list[dict] = []
    while offset < total:
        data = client.get(
            _VOD_ACTION_LIST_DOMAIN,
            _VOD_VERSION,
            {"SpaceName": space_name, "SourceStationType": 1, "DomainType": "play", "Offset": offset},
        )
        offset = int(data.get("Offset", 0) or 0)
        total = int(data.get("Total", 0) or 0)
        result = data.get("Result", {}) or {}
        instances = ((result.get("PlayInstanceInfo") or {}).get("ByteInstances") or [])
        for item in instances:
            domains = item.get("Domains") or []
            for domain in domains:
                d = dict(domain)
                d["SourceStationType"] = 1
                d["DomainType"] = "play"
                domain_list.append(d)

    domain_list = [d for d in domain_list if d.get("CdnStatus") == "enable"]
    enriched: list[dict] = []
    for d in domain_list:
        auth_info = _get_domain_config(client, d.get("Domain", ""), space_name, d.get("DomainType", "play"))
        d2 = dict(d)
        d2["AuthInfo"] = auth_info
        enriched.append(d2)

    available = [d for d in enriched if (not d.get("AuthInfo")) or ((d.get("AuthInfo") or {}).get("AuthType") == "typea")]
    _CACHE["available_domains"] = {**(_CACHE.get("available_domains") or {}), space_name: available}
    return available


def _gen_url(domain_obj: dict, path: str, expired_minutes: int) -> str:
    is_https = _is_https_available(domain_obj.get("Certificate") or {})
    file_name = f"/{path}"
    auth_info = domain_obj.get("AuthInfo") or {}
    if auth_info.get("AuthType") == "typea":
        expire_ts = int((datetime.now(timezone.utc) + timedelta(minutes=expired_minutes)).timestamp())
        rand_str = _random_string(16)
        key = auth_info.get("AuthKey") or ""
        md5_input = f"{_encode_path_str(file_name)}-{expire_ts}-{rand_str}-0-{key}".encode("utf-8")
        md5_str = hashlib.md5(md5_input).hexdigest()
        url = (
            f"{'https' if is_https else 'http'}://{domain_obj.get('Domain')}{file_name}"
            f"?auth_key={expire_ts}-{rand_str}-0-{md5_str}"
        )
        return _encode_rfc3986_uri_component(url)
    url = f"{'https' if is_https else 'http'}://{domain_obj.get('Domain')}{file_name}"
    return _encode_rfc3986_uri_component(url)


def _get_storage_config(client: VolcClient, space_name: str) -> dict:
    cached = (_CACHE.get("storage_config") or {}).get(space_name) or {}
    if cached:
        return cached
    reqs = client.get(_VOD_ACTION_GET_STORAGE_CONFIG, _VOD_VERSION, {"SpaceName": space_name})
    storage_config = reqs.get("Result") or {}
    _CACHE["storage_config"] = {**(_CACHE.get("storage_config") or {}), space_name: storage_config}
    return storage_config


def _gen_wild_url(storage_config: dict, file_name: str) -> str:
    file_path = f"/{file_name}"
    conf = storage_config.get("StorageUrlAuthConfig") or {}
    if (
        storage_config.get("StorageType") == "volc"
        and conf.get("Type") == "cdn_typea"
        and conf.get("Status") == "enable"
    ):
        type_a = conf.get("TypeAConfig") or {}
        expire_seconds = int(type_a.get("ExpireTime") or 0)
        expire_ts = int((datetime.now(timezone.utc) + timedelta(seconds=expire_seconds)).timestamp())
        rand_str = _random_string(16)
        key = type_a.get("MasterKey") or type_a.get("BackupKey") or ""
        md5_input = f"{_encode_path_str(file_path)}-{expire_ts}-{rand_str}-0-{key}".encode("utf-8")
        md5_str = hashlib.md5(md5_input).hexdigest()
        sig_arg = type_a.get("SignatureArgs") or "auth_key"
        signed = f"{storage_config.get('StorageHost')}{file_path}?{sig_arg}={expire_ts}-{rand_str}-0-{md5_str}&preview=1"
        return _encode_rfc3986_uri_component(signed)
    if storage_config.get("StorageType") == "volc" and conf.get("Status") == "disable":
        signed = f"{storage_config.get('StorageHost')}{file_path}?preview=1"
        return _encode_rfc3986_uri_component(signed)
    return ""


def get_play_url_by_filename(
    client: VolcClient,
    space_name: str,
    file_name: str,
    *,
    expired_minutes: int = 60,
) -> str:
    """
    Turn a DirectUrl/FileName into an accessible URL (possibly carrying typea auth params).

    Priority:
    1) env `VOD_PLAY_DOMAIN` (build the URL directly from this domain; use to force a specific domain)
    2) ListDomain + DescribeDomainConfig (obtain the CDN domain and auth rules)
    3) GetStorageConfig fallback (use StorageHost + optional cdn_typea)
    """
    if not file_name:
        return ""
    cleaned = file_name
    if cleaned.startswith("directurl://"):
        cleaned = cleaned[len("directurl://"):]

    forced_domain = (os.environ.get("VOD_PLAY_DOMAIN") or "").strip()
    if forced_domain:
        domain = forced_domain.rstrip("/")
        scheme = "https" if "://" not in domain else ""
        if scheme:
            domain = f"https://{domain}"
        return _encode_rfc3986_uri_component(f"{domain}/{cleaned.lstrip('/')}")

    try:
        available = _get_available_domain(client, space_name)
        if available:
            return _gen_url(available[0], cleaned.lstrip("/"), expired_minutes)
    except Exception as exc:
        log(f"Failed to fetch play domain; falling back to storage: {exc}")

    try:
        storage_config = _get_storage_config(client, space_name)
        return _gen_wild_url(storage_config, cleaned.lstrip("/"))
    except Exception as exc:
        log(f"Storage fallback signing failed: {exc}")
        return ""


# ══════════════════════════════════════════════════════════════════════════
# Local file upload: ApplyUploadInfo → TOS PUT → CommitUploadInfo
# Docs: https://docs.byteplus.com/en/byteplus-vod/reference/applyuploadinfo
#       https://docs.byteplus.com/en/byteplus-vod/reference/commituploadinfo
# ══════════════════════════════════════════════════════════════════════════

def apply_upload_info(client: VolcClient, space_name: str, *,
                      file_size: int, file_name: str, file_ext: str) -> dict:
    """
    Call ApplyUploadInfo and return Result.Data (contains UploadAddress, SessionKey, etc.).
    """
    resp = client.get(
        _VOD_ACTION_APPLY_UPLOAD_INFO,
        _VOD_VERSION,
        {
            "SpaceName": space_name,
            "FileSize": file_size,
            "FileType": "",
            "FileName": file_name,
            "FileExtension": file_ext,
            "StorageClass": 1,
            "NeedFallback": True,
        },
    )
    _raise_for_vod(resp)
    return ((resp.get("Result") or {}).get("Data")) or {}


def commit_upload_info(client: VolcClient, space_name: str, session_key: str) -> dict:
    """
    Call CommitUploadInfo and return Result.Data (contains Vid, SourceInfo, etc.).
    """
    resp = client.get(
        _VOD_ACTION_COMMIT_UPLOAD_INFO,
        _VOD_VERSION,
        {"SpaceName": space_name, "SessionKey": session_key},
    )
    _raise_for_vod(resp)
    return ((resp.get("Result") or {}).get("Data")) or {}


def _raise_for_vod(resp: dict) -> None:
    meta = resp.get("ResponseMetadata") or {}
    err = meta.get("Error") or {}
    code = err.get("Code", "") or err.get("code", "")
    if code not in ("", None, 0, "0"):
        rid = meta.get("RequestId", "")
        raise RuntimeError(f"VOD API error: {err} request_id={rid}")


# ══════════════════════════════════════════════════════════════════════════
# Publish + GetPlayInfo helpers
# ══════════════════════════════════════════════════════════════════════════

def _update_media_publish_status(client: VolcClient, vid: str, status: str = "Published") -> None:
    """
    Publish (or unpublish) a media asset.

    Docs: https://docs.byteplus.com/en/docs/byteplus-vod/reference-updatemediapublishstatus
    Required before GetPlayInfo will return a playable URL.
    """
    client.get(
        _VOD_ACTION_UPDATE_MEDIA_PUBLISH_STATUS,
        _VOD_VERSION,
        {"Vid": vid, "Status": status},
    )


def _get_play_info(client: VolcClient, vid: str) -> str:
    """
    Call GetPlayInfo once and return the first playable URL, or "" if none.

    Docs: https://docs.byteplus.com/en/docs/byteplus-vod/reference-getplayinfo
    Response shape: Result.PlayInfoList[*].{MainPlayUrl, BackupPlayUrl}.
    Ssl=1 requests HTTPS playback URLs.
    """
    resp = client.get(
        _VOD_ACTION_GET_PLAY_INFO,
        _VOD_VERSION,
        {"Vid": vid, "Ssl": "1"},
    )
    result = resp.get("Result", {}) if isinstance(resp, dict) else {}
    play_list = result.get("PlayInfoList") or []
    for entry in play_list:
        if not isinstance(entry, dict):
            continue
        url = entry.get("MainPlayUrl") or entry.get("BackupPlayUrl") or ""
        if url:
            return url
    return ""


def get_play_url_by_vid(client: VolcClient, vid: str) -> str:
    """
    Fetch a playable URL by Vid.

    Per the BytePlus docs, GetPlayInfo will only return URLs after the asset
    has been published. UpdateMediaPublishStatus is idempotent, so we always
    publish first and then query once:
      1. UpdateMediaPublishStatus(Published)
      2. GetPlayInfo
    """
    if not vid:
        return ""
    v = vid[len("vid://"):] if vid.startswith("vid://") else vid

    try:
        _update_media_publish_status(client, v, "Published")
    except Exception as exc:
        # Publishing failures are logged but not fatal — we still attempt
        # GetPlayInfo in case the asset was already Published.
        log(f"UpdateMediaPublishStatus failed (vid={v}): {exc}")
    else:
        # Small delay to let the publish propagate before querying.
        time.sleep(0.35)

    try:
        return _get_play_info(client, v)
    except Exception as exc:
        log(f"GetPlayInfo failed (vid={v}): {exc}")
        return ""
