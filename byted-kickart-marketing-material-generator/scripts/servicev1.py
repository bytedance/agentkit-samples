import os
import hmac
import hashlib
import jsonpath
import requests
from urllib.parse import urlencode, urlparse

from model import *
# 请求接口信息
ADDR = "https://icp.volcengineapi.com"
SERVICE = "iccloud_muse"
REGION = "cn-north"
ACTION = "SubmitAiTemplateTaskAsync"
VERSION = "2025-11-25"
### 认证配置
ACCESS_KEY_ID = os.getenv("ACCESS_KEY_ID") or ""
SECRET_ACCESS_KEY = os.getenv("SECRET_ACCESS_KEY") or ""

# 构造header Authorization
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

# 请求示例
def _do_request(method: str, queries: dict, body: bytes, action: str, version: str = VERSION, service: str=SERVICE):
    """发起请求（支持GET/POST，包含签名逻辑）"""
    # 1. 处理查询参数，添加Action和Version
    queries["Action"] = action or ACTION
    queries["Version"] = version or VERSION

    # 构建请求地址
    query_string = urlencode(queries)
    query_string = query_string.replace("+", "%20")
    url = f"{ADDR}?{query_string}"

    # 2. 构建签名核心材料
    date = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(time.time()))
    auth_date = date[:8]  # 提取日期部分（YYYYMMDD）

    # 计算请求体哈希
    payload = hash_sha256(body).hex()

    # 构建签名头部列表
    signed_headers = ["host", "x-date", "x-content-sha256", "content-type"]
    parsed_url = urlparse(ADDR)
    host = parsed_url.netloc  # 提取主机名（如：icp.volcengineapi.com）

    # 构建规范头部字符串
    header_list = []
    for header in signed_headers:
        if header == "host":
            header_list.append(f"{header}:{host}")
        elif header == "x-date":
            header_list.append(f"{header}:{date}")
        elif header == "x-content-sha256":
            header_list.append(f"{header}:{payload}")
        elif header == "content-type":
            header_list.append(f"{header}:application/json")
    header_string = "\n".join(header_list)

    # 构建规范请求字符串
    canonical_string = "\n".join([method.upper(),"/",query_string,f"{header_string}\n",";".join(signed_headers),payload])
    hashed_canonical_string = hash_sha256(canonical_string.encode("utf-8")).hex()
    credential_scope = f"{auth_date}/{REGION}/{SERVICE}/request"
    sign_string = "\n".join(["HMAC-SHA256",date,credential_scope,hashed_canonical_string])
    signed_key = get_signed_key(SECRET_ACCESS_KEY, auth_date, REGION, SERVICE)
    signature = hmac_sha256(signed_key, sign_string).hex()
    authorization = (f"HMAC-SHA256 Credential={ACCESS_KEY_ID}/{credential_scope},"f" SignedHeaders={';'.join(signed_headers)},"f" Signature={signature}")

    # 4. 构建完整请求头
    headers = {
        "X-Date": date,
        "X-Content-Sha256": payload,
        "Content-Type": "application/json",
        "Authorization": authorization
    }

    # 6. 发起请求并处理响应
    logging.info(f">>> {method.upper()} {url} {headers} {body}")
    response = requests.request(method=method.upper(),url=url,headers=headers,data=body,timeout=30)
    logging.info(f"<<< {response.headers} {response.text}")

    return response
