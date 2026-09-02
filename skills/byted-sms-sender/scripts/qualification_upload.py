# Copyright (c) 2026 Beijing Volcano Engine Technology Co., Ltd. and/or its affiliates.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
"""Upload one qualification image with platform STS and run SMS OCR.

This module is intentionally stdlib-only.  Temporary ImageX credentials stay in
memory and never cross the command output boundary.
"""

from __future__ import annotations

import datetime
import hashlib
import hmac
import json
import re
import sys
import zlib
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple
from urllib import error, parse, request

from api_client import ACTION_REGISTRY, SmsApiClient


IMAGEX_ENDPOINT = "https://imagex.bytedanceapi.com"
IMAGEX_REGION = "cn-north-1"
IMAGEX_SERVICE = "ImageX"
IMAGEX_VERSION = "2018-08-01"
IMAGEX_SERVICE_ID = "2rcdq6eupd"
IMAGEX_APP_ID = "5997"
IMAGEX_USER_ID = "sms"
MAX_IMAGE_BYTES = 2 * 1024 * 1024
ALLOWED_DOCUMENT_TYPES = frozenset({1, 4, 6, 7})
BUSINESS_CHECK_SKIP_TICKET = "force_skip_check"
MOBILE_VERIFY_APP_ID = 482875
MOBILE_VERIFY_SCENE = 3
MOBILE_VERIFY_CHANNEL_ID = 2430
MOBILE_VERIFY_TEMPLATE_IDS = {
    "operator": 59030,
    "responsible": 59029,
}

_UPLOAD_TOKEN_KEYS = (
    "accessKeyId",
    "secretAccessKey",
    "sessionToken",
)
_OCR_FIELDS = (
    "businessCertificateType",
    "businessCertificateName",
    "unifiedSocialCreditIdentifier",
    "businessCertificateValidityPeriodStart",
    "businessCertificateValidityPeriodEnd",
    "legalPersonName",
)
_PERSON_OCR_FIELDS = (
    "personName",
    "personIDCard",
    "isIDCardValid",
)

_NAME_FIELDS = frozenset(
    {
        "personname",
        "legalpersonname",
        "operatorpersonname",
        "responsiblepersonname",
        "operatorname",
        "responsiblename",
    }
)
_ID_FIELDS = frozenset(
    {"personidcard", "idcard", "idcardnumber", "identitynumber"}
)
_MOBILE_FIELDS = frozenset(
    {
        "personmobile",
        "mobile",
        "phone",
        "phonenumber",
        "operatormobile",
        "responsiblemobile",
        "legalmobile",
    }
)
_FREE_TEXT_FIELDS = frozenset(
    {"message", "errormessage", "detail", "reason", "description"}
)
_SECRET_FIELDS = frozenset(
    {
        "accesskey",
        "accesskeyid",
        "secretkey",
        "secretaccesskey",
        "sessiontoken",
        "securitytoken",
        "authorization",
        "auth",
        "cookie",
        "setcookie",
        "token",
        "ticket",
        "businesscheckticket",
        "operatorcheckticket",
        "responsiblecheckticket",
        "legalcheckticket",
        "sessionkey",
        "decryptkeys",
    }
)
_IMAGE_FIELDS = frozenset(
    {
        "image",
        "imageuri",
        "imageuris",
        "uri",
        "filecontent",
        "fileurl",
        "fileuri",
        "filename",
        "imageurl",
        "imageurls",
        "url",
        "signedurl",
        "uploadurl",
        "objectkey",
        "storeuri",
        "successoids",
        "certificate",
        "idcardfrontimage",
        "idcardbackimage",
        "uploadhosts",
        "uploadheader",
    }
)
_MOBILE_PATTERN = re.compile(r"(?<![0-9])1[3-9][0-9]{9}(?![0-9])")
_ID_PATTERN = re.compile(r"(?<![0-9A-Za-z])[0-9]{17}[0-9Xx](?![0-9A-Za-z])")
_URL_PATTERN = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)


class QualificationUploadError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        request_id: str = "",
        log_id: str = "",
        outcome_unknown: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.request_id = request_id or None
        self.log_id = log_id or None
        self.outcome_unknown = outcome_unknown


class QualificationResponse(dict):
    """A decoded response body with its public transport diagnostics."""

    def __init__(
        self,
        value: Mapping[str, Any],
        *,
        http_status: Optional[int],
        request_id: str,
        log_id: str,
    ) -> None:
        super().__init__(value)
        self.http_status = http_status
        self.request_id = request_id
        self.log_id = log_id


def _diagnostic_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def _mask_name(value: str) -> str:
    return "*" if len(value) <= 1 else value[0] + "*" * (len(value) - 1)


def _mask_id_card(value: str) -> str:
    if len(value) < 10:
        return "*" * len(value)
    return value[:6] + "*" * (len(value) - 10) + value[-4:]


def _mask_mobile(value: str) -> str:
    if len(value) != 11:
        return "*" * len(value)
    return value[:3] + "****" + value[-4:]


def _protected_summary(value: Any, kind: str) -> Dict[str, Any]:
    summary: Dict[str, Any] = {"protected": kind, "present": bool(value)}
    if isinstance(value, (list, tuple, Mapping)):
        summary["count"] = len(value)
    return summary


def _add_protected_replacements(
    value: Any, replacement: str, result: Dict[str, str]
) -> None:
    if isinstance(value, str):
        if value:
            result[value] = replacement
        return
    if isinstance(value, Mapping):
        for item in value.values():
            _add_protected_replacements(item, replacement, result)
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            _add_protected_replacements(item, replacement, result)


def _diagnostic_replacements(value: Any) -> Dict[str, str]:
    replacements: Dict[str, str] = {}
    if not isinstance(value, Mapping):
        return replacements
    for key, item in value.items():
        field = _diagnostic_key(key)
        if field in _SECRET_FIELDS:
            _add_protected_replacements(item, "[凭证已隐藏]", replacements)
        elif field in _IMAGE_FIELDS:
            _add_protected_replacements(item, "[图片已隐藏]", replacements)
        elif isinstance(item, str) and item:
            if field in _NAME_FIELDS:
                replacements[item] = _mask_name(item)
            elif field in _ID_FIELDS:
                replacements[item] = _mask_id_card(item)
            elif field in _MOBILE_FIELDS:
                replacements[item] = _mask_mobile(item)
        elif isinstance(item, Mapping):
            replacements.update(_diagnostic_replacements(item))
        elif isinstance(item, (list, tuple)):
            for nested in item:
                replacements.update(_diagnostic_replacements(nested))
    return replacements


def _mask_diagnostic_text(value: str, replacements: Mapping[str, str]) -> str:
    masked = _ID_PATTERN.sub(lambda match: _mask_id_card(match.group(0)), value)
    masked = _MOBILE_PATTERN.sub(lambda match: _mask_mobile(match.group(0)), masked)
    for raw, replacement in sorted(
        replacements.items(), key=lambda item: len(item[0]), reverse=True
    ):
        masked = masked.replace(raw, replacement)
    return _URL_PATTERN.sub("[地址已隐藏]", masked)


def _diagnostic_value(
    value: Any,
    *,
    field: str = "",
    replacements: Optional[Mapping[str, str]] = None,
) -> Any:
    replacements = replacements or {}
    normalized = _diagnostic_key(field)
    if normalized in _SECRET_FIELDS:
        return _protected_summary(value, "credential")
    if normalized in _IMAGE_FIELDS:
        return _protected_summary(value, "image")
    if isinstance(value, Mapping):
        return {
            str(key): _diagnostic_value(
                item,
                field=str(key),
                replacements=replacements,
            )
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [
            _diagnostic_value(item, replacements=replacements) for item in value
        ]
    if isinstance(value, str):
        if normalized in _NAME_FIELDS:
            return _mask_name(value)
        if normalized in _ID_FIELDS:
            return _mask_id_card(value)
        if normalized in _MOBILE_FIELDS:
            return _mask_mobile(value)
        if normalized in _FREE_TEXT_FIELDS:
            return _mask_diagnostic_text(value, replacements)
        return value
    return value


def _qualification_exchange_event(
    stage: str,
    method: str,
    request_value: Mapping[str, Any],
    response_value: Mapping[str, Any],
    *,
    context: Optional[Mapping[str, Any]] = None,
    http_status: Optional[int] = None,
    request_id: str = "",
    log_id: str = "",
) -> Dict[str, Any]:
    replacements = _diagnostic_replacements(request_value)
    replacements.update(_diagnostic_replacements(response_value))
    return {
        "event": "qualification_exchange",
        "stage": stage,
        "method": method.upper(),
        "context": _diagnostic_value(context or {}, replacements=replacements),
        "request": _diagnostic_value(request_value, replacements=replacements),
        "response": _diagnostic_value(response_value, replacements=replacements),
        "httpStatus": http_status,
        "requestId": request_id or None,
        "logId": log_id or None,
    }


def _emit_qualification_exchange(
    stage: str,
    method: str,
    request_value: Mapping[str, Any],
    response_value: Mapping[str, Any],
    *,
    context: Optional[Mapping[str, Any]] = None,
    http_status: Optional[int] = None,
    request_id: str = "",
    log_id: str = "",
) -> None:
    event = _qualification_exchange_event(
        stage,
        method,
        request_value,
        response_value,
        context=context,
        http_status=http_status,
        request_id=request_id,
        log_id=log_id,
    )
    sys.stderr.write(
        "QUALIFICATION_EXCHANGE "
        + json.dumps(event, ensure_ascii=False, separators=(",", ":"))
        + "\n"
    )
    sys.stderr.flush()


@dataclass(frozen=True)
class ImageXCredentials:
    access_key: str
    secret_key: str
    session_token: str


def _response_request_id(payload: Mapping[str, Any], headers: Any = None) -> str:
    transport_request_id = getattr(payload, "request_id", "")
    if transport_request_id:
        return str(transport_request_id)
    metadata = payload.get("ResponseMetadata")
    if isinstance(metadata, Mapping):
        request_id = metadata.get("RequestId") or metadata.get("RequestID")
        if request_id:
            return str(request_id)
    request_id = payload.get("RequestId") or payload.get("RequestID")
    if request_id:
        return str(request_id)
    return _header_value(headers, "X-Tt-RequestId", "X-Request-Id", "X-RequestId")


def _response_result(payload: Mapping[str, Any], stage: str) -> Mapping[str, Any]:
    metadata = payload.get("ResponseMetadata")
    if isinstance(metadata, Mapping):
        failure = metadata.get("Error")
        if isinstance(failure, Mapping):
            code = str(failure.get("Code") or failure.get("CodeN") or "api_error")
            message = str(
                failure.get("Message")
                or failure.get("message")
                or "{} failed.".format(stage)
            )
            raise QualificationUploadError(
                code,
                message,
                request_id=_response_request_id(payload),
                log_id=_response_log_id(payload, None),
            )
    http_status = getattr(payload, "http_status", None)
    if http_status is not None and not 200 <= http_status < 300:
        raise QualificationUploadError(
            "http_{}".format(http_status),
            "{} returned HTTP {}.".format(stage, http_status),
            request_id=_response_request_id(payload),
            log_id=_response_log_id(payload, None),
        )
    result = payload.get("Result")
    if not isinstance(result, Mapping):
        raise QualificationUploadError(
            "invalid_response",
            "{} returned no structured result.".format(stage),
            request_id=_response_request_id(payload),
            log_id=_response_log_id(payload, None),
        )
    return result


def _response_value(payload: Mapping[str, Any], stage: str) -> Any:
    """Return a successful Result value, including scalar write results."""
    metadata = payload.get("ResponseMetadata")
    if isinstance(metadata, Mapping):
        failure = metadata.get("Error")
        if isinstance(failure, Mapping):
            code = str(failure.get("Code") or failure.get("CodeN") or "api_error")
            raise QualificationUploadError(
                code,
                "{} failed.".format(stage),
                request_id=_response_request_id(payload),
                log_id=_response_log_id(payload, None),
            )
    http_status = getattr(payload, "http_status", None)
    if http_status is not None and not 200 <= http_status < 300:
        raise QualificationUploadError(
            "http_{}".format(http_status),
            "{} returned HTTP {}.".format(stage, http_status),
            request_id=_response_request_id(payload),
            log_id=_response_log_id(payload, None),
        )
    if "Result" not in payload:
        raise QualificationUploadError(
            "invalid_response",
            "{} returned no structured result.".format(stage),
            request_id=_response_request_id(payload),
            log_id=_response_log_id(payload, None),
        )
    return payload["Result"]


def _header_value(headers: Any, *names: str) -> str:
    if headers is None:
        return ""
    for name in names:
        try:
            value = headers.get(name)
        except AttributeError:
            value = None
        if value:
            return str(value)
    return ""


def _response_log_id(payload: Mapping[str, Any], headers: Any) -> str:
    transport_log_id = getattr(payload, "log_id", "")
    if transport_log_id:
        return str(transport_log_id)
    header_value = _header_value(headers, "X-Tt-Logid", "X-Tt-Log-Id")
    if header_value:
        return header_value
    metadata = payload.get("ResponseMetadata")
    if isinstance(metadata, Mapping):
        return str(metadata.get("LogId") or metadata.get("LogID") or "")
    return str(payload.get("LogId") or payload.get("LogID") or "")


def _open_json(
    req: request.Request,
    timeout: float,
    stage: str,
    *,
    diagnostic_request: Optional[Mapping[str, Any]] = None,
    diagnostic_context: Optional[Mapping[str, Any]] = None,
) -> Mapping[str, Any]:
    request_value = dict(diagnostic_request or {})
    method = req.get_method()
    status_code: Optional[int] = None
    headers: Any = None
    try:
        with request.urlopen(req, timeout=timeout) as response:
            status_code = response.getcode()
            headers = response.headers
            data = response.read()
    except error.HTTPError as exc:
        status_code = exc.code
        headers = exc.headers
        data = exc.read() if hasattr(exc, "read") else b""
    except (OSError, error.URLError, TimeoutError) as exc:
        _emit_qualification_exchange(
            stage,
            method,
            request_value,
            {
                "error": {
                    "code": "network_error",
                    "message": "Request could not reach the service.",
                }
            },
            context=diagnostic_context,
        )
        raise QualificationUploadError(
            "network_error", "{} could not reach the service.".format(stage)
        ) from exc
    try:
        value = json.loads(data.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        _emit_qualification_exchange(
            stage,
            method,
            request_value,
            {
                "error": {
                    "code": "invalid_response",
                    "message": "Response was not valid JSON.",
                },
                "bodySize": len(data),
            },
            context=diagnostic_context,
            http_status=status_code,
            request_id=_response_request_id({}, headers),
            log_id=_header_value(headers, "X-Tt-Logid", "X-Tt-Log-Id"),
        )
        raise QualificationUploadError(
            "invalid_response",
            "{} returned an invalid response.".format(stage),
            request_id=_response_request_id({}, headers),
            log_id=_header_value(headers, "X-Tt-Logid", "X-Tt-Log-Id"),
        ) from exc
    if not isinstance(value, Mapping):
        _emit_qualification_exchange(
            stage,
            method,
            request_value,
            {
                "error": {
                    "code": "invalid_response",
                    "message": "Response root was not an object.",
                }
            },
            context=diagnostic_context,
            http_status=status_code,
            request_id=_response_request_id({}, headers),
            log_id=_header_value(headers, "X-Tt-Logid", "X-Tt-Log-Id"),
        )
        raise QualificationUploadError(
            "invalid_response",
            "{} returned an invalid response.".format(stage),
            request_id=_response_request_id({}, headers),
            log_id=_header_value(headers, "X-Tt-Logid", "X-Tt-Log-Id"),
        )
    response_request_id = _response_request_id(value, headers)
    response_log_id = _response_log_id(value, headers)
    _emit_qualification_exchange(
        stage,
        method,
        request_value,
        value,
        context=diagnostic_context,
        http_status=status_code,
        request_id=response_request_id,
        log_id=response_log_id,
    )
    return QualificationResponse(
        value,
        http_status=status_code,
        request_id=response_request_id,
        log_id=response_log_id,
    )


def _sms_agent_call(
    client: SmsApiClient,
    action: str,
    params: Mapping[str, Any],
    *,
    diagnostic_context: Optional[Mapping[str, Any]] = None,
) -> QualificationResponse:
    """Call one published Agent Action and preserve qualification diagnostics."""
    spec = ACTION_REGISTRY.get(action)
    if spec is None:
        raise QualificationUploadError(
            "unknown_action",
            "{} is not in the published Action contract.".format(action),
        )
    method = spec.method
    request_value = dict(params)
    payload = client.call(action, request_value)
    diagnostic_request = dict(request_value)
    if action == "CheckSmsVerifyCodeByMobile" and "code" in diagnostic_request:
        diagnostic_request["code"] = _protected_summary(
            diagnostic_request["code"], "verification_code"
        )
    if not isinstance(payload, Mapping):
        _emit_qualification_exchange(
            action,
            method,
            diagnostic_request,
            {"error": {"code": "invalid_response"}},
            context=diagnostic_context,
        )
        raise QualificationUploadError(
            "invalid_response", "{} returned an invalid response.".format(action)
        )

    request_id = str(payload.get("request_id") or "")
    log_id = str(payload.get("log_id") or "")
    _emit_qualification_exchange(
        action,
        method,
        diagnostic_request,
        payload,
        context=diagnostic_context,
        request_id=request_id,
        log_id=log_id,
    )
    if payload.get("success") is not True:
        failure = payload.get("error")
        if not isinstance(failure, Mapping):
            raise QualificationUploadError(
                "invalid_response",
                "{} returned an invalid error response.".format(action),
                request_id=request_id,
                log_id=log_id,
            )
        code = str(failure.get("code") or "api_error")
        message = str(failure.get("message") or "{} failed.".format(action))
        raise QualificationUploadError(
            code,
            message,
            request_id=request_id,
            log_id=log_id,
            outcome_unknown=bool(failure.get("outcome_unknown")),
        )
    if "result" not in payload:
        raise QualificationUploadError(
            "invalid_response",
            "{} returned no result.".format(action),
            request_id=request_id,
            log_id=log_id,
        )
    return QualificationResponse(
        {
            "ResponseMetadata": {"RequestId": request_id} if request_id else {},
            "Result": payload["result"],
        },
        http_status=200,
        request_id=request_id,
        log_id=log_id,
    )


def send_mobile_verification_code(
    client: SmsApiClient,
    mobile: str,
    role: str,
) -> str:
    """Send one qualification mobile verification code."""
    if role not in ("operator", "responsible"):
        raise QualificationUploadError(
            "invalid_role", "手机号验证码角色无效。"
        )
    action = "SendSmsVerifyCodeByMobile"
    payload = _sms_agent_call(
        client,
        action,
        {
            "appId": MOBILE_VERIFY_APP_ID,
            "scene": MOBILE_VERIFY_SCENE,
            "codeType": 0,
            "mobile": mobile,
            "templateId": MOBILE_VERIFY_TEMPLATE_IDS[role],
            "channelId": MOBILE_VERIFY_CHANNEL_ID,
        },
        diagnostic_context={"phase": "mobile_code_send", "role": role},
    )
    result = _response_result(payload, action)
    message_id = result.get("messageId")
    if not isinstance(message_id, str) or not message_id.strip():
        raise QualificationUploadError(
            "invalid_response",
            "验证码发送接口未返回消息 ID。",
            request_id=_response_request_id(payload),
            log_id=_response_log_id(payload, None),
        )
    return message_id.strip()


def check_mobile_verification_code(
    client: SmsApiClient,
    mobile: str,
    code: str,
    role: str,
) -> None:
    """Check one qualification mobile verification code."""
    if role not in ("operator", "responsible"):
        raise QualificationUploadError(
            "invalid_role", "手机号验证码角色无效。"
        )
    action = "CheckSmsVerifyCodeByMobile"
    payload = _sms_agent_call(
        client,
        action,
        {
            "appId": MOBILE_VERIFY_APP_ID,
            "scene": MOBILE_VERIFY_SCENE,
            "mobile": mobile,
            "code": code,
            "func": 2,
        },
        diagnostic_context={"phase": "mobile_code_check", "role": role},
    )
    result = _response_result(payload, action)
    status = result.get("status")
    if isinstance(status, bool) or not isinstance(status, int):
        raise QualificationUploadError(
            "invalid_response",
            "验证码校验接口返回了无效状态。",
            request_id=_response_request_id(payload),
            log_id=_response_log_id(payload, None),
        )
    if status == 0:
        return
    if status == 1:
        raise QualificationUploadError(
            "mobile_code_invalid", "验证码不正确，请重新输入。"
        )
    if status == 2:
        raise QualificationUploadError(
            "mobile_code_expired", "验证码已过期，请重新获取。"
        )
    raise QualificationUploadError(
        "invalid_response",
        "验证码校验接口返回了未知状态。",
        request_id=_response_request_id(payload),
        log_id=_response_log_id(payload, None),
    )


def get_account_ident_rank(client: SmsApiClient) -> Dict[str, bool]:
    """Load the server-owned qualification requirements for the current account."""
    action = "GetAccountIdentRankForAgent"
    payload = _sms_agent_call(
        client,
        action,
        {},
        diagnostic_context={"phase": "requirements"},
    )
    result = _response_result(payload, action)
    fields = (
        "isOnlyTwoElement",
        "isSkipOtherUse",
        "needOtherUseCheck",
        "operatorThreeElement",
        "needOperatorImage",
        "needOperatorMobile",
        "responsibleThreeElement",
        "needResponsibleImage",
        "needResponsibleMobile",
        "needBusinessCertificateImage",
    )
    if any(field not in result or not isinstance(result[field], bool) for field in fields):
        raise QualificationUploadError(
            "invalid_response",
            "{} returned incomplete requirements.".format(action),
            request_id=_response_request_id(payload),
            log_id=_response_log_id(payload, None),
        )
    return {field: result[field] for field in fields}


def get_account_identity(client: SmsApiClient) -> Dict[str, str]:
    """Return qualification-relevant identity fields for the current account."""
    action = "ListAllSmsProduct"
    payload = _sms_agent_call(
        client,
        action,
        {},
        diagnostic_context={"phase": "account_identity"},
    )
    result = _response_result(payload, action)
    business_name = result.get("businessName")
    user_type = result.get("userType")
    if not isinstance(business_name, str) or not business_name.strip():
        raise QualificationUploadError(
            "invalid_response",
            "当前火山账号未返回企业名称，暂时无法创建资质。",
            request_id=_response_request_id(payload),
            log_id=_response_log_id(payload, None),
        )
    if not isinstance(user_type, str) or not user_type.strip():
        raise QualificationUploadError(
            "invalid_response",
            "当前火山账号未返回用户类型，暂时无法创建资质。",
            request_id=_response_request_id(payload),
            log_id=_response_log_id(payload, None),
        )
    return {
        "businessName": business_name.strip(),
        "userType": user_type.strip().lower(),
    }


def get_account_business_name(client: SmsApiClient) -> str:
    """Return the enterprise name bound to the current Volcengine account."""
    return get_account_identity(client)["businessName"]


def normalize_check_status(value: Any) -> str:
    """Normalize documented check codes and the service's rune-encoded form."""
    if isinstance(value, bool):
        return ""
    if isinstance(value, int):
        return str(value) if 0 <= value <= 3 else ""
    if not isinstance(value, str):
        return ""
    if value in ("0", "1", "2", "3"):
        return value
    if len(value) == 1 and 0 <= ord(value) <= 3:
        return str(ord(value))
    return ""


def check_signature_qualification_information(
    client: SmsApiClient,
    target: str,
    params: Mapping[str, Any],
) -> Dict[str, Any]:
    """Run one customer-requested qualification check without exposing its ticket."""
    if target not in ("business", "legal", "operator", "responsible"):
        raise QualificationUploadError(
            "qualification_check_invalid", "不支持当前信息校验。"
        )
    action = (
        "ThreeElementEnterpriseCheckForAgent"
        if target == "business"
        else "ThreeElementPersonCheckForAgent"
    )
    payload = _sms_agent_call(
        client,
        action,
        params,
        diagnostic_context={"phase": "verification", "role": target},
    )
    result = _response_result(payload, action)
    status = normalize_check_status(result.get("status"))
    ticket = str(result.get("ticket") or "")
    if status not in ("0", "1", "2", "3"):
        raise QualificationUploadError(
            "invalid_response",
            "校验服务没有返回可识别的校验状态，请稍后重试。",
            request_id=_response_request_id(payload),
            log_id=_response_log_id(payload, None),
        )
    matched = status == "0" and bool(ticket)
    if status == "0" and not ticket:
        raise QualificationUploadError(
            "invalid_response",
            "校验服务没有返回有效结果，请稍后重试。",
            request_id=_response_request_id(payload),
            log_id=_response_log_id(payload, None),
        )
    if not matched:
        ticket = BUSINESS_CHECK_SKIP_TICKET if target == "business" else ""
    return {
        "target": target,
        "status": status,
        "matched": matched,
        "canContinue": target == "business" or matched,
        "ticket": ticket,
    }


def create_signature_qualification(
    client: SmsApiClient,
    params: Mapping[str, Any],
) -> Dict[str, Any]:
    """Create one review order with tickets obtained from explicit form checks.

    The caller must preserve the Agent Action's structured outcome flag and must
    never retry an uncertain write automatically.
    """
    body = dict(params)
    business = body.get("businessInfo")
    operator = body.get("operatorPerson")
    responsible = body.get("responsiblePersonInfo")
    if not all(isinstance(value, Mapping) for value in (business, operator, responsible)):
        raise QualificationUploadError(
            "qualification_draft_invalid", "The qualification draft is incomplete."
        )
    required_tickets = (
        "businessCheckTicket",
        "operatorCheckTicket",
        "responsibleCheckTicket",
    )
    if any(not str(body.get(name) or "") for name in required_tickets):
        raise QualificationUploadError(
            "qualification_check_required", "请先完成页面中的信息校验。"
        )
    legal = body.get("legalPerson")
    if (
        isinstance(legal, Mapping)
        and int(legal.get("certificateType") or 0) == 0
        and legal.get("personIDCard")
        and not str(body.get("legalCheckTicket") or "")
    ):
        raise QualificationUploadError(
            "qualification_check_required", "请先完成法人信息校验。"
        )
    if (
        body.get("sameOperator") is True
        and body["responsibleCheckTicket"] != body["operatorCheckTicket"]
    ):
        raise QualificationUploadError(
            "qualification_check_invalid", "经办人校验结果已变化，请重新校验。"
        )
    if int(body.get("purpose") or 0) == 2 and (
        not str(body.get("authorizer") or "").strip()
        or not str(body.get("authorizee") or "").strip()
    ):
        raise QualificationUploadError(
            "qualification_draft_invalid", "请完善授权方和被授权方信息。"
        )

    action = "ApplySignatureIdentificationForAgent"
    try:
        payload = _sms_agent_call(
            client,
            action,
            body,
            diagnostic_context={"phase": "submission"},
        )
        result = _response_value(payload, action)
        qualification_id = int(result)
    except (TypeError, ValueError) as exc:
        raise QualificationUploadError(
            "invalid_response",
            "{} returned no qualification id.".format(action),
            request_id=_response_request_id(payload),
            log_id=_response_log_id(payload, None),
            outcome_unknown=True,
        ) from exc
    if qualification_id <= 0:
        raise QualificationUploadError(
            "invalid_response",
            "{} returned no qualification id.".format(action),
            request_id=_response_request_id(payload),
            log_id=_response_log_id(payload, None),
            outcome_unknown=True,
        )
    return {
        "qualificationId": qualification_id,
        "requestId": _response_request_id(payload) or None,
        "logId": _response_log_id(payload, None) or None,
        "status": "submitted_for_review",
    }


def _aws_hmac(key: bytes, value: str) -> bytes:
    return hmac.new(key, value.encode("utf-8"), hashlib.sha256).digest()


def _aws_sign(
    method: str,
    query: Sequence[Tuple[str, str]],
    body: bytes,
    credentials: ImageXCredentials,
    headers: Optional[Mapping[str, str]] = None,
) -> request.Request:
    endpoint = parse.urlsplit(IMAGEX_ENDPOINT)
    canonical_query = "&".join(
        "{}={}".format(
            parse.quote(str(key), safe="-_.~"),
            parse.quote(str(value), safe="-_.~"),
        )
        for key, value in sorted(query)
    )
    now = datetime.datetime.now(datetime.timezone.utc)
    x_date = now.strftime("%Y%m%dT%H%M%SZ")
    short_date = x_date[:8]
    content_type = (
        "application/json"
        if method.upper() == "POST"
        else "application/x-www-form-urlencoded; charset=utf-8"
    )
    body_hash = hashlib.sha256(body).hexdigest()
    signed_values = {
        "content-type": content_type,
        "host": endpoint.netloc,
        "x-amz-content-sha256": body_hash,
        "x-amz-date": x_date,
        "x-amz-security-token": credentials.session_token,
    }
    signed_names = ";".join(sorted(signed_values))
    canonical_headers = "".join(
        "{}:{}\n".format(name, signed_values[name].strip())
        for name in sorted(signed_values)
    )
    canonical_request = "\n".join(
        [
            method.upper(),
            "/",
            canonical_query,
            canonical_headers,
            signed_names,
            body_hash,
        ]
    )
    scope = "{}/{}/{}/aws4_request".format(
        short_date, IMAGEX_REGION, IMAGEX_SERVICE
    )
    string_to_sign = "\n".join(
        [
            "AWS4-HMAC-SHA256",
            x_date,
            scope,
            hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
        ]
    )
    date_key = _aws_hmac(("AWS4" + credentials.secret_key).encode("utf-8"), short_date)
    region_key = _aws_hmac(date_key, IMAGEX_REGION)
    service_key = _aws_hmac(region_key, IMAGEX_SERVICE)
    signing_key = _aws_hmac(service_key, "aws4_request")
    signature = hmac.new(
        signing_key, string_to_sign.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    request_headers: Dict[str, str] = {
        "Host": endpoint.netloc,
        "Content-Type": content_type,
        "X-Amz-Content-Sha256": body_hash,
        "X-Amz-Date": x_date,
        "X-Amz-Security-Token": credentials.session_token,
        "Authorization": (
            "AWS4-HMAC-SHA256 Credential={}/{}, SignedHeaders={}, Signature={}"
        ).format(credentials.access_key, scope, signed_names, signature),
    }
    request_headers.update(dict(headers or {}))
    url = "{}?{}".format(IMAGEX_ENDPOINT.rstrip("/") + "/", canonical_query)
    return request.Request(
        url,
        data=body if method.upper() != "GET" else None,
        headers=request_headers,
        method=method.upper(),
    )


def _image_credentials(upload_result: Mapping[str, Any]) -> ImageXCredentials:
    token = upload_result.get("token")
    if not isinstance(token, Mapping) or not all(token.get(key) for key in _UPLOAD_TOKEN_KEYS):
        raise QualificationUploadError(
            "upload_credentials_unavailable",
            "The SMS service returned no usable material-upload credentials.",
        )
    return ImageXCredentials(
        str(token["accessKeyId"]),
        str(token["secretAccessKey"]),
        str(token["sessionToken"]),
    )


def _load_image_credentials(client: SmsApiClient) -> ImageXCredentials:
    action = "GetMUploadParam"
    payload = _sms_agent_call(
        client,
        action,
        {},
        diagnostic_context={"phase": "material_upload"},
    )
    return _image_credentials(_response_result(payload, action))


def _validated_image_bytes(data: bytes, content_type: str) -> Tuple[bytes, str]:
    if not data or len(data) > MAX_IMAGE_BYTES:
        raise QualificationUploadError(
            "invalid_image_size", "Use a non-empty JPG, JPEG, or PNG no larger than 2 MB."
        )
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return data, "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return data, "image/jpeg"
    raise QualificationUploadError(
        "invalid_image_type",
        "Use a JPEG or PNG image, not {}.".format(content_type or "this file type"),
    )


def _apply_image_upload(
    credentials: ImageXCredentials, *, timeout: float
) -> Mapping[str, Any]:
    query = (
        ("Action", "ApplyImageUpload"),
        ("Version", IMAGEX_VERSION),
        ("ServiceId", IMAGEX_SERVICE_ID),
        ("NeedFallback", "true"),
        ("UploadNum", "1"),
        ("uid", IMAGEX_USER_ID),
        ("appid", IMAGEX_APP_ID),
    )
    req = _aws_sign(
        "GET",
        query,
        b"",
        credentials,
        {
            "X-Vod-Upload-AppID": IMAGEX_APP_ID,
            "X-Vod-Upload-UserID": IMAGEX_USER_ID,
        },
    )
    payload = _open_json(
        req,
        timeout,
        "ApplyImageUpload",
        diagnostic_request=dict(query),
        diagnostic_context={"phase": "material_upload"},
    )
    return _response_result(payload, "ApplyImageUpload")


def _upload_image_bytes(
    upload_address: Mapping[str, Any],
    data: bytes,
    content_type: str,
    *,
    timeout: float,
) -> Tuple[str, str]:
    hosts = upload_address.get("UploadHosts")
    stores = upload_address.get("StoreInfos")
    if not isinstance(hosts, list) or not hosts or not isinstance(stores, list) or len(stores) != 1:
        raise QualificationUploadError(
            "invalid_upload_address", "ImageX returned an invalid upload address."
        )
    host = str(hosts[0]).strip()
    parsed_host = parse.urlsplit("https://" + host)
    if (
        not host
        or parsed_host.hostname != host
        or parsed_host.port is not None
        or parsed_host.path not in ("", "/")
    ):
        raise QualificationUploadError(
            "invalid_upload_address", "ImageX returned an invalid upload host."
        )
    store = stores[0]
    if not isinstance(store, Mapping):
        raise QualificationUploadError(
            "invalid_upload_address", "ImageX returned invalid upload metadata."
        )
    store_uri = str(store.get("StoreUri") or "").strip()
    authorization = str(store.get("Auth") or "").strip()
    bucket, separator, object_key = store_uri.partition("/")
    if not separator or not bucket or not object_key or not authorization:
        raise QualificationUploadError(
            "invalid_upload_address", "ImageX returned invalid upload metadata."
        )
    url = "https://{}/upload/v1/{}/{}".format(
        host,
        parse.quote(bucket, safe="-_.~"),
        parse.quote(object_key, safe="/-_.~"),
    )
    headers = {
        "Authorization": authorization,
        "X-Upload-Content-CRC32": "{:08x}".format(zlib.crc32(data) & 0xFFFFFFFF),
        "Specified-Content-Type": content_type,
    }
    upload_headers = upload_address.get("UploadHeader")
    if isinstance(upload_headers, Mapping):
        for key, value in upload_headers.items():
            if isinstance(key, str) and isinstance(value, str):
                headers[key] = value
    payload = _open_json(
        request.Request(url, data=data, headers=headers, method="POST"),
        timeout,
        "ImageX upload",
        diagnostic_request={
            "contentType": content_type,
            "imageSizeBytes": len(data),
        },
        diagnostic_context={"phase": "material_upload"},
    )
    if int(payload.get("code") or 0) != 2000:
        raise QualificationUploadError("image_upload_failed", "Image upload failed.")
    return store_uri, str(upload_address.get("SessionKey") or "")


def _commit_image_upload(
    credentials: ImageXCredentials,
    session_key: str,
    store_uri: str,
    *,
    timeout: float,
) -> str:
    body_document = {
        "SessionKey": session_key,
        "SuccessOids": [store_uri],
        "Functions": [],
        "PostProcess": [],
        "DecryptKeys": [],
    }
    body = json.dumps(
        body_document,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    query = (
        ("Action", "CommitImageUpload"),
        ("Version", IMAGEX_VERSION),
        ("ServiceId", IMAGEX_SERVICE_ID),
        ("SkipMeta", "true"),
    )
    req = _aws_sign(
        "POST",
        query,
        body,
        credentials,
        {
            "X-Vod-Upload-AppID": IMAGEX_APP_ID,
            "X-Vod-Upload-UserID": IMAGEX_USER_ID,
        },
    )
    payload = _open_json(
        req,
        timeout,
        "CommitImageUpload",
        diagnostic_request=body_document,
        diagnostic_context={"phase": "material_upload"},
    )
    result = _response_result(payload, "CommitImageUpload")
    results = result.get("Results")
    if not isinstance(results, list) or not results or not isinstance(results[0], Mapping):
        raise QualificationUploadError(
            "invalid_response", "ImageX returned no committed image."
        )
    image = results[0]
    image_uri = str(image.get("Uri") or "").strip()
    if int(image.get("UriStatus") or 0) != 2000 or not image_uri:
        raise QualificationUploadError("image_commit_failed", "Image upload commit failed.")
    return image_uri


def _upload_one_image(
    credentials: ImageXCredentials,
    data: bytes,
    content_type: str,
    *,
    timeout: float,
) -> str:
    apply_result = _apply_image_upload(credentials, timeout=timeout)
    upload_address = apply_result.get("UploadAddress")
    if not isinstance(upload_address, Mapping):
        raise QualificationUploadError(
            "invalid_upload_address", "ImageX returned no upload address."
        )
    store_uri, session_key = _upload_image_bytes(
        upload_address, data, content_type, timeout=timeout
    )
    return _commit_image_upload(
        credentials, session_key, store_uri, timeout=timeout
    )


def upload_qualification_file_bytes(
    client: SmsApiClient,
    data: bytes,
    content_type: str,
) -> Dict[str, str]:
    """Upload one image material and return only its internal URI metadata."""
    data, content_type = _validated_image_bytes(data, content_type)
    timeout = max(1.0, float(client._timeout))
    image_credentials = _load_image_credentials(client)
    try:
        image_uri = _upload_one_image(
            image_credentials, data, content_type, timeout=timeout
        )
    finally:
        image_credentials = None
    return {
        "imageUri": image_uri,
        "imageSuffix": "png" if content_type == "image/png" else "jpg",
    }


def upload_and_ocr_business_certificate_bytes(
    client: SmsApiClient,
    data: bytes,
    content_type: str,
    business_certificate_type: int = 1,
) -> Dict[str, Any]:
    if business_certificate_type not in ALLOWED_DOCUMENT_TYPES:
        raise QualificationUploadError(
            "invalid_document_type", "Unsupported business certificate type."
        )
    data, content_type = _validated_image_bytes(data, content_type)
    image_suffix = "png" if content_type == "image/png" else "jpg"
    timeout = max(1.0, float(client._timeout))
    image_credentials = _load_image_credentials(client)
    try:
        image_uri = _upload_one_image(
            image_credentials, data, content_type, timeout=timeout
        )
    finally:
        image_credentials = None

    ocr_action = "GetOCRLicenseForAgent"
    ocr_payload = _sms_agent_call(
        client,
        ocr_action,
        {
            "businessCertificateType": business_certificate_type,
            "certificate": image_uri,
        },
        diagnostic_context={"phase": "ocr", "document": "business"},
    )
    ocr_result = _response_result(ocr_payload, ocr_action)
    return {
        "status": "ocr_completed",
        "imageUri": image_uri,
        "imageSuffix": image_suffix,
        "document": {
            key: ocr_result.get(key)
            for key in _OCR_FIELDS
            if key in ocr_result
        },
        "next": "confirm_ocr_fields",
    }


def upload_and_ocr_identity_document_bytes(
    client: SmsApiClient,
    front_data: bytes,
    front_content_type: str,
    back_data: bytes,
    back_content_type: str,
) -> Dict[str, Any]:
    front_data, front_content_type = _validated_image_bytes(
        front_data, front_content_type
    )
    back_data, back_content_type = _validated_image_bytes(
        back_data, back_content_type
    )
    image_suffixes = {
        "front": "png" if front_content_type == "image/png" else "jpg",
        "back": "png" if back_content_type == "image/png" else "jpg",
    }
    timeout = max(1.0, float(client._timeout))
    image_credentials = _load_image_credentials(client)
    try:
        front_uri = _upload_one_image(
            image_credentials, front_data, front_content_type, timeout=timeout
        )
        back_uri = _upload_one_image(
            image_credentials, back_data, back_content_type, timeout=timeout
        )
    finally:
        image_credentials = None

    return ocr_identity_document_images(
        client,
        front_uri,
        back_uri,
        image_suffixes=image_suffixes,
    )


def ocr_identity_document_images(
    client: SmsApiClient,
    front_uri: str,
    back_uri: str,
    *,
    image_suffixes: Optional[Mapping[str, str]] = None,
) -> Dict[str, Any]:
    image_suffixes = dict(image_suffixes or {"front": "jpg", "back": "jpg"})
    ocr_action = "GetOCRLicenseForAgent"
    ocr_payload = _sms_agent_call(
        client,
        ocr_action,
        {
            "iDCardFrontImage": front_uri,
            "iDCardBackImage": back_uri,
        },
        diagnostic_context={"phase": "ocr", "document": "identity"},
    )
    ocr_result = _response_result(ocr_payload, ocr_action)
    return {
        "status": "ocr_completed",
        "imageUris": {
            "front": front_uri,
            "back": back_uri,
        },
        "imageSuffixes": image_suffixes,
        "person": {
            key: ocr_result.get(key)
            for key in _PERSON_OCR_FIELDS
            if key in ocr_result
        },
        "next": "confirm_person_fields",
    }
