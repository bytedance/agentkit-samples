# coding:utf-8
"""
Copyright (year) Beijing Volcano Engine Technology Ltd.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

     http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""
import json
import datetime
import hashlib
import hmac
import os
from urllib.parse import quote, urlencode
import dataclasses
from typing import Any, Dict, Union, List

import requests

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


def hmac_sha256(key: bytes, content: str):
    return hmac.new(key, content.encode("utf-8"), hashlib.sha256).digest()


def hash_sha256(content: str):
    return hashlib.sha256(content.encode("utf-8")).hexdigest()

# ref: https://www.volcengine.com/docs/6369/67269
def generate_signature(request_param, credential):
    """
    生成请求的签名和必要的头信息
    
    Args:
        request_param: 请求参数字典，包含body、host、path、method、content_type、query等
        credential: 凭证信息，包含access_key_id、secret_access_key、region、service等
        
    Returns:
        dict: 包含签名信息的头信息字典
    """
    x_date = utc_now().strftime("%Y%m%dT%H%M%SZ")
    short_x_date = x_date[:8]
    x_content_sha256 = hash_sha256(request_param["body"])
    
    # init sign result
    sign_result = {
        "Host": request_param["host"],
        "X-Content-Sha256": x_content_sha256,
        "X-Date": x_date,
        "Content-Type": request_param["content_type"],
    }

    # build signed headers string
    signed_headers_str = ";".join(
        ["content-type", "host", "x-content-sha256", "x-date"]
    )
    
    # build canonical request string
    canonical_request_str = "\n".join([
        request_param["method"].upper(),
        request_param["path"],
        norm_query(request_param["query"]),
        "\n".join([
            "content-type:" + request_param["content_type"],
            "host:" + request_param["host"],
            "x-content-sha256:" + x_content_sha256,
            "x-date:" + x_date,
        ]),
        "",
        signed_headers_str,
        x_content_sha256,
    ])
    
    # calculate hashed canonical request
    hashed_canonical_request = hash_sha256(canonical_request_str)

    # build credential scope and string to sign
    credential_scope = "/".join([short_x_date, credential.region, credential.service, "request"])
    string_to_sign = "\n".join(["HMAC-SHA256", x_date, credential_scope, hashed_canonical_request])

    # calculate HMAC key chain
    k_date = hmac_sha256(credential.secret_access_key.encode("utf-8"), short_x_date)
    k_region = hmac_sha256(k_date, credential.region)
    k_service = hmac_sha256(k_region, credential.service)
    k_signing = hmac_sha256(k_service, "request")
    
    # calculate final signature
    signature = hmac_sha256(k_signing, string_to_sign).hex()

    # build Authorization header
    sign_result["Authorization"] = "HMAC-SHA256 Credential={}, SignedHeaders={}, Signature={}".format(
        credential.access_key_id + "/" + credential_scope,
        signed_headers_str,
        signature,
    )
    
    # if session token is not empty, add it to sign result
    if not is_empty_value(credential.session_token):
        sign_result["x-security-token"] = credential.session_token
    
    return sign_result

def is_empty_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, (str, list, dict)) and len(value) == 0:
        return True
    return False

def to_serializable_dict(obj: Any) -> Union[Dict[str, Any], List[Any], Any]:
    if dataclasses.is_dataclass(obj):
        result_dict = {}
        for field in dataclasses.fields(obj):
            value = getattr(obj, field.name)
            if not is_empty_value(value):
                serialized_value = to_serializable_dict(value)
                if not is_empty_value(serialized_value):
                    result_dict[field.name] = serialized_value
        return result_dict
    
    if isinstance(obj, dict):
        result_dict = {}
        for k, v in obj.items():
            if not is_empty_value(v):
                serialized_value = to_serializable_dict(v)
                if not is_empty_value(serialized_value):
                    result_dict[k] = serialized_value
        return result_dict

    if isinstance(obj, list):
        result_list = []
        for item in obj:
            if not is_empty_value(item):
                serialized_item = to_serializable_dict(item)
                if not is_empty_value(serialized_item):
                    result_list.append(serialized_item)
        return result_list

    return obj

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

def get_content_type(headers):
    lower_headers = {k.lower(): v for k, v in headers.items()}
    return lower_headers.get('content-type')

def sign_and_request(info, credential, query, header, host, body=None):
    content_type = get_content_type(header)
    
    if body is not None:
        body_dict = to_serializable_dict(body)
        
        if content_type == "application/x-www-form-urlencoded":
            body_str = urlencode(body_dict, doseq=True)
        else:
            body_str = json.dumps(body_dict)
    else:
        body_str = ""

    request_param = {
        "body": body_str,
        "host": host,
        "path": "/",
        "method": info.method,
        "content_type": content_type,
        "query": {"Action": info.action, "Version": info.version, **query},
    }
   
    sign_result = generate_signature(request_param, credential)
    
    header = {**header, **sign_result}
    # 默认不输出签名/请求体，避免污染脚本输出；需要排障时再打开
    if os.getenv("VMP_DEBUG", "") in ("1", "true", "TRUE"):
        print(header)
        print(request_param["body"])
        print(request_param["query"])
    
    timeout = (10, 30)
    
    try:
        r = requests.request(
            method=info.method,
            url="https://{}{}".format(request_param["host"], request_param["path"]),
            headers=header,
            params=request_param["query"],
            data=request_param["body"],
            timeout=timeout  
        )
        
        try:
            return r.json()
        except json.JSONDecodeError:
            return {
                "error": "Invalid JSON response",
                "status_code": r.status_code,
                "response_text": r.text
            }
    except requests.exceptions.Timeout:
        return {
            "error": "Request timed out",
            "timeout": timeout
        }
    except requests.exceptions.ConnectionError:
        return {
            "error": "Connection error",
            "host": request_param["host"]
        }
    except requests.exceptions.RequestException as e:
        return {
            "error": "Request failed",
            "message": str(e)
        }
