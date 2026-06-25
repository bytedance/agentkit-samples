# Copyright (c) 2026 Beijing Volcano Engine Technology Co., Ltd. and/or its affiliates.
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
"""byted-vms-voice-notify 内部 helper: 签名 + TOP 调用 + 错误码映射.

仅供本 skill 包内 import. 与其他 skill 的同名文件互相独立, 不跨包共享.
"""
from __future__ import annotations

import datetime
import hashlib
import hmac
import json
import os
import sys
from typing import Any, Dict, Optional, Tuple
from urllib import error, parse, request

DEFAULT_HOST = "cloud-vms.volcengineapi.com"
DEFAULT_VERSION = "2022-01-01"
DEFAULT_REGION = "cn-north-1"
DEFAULT_SERVICE = "vms"

ERROR_MAP = {
    "OperationDenied": "语音服务尚未开通. 请前往 https://console.volcengine.com/cloud_vms 点击「立即开通」.",
    "AccessDenied": "鉴权失败: 请检查个人版 AK/SK (arkclaw / openclaw / 其他 agent: VOLC_ACCESS_KEY/VOLC_SECRET_KEY); 企业版 arkclaw 请在火山后台配置 AK/SK 后设置 ARK_SKILL_API_KEY/ARK_SKILL_API_BASE.",
    "SignatureDoesNotMatch": "签名错误, 一般是机器时钟漂移, 请同步本机时间后重试.",
    "QUALIFICATION_REJECTED": "资质审核未通过. 请前往 https://console.volcengine.com/cloud_vms/qualification 重新提交.",
    "QUALIFICATION_MISSING": "尚未提交资质. 请前往 https://console.volcengine.com/cloud_vms/qualification 提交主体信息.",
    "NOT_AUTH": "账号未实名. 请先完成企业实名认证: https://console.volcengine.com/user/authentication/enterprise/",
    "NOT_IN_NUMBER_POOL": "号码池中无可用号码. 请前往 https://console.volcengine.com/cloud_vms/number 申请号码.",
    "NO_USABLE_NUMBER": "无可用主叫号码. 请前往 https://console.volcengine.com/cloud_vms/number 申请号码.",
    "RESOURCE_NOT_FOUND": "未找到对应语音资源. 请前往 https://console.volcengine.com/cloud_vms/voice-file 创建并提交审核.",
    "RESOURCE_KEY_IS_NOT_EXIST": "语音资源 ResourceKey 不存在. 请用 list_resource / list_usable 拿到正确的 ResourceKey 后重试.",
    "BLACK_LIST_PHONE": "该号码命中平台黑名单, 请确认号码或联系客户经理.",
    "FORBIDDEN_TIME": "当前处于禁呼时段, 请在允许时段重试.",
    "InvalidParameter": "请求参数有误, 请检查必填字段.",
    "InternalError": "服务侧异常, 请提供 RequestId 联系 Oncall.",
    "InternalServiceTimeout": "服务侧超时 (常见于测试号 / 未开通业务线). 请确认账号已开通对应业务 (语音通知 / 智能外呼 / Click2Call) 并已申请号码池, 或带 RequestId 联系 Oncall.",
    "200006": "参数有误 (常见于测试号未开通对应业务线 / customerNumberList 为空 / businessLineId 与账号不匹配). 请确认账号已开通该业务并复核入参.",
    "-1": "服务侧返回 '系统异常', 通常是账号在该接口下无业务数据 / 测试号限制. 请用真实业务账号或带 RequestId 联系 Oncall.",
}


class VmsError(Exception):
    def __init__(self, message: str, code: Optional[str] = None,
                 request_id: Optional[str] = None,
                 raw: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.code = code
        self.request_id = request_id
        self.raw = raw or {}


def _utc_xdate() -> str:
    return datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")


def _sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _hmac_sha256(key: bytes, content: str) -> bytes:
    return hmac.new(key, content.encode("utf-8"), hashlib.sha256).digest()


def _norm_query(params: Dict[str, Any]) -> str:
    return "&".join(parse.quote(k, safe="-_.~") + "=" + parse.quote(str(params[k]), safe="-_.~")
                    for k in sorted(params.keys())).replace("+", "%20")


def _signing_key(sk: str, date: str, region: str, service: str) -> bytes:
    kdate = _hmac_sha256(sk.encode("utf-8"), date)
    kregion = _hmac_sha256(kdate, region)
    kservice = _hmac_sha256(kregion, service)
    return _hmac_sha256(kservice, "request")


def _build_authorization(ak: str, sk: str, region: str, xdate: str,
                         method: str, query: Dict[str, Any],
                         headers: Dict[str, str], body: bytes,
                         path: str = "/") -> str:
    body_hash = _sha256_hex(body)
    signed = {k.lower(): v.strip() for k, v in headers.items()
              if k in ("Content-Type", "Content-Md5", "Host") or k.startswith("X-")}
    signed_str = "".join(f"{k}:{signed[k]}\n" for k in sorted(signed.keys()))
    signed_keys = ";".join(sorted(signed.keys()))
    canonical = "\n".join([method, path, _norm_query(query), signed_str, signed_keys, body_hash])
    hashed_req = _sha256_hex(canonical.encode("utf-8"))
    date = xdate[:8]
    credential_scope = f"{date}/{region}/{DEFAULT_SERVICE}/request"
    string_to_sign = "\n".join(["HMAC-SHA256", xdate, credential_scope, hashed_req])
    signature = hmac.new(_signing_key(sk, date, region, DEFAULT_SERVICE),
                         string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
    return (f"HMAC-SHA256 Credential={ak}/{credential_scope}, "
            f"SignedHeaders={signed_keys}, Signature={signature}")


def _resolve_auth_mode() -> str:
    if os.getenv("ARK_SKILL_API_KEY") and os.getenv("ARK_SKILL_API_BASE"):
        return "arkSkill"
    if (os.getenv("VOLC_ACCESS_KEY") and os.getenv("VOLC_SECRET_KEY")) or \
       (os.getenv("VOLCENGINE_ACCESS_KEY") and os.getenv("VOLCENGINE_SECRET_KEY")):
        return "akSk"
    return "none"


def _get_ak_sk() -> Tuple[str, str]:
    ak = os.getenv("VOLC_ACCESS_KEY") or os.getenv("VOLCENGINE_ACCESS_KEY")
    sk = os.getenv("VOLC_SECRET_KEY") or os.getenv("VOLCENGINE_SECRET_KEY")
    if not ak or not sk:
        raise VmsError("缺少 AK/SK. 请配置个人版 AK/SK (arkclaw / openclaw / 其他 agent: VOLC_ACCESS_KEY/VOLC_SECRET_KEY), 或在火山引擎 arkclaw 企业版后台配置 AK/SK 后设置 ARK_SKILL_API_KEY/ARK_SKILL_API_BASE.", code="AccessDenied")
    return ak, sk


def _http_request(method: str, url: str, headers: Dict[str, str], body: bytes,
                  timeout: int = 15) -> Dict[str, Any]:
    req = request.Request(url=url, data=body if body else None,
                          headers=headers, method=method)
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="ignore") if hasattr(e, "read") else ""
        try:
            payload = json.loads(detail) if detail else {}
        except json.JSONDecodeError:
            payload = {"RawBody": detail}
        meta = (payload.get("ResponseMetadata") or {}) if isinstance(payload, dict) else {}
        err = (meta.get("Error") or {}) if isinstance(meta, dict) else {}
        raise VmsError(err.get("Message") or f"HTTP {e.code}: {detail}",
                       code=err.get("Code") or f"HTTP_{e.code}",
                       request_id=meta.get("RequestId"),
                       raw=payload if isinstance(payload, dict) else {}) from e
    except error.URLError as e:
        raise VmsError(f"网络错误: {e}", code="NetworkError") from e
    except json.JSONDecodeError as e:
        raise VmsError("响应不是合法 JSON", code="InvalidResponse") from e


def call_top(action: str, params: Dict[str, Any], *,
             version: str = DEFAULT_VERSION, form: bool = False,
             method: str = "POST", path: str = "/",
             timeout: int = 15) -> Dict[str, Any]:
    region = os.getenv("VOLC_VMS_REGION") or DEFAULT_REGION
    mode = _resolve_auth_mode()
    if mode == "none":
        raise VmsError("未配置鉴权: 请配置个人版 AK/SK (arkclaw / openclaw / 其他 agent: VOLC_ACCESS_KEY/VOLC_SECRET_KEY), "
                       "或在火山引擎 arkclaw 企业版后台配置 AK/SK 后, 设置 ARK_SKILL_API_KEY/ARK_SKILL_API_BASE.",
                       code="AccessDenied")
    method = method.upper()
    is_get = method == "GET"
    if is_get:
        body = b""
        ctype = None
    elif form:
        pairs = []
        for k, v in params.items():
            if isinstance(v, (list, tuple)):
                for item in v:
                    pairs.append(f"{parse.quote(str(k), safe='')}={parse.quote(str(item), safe='')}")
            else:
                pairs.append(f"{parse.quote(str(k), safe='')}={parse.quote(str(v), safe='')}")
        body = "&".join(pairs).encode("utf-8")
        ctype = "application/x-www-form-urlencoded"
    else:
        body = json.dumps(params, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        ctype = "application/json"

    if mode == "arkSkill":
        api_base = os.environ["ARK_SKILL_API_BASE"].rstrip("/")
        api_key = os.environ["ARK_SKILL_API_KEY"]
        qs = {"Action": action, "Version": version}
        if is_get:
            qs.update({k: str(v) for k, v in params.items()})
        url = f"{api_base}?{_norm_query(qs)}"
        headers = {"ServiceName": DEFAULT_SERVICE,
                   "Authorization": f"Bearer {api_key}"}
        if ctype:
            headers["Content-Type"] = ctype
        resp = _http_request(method, url, headers, body, timeout=timeout)
    else:
        ak, sk = _get_ak_sk()
        query = {"Action": action, "Version": version}
        if is_get:
            query.update({k: str(v) for k, v in params.items()})
        url = f"https://{DEFAULT_HOST}{path}?{_norm_query(query)}"
        xdate = _utc_xdate()
        headers = {"Host": DEFAULT_HOST, "X-Date": xdate}
        if ctype:
            headers["Content-Type"] = ctype
        headers["Authorization"] = _build_authorization(
            ak, sk, region, xdate, method, query, headers, body, path=path)
        resp = _http_request(method, url, headers, body, timeout=timeout)

    meta = resp.get("ResponseMetadata") if isinstance(resp, dict) else None
    if isinstance(meta, dict) and isinstance(meta.get("Error"), dict):
        err = meta["Error"]
        raise VmsError(err.get("Message") or "TOP 接口返回错误",
                       code=err.get("Code"), request_id=meta.get("RequestId"), raw=resp)
    return resp


def emit(result: Any) -> None:
    print(json.dumps(result, ensure_ascii=False, indent=2))


def fail(exc: BaseException) -> None:
    if isinstance(exc, VmsError):
        out = {"ok": False, "errorCode": exc.code, "message": str(exc),
               "requestId": exc.request_id,
               "suggest": ERROR_MAP.get(exc.code or "", None)}
    else:
        out = {"ok": False, "errorCode": "InternalError", "message": str(exc)}
    print(json.dumps(out, ensure_ascii=False, indent=2), file=sys.stderr)
    sys.exit(1)
