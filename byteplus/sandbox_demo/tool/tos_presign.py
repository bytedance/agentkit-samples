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
"""
TOS presigned URL utility (BytePlus)

Generates a presigned upload (PUT) / download (GET) URL pair for a TOS object.
The sandbox has outbound network access but no cloud credentials, so the agent
hands the sandbox a presigned PUT URL to push the finished artifact directly to
TOS (e.g. `curl -T project.zip "<upload_url>"`), then returns the matching
presigned GET URL to the user as the download link. Credentials never leave the
agent runtime.
"""

import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import tos
from tos import HttpMethodType

# Current directory
sys.path.append(str(Path(__file__).resolve().parent))
# Parent directory
sys.path.append(str(Path(__file__).resolve().parent.parent))
from veadk.auth.veauth.utils import get_credential_from_vefaas_iam
from consts import DEFAULT_BUCKET, DEFAULT_REGION

logger = logging.getLogger(__name__)


def create_tos_transfer_urls(
    filename: str,
    bucket_name: Optional[str] = None,
    region: Optional[str] = None,
    expires: int = 604800,  # 7-day validity
) -> dict:
    """
    Create a presigned upload (PUT) and download (GET) URL pair for a TOS object.

    Give the upload_url to the sandbox so it can push a finished artifact to TOS
    with `curl -f -sS -X PUT -T <file> "<upload_url>"`, then share the
    download_url with the user. No cloud credentials are needed inside the
    sandbox.

    Args:
        filename: Artifact filename (e.g. "todo-app.zip"). Used to build the
            object key; a timestamp prefix is added automatically to avoid
            collisions.
        bucket_name: TOS bucket name. Defaults to the DATABASE_TOS_BUCKET
            environment variable.
        region: TOS region. Defaults to the DATABASE_TOS_REGION environment
            variable, or ap-southeast-1.
        expires: Validity period of both URLs in seconds. Defaults to 7 days.

    Returns:
        dict with keys:
            upload_url (str): presigned PUT URL for uploading the artifact
            download_url (str): presigned GET URL for downloading the artifact
            object_key (str): the TOS object key
        or a dict with an "error" key describing what went wrong.

    Environment variables required (when not running with an IAM role):
        BYTEPLUS_ACCESS_KEY (or VOLCENGINE_ACCESS_KEY): BytePlus access key
        BYTEPLUS_SECRET_KEY (or VOLCENGINE_SECRET_KEY): BytePlus secret key
    """

    if bucket_name is None:
        bucket_name = os.getenv("DATABASE_TOS_BUCKET")
        if bucket_name is None:
            bucket_name = DEFAULT_BUCKET
            logger.info(
                f"Warn: bucket_name is not provided in env, using default bucket name: {bucket_name}"
            )
        else:
            logger.info(f"Using bucket_name from env: {bucket_name}")
    if region is None:
        region = os.getenv("DATABASE_TOS_REGION")
        if region is None:
            region = DEFAULT_REGION
            logger.info(
                f"Warn: region is not provided in env, using default region: {region}"
            )
        else:
            logger.info(f"Using region from env: {region}")

    # Retrieve credentials from env, falling back to the runtime IAM role.
    # veadk maps BYTEPLUS_* onto VOLCENGINE_* when CLOUD_PROVIDER=byteplus,
    # but fall back to BYTEPLUS_* directly so this tool also works standalone.
    access_key = os.getenv("VOLCENGINE_ACCESS_KEY") or os.getenv("BYTEPLUS_ACCESS_KEY")
    secret_key = os.getenv("VOLCENGINE_SECRET_KEY") or os.getenv("BYTEPLUS_SECRET_KEY")
    session_token = ""

    if not (access_key and secret_key):
        cred = get_credential_from_vefaas_iam()
        access_key = cred.access_key_id
        secret_key = cred.secret_access_key
        session_token = cred.session_token

    if not access_key or not secret_key:
        return {
            "error": "BYTEPLUS_ACCESS_KEY and BYTEPLUS_SECRET_KEY are not provided and no IAM role is configured."
        }

    # Timestamped object key so repeated runs never overwrite each other
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = os.path.basename(filename) or "artifact.zip"
    object_key = f"sandbox_coder/{timestamp}_{safe_name}"

    client = None
    try:
        # BytePlus TOS endpoint
        endpoint = f"tos-{region}.bytepluses.com"
        client = tos.TosClientV2(
            ak=access_key,
            sk=secret_key,
            security_token=session_token,
            endpoint=endpoint,
            region=region,
        )

        # Fail fast with a clear message if the bucket is missing
        try:
            client.head_bucket(bucket_name)
        except tos.exceptions.TosServerError as e:
            if e.status_code == 404:
                return {
                    "error": f"TOS bucket {bucket_name} does not exist. Create it or set DATABASE_TOS_BUCKET to an existing bucket."
                }
            raise

        upload_url = client.pre_signed_url(
            http_method=HttpMethodType.Http_Method_Put,
            bucket=bucket_name,
            key=object_key,
            expires=expires,
        ).signed_url
        download_url = client.pre_signed_url(
            http_method=HttpMethodType.Http_Method_Get,
            bucket=bucket_name,
            key=object_key,
            expires=expires,
        ).signed_url

        logger.info(f"Presigned URL pair generated for object key: {object_key}")
        return {
            "upload_url": upload_url,
            "download_url": download_url,
            "object_key": object_key,
        }

    except tos.exceptions.TosClientError as e:
        logger.info(f"TOS client error: {e}")
        return {"error": f"TOS client error: {e}"}
    except tos.exceptions.TosServerError as e:
        logger.info(f"TOS server error: {e} (status {e.status_code}, code {e.code})")
        return {"error": f"TOS server error: {e.message} (status {e.status_code})"}
    except Exception as e:
        logger.info(f"Presigned URL generation failed: {e}")
        return {"error": f"Presigned URL generation failed: {e}"}
    finally:
        if client:
            client.close()


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = create_tos_transfer_urls("smoke-test.zip", expires=3600)
    if "error" in result:
        print(f"❌ {result['error']}")
    else:
        print("✅ Presigned URL pair created")
        print(f"Object key:   {result['object_key']}")
        print(f"Upload URL:   {result['upload_url'][:100]}...")
        print(f"Download URL: {result['download_url'][:100]}...")
