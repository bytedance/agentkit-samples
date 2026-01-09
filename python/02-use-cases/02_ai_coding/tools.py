import os
import time
import uuid

import tos
from veadk.auth.veauth.utils import get_credential_from_vefaas_iam

region = os.getenv("REGION", "cn-beijing")
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
        endpoint=f"tos-{region}.volces.com",
        region=region,
    )


def upload_frontend_code_to_tos(code: str, code_type: str) -> str:
    """上传前端代码到TOS, 当前支持html、css、js代码; 同时设置该文件的访问权限为public-read
    Args:
        code: 前端代码字符串
        code_type: 前端代码类型，支持html、css、js

    Returns:
        str: 上传到TOS后的对象键（object key）
    """
    # 验证代码类型
    if code_type not in ["html", "css", "js"]:
        raise ValueError(f"不支持的代码类型: {code_type}，仅支持html、css、js")

    _init_tos_client()

    # 生成唯一的对象键
    timestamp = int(time.time())
    unique_id = uuid.uuid4().hex[:8]
    object_key = f"frontend/{timestamp}_{unique_id}.{code_type}"

    # 如果 bucket_name 不存在，创建 bucket
    try:
        client.head_bucket(bucket_name)
    except Exception as e:
        if e.status_code == 404:
            client.create_bucket(bucket_name)
        else:
            raise e

    try:
        # 上传文件到TOS
        resp = client.put_object(
            bucket_name,
            object_key,
            content=code.encode("utf-8"),
            acl=tos.ACLType.ACL_Public_Read,
        )
        if resp.status_code == 200:
            return object_key
        else:
            raise Exception(f"上传前端代码到TOS失败: {resp.status_code}")
    except Exception as e:
        raise Exception(f"上传前端代码到TOS失败: {str(e)}")


def get_url_of_frontend_code_in_tos(tos_object_key: str) -> str:
    """获取前端代码在TOS中的URL
    Args:
        tos_object_key: 上传到TOS后的对象键（object key）

    Returns:
        str: 前端代码在TOS中的URL
    """

    _init_tos_client()

    # 构建URL
    # 格式: https://<bucket-name>.<endpoint>/<object-key>
    endpoint = f"tos-{region}.volces.com"
    url = f"https://{bucket_name}.{endpoint}/{tos_object_key}"

    return url
