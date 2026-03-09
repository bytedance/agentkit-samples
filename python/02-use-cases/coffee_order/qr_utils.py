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

import base64
import io
import os
import time
import uuid

import qrcode
import tos
from veadk.auth.veauth.utils import get_credential_from_vefaas_iam

region = os.getenv("DATABASE_TOS_REGION", "")
bucket_name = os.getenv("DATABASE_TOS_BUCKET", "")

client: tos.TosClientV2 = None


def _init_tos_client():
    global client, bucket_name
    # if client is not None:
    #     return

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
    try:
        client.head_bucket(bucket_name)
    except Exception as e:
        if e.status_code == 404:
            client.create_bucket(bucket_name)
        else:
            raise e


def upload_frontend_code_to_tos(code: str, code_type: str) -> str:
    """Upload frontend code to TOS. Currently supports html, css, and js code.
    Also sets the file access permission to public-read.

    Args:
        code: Frontend code string
        code_type: Frontend code type, supports html, css, js
    Returns:
        str: The object's access URL
    """

    if code_type not in ["html", "css", "js"]:
        raise ValueError(
            f"unsupported code type: {code_type}，currently supports html、css、js"
        )

    _init_tos_client()

    timestamp = int(time.time())
    unique_id = uuid.uuid4().hex[:8]
    object_key = f"frontend/{timestamp}_{unique_id}.{code_type}"

    # check if bucket_name exists, if not then create
    try:
        client.head_bucket(bucket_name)
    except Exception as e:
        if e.status_code == 404:
            client.create_bucket(bucket_name)
        else:
            raise e

    try:
        # upload object to bucket
        resp = client.put_object(
            bucket_name,
            object_key,
            content=code.encode("utf-8"),
            acl=tos.ACLType.ACL_Public_Read,
        )
        if resp.status_code == 200:
            endpoint = f"tos-{region}.volces.com"
            return f"https://{bucket_name}.{endpoint}/{object_key}"
        else:
            raise Exception(
                f"Failed to upload frontend code to TOS: {resp.status_code}"
            )

    except Exception as e:
        raise Exception(f"Failed to upload frontend code to TOS: {str(e)}")


def generate_qr_data_url(text: str, box_size: int = 10, border: int = 4) -> str:
    """
    generate QR code and return base64 encoded data URL
    """
    try:
        # Generate QR code
        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=box_size,
            border=border,
        )
        qr.add_data(text)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        # Create in-memory image
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        image_bytes = buf.getvalue()

        # Convert to base64
        base64_image = base64.b64encode(image_bytes).decode("utf-8")

        # Return data URL
        return f"data:image/png;base64,{base64_image}"

    except Exception as e:
        raise RuntimeError(f"QR generation failed: {e}") from e


def generate_qr_tos_url(text: str, box_size: int = 10, border: int = 4) -> str:
    """
    For backward compatibility，try to generate QR code using TOS, fall back to base64 if it fails.
    Args:
        text: Text to encode
        box_size: Pixel size of each QR code dot
        border: Width of QR code border (in dots)
    Returns:
        str: URL of the QR code image
    """

    global client, bucket_name
    # TOS configuration (should be set as environment variables)
    _init_tos_client()

    # Generate QR code
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=border,
    )
    qr.add_data(text)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    # Create in-memory image
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    image_bytes = buf.getvalue()

    # Upload to TOS
    object_name = f"qr-codes/{uuid.uuid4().hex}.png"
    client.put_object(
        bucket=bucket_name,
        key=object_name,
        content=image_bytes,
        content_type="image/png",
        acl=tos.ACLType.ACL_Public_Read,
    )
    endpoint = f"tos-{region}.volces.com"
    return f"https://{bucket_name}.{endpoint}/{object_name}"


# # For backward compatibility
# def generate_qr_data_url(text: str, box_size: int = 10, border: int = 4) -> str:
#     """Deprecated: Use generate_qr_tos_url instead"""
#     return generate_qr_tos_url(text, box_size, border)


if __name__ == "__main__":
    test_text = "https://example.com/pay?order_id=12345"
    qr_url = generate_qr_tos_url(test_text)
    print(f"Generated QR code URL: {qr_url}")
