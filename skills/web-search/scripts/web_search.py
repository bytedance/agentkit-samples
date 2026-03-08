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
The document of this tool see: https://www.volcengine.com/docs/85508/1650263
"""

import datetime
import hashlib
import hmac
import os
from pathlib import Path
import warnings
from typing import Literal
from urllib.parse import quote

from dotenv import load_dotenv
import requests

warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings(
    "ignore",
    message="urllib3 (.*) or chardet (.*)/charset_normalizer (.*) doesn't match a supported version!",
)

Service = ""
Version = ""
Region = ""
Host = ""
ContentType = ""
Scheme = "https"


def norm_query(params):
    query = ""
    for key in sorted(params.keys()):
        if isinstance(params[key], list):
            for k in params[key]:
                query = (
                    query + quote(key, safe="-_.~") + "=" + quote(k, safe="-_.~") + "&"
                )
        else:
            query = (
                query
                + quote(key, safe="-_.~")
                + "="
                + quote(params[key], safe="-_.~")
                + "&"
            )
    query = query[:-1]
    return query.replace("+", "%20")


# 第一步：准备辅助函数。
# sha256 非对称加密
def hmac_sha256(key: bytes, content: str):
    return hmac.new(key, content.encode("utf-8"), hashlib.sha256).digest()


# sha256 hash算法
def hash_sha256(content: str):
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


# 第二步：签名请求函数
def request(
    method,
    date,
    query,
    header,
    ak,
    sk,
    action,
    body,
    scheme: Literal["http", "https"] = "https",
):
    # 第三步：创建身份证明。其中的 Service 和 Region 字段是固定的。ak 和 sk 分别代表
    # AccessKeyID 和 SecretAccessKey。同时需要初始化签名结构体。一些签名计算时需要的属性也在这里处理。
    # 初始化身份证明结构体
    credential = {
        "access_key_id": ak,
        "secret_access_key": sk,
        "service": Service,
        "region": Region,
    }
    # 初始化签名结构体
    request_param = {
        "body": body,
        "host": Host,
        "path": "/",
        "method": method,
        "content_type": ContentType,
        "date": date,
        "query": {"Action": action, "Version": Version, **query},
    }
    if body is None:
        request_param["body"] = ""
    # 第四步：接下来开始计算签名。在计算签名前，先准备好用于接收签算结果的 signResult 变量，并设置一些参数。
    # 初始化签名结果的结构体
    x_date = request_param["date"].strftime("%Y%m%dT%H%M%SZ")
    short_x_date = x_date[:8]
    x_content_sha256 = hash_sha256(request_param["body"])
    sign_result = {
        "Host": request_param["host"],
        "X-Content-Sha256": x_content_sha256,
        "X-Date": x_date,
        "Content-Type": request_param["content_type"],
    }
    # 第五步：计算 Signature 签名。
    signed_headers_str = ";".join(
        ["content-type", "host", "x-content-sha256", "x-date"]
    )
    # signed_headers_str = signed_headers_str + ";x-security-token"
    canonical_request_str = "\n".join(
        [
            request_param["method"].upper(),
            request_param["path"],
            norm_query(request_param["query"]),
            "\n".join(
                [
                    "content-type:" + request_param["content_type"],
                    "host:" + request_param["host"],
                    "x-content-sha256:" + x_content_sha256,
                    "x-date:" + x_date,
                ]
            ),
            "",
            signed_headers_str,
            x_content_sha256,
        ]
    )

    # 打印正规化的请求用于调试比对
    # print(canonical_request_str)
    hashed_canonical_request = hash_sha256(canonical_request_str)

    # 打印hash值用于调试比对
    # print(hashed_canonical_request)
    credential_scope = "/".join(
        [short_x_date, credential["region"], credential["service"], "request"]
    )
    string_to_sign = "\n".join(
        ["HMAC-SHA256", x_date, credential_scope, hashed_canonical_request]
    )

    # 打印最终计算的签名字符串用于调试比对
    # print(string_to_sign)
    k_date = hmac_sha256(credential["secret_access_key"].encode("utf-8"), short_x_date)
    k_region = hmac_sha256(k_date, credential["region"])
    k_service = hmac_sha256(k_region, credential["service"])
    k_signing = hmac_sha256(k_service, "request")
    signature = hmac_sha256(k_signing, string_to_sign).hex()

    sign_result["Authorization"] = (
        "HMAC-SHA256 Credential={}, SignedHeaders={}, Signature={}".format(
            credential["access_key_id"] + "/" + credential_scope,
            signed_headers_str,
            signature,
        )
    )
    header = {**header, **sign_result}
    if "X-Security-Token" in header and header["X-Security-Token"] == "":
        del header["X-Security-Token"]
    # header = {**header, **{"X-Security-Token": SessionToken}}
    # 第六步：将 Signature 签名写入 HTTP Header 中，并发送 HTTP 请求。
    r = requests.request(
        method=method,
        url=f"{scheme}://{request_param['host']}{request_param['path']}",
        headers=header,
        params=request_param["query"],
        data=request_param["body"],
    )
    try:
        return r.json()
    except Exception:
        raise ValueError(f"Error occurred. Bad response: {r}")


def ve_request_with_aksk(
    request_body: dict,
    action: str,
    ak: str,
    sk: str,
    service: str,
    version: str,
    region: str,
    host: str,
    content_type: str = "application/json",
    header: dict = {},
    query: dict = {},
    method: Literal["GET", "POST", "PUT", "DELETE"] = "POST",
    scheme: Literal["http", "https"] = "https",
):
    global Service
    Service = service
    global Version
    Version = version
    global Region
    Region = region
    global Host
    Host = host
    global ContentType
    ContentType = content_type
    global Scheme
    Scheme = scheme
    AK = ak
    SK = sk

    # Check if AK and SK are provided
    if not (AK and SK):
        raise ValueError("Access key and secret key are required")

    now = datetime.datetime.utcnow()
    # Body的格式需要配合Content-Type，API使用的类型请阅读具体的官方文档，如:json格式需要json.dumps(obj)
    # response_body = request("GET", now, {"Limit": "2"}, {}, AK, SK, "ListUsers", None)
    import json

    try:
        response_body = request(
            method,
            now,
            query,
            header,
            AK,
            SK,
            action,
            json.dumps(request_body),
            Scheme,
        )
        return response_body
    except Exception as e:
        raise e


def ve_request_with_apikey(
    request_body: dict,
    api_key: str,
    content_type: str = "application/json",
    header: dict = {},
    method: Literal["GET", "POST", "PUT", "DELETE"] = "POST",
):
    # Check if API key is provided
    if not api_key:
        raise ValueError("API key is required")

    import json

    try:
        # Use the provided API Key access URL
        url = "https://open.feedcoopapi.com/search_api/web_search"

        # Construct headers
        headers = {**header}
        headers["Authorization"] = f"Bearer {api_key}"
        headers["Content-Type"] = content_type

        print(f"Request URL: {url}")
        print(f"Request Headers: {headers}")
        print(f"Request Body: {json.dumps(request_body)}")

        # Send request
        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            data=json.dumps(request_body),
        )

        try:
            return response.json()
        except Exception:
            raise ValueError(f"Error occurred. Bad response: {response}")
    except Exception as e:
        raise e


def web_search(query: str) -> list[str]:
    """Search a query in websites.

    Args:
        query: The query to search.

    Returns:
        A list of result documents.
    """
    if not query:
        print("Query is empty.")
        return []

    web_search_env = Path("/root/.openclaw/.env")
    if web_search_env.exists():
        load_dotenv(web_search_env)
        print(f"Successfully load environment variables from {web_search_env} file.")

    api_key = os.getenv("WEB_SEARCH_API_KEY")
    ak = None
    sk = None
    session_token = ""

    # Use API key if available
    if not api_key:
        print("WEB_SEARCH_API_KEY not found in environment variables.")
        ak = os.getenv("VOLCENGINE_ACCESS_KEY")
        sk = os.getenv("VOLCENGINE_SECRET_KEY")
        if not (ak and sk):
            print(
                "VOLCENGINE_ACCESS_KEY or VOLCENGINE_SECRET_KEY not found in environment variables."
            )
        else:
            print("Successfully get AK/SK from environment variables.")
    else:
        print("Successfully get API key from environment variables.")

    # Use AK/SK if API key is not available
    if not (ak and sk) and not api_key:
        platform = os.getenv("PLATFORM", "ecs")
        if platform == "vefaas":
            from veadk.auth.veauth.utils import get_credential_from_vefaas_iam

            credential = get_credential_from_vefaas_iam()
            if credential:
                ak = credential.access_key_id
                sk = credential.secret_access_key
                session_token = credential.session_token
                if not (ak and sk):
                    print("Get AK/SK from vefaas credential failed.")
            else:
                print("Get credential from vefaas failed.")
        elif platform == "ecs":
            # TODO: Support ecs metadata later.
            print("Support ecs metadata later.")

        if not (ak and sk):
            print("Get AK/SK from credential failed.")
        else:
            print("Successfully get AK/SK from credential.")

    if not (ak and sk) and not api_key:
        raise PermissionError("no credential found")

    header = {"X-Security-Token": session_token}
    # Use API key if available
    if api_key:
        response = ve_request_with_apikey(
            request_body={
                "Query": query,
                "SearchType": "web",
                "Count": 5,
                "NeedSummary": True,
            },
            api_key=api_key,
            header=header,
        )
    else:
        response = ve_request_with_aksk(
            request_body={
                "Query": query,
                "SearchType": "web",
                "Count": 5,
                "NeedSummary": True,
            },
            action="WebSearch",
            ak=ak,
            sk=sk,
            service="volc_torchlight_api",
            version="2025-01-01",
            region="cn-beijing",
            host="mercury.volcengineapi.com",
            header=header,
        )

    try:
        results: list = response["Result"]["WebResults"]
        final_results = []
        for result in results:
            final_results.append(result["Summary"].strip())
        return final_results
    except Exception as e:
        print(f"Web search failed {e}, response body: {response}")
        return [response]


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print("Usage: python web_search.py <query>")
        sys.exit(1)

    query = sys.argv[1]
    results = web_search(query)
    print(results)
