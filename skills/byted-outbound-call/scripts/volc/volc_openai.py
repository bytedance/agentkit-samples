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

import datetime
import hashlib
import hmac
import json
from urllib.parse import quote

import requests
import os
import sys

# 添加scripts目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.logger_config import get_file_logger
file_logger = get_file_logger('volc_openai')
# 以下参数视服务不同而不同，一个服务内通常是一致的
Service = "bytebot"
Version = "2023-01-01"
Region = "cn-north-1"
Host = "open.volcengineapi.com"
ContentType = "application/json"

def norm_query(params):
    query = ""
    for key in sorted(params.keys()):
        if type(params[key]) == list:
            for k in params[key]:
                query = (
                        query + quote(key, safe="-_.~") + "=" + quote(k, safe="-_.~") + "&"
                )
        else:
            query = (query + quote(key, safe="-_.~") + "=" + quote(params[key], safe="-_.~") + "&")
    query = query[:-1]
    return query.replace("+", "%20")


# 第一步：准备辅助函数。
# sha256 非对称加密
def hmac_sha256(key: bytes, content: str):
    return hmac.new(key, content.encode("utf-8"), hashlib.sha256).digest()


# sha256 hash算法
def hash_sha256(content: str):
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def request(method, action, body, headers={}):
    date = utc_now()
    query = {}
    ak = os.environ.get("VOLCENGINE_ACCESS_KEY")
    if ak is None:
        raise ValueError("VOLCENGINE_ACCESS_KEY is not set")

    sk = os.environ.get("VOLCENGINE_SECRET_KEY")
    if sk is None:
        raise ValueError("VOLCENGINE_SECRET_KEY is not set")

    return _request(method, date, query, headers, ak, sk, action, body)


# 第二步：签名请求函数
def _request(method, date, query, header, ak, sk, action, body):
    # 第三步：创建身份证明。其中的 Service 和 Region 字段是固定的。ak 和 sk 分别代表
    # AccessKeyID 和 SecretAccessKey。同时需要初始化签名结构体。一些签名计算时需要的属性也在这里处理。
    # 初始化身份证明结构体
    credential = {
        "access_key_id": ak,
        "secret_access_key": sk,
        "service": Service,
        "region": Region,
    }
    path = "/"
    # 初始化签名结构体
    request_param = {
        "body": body,
        "host": Host,
        "path": path,
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
        [request_param["method"].upper(),
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
    file_logger.info("正规化的请求: %s", canonical_request_str)
    hashed_canonical_request = hash_sha256(canonical_request_str)

    # 打印hash值用于调试比对
    file_logger.info("hash值: %s", hashed_canonical_request)
    credential_scope = "/".join([short_x_date, credential["region"], credential["service"], "request"])
    string_to_sign = "\n".join(["HMAC-SHA256", x_date, credential_scope, hashed_canonical_request])

    # 打印最终计算的签名字符串用于调试比对
    file_logger.info("最终计算的签名字符串: %s", string_to_sign)
    k_date = hmac_sha256(credential["secret_access_key"].encode("utf-8"), short_x_date)
    k_region = hmac_sha256(k_date, credential["region"])
    k_service = hmac_sha256(k_region, credential["service"])
    k_signing = hmac_sha256(k_service, "request")
    signature = hmac_sha256(k_signing, string_to_sign).hex()

    sign_result["Authorization"] = "HMAC-SHA256 Credential={}, SignedHeaders={}, Signature={}".format(
        credential["access_key_id"] + "/" + credential_scope,
        signed_headers_str,
        signature,
        )
    header = {**header, **sign_result}
    # header = {**header, **{"X-Security-Token": SessionToken}}
    # 第六步：将 Signature 签名写入 HTTP Header 中，并发送 HTTP 请求。
    request_host = Host
    r = requests.request(method=method,
                         url="https://{}{}".format(request_host, request_param["path"]),
                         headers=header,
                         params=request_param["query"],
                         data=request_param["body"],
                         )
    # print(f"Response status code: {r.status_code}")
    # print(f"Response content: {r.text}")
    try:
        return r.json()
    except Exception as e:
        print(f"JSON decode error: {e}")
        return None

# datetime.utcnow() 在 3.12+ 已经过期，使用如下方法兼容
def utc_now():

    try:
        from datetime import timezone
        return datetime.datetime.now(timezone.utc)
    except ImportError:
        class UTC(datetime.tzinfo):
            def utcoffset(self, dt):
                return datetime.timedelta(0)
            def tzname(self, dt):
                return "UTC"
            def dst(self, dt):
                return datetime.timedelta(0)
        return datetime.datetime.now(UTC())


if __name__ == "__main__":
    now = utc_now()
    from common.http_request import build_headers

    headers = build_headers()
    # --header 'ServiceName: bytebot' \
    # --header 'Region: cn-north-1' \
    # --header 'Content-Type: application/json' \

    # headers["ServiceName"] = "bytebot"
    # headers["Region"] = "cn-north-1"
    # headers["Content-Type"] = "application/json"

    # response_body = request("POST", "QueryTaskList", '{"Limit":20,"Offset":0}')
    # print(json.dumps(response_body, ensure_ascii=False))

    body = '{"ScriptName":"llm_axfn_biffg","Phone":"15201586220","VariableParams":{"user_phone_number":"213213123","first_name":"朱","time":"19点","date":"2016年3月24日","shop_name":"海底捞"}}'
    # headers['x-use-ppe'] = '1'
    # headers['X-TT-ENV'] = 'ppe_volcengine'
    headers['X-VOLC-ENV'] = 'ppe_open_claw'
    print(os.environ.get("VOLCENGINE_ACCESS_KEY"))
    print(os.environ.get("VOLCENGINE_SECRET_KEY"))
    response_body = request("POST", "SubmitJob", body, headers)
    print(json.dumps(response_body, ensure_ascii=False))

    sys.exit(1)

    file_logger.info("=" * 60)

    body = '{"JobId":"e705f53f-0bbf-4770-a288-8f2f035ea58a"}'
    # headers['x-use-ppe'] = '1'
    # headers['X-TT-ENV'] = 'ppe_volcengine'
    headers['X-VOLC-ENV'] = 'ppe_open_claw'
    response_body = request("POST", "QueryJobStatus", body, headers)
    print(json.dumps(response_body, ensure_ascii=False))


    file_logger.info("=" * 60)

    body = '{"JobId":"e705f53f-0bbf-4770-a288-8f2f035ea58a"}'
    headers['x-use-ppe'] = '1'
    headers['X-TT-ENV'] = 'ppe_volcengine'
    headers['X-VOLC-ENV'] = 'ppe_open_claw'
    response_body = request("POST", "QueryJobDetail", body, headers)
    print(json.dumps(response_body, ensure_ascii=False))

