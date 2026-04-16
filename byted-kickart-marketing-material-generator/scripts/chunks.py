#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能创作云 aPaaS 媒资上传完整流程脚本 (含 ListUsers 获取 Admin ID)

流程：
  0. ListUsers        — 查找角色为 admin 的用户，获取其 Uid 作为 owner-id
  1. GetUploadState   — 查询文件是否已上传（支持断点续传）
  2. StreamUploadData — 分片上传文件（支持并发、幂等）
  3. CreateMaterial   — 创建媒资，获取 MediaId
  4. GetMediaInfo     — 轮询媒资详情，获取处理状态
  5. 提取下载链接

用法：
  pip install requests
  # 使用 ArkClaw Token
  export ARKCLAW_TOKEN="your-token"
  python upload_material.py --host <host> --file /path/to/file.mp4 \
      --owner-type user --title "我的视频" --category video
  
  # 使用 AK/SK
  export ACCESS_KEY_ID="your-ak"
  export SECRET_ACCESS_KEY="your-sk"
  python upload_material.py --host <host> --file /path/to/file.mp4 \
      --owner-type user --title "我的视频" --category video
"""

import argparse
import hashlib
import json
import os
import sys
import time
import hmac
import jsonpath
from urllib.parse import urlencode, urlparse, parse_qs, urlunparse
from typing import List, TypedDict
from model import *

# ─── 类型定义 ──────────────────────────────────────────

class RangeDict(TypedDict):
    Start: int
    End: int

class UploadStateResult(TypedDict):
    SkipDataComplete: bool
    PartSize: int
    Ranges: List[RangeDict]

import requests

# ─── 全局常量 ──────────────────────────────────────────

# 从环境变量读取配置
ACCESS_KEY_ID = os.getenv("ACCESS_KEY_ID") or ""
SECRET_ACCESS_KEY = os.getenv("SECRET_ACCESS_KEY") or ""
ARKCLAW_TOKEN = os.getenv("ARK_SKILL_API_KEY") or ""

# 默认域名（ArkClaw 方式）
DEFAULT_HOST = os.getenv("ARK_SKILL_API_BASE") or ""
# AK/SK 方式的默认域名
DEFAULT_ICP_HOST = "https://icp.volcengineapi.com"

REGION = "cn-north"
VERSION = "2022-02-01"

# 不同接口可能属于不同的 Service
SERVICE_MUSE = "iccloud_muse"  # 媒资/任务相关
SERVICE_IAM = "ic_iam"         # 用户/权限相关

POLL_MAX_ATTEMPTS = 60  # 最多轮询 60 次
POLL_INTERVAL = 5        # 每次间隔 5 秒

# 文件类型与后缀映射
IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "bmp", "webp", "tiff", "tif"}
VIDEO_EXTENSIONS = {"mp4", "avi", "mov", "wmv", "flv", "mkv", "webm", "m4v", "3gp"}

# Debug 开关
DEBUG = False

def debug_print(*args, **kwargs):
    if DEBUG:
        print(*args, **kwargs)


# ─── AK/SK 鉴权函数（参考 icp.py）─────────────────────

def hmac_sha256(key: bytes, content: str) -> bytes:
    """HMAC-SHA256加密"""
    h = hmac.new(key, content.encode("utf-8"), hashlib.sha256)
    return h.digest()

def get_signed_key(secret_key: str, date: str, region: str, service: str) -> bytes:
    """生成签名密钥链"""
    k_date = hmac_sha256(secret_key.encode("utf-8"), date)
    k_region = hmac_sha256(k_date, region)
    k_service = hmac_sha256(k_region, service)
    k_signing = hmac_sha256(k_service, "request")
    return k_signing

def hash_sha256(data: bytes) -> bytes:
    """SHA256哈希"""
    h = hashlib.sha256()
    h.update(data)
    return h.digest()

# ─── 通用请求 ──────────────────────────────────────────

def _request_with_aksk(action: str, service: str, host: str | None, body: dict | None = None, extra_query: dict | None = None) -> dict:
    """使用 AK/SK 鉴权发起请求"""
    extra_query = extra_query or {}
    body_bytes = json.dumps(body or {}, ensure_ascii=False).encode()
    
    queries = extra_query.copy()
    queries["Action"] = action
    queries["Version"] = VERSION

    query_string = urlencode(sorted(queries.items()))
    query_string = query_string.replace("+", "%20")
    url = f"{host}?{query_string}"

    date = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(time.time()))
    auth_date = date[:8]

    payload = hash_sha256(body_bytes).hex()

    signed_headers = ["host", "x-date", "x-content-sha256", "content-type"]
    parsed_url = urlparse(host)
    host_name = parsed_url.netloc

    header_list = []
    for header in signed_headers:
        if header == "host":
            header_list.append(f"{header}:{host_name}")
        elif header == "x-date":
            header_list.append(f"{header}:{date}")
        elif header == "x-content-sha256":
            header_list.append(f"{header}:{payload}")
        elif header == "content-type":
            header_list.append(f"{header}:application/json")
    header_string = "\n".join(header_list)

    canonical_string = "\n".join(["POST", "/", query_string, f"{header_string}\n", ";".join(signed_headers), payload])
    hashed_canonical_string = hash_sha256(canonical_string.encode("utf-8")).hex()
    credential_scope = f"{auth_date}/{REGION}/{service}/request"
    sign_string = "\n".join(["HMAC-SHA256", date, credential_scope, hashed_canonical_string])
    signed_key = get_signed_key(SECRET_ACCESS_KEY, auth_date, REGION, service)
    signature = hmac_sha256(signed_key, sign_string).hex()
    authorization = (f"HMAC-SHA256 Credential={ACCESS_KEY_ID}/{credential_scope},"
                     f" SignedHeaders={';'.join(signed_headers)},"
                     f" Signature={signature}")

    headers = {
        "X-Date": date,
        "X-Content-Sha256": payload,
        "Content-Type": "application/json",
        "Authorization": authorization
    }

    debug_print(f"result is {url}")
    debug_print(f"headers is {headers}")
    debug_print(f"url is {url}, body is {body_bytes}")
    debug_print(f"canonical_string: {repr(canonical_string)}")
    debug_print(f"sign_string: {repr(sign_string)}")
    
    resp = requests.post(url, data=body_bytes, headers=headers, timeout=30)
    
    try:
        result = resp.json()
    except:
        print(f"json parse error, resp is {resp.text}")
        sys.exit(1)
    
    _check_resp(result, action)
    
    return result

def _request_with_arkclaw(action: str, service: str, host: str | None, arkclaw_token: str | None, body: dict | None, extra_query: dict | None) -> dict:
    """使用 ArkClaw Token 鉴权发起请求"""
    extra_query = extra_query or {}
    body_bytes = json.dumps(body or {}, ensure_ascii=False).encode()
    headers = {
        "ServiceName": service,
        "Authorization": f"Bearer {arkclaw_token}",
        "Content-Type": "application/json"
    }
    url = f"{host}/?Action={action}&Version={VERSION}"
    if extra_query:
        url += "&" + urlencode(extra_query)
    debug_print(f"result is {url}")
    debug_print(f"headers is {headers}")
    debug_print(f"url is {url}, body is {body_bytes}")
    resp = requests.post(url, data=body_bytes, headers=headers, timeout=30)
    
    try:
        result = resp.json()
    except:
        print(f"json parse error, resp is {resp.text}")
        sys.exit(1)
    
    _check_resp(result, action)
    
    return result

def _request_binary_with_arkclaw(action: str, service: str, host: str | None, arkclaw_token: str | None, extra_query: dict | None, data: bytes) -> dict:
    """使用 ArkClaw Token 鉴权发起二进制请求"""
    headers = {
        "ServiceName": service,
        "Authorization": f"Bearer {arkclaw_token}",
        "Content-Type": "application/octet-stream"
    }

    url = f"{host}/?Action={action}&Version={VERSION}"
    if extra_query:
        url += "&" + urlencode(extra_query)
    debug_print(f"url is {url}, data size is {len(data)}")
    resp = requests.post(url, data=data, headers=headers, timeout=60)
    
    try:
        result = resp.json()
    except:
        print(f"json parse error, resp is {resp.text}")
        sys.exit(1)
    
    _check_resp(result, action)
    
    return result

def _request_binary_with_aksk(action: str, service: str, host: str | None, extra_query: dict, data: bytes) -> dict:
    """使用 AK/SK 鉴权发起二进制请求"""
    queries = extra_query.copy()
    queries["Action"] = action
    queries["Version"] = VERSION

    query_string = urlencode(sorted(queries.items()))
    query_string = query_string.replace("+", "%20")
    url = f"{host}?{query_string}"

    date = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(time.time()))
    auth_date = date[:8]

    payload = hash_sha256(data).hex()

    signed_headers = ["host", "x-date", "x-content-sha256", "content-type"]
    parsed_url = urlparse(host)
    host_name = parsed_url.netloc

    header_list = []
    for header in signed_headers:
        if header == "host":
            header_list.append(f"{header}:{host_name}")
        elif header == "x-date":
            header_list.append(f"{header}:{date}")
        elif header == "x-content-sha256":
            header_list.append(f"{header}:{payload}")
        elif header == "content-type":
            header_list.append(f"{header}:application/octet-stream")
    header_string = "\n".join(header_list)

    canonical_string = "\n".join(["POST", "/", query_string, f"{header_string}\n", ";".join(signed_headers), payload])
    hashed_canonical_string = hash_sha256(canonical_string.encode("utf-8")).hex()
    credential_scope = f"{auth_date}/{REGION}/{service}/request"
    sign_string = "\n".join(["HMAC-SHA256", date, credential_scope, hashed_canonical_string])
    signed_key = get_signed_key(SECRET_ACCESS_KEY, auth_date, REGION, service)
    signature = hmac_sha256(signed_key, sign_string).hex()
    authorization = (f"HMAC-SHA256 Credential={ACCESS_KEY_ID}/{credential_scope},"
                     f" SignedHeaders={';'.join(signed_headers)},"
                     f" Signature={signature}")

    headers = {
        "X-Date": date,
        "X-Content-Sha256": payload,
        "Content-Type": "application/octet-stream",
        "Authorization": authorization
    }

    debug_print(f"url is {url}, data size is {len(data)}")
    debug_print(f"canonical_string: {repr(canonical_string)}")
    debug_print(f"sign_string: {repr(sign_string)}")
    resp = requests.post(url, data=data, headers=headers, timeout=60)
    
    try:
        result = resp.json()
    except:
        print(f"json parse error, resp is {resp.text}")
        sys.exit(1)
    
    _check_resp(result, action)
    
    return result

# 全局变量，存储授权方式和参数
_auth_mode = None
_arkclaw_token = None
_host = None

def init_auth(auth_mode: str, arkclaw_token: str | None = None, host: str | None = None):
    """初始化授权配置"""
    global _auth_mode, _arkclaw_token, _host
    _auth_mode = auth_mode
    _arkclaw_token = arkclaw_token
    _host = host

def _request(action: str, service: str = SERVICE_MUSE, body: dict | None = None, extra_query: dict | None = None) -> dict:
    """通用请求函数，根据授权模式选择"""
    if _auth_mode == "arkclaw":
        return _request_with_arkclaw(action, service, _host, _arkclaw_token, body, extra_query)
    else:
        return _request_with_aksk(action, service, _host, body, extra_query)

def _request_binary(action: str, service: str, extra_query: dict, data: bytes) -> dict:
    """通用二进制请求函数，根据授权模式选择"""
    if _auth_mode == "arkclaw":
        return _request_binary_with_arkclaw(action, service, _host, _arkclaw_token, extra_query, data)
    else:
        return _request_binary_with_aksk(action, service, _host, extra_query, data)

# ─── Step 0: ListUsers ────────────────────────────────

def get_admin_user_id() -> int:
    """调用 ListUsers 接口，从用户列表中寻找 admin 用户。"""
    debug_print("[0/5] ListUsers — 正在寻找 admin 用户...")
    result = _request(action="ListUsers", service=SERVICE_IAM, body={"UserType": "All"})
    _check_resp(result, "ListUsers")

    users = result.get("Result", {}).get("Users", [])
    
    debug_print(f"\n📋 调试信息：共找到 {len(users)} 个用户")
    for i, user in enumerate(users, 1):
        debug_print(f"\n用户 {i}:")
        debug_print(f"  Id: {user.get('Id')}")
        debug_print(f"  IsAdmin: {user.get('IsAdmin')}")
        debug_print(f"  Permitted: {user.get('Permitted')}")
        debug_print(f"  DisplayName: {user.get('DisplayName')}")
        debug_print(f"  VolcUserName: {user.get('VolcUserName')}")
        debug_print(f"  VolcUserId: {user.get('VolcUserId')}")
    
    if not users:
        print("❌ 未获取到任何用户信息")
        sys.exit(1)

    for user in users:
        if user.get("IsAdmin"):
            uid = user.get("Id")
            name = user.get("DisplayName") or user.get("VolcUserName") or ""
            if uid:
                debug_print(f"    找到 admin 用户: {name} (Id={uid}) ✅")
                return uid

    first_uid = users[0].get("Id")
    first_name = users[0].get("DisplayName") or users[0].get("VolcUserName") or ""
    debug_print(f"⚠️ 未找到 IsAdmin=true 的用户，使用第一个用户代替: {first_name} (Id={first_uid})")
    return first_uid

# ─── Step 1: GetUploadState ────────────────────────────

def get_upload_state(file_md5: str, file_size: int, file_crc32: int, owner_id: int) -> UploadStateResult:
    """查询文件是否已上传（支持断点续传）"""
    debug_print(f"[1/5] GetUploadState — md5={file_md5}, size={file_size}, crc32={file_crc32}")
    
    body = {
        "Owner": {"Id": owner_id, "Type": "PERSON"},
        "Md5": file_md5,
        "Size": file_size,
        "Start": 0,
        "End": file_size - 1,
        "Crc": file_crc32
    }
    
    result = _request(
        action="GetUploadState",
        service=SERVICE_MUSE,
        body=body
    )
    _check_resp(result, "GetUploadState")
    
    raw_state = result.get("Result", {})
    state: UploadStateResult = {
        "SkipDataComplete": bool(raw_state.get("SkipDataComplete", False)),
        "PartSize": int(raw_state.get("PartSize", 0)),
        "Ranges": raw_state.get("Ranges", [])
    }
    debug_print(f"文件上传状态：{state}") 
    return state

def upload_part(owner_id: int, chunk: bytes, offset: int, part_size: int, chunk_md5: str) -> dict:
    """上传文件分片"""
    debug_print(f"    上传分片 {offset} 到 {offset + part_size - 1} (大小 {part_size} 字节)")
    
    query = {
        "Md5": chunk_md5,
        "Size": part_size,
        "Offset": offset,
        "OwnerId": owner_id, "OwnerType": "PERSON"
    }
    resp = _request_binary("StreamUploadData", SERVICE_MUSE, query, chunk)
    _check_resp(resp, f"StreamUploadData，分片 {offset} 到 {offset + part_size - 1}")
    
    return resp

# ─── Step 2: StreamUploadData ──────────────────────────

def stream_upload_data(file_path: str, file_md5: str, file_size: int, file_crc32: int,
                       owner_id: int, upload_state: UploadStateResult) -> UploadStateResult:
    if upload_state["SkipDataComplete"]:
        debug_print("[2/5] 文件已存在且上传完成，跳过上传 ✅")
        return upload_state
    
    with open(file_path, "rb") as f:
        data = f.read()
    
    current_state = upload_state
    chunk_count = 0
    max_chunks = 1000
    offset = 0
    
    debug_print("[2/5] StreamUploadData — 开始上传...")
    
    while not current_state["SkipDataComplete"] and chunk_count < max_chunks:
        skip_data_complete = current_state["SkipDataComplete"]
        part_size = current_state.get("PartSize", 0)
        
        if skip_data_complete:
            break
        
        if part_size == 0:
            debug_print(f"    PartSize 为 0，上传整个文件")
            chunk = data
            chunk_size = file_size
        else:
            debug_print(f"    使用服务端返回的 PartSize: {part_size} bytes")
            debug_print(f"    当前上传位置: offset={offset}")
            
            if offset + part_size * 2 <= file_size:
                chunk = data[offset : offset + part_size]
                chunk_size = part_size
            else:
                chunk = data[offset : file_size]
                chunk_size = file_size - offset
        
        debug_print(f"[2/5] StreamUploadData — 上传第 {chunk_count + 1} 个分片，offset={offset}, size={chunk_size}")
        resp = upload_part(owner_id, chunk, offset, chunk_size, file_md5)
        
        chunk_count += 1
        offset += chunk_size
        
        current_state = get_upload_state(file_md5, file_size, file_crc32, owner_id)
        debug_print(f"current_state is {current_state}")
        
        if current_state["SkipDataComplete"] or current_state["Ranges"] == [] or offset >= file_size:
            debug_print("    上传完成，SkipDataComplete=true 或 Ranges 为空 或 offset 已超过文件大小 ✅")
            return current_state
    
    if chunk_count >= max_chunks and not current_state["SkipDataComplete"]:
        print(f"❌ 上传失败：已上传 {max_chunks} 个分片，但 SkipDataComplete 仍为 false")
        sys.exit(1)
    
    return current_state

# ─── Step 3: CreateMaterial ────────────────────────────

def create_material(file_md5: str, file_size: int, file_name: str, file_ext: str,
                    skip_data_complete: bool, owner_id: int, owner_type: str,
                    title: str, category: str) -> str:
    debug_print(f"[3/5] CreateMaterial — title={title}, category={category}, skip_data_complete={skip_data_complete}")
    
    
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
    
    debug_print(f"    [DEBUG] CreateMaterial Body: {json.dumps(body, ensure_ascii=False)}")
    
    result = _request(action="CreateMaterial", service=SERVICE_MUSE, body=body)
    _check_resp(result, "CreateMaterial")
    media_id = result.get("Result", {}).get("MediaId")
    debug_print(f"    MediaId={media_id} ✅")
    return media_id

# ─── Step 4: GetMediaInfo ──────────────────────────────

def get_media_info(media_id: str, owner_id: int, owner_type: str) -> dict:
    debug_print(f"[4/5] GetMediaInfo 轮询 — MediaId={media_id}")
    
    for attempt in range(1, POLL_MAX_ATTEMPTS + 1):
        result = _request(
            action="GetMediaInfo", service=SERVICE_MUSE,
            body={"MediaIds": [media_id], "MediaType": 1},
        )
        _check_resp(result, "GetMediaInfo")
        media_infos = result.get("Result", {}).get("MediaInfos", [])
        if not media_infos:
            debug_print(f"    [{attempt}/{POLL_MAX_ATTEMPTS}] 未获取到媒资信息...")
            time.sleep(POLL_INTERVAL)
            continue
        
        media_info = media_infos[0]
        status = media_info.get("BasicInfo", {}).get("MediaStatus")
        
        if status >= 2:
            debug_print(f"    处理成功 ✅, media_info={media_info}")
            return media_info
        if status == 5 or status == 1:
            print("❌ 处理失败")
            sys.exit(1)

        debug_print(f"    [{attempt}/{POLL_MAX_ATTEMPTS}] 处理中 (MediaStatus={status})...")
        time.sleep(POLL_INTERVAL)
    sys.exit(1)

# ─── Step 5: 提取下载链接 ──────────────────────────────

def extract_url(media_info: dict) -> str:    
    media_first_category = media_info.get("BasicInfo", {}).get("MediaFirstCategory", "")
    
    if media_first_category == "image":
        image_media = media_info.get("ImageMedia", {})
        download_url = image_media.get("DownloadUrl", "")
        if download_url:
            return (download_url)
        transcode_urls = image_media.get("TranscodeDownloadUrls", {})
        if transcode_urls:
            for quality in ["origin", "jpeg_1080p", "jpeg_480p"]:
                if quality in transcode_urls:
                    return (transcode_urls[quality])
    elif media_first_category == "video":
        video_media = media_info.get("VideoMedia", {})
        download_url = video_media.get("DownloadUrl", "")
        if download_url:
            return (download_url)
        play_info = video_media.get("PlayInfo", [])
        if play_info and play_info[0].get("Url"):
            return (play_info[0]["Url"])
    elif media_first_category == "audio":
        audio_media = media_info.get("AudioMedia", {})
        download_url = audio_media.get("DownloadUrl", "")
        if download_url:
            return (download_url)
        play_info = audio_media.get("PlayInfo", [])
        if play_info and play_info[0].get("Url"):
            return (play_info[0]["Url"])
    
    return ""

# ─── 辅助函数 ──────────────────────────────────────────

def _file_md5(file_path: str) -> str:
    h = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""): h.update(chunk)
    return h.hexdigest()

def _check_resp(resp: dict, action: str):
    debug_print(f"resp is {resp}")
    meta = resp.get("ResponseMetadata", {})
    
    error_obj = meta.get("Error")
    if error_obj:
        code = error_obj.get("Code") or error_obj.get("CodeN")
        if code == 500 or code == "500":
            print(Result(code="x01010", message="阅读SKILL.md中的「错误处理规范」，向用户推荐处理意见～").model_dump_json())
            sys.exit(1)
        msg = error_obj.get("Message", "")
        print(f"❌ {action} 失败: code={code}, msg={msg}")
        sys.exit(1)
        
    code = meta.get("Code")
    if code is not None and str(code) not in ("0", "Success", "200"):
        if code == 500 or code == "500":
            print(Result(code="x01010", message="阅读SKILL.md中的「错误处理规范」，向用户推荐处理意见～").model_dump_json())
            sys.exit(1)
        msg = meta.get("Message") or ""
        print(f"❌ {action} 失败: code={code}, msg={msg}")
        sys.exit(1)
        
    debug_print(f"✅ {action} 成功")

# ─── 主流程 ────────────────────────────────────────────

def list_users_debug():
    """调试接口：单独列出所有用户信息"""
    print("🔍 调试模式：获取用户列表\n")
    result = _request(action="ListUsers", service=SERVICE_IAM, body={"UserType": "All"})
    _check_resp(result, "ListUsers")
    
    users = result.get("Result", {}).get("Users", [])
    print(f"共找到 {len(users)} 个用户\n")
    
    for i, user in enumerate(users, 1):
        print(f"{'='*60}")
        print(f"用户 {i}:")
        print(f"{'='*60}")
        print(f"  Id:            {user.get('Id')}")
        print(f"  IsAdmin:       {user.get('IsAdmin')}")
        print(f"  Permitted:     {user.get('Permitted')}")
        print(f"  DisplayName:   {user.get('DisplayName')}")
        print(f"  Description:   {user.get('Description')}")
        print(f"  VolcUserName:  {user.get('VolcUserName')}")
        print(f"  VolcUserId:    {user.get('VolcUserId')}")
        print(f"  TeamInfos:     {user.get('TeamInfos')}")
        print(f"  RoleInfos:     {user.get('RoleInfos')}")
        print(f"  完整信息:      {json.dumps(user, ensure_ascii=False, indent=4)}")
        print()
    
    return users

def main():
    parser = argparse.ArgumentParser(description="智能创作云媒资上传工具")
    parser.add_argument("--host", help="API 域名地址")
    parser.add_argument("--list-users", action="store_true", help="调试模式：仅列出所有用户信息")
    parser.add_argument("--file", help="本地文件路径")
    parser.add_argument("--owner-id", type=int, help="Owner Id (可选，若不提供则自动查找 admin)")
    parser.add_argument("--owner-type", default="user", help="Owner Type (user/team)")
    parser.add_argument("--title", help="标题（可选，默认自动生成）")
    parser.add_argument("--category", default="video", help="类型: video/image/audio")
    parser.add_argument("--debug", action="store_true", help="开启调试日志")
    args = parser.parse_args()
    
    if args.debug:
        global DEBUG
        DEBUG = True
    
    auth_mode = None
    arkclaw_token = None
    host = None
    
    if ARKCLAW_TOKEN:
        auth_mode = "arkclaw"
        arkclaw_token = ARKCLAW_TOKEN
        host = args.host or DEFAULT_HOST
        debug_print(f"使用 ArkClaw Token 方式，域名: {host}")
    elif ACCESS_KEY_ID and SECRET_ACCESS_KEY:
        auth_mode = "aksk"
        host = args.host or DEFAULT_ICP_HOST
        debug_print(f"使用 AK/SK 方式，域名: {host}")
    else:
        print("❌ 请设置环境变量 ARKCLAW_TOKEN 或 ACCESS_KEY_ID/SECRET_ACCESS_KEY")
        sys.exit(1)
    
    init_auth(auth_mode, arkclaw_token, host)
    
    if args.list_users:
        list_users_debug()
        return
    
    if not args.file:
        parser.error("上传模式需要 --file 参数")
    
    if not args.title:
        args.title = f"artclaw-material-{int(time.time())}"

    if not os.path.exists(args.file):
        print(f"❌ 文件不存在: {args.file}")
        sys.exit(1)
    if not os.path.isfile(args.file):
        print(f"❌ 路径不是文件: {args.file}")
        sys.exit(1)

    owner_id = args.owner_id
    if owner_id is None:
        owner_id = get_admin_user_id()

    import hashlib
    import zlib
    file_md5_obj = hashlib.md5()
    file_crc32 = 0
    file_size = 0
    
    with open(args.file, "rb") as f:
        while chunk := f.read(8192 * 1024):
            file_md5_obj.update(chunk)
            file_crc32 = zlib.crc32(chunk, file_crc32)
            file_size += len(chunk)
            
    file_md5 = file_md5_obj.hexdigest()
    file_crc32 = file_crc32 & 0xFFFFFFFF
    
    file_name = os.path.splitext(os.path.basename(args.file))[0]
    file_ext = os.path.splitext(args.file)[1].lstrip(".")
    
    if not args.category or args.category == "video":
        file_ext_lower = file_ext.lower()
        if file_ext_lower in IMAGE_EXTENSIONS:
            args.category = "image"
        elif file_ext_lower in VIDEO_EXTENSIONS:
            args.category = "video"

    state = get_upload_state(file_md5, file_size, file_crc32, owner_id)

    state = stream_upload_data(args.file, file_md5, file_size, file_crc32, owner_id, state)
    
    media_id = create_material(file_md5, file_size, file_name, file_ext, 
                               state["SkipDataComplete"], 
                               owner_id, args.owner_type, args.title, args.category)
    media_info = get_media_info(media_id, owner_id, args.owner_type)
    url = extract_url(media_info)

    print(f"\n✅ 流程结束！\nMediaId: {media_id}\nDownloadUrl: {url}")

def simplify(media_info: dict):
    media_first_category = media_info.get("BasicInfo", {}).get("MediaFirstCategory", "")
    if media_first_category == "image":
        image_media = media_info.get("ImageMedia", {})
        download_url = image_media.get("DownloadUrl", None)
        if download_url: image_media["DownloadUrl"] = (download_url)

        transcode_urls = image_media.get("TranscodeDownloadUrls", {})
        for quality in ["origin", "jpeg_1080p", "jpeg_480p"]:
            if quality in transcode_urls:
                transcode_urls[quality] = (transcode_urls[quality])

    if media_first_category == "video":
        video_media = media_info.get("VideoMedia", {})
        download_url = video_media.get("DownloadUrl", None)
        if download_url: video_media["DownloadUrl"] = (download_url)
        play_info = video_media.get("PlayInfo", [])
        if play_info and play_info[0].get("Url"):
            play_info[0]["Url"] = (play_info[0]["Url"])
    
    if media_first_category == "audio":
        audio_media = media_info.get("AudioMedia", {})
        download_url = audio_media.get("DownloadUrl", None)
        if download_url: audio_media["DownloadUrl"] = (download_url)
        play_info = audio_media.get("PlayInfo", [])
        if play_info and play_info[0].get("Url"):
            play_info[0]["Url"] = (play_info[0]["Url"])

    return media_info

def format(media_info: dict)->Matriel:
    image_media = jsonpath.jsonpath(media_info, "$.ImageMedia")
    if image_media:
        matriel = ImageMatriel(type="image", url="", height=0, width=0)
        url = jsonpath.jsonpath(media_info, "$.ImageMedia.DownloadUrl")
        matriel.url = url[0] if url else ""

        width = jsonpath.jsonpath(media_info, "$.ImageMedia.Width")
        matriel.width = width[0] if width else 0

        height = jsonpath.jsonpath(media_info, "$.ImageMedia.Height")
        matriel.height = height[0] if height else 0
        return matriel

    video_media = jsonpath.jsonpath(media_info, "$.VideoMedia")
    if video_media:
        matriel = VideoMatriel(type="video", url="", height=0, width=0, duration=0)
        url = jsonpath.jsonpath(media_info, "$.VideoMedia.DownloadUrl")
        matriel.url = url[0] if url else ""

        width = jsonpath.jsonpath(media_info, "$.VideoMedia.MediaMetaInfo.Width")
        matriel.width = width[0] if width else 0

        height = jsonpath.jsonpath(media_info, "$.VideoMedia.MediaMetaInfo.Height")
        matriel.height = height[0] if height else 0

        duration = jsonpath.jsonpath(media_info, "$.VideoMedia.MediaMetaInfo.Duration")
        matriel.duration = duration[0] / 1000 if duration else 0.0
        return matriel
    return Matriel(type="", url="", height=0, width=0)

def upload(args: dict)->Matriel:
    # 自动生成 title
    args["title"] = f"artclaw-material-{int(time.time())}"
    args["owner_type"] = "user"

    auth_mode = None
    arkclaw_token = None
    host = None

    if ARKCLAW_TOKEN:
        auth_mode = "arkclaw"
        arkclaw_token = ARKCLAW_TOKEN
        host = DEFAULT_HOST
        debug_print(f"使用 ArkClaw Token 方式，域名: {host}")
    elif ACCESS_KEY_ID and SECRET_ACCESS_KEY:
        auth_mode = "aksk"
        host = DEFAULT_ICP_HOST
        debug_print(f"使用 AK/SK 方式，域名: {host}")
    else:
        print("❌ 请设置环境变量 ARKCLAW_TOKEN 或 ACCESS_KEY_ID/SECRET_ACCESS_KEY")
        sys.exit(1)
    
    init_auth(auth_mode, arkclaw_token, host)
    # 如果没有提供 owner-id，则自动通过 ListUsers 获取
    owner_id = args["owner_id"] if "owner_id" in args else get_admin_user_id()
    

    import hashlib
    import zlib
    file_md5_obj = hashlib.md5()
    file_crc32 = 0
    file_size = 0
    
    with open(args["file"], "rb") as f:
        while chunk := f.read(8192 * 1024):
            file_md5_obj.update(chunk)
            file_crc32 = zlib.crc32(chunk, file_crc32)
            file_size += len(chunk)
            
    file_md5 = file_md5_obj.hexdigest()
    file_crc32 = file_crc32 & 0xFFFFFFFF
    
    file_name = os.path.splitext(os.path.basename(args["file"]))[0]
    file_ext = os.path.splitext(args["file"])[1].lstrip(".")
    

    # 根据文件后缀自动识别 category
    file_ext_lower = file_ext.lower()
    if file_ext_lower in IMAGE_EXTENSIONS:
        args["category"] = "image"
    elif file_ext_lower in VIDEO_EXTENSIONS:
        args["category"] = "video"

    state = get_upload_state(file_md5, file_size, file_crc32, owner_id)

    state = stream_upload_data(args["file"], file_md5, file_size, file_crc32, owner_id, state)
    
    media_id = create_material(file_md5, file_size, file_name, file_ext, 
                               state["SkipDataComplete"], 
                               owner_id, args["owner_type"], args["title"], args["category"])
    media_info = get_media_info(media_id, owner_id, args["owner_type"])

    return format(simplify(media_info))


if __name__ == "__main__":
    main()
    
