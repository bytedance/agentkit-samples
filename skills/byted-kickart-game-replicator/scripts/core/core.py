import os
import time
import json
import hashlib
import hmac
import zlib
import logging
import requests
from requests.models import PreparedRequest
from requests.auth import AuthBase
from collections import defaultdict
from functools import cache
from urllib.parse import urlparse, urlencode
from typing import Optional
from pydantic import BaseModel, Field

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


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
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code

class TokenException(SkillException):
    """Token exception."""
    @staticmethod
    def throw(code: str, message: str) -> None:
        if "1401" == code:
            raise TokenException("x0" + code, message)
        raise SkillException(code, message)

class HashUtils:
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
    def __init__(self, service: str, action: str, region: str, version: str):
        self.service = service
        self.region = region
        self.version = version
        self.action = action
        self.ak = os.getenv("KICKART_ACCESS_KEY") or os.getenv("ACCESS_KEY_ID", "")
        self.sk = os.getenv("KICKART_SECRET_KEY") or os.getenv("SECRET_ACCESS_KEY", "")

    def _get_signed_key(self, secret_key: str, date: str, region: str, service: str) -> bytes:
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
        sign_string = f"HMAC-SHA256\n{date}\n{credential_scope}\n{hashed_canonical_string}"
        signed_key = self._get_signed_key(self.sk, auth_date, self.region, self.service)
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
def init() -> logging.Logger:
    os.makedirs("/tmp/kickart/logs", exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        filename=f"/tmp/kickart/logs/info.{time.strftime('%Y%m%d', time.localtime())}.log",
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    return logging.getLogger(__name__)


logger = init()


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
    response_metadata: Optional[Metadata] = Field(default=None, alias="ResponseMetadata", description="Response metadata")


def token() -> str:
    """Get token from Kickart"""
    ak = os.getenv("KICKART_ACCESS_KEY") or os.getenv("ACCESS_KEY_ID", "")
    token = XMuseToken()
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

    url = "https://open.volcengineapi.com"
    auth = AkSkAuth(
        service="ic_iam",
        action="GetOpenAPITicket",
        region="cn-north",
        version="2025-08-25",
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
            expire=int(time.time() + 3600),
        )
        json.dump(token.model_dump(), f)

    return result.data.ticket  # pyright: ignore[reportOptionalMemberAccess] # pyright: ignore[reportOptionalMemberAccess]


if __name__ == "__main__":
    print(token())