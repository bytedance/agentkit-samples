# Copyright (c) 2026 ByteDance Ltd. and/or its affiliates
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

import os
import time
import json
import hmac
import zlib
import hashlib
import logging
import requests
from requests.models import PreparedRequest
from requests.auth import AuthBase
from collections import defaultdict
from functools import cache
from urllib.parse import urlparse, urlencode
from typing import Optional
from pydantic import BaseModel, Field

from dotenv import load_dotenv


class Error(BaseModel):
    code: str = Field(alias="Code")
    code_n: int = Field(alias="CodeN")
    message: str = Field(alias="Message")


class Metadata(BaseModel):
    action: str = Field(alias="Action")
    error: Optional[Error] = Field(default=None, alias="Error")
    region: str = Field(alias="Region")
    request_id: str = Field(alias="RequestId")
    service: str = Field(alias="Service")
    version: str = Field(alias="Version")


class SkillException(Exception):
    """A custom exception base class for skill errors."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code

    @staticmethod
    def throw(code: str, message: str) -> None:
        # ========== TOP Gateway Errors (100001-100036) ==========
        if "100001" == code:
            raise SkillException(
                code,
                "Undefined internal error occurred. Please contact the administrator immediately.",
            )
        if "100002" == code:
            raise SkillException(
                code,
                f"Request is missing required parameter: {message}. Please check if all required parameters (Action, Version, path parameters) are included.",
            )
        if "100003" == code:
            raise SkillException(
                code,
                "Request is missing authentication token. Please add authentication information to the request header.",
            )
        if "100004" == code:
            raise SkillException(
                code,
                f"Request is missing required information: {message}. Please check path parameters, X-Date header, etc.",
            )
        if "100005" == code:
            raise SkillException(
                code,
                "Request is missing signature. Please add signature to the request.",
            )
        if "100006" == code:
            raise SkillException(
                code,
                "The signature of the request is expired or the timestamp is from the future. Please check your system time, regenerate the signature, and retry.",
            )
        if "100007" == code:
            raise SkillException(
                code,
                "This service is not found. Please check if the service name is correct.",
            )
        if "100008" == code:
            raise SkillException(
                code,
                "Could not find operation for the specified version. The interface may not exist, has been taken offline, or you don't have permission to access it. Please check Action/Version parameters.",
            )
        if "100009" == code:
            raise SkillException(
                code,
                "The AccessKey included in the request is invalid. Please check your AccessKey in [Byteplus Console](https://console.byteplus.com/iam/keymanage?utm_source=tiktok&utm_medium=lead-generation&utm_campaign=BP_TikTok_Agentic_Hub_Kickart_Q3July_FY26&utm_term=tiktok&utm_content=20260721).",
            )
        if "100010" == code:
            raise SkillException(
                code,
                "The request signature does not match. Please check your Secret Access Key and signing method. Verify credentials in [Byteplus Console](https://console.byteplus.com/iam/keymanage?utm_source=tiktok&utm_medium=lead-generation&utm_campaign=BP_TikTok_Agentic_Hub_Kickart_Q3July_FY26&utm_term=tiktok&utm_content=20260721).",
            )
        if "100011" == code:
            raise SkillException(
                code,
                "Service AK/SK can only call its own APIs. Do not use service AK/SK to call other services' interfaces.",
            )
        if "100012" == code:
            raise SkillException(
                code,
                "Request was rejected due to lack of policy. Sub-users require explicit permissions. Please contact your administrator to add the necessary policy.",
            )
        if "100013" == code:
            raise SkillException(
                code,
                "You are not authorized to perform this operation. Please contact your enterprise administrator to grant permissions, or visit [Kickart Plan Page](https://console.byteplus.com/kickart/setting/combobuy?utm_source=tiktok&utm_medium=lead-generation&utm_campaign=BP_TikTok_Agentic_Hub_Kickart_Q3July_FY26&utm_term=tiktok&utm_content=20260721) to subscribe to a plan.",
            )
        if "100014" == code:
            raise SkillException(
                code,
                "Internal service error occurred. Please contact the administrator or retry later.",
            )
        if "100015" == code:
            raise SkillException(
                code,
                "Failed to connect to internal service. Please check if the backend service (e.g., imagex, vod) is running normally.",
            )
        if "100016" == code:
            raise SkillException(
                code,
                "Internal service execution timeout. Please check timeout configuration and retry later.",
            )
        if "100017" == code:
            raise SkillException(
                code,
                "Inner request using service AK/SK is missing account information. Please add account info to the request.",
            )
        if "100018" == code:
            raise SkillException(
                code,
                "Request rate exceeded the flow control limit. Please reduce request frequency.",
            )
        if "100019" == code:
            raise SkillException(
                code,
                "Service is temporarily unavailable due to circuit breaking. Please retry later.",
            )
        if "100020" == code:
            raise SkillException(
                code,
                "HTTP method is not allowed. Please use the correct HTTP method (GET, POST, etc.).",
            )
        if "100021" == code:
            raise SkillException(
                code,
                "Request requires Project permission verification. Please check your Project permission configuration.",
            )
        if "100023" == code:
            raise SkillException(
                code,
                "Backend service has an internal error. Please check if services like imagex/vod are functioning normally.",
            )
        if "100024" == code:
            raise SkillException(
                code,
                "Invalid 'Authorization' header format. Please check the Authorization header syntax.",
            )
        if "100025" == code:
            raise SkillException(
                code,
                "Invalid credential format in 'Authorization' header. Please check the credential syntax.",
            )
        if "100026" == code:
            raise SkillException(
                code,
                "Invalid secret token (STS or STS2). Please check if the token is valid and not expired.",
            )
        if "100027" == code:
            raise SkillException(
                code,
                "Account request rate exceeded the flow control limit. Please reduce the request frequency for this account.",
            )
        if "100028" == code:
            raise SkillException(
                code,
                "User does not exist. Please check the user ID in STS token or userid parameter.",
            )
        if "100029" == code:
            raise SkillException(
                code,
                "Role does not exist. Please check the role ID in STS token or roleid parameter.",
            )
        if "100030" == code:
            raise SkillException(
                code,
                "Service is not available in the specified region. Please check if the service supports the region you're accessing.",
            )
        if "100031" == code:
            raise SkillException(
                code,
                "The requested endpoint is invalid or does not match the service/region. Please check your endpoint configuration.",
            )
        if "100032" == code:
            raise SkillException(
                code,
                "Request is forbidden. Your account, AK, or STS may be blacklisted or blocked by security policies.",
            )
        if "100033" == code:
            raise SkillException(
                code,
                "The requested endpoint does not match the service or region. Please check CAM endpoint configuration.",
            )
        if "100034" == code:
            raise SkillException(
                code,
                "Account traffic limit exceeded. Please reduce the traffic for single account/machine requests.",
            )
        if "100035" == code:
            raise SkillException(
                code, "Service is busy due to overload. Please retry later."
            )
        if "100036" == code:
            raise SkillException(
                code,
                "Internal service error was denied. Please check network configuration.",
            )

        # ========== Bypass Authentication Errors (200000-200005) ==========
        if "200001" == code:
            raise SkillException(
                code,
                f"Bypass request is missing parameter: {message}. Please add the required bypass authentication parameters.",
            )
        if "200004" == code:
            raise SkillException(
                code,
                f"Bypass parameter is invalid: {message}. Please check X-User-Id or X-Role-Id validity.",
            )
        if "200005" == code:
            raise SkillException(
                code,
                f"Bypass identity does not exist: {message}. Please verify that the user or role exists.",
            )

        # ========== Business Logic Errors (Existing mappings) ==========
        if "1000" == code:
            raise SkillException(
                code,
                "Task is being processed, please poll the query task interface later.",
            )
        if "1400" == code:
            raise SkillException(
                code,
                "Parameter error! The request contains invalid or missing parameters. Please check the request body structure, field types, and required fields against the documentation.",
            )
        if "1401" == code:
            raise SkillException(
                code,
                "Concurrency limit exceeded! The current number of concurrent requests exceeds the agreed-upon limit. Please reduce the request frequency or contact your business representative to adjust your concurrency quota.",
            )
        if "1402" == code:
            raise SkillException(
                code,
                "Insufficient Credits! Your account balance is insufficient to cover the cost of this task. Please top up your account in [Kickart Plan Page](https://console.byteplus.com/kickart/setting/combobuy?utm_source=tiktok&utm_medium=lead-generation&utm_campaign=BP_TikTok_Agentic_Hub_Kickart_Q3July_FY26&utm_term=tiktok&utm_content=20260721).",
            )
        if "1403" == code:
            raise SkillException(
                code,
                "Your account does not have permission to call this API. Please contact your enterprise administrator to enable access to the relevant service, or visit [Kickart Plan Page](https://console.byteplus.com/kickart/setting/combobuy?utm_source=tiktok&utm_medium=lead-generation&utm_campaign=BP_TikTok_Agentic_Hub_Kickart_Q3July_FY26&utm_term=tiktok&utm_content=20260721) to subscribe to a plan.",
            )
        if "1404" == code:
            raise SkillException(
                code,
                "Current user no combo permission, please contact admin for help, or visit [Kickart Plan Page](https://console.byteplus.com/kickart/setting/combobuy?utm_source=tiktok&utm_medium=lead-generation&utm_campaign=BP_TikTok_Agentic_Hub_Kickart_Q3July_FY26&utm_term=tiktok&utm_content=20260721) to subscribe to a plan.",
            )
        if "1410" == code:
            raise SkillException(
                code,
                "Template ID does not exist! The requested template_id is invalid or the template is not online. Please upgrade the SKILL to latest version.",
            )
        if "1411" == code:
            raise SkillException(
                code,
                "Input resolution error! The requested resolution is not within the range supported by the template. Please check material resolution meets requirements (e.g., ≥480p).",
            )
        if "1412" == code:
            raise SkillException(
                code,
                "Image format error! The input image format is not supported or the file is corrupted. It is recommended to use JPEG or PNG format.",
            )
        if "1413" == code:
            raise SkillException(
                code,
                "Invalid media URL! Please ensure the URL is publicly accessible and has not expired.",
            )
        if "1414" == code:
            raise SkillException(
                code,
                "Media sensitive content! Input content triggered the platform's security review policy. Please change the content and try again.",
            )
        if "1415" == code:
            raise SkillException(
                code,
                "Output media sensitive content! Output content triggered the platform's security review policy. Please change the content and try again.",
            )
        if "1416" == code:
            raise SkillException(
                code,
                "Invalid media count! Please check whether the material quantity meets the requirements. Provided media count exceeds limit, excess materials may not be used.",
            )
        if "1417" == code:
            raise SkillException(
                code,
                "Chat completion error! An exception was thrown when calling the large model. Media processing issue, please retry. If persists, contact Volcengine technical support.",
            )
        if "1418" == code:
            raise SkillException(
                code,
                "Invalid duration parameter! The input duration parameter does not meet the API requirements. Required video duration doesn't meet skill requirements, please submit with 0-60s duration.",
            )
        if "1421" == code:
            raise SkillException(
                code,
                "Duration enum error! The input duration parameter does not meet the interface enum value requirements.",
            )
        if "1422" == code:
            raise SkillException(
                code,
                "Get product info error! Please check whether the product link is correct.",
            )
        if "1423" == code:
            raise SkillException(
                code,
                "Reference video resolution error! The reference video resolution does not meet the requirements.",
            )
        if "1424" == code:
            raise SkillException(
                code,
                "Reference video duration error! The duration of the reference video does not meet the requirements.",
            )
        if "1425" == code:
            raise SkillException(
                code,
                "Reference video format error! The reference video format is not supported.",
            )
        if "1426" == code:
            raise SkillException(
                code,
                "Reference video size error! The reference video file size does not meet the requirements.",
            )
        if "1427" == code:
            raise SkillException(
                code,
                "Reference video link error! The reference video link is invalid or inaccessible.",
            )
        if "1428" == code:
            raise SkillException(
                code,
                "Language enum error! Please check whether the input language field matches the language enum values supported.",
            )
        if "1429" == code:
            raise SkillException(
                code,
                "Model image count error! The number of images in payload.model_images exceeds the limit allowed.",
            )
        if "1430" == code:
            raise SkillException(
                code,
                "Ratio enum error! Please check whether the input media assets comply with the media asset ratio requirements of the field.",
            )
        if "1500" == code:
            raise SkillException(
                code,
                "An unknown error occurred on the server. Please contact technical support.",
            )
        if "1501" == code:
            raise SkillException(
                code,
                "Your subscription plan has expired. Please visit [kickart plan](https://console.byteplus.com/kickart/setting/combobuy?utm_source=tiktok&utm_medium=lead-generation&utm_campaign=BP_TikTok_Agentic_Hub_Kickart_Q3July_FY26&utm_term=tiktok&utm_content=20260721) to activate a plan.",
            )
        if "1600" == code:
            raise SkillException(
                code,
                "Task does not exist! The queried task_id is invalid. Please check whether the task_id is the value successfully returned by the submit task interface.",
            )
        if "1601" == code:
            raise SkillException(
                code,
                "Task timeout! Task execution exceeded the maximum processing time (currently 1 hour) set by the system. Please retry the task.",
            )
        if "1602" == code:
            raise SkillException(code, "Task canceled! The task has been canceled.")
        if "1603" == code:
            raise SkillException(
                code,
                "Task ended! The task is already in success/failure state and cannot be canceled.",
            )
        if "1604" == code:
            raise SkillException(
                code,
                "Task cancel failed! Task cancellation failed, please try again later.",
            )
        if "2000" == code:
            raise SkillException(
                code,
                f"Server internal error occurred (Code: 2000). This is NOT a request issue. Error details: {message}. Please contact Volcengine technical support or retry later.",
            )
        if "5000" == code:
            raise SkillException(
                code,
                "River workflow failed! The underlying AI workflow execution failed, usually as a fallback for more specific errors (such as 1412-1414).",
            )

        raise SkillException(code, message)


class TokenException(SkillException):
    """Token exception."""

    @staticmethod
    def throw(code: str, message: str) -> None:
        if "1401" == code:
            raise TokenException(
                code,
                "Current user no combo permission, please contact admin for help, or visit [Kickart Plan Page](https://console.byteplus.com/kickart/setting/combobuy?utm_source=tiktok&utm_medium=lead-generation&utm_campaign=BP_TikTok_Agentic_Hub_Kickart_Q3July_FY26&utm_term=tiktok&utm_content=20260721) to subscribe to a plan.",
            )
        SkillException.throw(code, message)


class HashUtils:
    """Hash calculation utils."""

    @staticmethod
    def hmac_sha256(key: bytes, content: str) -> bytes:
        h = hmac.new(key, content.encode("utf-8"), hashlib.sha256)
        return h.digest()

    @staticmethod
    def hash_sha256(data: bytes) -> bytes:
        h = hashlib.sha256()
        h.update(data)
        return h.digest()

    @staticmethod
    def file_hash(file_path: str):
        file_md5_obj = hashlib.md5()
        file_crc32 = 0
        file_size = 0
        with open(file_path, "rb") as f:
            while chunk := f.read(8192 * 1024):
                file_md5_obj.update(chunk)
                file_crc32 = zlib.crc32(chunk, file_crc32)
                file_size += len(chunk)
        return file_md5_obj.hexdigest(), file_crc32 & 0xFFFFFFFF, file_size


class AkSkAuth(AuthBase):
    """AK and SK authentication utils."""

    def __init__(self, service: str, action: str, region: str, version: str):
        self.service = service
        self.region = region
        self.version = version
        self.action = action
        self.ak = os.getenv("KICKART_ACCESS_KEY")
        self.sk = os.getenv("KICKART_SECRET_KEY")

        if self.ak is None:
            raise ValueError(
                "Kickart AccessKey cannot be empty! Please set it in the environment variables."
            )
        if self.sk is None:
            raise ValueError(
                "Kickart SecretKey cannot be empty! Please set it in the environment variables."
            )

    def _get_signed_key(
        self, secret_key: str, date: str, region: str, service: str
    ) -> bytes:
        k_date = HashUtils.hmac_sha256(secret_key.encode("utf-8"), date)
        k_region = HashUtils.hmac_sha256(k_date, region)
        k_service = HashUtils.hmac_sha256(k_region, service)
        return HashUtils.hmac_sha256(k_service, "request")

    def _get_sha_payload(self, r: PreparedRequest) -> str:
        if r.body is None:
            return HashUtils.hash_sha256(b"").hex()
        if isinstance(r.body, str):
            return HashUtils.hash_sha256(r.body.encode("utf-8")).hex()
        if isinstance(r.body, bytes):
            return HashUtils.hash_sha256(r.body).hex()
        raise ValueError("Body must be str or bytes")

    def __call__(self, r: PreparedRequest) -> PreparedRequest:
        queries = defaultdict(str)
        queries["Action"] = self.action
        queries["Version"] = self.version
        r.prepare_url(str(r.url), params=queries)

        date = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(time.time()))
        auth_date = date[:8]
        payload = self._get_sha_payload(r)

        signed = "host;x-date;x-content-sha256;content-type"
        host = urlparse(str(r.url)).netloc

        header_string = f"host:{host}\nx-date:{date}\nx-content-sha256:{payload}\ncontent-type:application/json"
        query_string = urlencode(queries).replace("+", "%20")
        canonical_string = f"{str(r.method).upper()}\n/\n{query_string}\n{header_string}\n\n{signed}\n{payload}"
        hashed_canonical_string = HashUtils.hash_sha256(
            canonical_string.encode("utf-8")
        ).hex()

        credential_scope = f"{auth_date}/{self.region}/{self.service}/request"
        sign_string = (
            f"HMAC-SHA256\n{date}\n{credential_scope}\n{hashed_canonical_string}"
        )
        signed_key = self._get_signed_key(
            str(self.sk), auth_date, self.region, self.service
        )
        signature = HashUtils.hmac_sha256(signed_key, sign_string).hex()

        authorization = (
            f"HMAC-SHA256 Credential={self.ak}/{credential_scope},"
            f" SignedHeaders={signed},"
            f" Signature={signature}"
        )

        headers = defaultdict(str)
        headers["X-Date"] = date
        headers["X-Content-Sha256"] = payload
        headers["Content-Type"] = "application/json"
        headers["Authorization"] = authorization

        if ppe_env := os.getenv("X_VOLC_ENV"):
            headers["X-TT-Env"] = "ppe_volcengine"
            headers["X-Volc-Env"] = ppe_env
            headers["X-Use-Ppe"] = "1"
        r.prepare_headers(headers)
        return r


@cache
def initialize() -> logging.Logger:
    """Initialize"""
    os.makedirs("/tmp/kickart/logs", exist_ok=True)

    load_dotenv()

    logging.basicConfig(
        level=logging.INFO,
        filename=f"/tmp/kickart/logs/info.{time.strftime('%Y%m%d', time.localtime())}.log",
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    return logging.getLogger(__name__)


logger = initialize()


class XMuseToken(BaseModel):
    ak: str = Field(default="", description="Kickart AccessKey")
    value: str = Field(default="", description="xmuse token")
    expire: int = Field(default=0, description="xmuse token expire time")


class Ticket(BaseModel):
    ticket: str = Field(default="", description="Ticket")


class TicketResponse(BaseModel):
    code: Optional[int] = Field(default=None, description="Response code")
    message: Optional[str] = Field(default=None, description="Response message")
    data: Optional[Ticket] = Field(default=None, description="Response")
    response_metadata: Optional[Metadata] = Field(
        default=None, alias="ResponseMetadata", description="Response metadata"
    )


def token() -> str:
    """Get token from Kickart"""
    ak = os.getenv("KICKART_ACCESS_KEY")
    path = "/tmp/kickart/.token.json"

    if os.path.exists(path):
        with open(path, "r") as f:
            token = XMuseToken(**json.load(f))
            if (
                token is not None
                and token.ak == ak
                and token.value is not None
                and time.time() < token.expire
            ):
                return token.value

    url = "https://open.byteplusapi.com"
    auth = AkSkAuth(
        service="kickart",
        action="GetOpenAPITicket",
        region="ap-southeast-1",
        version="2026-02-27",
    )

    logger.info(f"[request] >>> {url}")
    response = requests.request("POST", url, auth=auth)
    logger.info(
        f"[response] <<< {response.headers['X-Tt-Logid']} {response.status_code}"
    )

    result = TicketResponse(**response.json())

    if result.code is not None and result.code != 0:
        TokenException.throw(str(result.code), str(result.message))
    if (
        result.response_metadata is not None
        and result.response_metadata.error is not None
        and result.response_metadata.error.code_n != 0
    ):
        TokenException.throw(
            str(result.response_metadata.error.code_n),
            result.response_metadata.error.message,
        )

    with open(path, "w") as f:
        token = XMuseToken(
            ak=str(ak),
            value=result.data.ticket,  # pyright: ignore[reportOptionalMemberAccess]
            expire=int(time.time() + 43200),
        )
        json.dump(token.model_dump(), f)

    return result.data.ticket  # pyright: ignore[reportOptionalMemberAccess]


if __name__ == "__main__":
    print(token())
