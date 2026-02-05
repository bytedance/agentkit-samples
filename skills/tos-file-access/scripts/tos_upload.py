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
TOS file/directory upload utility
Provides functionality to upload files or directories to Volcano Engine TOS object storage and returns signed access URLs
"""

import argparse
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Union

import tos
from tos import HttpMethodType

# Current directory
sys.path.append(str(Path(__file__).resolve().parent))
# Parent directory
sys.path.append(str(Path(__file__).resolve().parent.parent))
from veadk.auth.veauth.utils import get_credential_from_vefaas_iam

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

if not logger.handlers:
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    formatter = logging.Formatter("%(message)s")
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)


def _get_session_prefix() -> str:
    """Extract session prefix from TOOL_USER_SESSION_ID environment variable

    Returns:
        str: Session prefix (e.g., "skill_agent_veadk_default_user_tmp-session-20251210150057")
             or timestamp if not set
    """
    session_id = os.getenv("TOOL_USER_SESSION_ID", "")
    if session_id:
        return session_id
    else:
        # Fallback to timestamp if no session ID
        return datetime.now().strftime("%Y%m%d_%H%M%S")


def upload_file_to_tos(
    file_path: str,
    bucket_name: str,
    region: str = "cn-beijing",
    ak: Optional[str] = None,
    sk: Optional[str] = None,
    session_token: Optional[str] = None,
    expires: int = 604800,  # 7-day validity
) -> Optional[str]:
    """
    Upload a file to TOS object storage and return a signed accessible URL

    Args:
        file_path: Local file path
        bucket_name: TOS bucket name
        region: TOS region, defaults to cn-beijing
        ak: Access Key; if empty, reads from environment variables
        sk: Secret Key; if empty, reads from environment variables
        session_token: Session token
        expires: Signed URL validity period (seconds), defaults to 7 days

    Returns:
        str: Signed TOS URL that can be accessed directly
        None: Returns None if upload fails

    Environment variables:
        VOLCENGINE_ACCESS_KEY: Volcano Engine access key
        VOLCENGINE_SECRET_KEY: Volcano Engine secret key
        TOOL_USER_SESSION_ID: Session ID for generating object key prefix
    """
    if bucket_name is None:
        logger.error("Error: bucket name The bucket has not been specified.")
        return None

    # Check if file exists
    if not os.path.exists(file_path):
        logger.error(f"Error: File does not exist: {file_path}")
        return None

    if not os.path.isfile(file_path):
        logger.error(f"Error: Path is not a file: {file_path}")
        return None

    # Retrieve credentials
    access_key = ak or os.getenv("VOLCENGINE_ACCESS_KEY")
    secret_key = sk or os.getenv("VOLCENGINE_SECRET_KEY")
    session_token = session_token or ""

    if not (access_key and secret_key):
        try:
            cred = get_credential_from_vefaas_iam()
            access_key = cred.access_key_id
            secret_key = cred.secret_access_key
            session_token = cred.session_token
        except Exception as e:
            logger.error(f"Failed to get credentials from IAM: {e}")

    if not access_key or not secret_key:
        logger.error(
            "Error: VOLCENGINE_ACCESS_KEY and VOLCENGINE_SECRET_KEY are not provided or IAM Role is not configured."
        )
        return None

    # Auto-generate object_key: upload/{session_prefix}/{filename}
    session_prefix = _get_session_prefix()
    filename = os.path.basename(file_path)
    object_key = f"upload/{session_prefix}/{filename}"

    # Create TOS client
    client = None
    try:
        # Initialize TOS client
        endpoint = f"tos-{region}.volces.com"
        client = tos.TosClientV2(
            ak=access_key,
            sk=secret_key,
            security_token=session_token,
            endpoint=endpoint,
            region=region,
        )

        logger.info(f"Starting file upload: {file_path}")
        logger.info(f"Target Bucket: {bucket_name}")
        logger.info(f"Object Key: {object_key}")

        # Ensure bucket exists (create if not)
        try:
            client.head_bucket(bucket_name)
            logger.info(f"Bucket {bucket_name} already exists")
        except tos.exceptions.TosServerError as e:
            if e.status_code == 404:
                logger.info(f"Bucket {bucket_name} does not exist, creating...")
                client.create_bucket(
                    bucket=bucket_name,
                    acl=tos.ACLType.ACL_Private,
                    storage_class=tos.StorageClassType.Storage_Class_Standard,
                )
                logger.info(f"Bucket {bucket_name} created successfully")
            else:
                raise e

        # Upload file
        result = client.put_object_from_file(
            bucket=bucket_name, key=object_key, file_path=file_path
        )

        logger.info("File uploaded successfully!")
        logger.info(f"ETag: {result.etag}")

        # Generate signed URL
        signed_url_output = client.pre_signed_url(
            http_method=HttpMethodType.Http_Method_Get,
            bucket=bucket_name,
            key=object_key,
            expires=expires,
        )

        signed_url = signed_url_output.signed_url
        logger.info(
            f"Signed URL generated (valid for {expires} seconds / {expires // 86400} days)"
        )

        return signed_url

    except tos.exceptions.TosClientError as e:
        logger.error(f"TOS client error: {e}")
        return None
    except tos.exceptions.TosServerError as e:
        logger.error(f"TOS server error: {e}")
        logger.error(f"Status code: {e.status_code}")
        logger.error(f"Error code: {e.code}")
        logger.error(f"Error message: {e.message}")
        return None
    except Exception as e:
        logger.error(f"File upload failed: {e}")
        import traceback

        traceback.print_exc()
        return None
    finally:
        # Close client
        if client:
            client.close()


def upload_directory_to_tos(
    directory_path: str,
    bucket_name: str,
    region: str = "cn-beijing",
    ak: Optional[str] = None,
    sk: Optional[str] = None,
    session_token: Optional[str] = None,
    expires: int = 604800,
) -> Optional[str]:
    """
    Upload entire directory to TOS object storage and return signed URLs for all files

    Args:
        directory_path: Local directory path
        bucket_name: TOS bucket name
        region: TOS region, defaults to cn-beijing
        ak: Access Key; if empty, reads from environment variables
        sk: Secret Key; if empty, reads from environment variables
        session_token: Session token
        expires: Signed URL validity period (seconds), defaults to 7 days

    Returns:
        str: TOS path for uploaded directory
        None: Returns None if upload fails

    Environment variables:
        VOLCENGINE_ACCESS_KEY: Volcano Engine access key
        VOLCENGINE_SECRET_KEY: Volcano Engine secret key
    """
    if bucket_name is None:
        logger.error("Error: bucket name The bucket has not been specified.")
        return None

    # Check if directory exists
    if not os.path.exists(directory_path):
        logger.error(f"Error: Directory does not exist: {directory_path}")
        return None

    if not os.path.isdir(directory_path):
        logger.error(f"Error: Path is not a directory: {directory_path}")
        return None

    # Retrieve credentials
    access_key = ak or os.getenv("VOLCENGINE_ACCESS_KEY")
    secret_key = sk or os.getenv("VOLCENGINE_SECRET_KEY")
    session_token = session_token or ""

    if not (access_key and secret_key):
        try:
            cred = get_credential_from_vefaas_iam()
            access_key = cred.access_key_id
            secret_key = cred.secret_access_key
            session_token = cred.session_token
        except Exception as e:
            logger.error(f"Failed to get credentials from IAM: {e}")

    if not access_key or not secret_key:
        logger.error(
            "Error: VOLCENGINE_ACCESS_KEY and VOLCENGINE_SECRET_KEY are not provided or IAM Role is not configured."
        )
        return None

    # Auto-generate object_key_prefix: upload/{session_prefix}/{directory_name}
    session_prefix = _get_session_prefix()
    directory_name = os.path.basename(os.path.abspath(directory_path))
    object_key_prefix = f"upload/{session_prefix}/{directory_name}"

    # Create TOS client
    client = None

    try:
        # Initialize TOS client
        endpoint = f"tos-{region}.volces.com"
        client = tos.TosClientV2(
            ak=access_key,
            sk=secret_key,
            security_token=session_token,
            endpoint=endpoint,
            region=region,
        )

        logger.info(f"Starting directory upload: {directory_path}")
        logger.info(f"Target Bucket: {bucket_name}")
        logger.info(f"Object Key Prefix: {object_key_prefix}")

        # Ensure bucket exists (create if not)
        try:
            client.head_bucket(bucket_name)
            logger.info(f"Bucket {bucket_name} already exists")
        except tos.exceptions.TosServerError as e:
            if e.status_code == 404:
                logger.info(f"Bucket {bucket_name} does not exist, creating...")
                client.create_bucket(
                    bucket=bucket_name,
                    acl=tos.ACLType.ACL_Private,
                    storage_class=tos.StorageClassType.Storage_Class_Standard,
                )
                logger.info(f"Bucket {bucket_name} created successfully")
            else:
                raise e

        # Upload all files in directory recursively
        for root, dirs, files in os.walk(directory_path):
            for file in files:
                file_path = os.path.join(root, file)

                # Calculate relative path from directory_path
                relative_path = os.path.relpath(file_path, directory_path)

                # Construct object key: upload/{session_prefix}/{directory_name}/{relative_path}
                object_key = f"{object_key_prefix}/{relative_path}"

                # Upload file
                try:
                    result = client.put_object_from_file(
                        bucket=bucket_name, key=object_key, file_path=file_path
                    )
                    logger.info(
                        f"Uploaded: {file_path} -> {object_key}, result: {result}"
                    )

                except Exception as e:
                    logger.error(f"Failed to upload {file_path}: {e}")

        tos_path = f"tos://{bucket_name}/{object_key_prefix} "
        logger.info(f"Directory upload completed! TOS Path: {tos_path}")
        return tos_path

    except tos.exceptions.TosClientError as e:
        logger.error(f"TOS client error: {e}")
        return None
    except tos.exceptions.TosServerError as e:
        logger.error(f"TOS server error: {e}")
        logger.error(f"Status code: {e.status_code}")
        logger.error(f"Error code: {e.code}")
        logger.error(f"Error message: {e.message}")
        return None
    except Exception as e:
        logger.error(f"Directory upload failed: {e}")
        import traceback

        traceback.print_exc()
        return None
    finally:
        # Close client
        if client:
            client.close()


def upload_to_tos(
    path: str,
    bucket_name: str,
    region: str = "cn-beijing",
    ak: Optional[str] = None,
    sk: Optional[str] = None,
    session_token: Optional[str] = None,
    expires: int = 604800,
) -> Optional[Union[str, list[str]]]:
    """
    Upload a file or directory to TOS object storage

    This function automatically detects whether the path is a file or directory
    and calls the appropriate upload function.

    Args:
        path: Local file or directory path
        bucket_name: TOS bucket name
        region: TOS region
        ak: Access Key
        sk: Secret Key
        session_token: Session token
        expires: Signed URL validity period (seconds)

    Returns:
        str: Signed URL if uploading a file
        list[str]: List of signed URLs if uploading a directory
        None: Returns None if upload fails
    """
    if not os.path.exists(path):
        logger.error(f"Error: Path does not exist: {path}")
        return None

    if os.path.isfile(path):
        # Upload single file
        return upload_file_to_tos(
            file_path=path,
            bucket_name=bucket_name,
            region=region,
            ak=ak,
            sk=sk,
            session_token=session_token,
            expires=expires,
        )
    elif os.path.isdir(path):
        # Upload directory
        return upload_directory_to_tos(
            directory_path=path,
            bucket_name=bucket_name,
            region=region,
            ak=ak,
            sk=sk,
            session_token=session_token,
            expires=expires,
        )
    else:
        logger.error(f"Error: Path is neither a file nor a directory: {path}")
        return None


def main():
    """Command-line interface for tos_upload"""
    parser = argparse.ArgumentParser(
        description="Upload files or directories to Volcano Engine TOS and generate signed URLs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Upload a file (auto-detect)
  python tos_upload.py /path/to/file.mp4 --bucket my-bucket
  
  # Upload a directory (auto-detect)
  python tos_upload.py /path/to/directory --bucket my-bucket
  
  # Upload to different region with custom expiration
  python tos_upload.py /path/to/file.json --bucket my-bucket --region cn-beijing --expires 86400

File Upload Structure:
  File:      upload/{session_prefix}/{filename}
  Directory: upload/{session_prefix}/{directory_name}/{relative_path}
  
Environment Variables:
  VOLCENGINE_ACCESS_KEY     Volcano Engine access key
  VOLCENGINE_SECRET_KEY     Volcano Engine secret key
  TOOL_USER_SESSION_ID      Session ID for generating object key prefix
        """,
    )

    parser.add_argument("path", type=str, help="Local file or directory path to upload")

    parser.add_argument("--bucket", type=str, required=True, help="TOS bucket name")

    parser.add_argument(
        "--region",
        type=str,
        default="cn-beijing",
        help="TOS region (default: cn-beijing)",
    )

    parser.add_argument(
        "--expires",
        type=int,
        default=604800,
        help="Signed URL expiration in seconds (default: 604800 = 7 days)",
    )

    args = parser.parse_args()

    try:
        # Auto-detect and upload
        result = upload_to_tos(
            path=args.path,
            bucket_name=args.bucket,
            region=args.region,
            expires=args.expires,
        )

        if result:
            print("\n" + "=" * 60)
            print("✅ Upload Successful!")
            print("=" * 60)
            if os.path.isfile(args.path):
                print(f"Signed URL:\n{result}")
            elif os.path.isdir(args.path):
                print(f"TOS Path:\n{result}")
            print("=" * 60)
            sys.exit(0)
        else:
            logger.error("\n❌ Upload failed")
            sys.exit(1)

    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
