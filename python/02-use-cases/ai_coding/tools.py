import os
import time
import uuid

import tos
from veadk.auth.veauth.utils import get_credential_from_vefaas_iam

provider = os.getenv("CLOUD_PROVIDER", "volcengine")
if provider and provider.lower() == "byteplus":
    region = os.getenv("REGION", "cn-hongkong")
    sld = "bytepluses"
else:
    region = os.getenv("REGION", "cn-beijing")
    sld = "volces"

bucket_name = os.getenv("DATABASE_TOS_BUCKET")

client: tos.TosClientV2 = None


def _init_tos_client():
    global client
    if client is not None:
        return

    if not bucket_name:
        raise ValueError("DATABASE_TOS_BUCKET 环境变量未设置")

    ak = os.getenv("VOLCENGINE_ACCESS_KEY", "")
    sk = os.getenv("VOLCENGINE_SECRET_KEY", "")
    security_token = ""
    if not ak or not sk:
        cred = get_credential_from_vefaas_iam()
        ak = cred.access_key_id
        sk = cred.secret_access_key
        security_token = cred.session_token

    client = tos.TosClientV2(
        ak=ak,
        sk=sk,
        security_token=security_token,
        endpoint=f"tos-{region}.{sld}.com",
        region=region,
    )


def upload_frontend_code_to_tos(code: str, code_type: str) -> str:
    """upload frontend code to TOS, current support html, css, js code; also set the file's ACL to public-read
    Args:
        code: frontend code string
        code_type: frontend code type, support html, css, js

    Returns:
        str: the object key of the uploaded frontend code in TOS
    """
    # validate code type
    if code_type not in ["html", "css", "js"]:
        raise ValueError(
            f"Unsupported code type: {code_type}, only support html, css, js"
        )

    _init_tos_client()

    # generate unique object key
    timestamp = int(time.time())
    unique_id = uuid.uuid4().hex[:8]
    object_key = f"frontend/{timestamp}_{unique_id}.{code_type}"

    # if bucket_name not exist, create it
    try:
        client.head_bucket(bucket_name)
    except Exception as e:
        if e.status_code == 404:
            client.create_bucket(bucket_name)
        else:
            raise e

    try:
        # upload frontend code to TOS
        resp = client.put_object(
            bucket_name,
            object_key,
            content=code.encode("utf-8"),
            acl=tos.ACLType.ACL_Public_Read,
        )
        if resp.status_code == 200:
            return object_key
        else:
            raise Exception(
                f"Failed to upload frontend code to TOS: {resp.status_code}"
            )
    except Exception as e:
        raise Exception(f"Failed to upload frontend code to TOS: {str(e)}")


def get_url_of_frontend_code_in_tos(tos_object_key: str) -> str:
    """get the URL of frontend code in TOS
    Args:
        tos_object_key: the object key of the uploaded frontend code in TOS

    Returns:
        str: the URL of frontend code in TOS
    """

    _init_tos_client()

    # build URL
    # format: https://<bucket-name>.<endpoint>/<object-key>
    endpoint = f"tos-{region}.{sld}.com"
    url = f"https://{bucket_name}.{endpoint}/{tos_object_key}"

    return url
