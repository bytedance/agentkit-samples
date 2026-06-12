import base64
import json
import os

from mcp.server.session import ServerSession
from mcp.server.fastmcp import Context
from starlette.requests import Request

import json
from pathlib import Path

from pydantic import BaseModel

VOLCENGINE_ACCESS_KEY_ENV = 'VOLCENGINE_ACCESS_KEY'
VOLCENGINE_SECRET_KEY_ENV = 'VOLCENGINE_SECRET_KEY'
VOLCENGINE_SESSION_TOKEN_ENV = 'VOLCENGINE_SESSION_TOKEN'
VOLCENGINE_REGION_ENV = 'VOLCENGINE_REGION'
VOLCENGINE_HOST_ENV = 'VOLCENGINE_ENDPOINT'


def get_volcengine_credentials(ctx: Context, region: str | None):
    """Get Volcengine credentials from ctx variables."""
    credential = get_value_from_ctx_or_env(ctx, region)
    return {
        'access_key_id': credential.get('ak') or '',
        'secret_access_key': credential.get('sk') or '',
        'session_token': credential.get('token') or '',
        'region': credential.get('region') or 'cn-beijing',
        'host': credential.get('endpoint') or 'cloudcontrol.cn-beijing.volcengineapi.com',
    }


def get_value_from_ctx_or_env(ctx: Context[ServerSession, object], region: str | None) -> dict:
    credential_info = {}
    # 如果没有配置AK、SK
    if VOLCENGINE_ACCESS_KEY_ENV not in os.environ or VOLCENGINE_SECRET_KEY_ENV not in os.environ:
        auth = None
        raw_request: Request = ctx.request_context.request
        if raw_request:
            # 从 header 的 authorization 字段读取 base64 编码后的 sts json
            auth = raw_request.headers.get("authorization", None)

        if auth is None:
            # 如果 header 中没有认证信息，可能是 stdio 模式，尝试从环境变量获取
            auth = os.getenv("authorization", None)

        if auth is None:
            # 获取认证信息失败
            raise ValueError("Missing authorization info.")

        if ' ' in auth:
            _, base64_data = auth.split(' ', 1)
        else:
            base64_data = auth

        try:
            # 解码 Base64
            decoded_str = base64.b64decode(base64_data).decode('utf-8')
            data: dict = json.loads(decoded_str)

            if not data.get('AccessKeyId'):
                raise ValueError("get remote ak failed, it's empty")

            if not data.get('SecretAccessKey'):
                raise ValueError("get remote sk failed, it's empty")

            # get credential info
            credential_info["ak"] = data.get('AccessKeyId')
            credential_info["sk"] = data.get('SecretAccessKey')
            credential_info["token"] = data.get('SessionToken')
            credential_info["region"] = region or 'cn-beijing'
            credential_info["endpoint"] = f'cloudcontrol.{credential_info["region"]}.volcengineapi.com'

        except Exception as e:
            raise ValueError("Decode authorization info error", e)

        return credential_info
    else:
        credential_info["ak"] = os.environ.get(VOLCENGINE_ACCESS_KEY_ENV, "")
        credential_info["sk"] = os.environ.get(VOLCENGINE_SECRET_KEY_ENV, "")
        credential_info["token"] = os.environ.get(VOLCENGINE_SESSION_TOKEN_ENV, "")
        credential_info["region"] = os.environ.get(VOLCENGINE_REGION_ENV, 'cn-beijing')
        credential_info["endpoint"] = os.environ.get(VOLCENGINE_HOST_ENV) or 'cloudcontrol.cn-beijing.volcengineapi.com'

        # 如果环境变量未完整配置，则尝试从 VeFaaS IAM 文件获取
        if not (credential_info["ak"] or credential_info["sk"] or credential_info["token"]):
            vefaas_cred = get_credential_from_vefaas_iam()
            credential_info["ak"] = vefaas_cred.access_key_id
            credential_info["sk"] = vefaas_cred.secret_access_key
            credential_info["token"] = vefaas_cred.session_token
            credential_info["region"] = region or 'cn-beijing'
            credential_info["endpoint"] = f'cloudcontrol.{credential_info["region"]}.volcengineapi.com'

        # 如果仍未获取到有效凭证，则抛出异常
        if not (credential_info["ak"] and credential_info["sk"]):
            raise RuntimeError("无法获取有效的 Volcengine 凭证，请检查环境变量或 VeFaaS IAM 配置")

        return credential_info


class VeIAMCredential(BaseModel):
    access_key_id: str
    secret_access_key: str
    session_token: str


VEFAAS_IAM_CRIDENTIAL_PATH = "/var/run/secrets/iam/credential"


def get_credential_from_vefaas_iam() -> VeIAMCredential:
    """Get credential from VeFaaS IAM file"""

    path = Path(VEFAAS_IAM_CRIDENTIAL_PATH)

    if not path.exists():
        return VeIAMCredential(
            access_key_id="",
            secret_access_key="",
            session_token="",
        )

    with open(VEFAAS_IAM_CRIDENTIAL_PATH, "r") as f:
        cred_dict = json.load(f)
        access_key = cred_dict["access_key_id"]
        secret_key = cred_dict["secret_access_key"]
        session_token = cred_dict["session_token"]

        return VeIAMCredential(
            access_key_id=access_key,
            secret_access_key=secret_key,
            session_token=session_token,
        )
