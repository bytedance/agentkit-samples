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

import os
from datetime import datetime
from typing import Optional
import threading
import re

import tos
from google.adk.agents.callback_context import CallbackContext
from google.adk.models import LlmResponse
from tos import HttpMethodType
from veadk.auth.veauth.utils import get_credential_from_vefaas_iam
from veadk.utils.logger import get_logger

logger = get_logger(__name__)


# --- Define the Callback Function ---
def callback_for_debug(callback_context: CallbackContext) -> Optional[LlmResponse]:
    pass


# --- URL Shortener Singleton ---
class UrlShortener:
    _instance = None
    _lock = threading.Lock()

    # 进制转换字符集
    CHAR_SET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
    BASE = len(CHAR_SET)

    PREFIX = "⌥"

    def __new__(cls):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super(UrlShortener, cls).__new__(cls)
                    cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        self._id_lock = threading.Lock()
        self._current_id = 0
        self._short_to_long = {}  # key: short_url, value: original_url
        self._long_to_short = {}  # key: original_url, value: short_url

    def _encode(self, num: int) -> str:
        if num == 0:
            return self.CHAR_SET[0]

        encoded = []
        while num > 0:
            num, remainder = divmod(num, self.BASE)
            encoded.append(self.CHAR_SET[remainder])
        result = "".join(reversed(encoded))

        # Pad to 5 characters
        return result.rjust(5, "0")

    def url2code(self, original_url: str) -> str:
        """
        输入一个url字符串，换出来一个短ID
        """
        try:
            # 1. Check if already exists (Deduplication)
            with self._id_lock:
                if original_url in self._long_to_short:
                    return self._long_to_short[original_url]

                # 2. Increment ID and Encode
                self._current_id += 1
                current_id = self._current_id
                short_code = self._encode(current_id)

            # 3. Construct short ID
            short_id = f"{self.PREFIX}{short_code}"

            # 4. Store mappings
            with self._id_lock:
                # Double check in case another thread inserted it
                self._short_to_long[short_id] = original_url
                self._long_to_short[original_url] = short_id

            return short_id
        except Exception:
            return original_url

    def code2url(self, short_id: str) -> Optional[str]:
        """
        输入这个短ID，换出原始的url
        """
        return self._short_to_long.get(short_id, short_id)

    def replace_in_text(self, text: str) -> str:
        """
        给你一个长字符串，提取短ID并无缝替换回原始URL
        """
        # Pattern matches ⌥<code> where code is 5 characters
        pattern = r"⌥([0-9a-zA-Z]{5})"

        def replace_match(match):
            full_short_id = match.group(0)
            original_url = self.code2url(full_short_id)
            return original_url if original_url != full_short_id else full_short_id

        return re.sub(pattern, replace_match, text)

    def extract_ids_to_urls(self, text: str) -> list[str]:
        """
        从字符串中提取所有短ID并转换为URL列表
        """
        # Pattern matches ⌥<code> where code is 5 characters
        pattern = r"⌥([0-9a-zA-Z]{5})"
        matches = re.findall(pattern, text)

        urls = []
        for code in matches:
            short_id = f"⌥{code}"
            original_url = self.code2url(short_id)
            if original_url != short_id:
                urls.append(original_url)

        return urls


# Global instance
url_shortener = UrlShortener()


def upload_file_to_tos(
    file_path: str,
    object_key: Optional[str] = None,
    region: str = "cn-beijing",
    expires: int = 604800,  # 7-day validity
) -> Optional[str]:
    bucket_name = os.getenv("DATABASE_TOS_BUCKET")

    # Check if file exists
    if not os.path.exists(file_path):
        logger.info(f"Error: File does not exist: {file_path}")
        return None

    if not os.path.isfile(file_path):
        logger.info(f"Error: Path is not a file: {file_path}")
        return None

    # Retrieve STS from IAM Role
    access_key = os.getenv("VOLCENGINE_ACCESS_KEY")
    secret_key = os.getenv("VOLCENGINE_SECRET_KEY")
    session_token = ""

    if not (access_key and secret_key):
        # try to get from vefaas iam
        cred = get_credential_from_vefaas_iam()
        access_key = cred.access_key_id
        secret_key = cred.secret_access_key
        session_token = cred.session_token

    if not access_key or not secret_key:
        logger.info(
            "Error: VOLCENGINE_ACCESS_KEY and VOLCENGINE_SECRET_KEY are not provided or IAM Role is not configured."
        )
        return None

    # Auto-generate object_key (using filename)
    if not object_key:
        # Combine timestamp and original filename to avoid overwriting
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.basename(file_path)
        name, ext = os.path.splitext(filename)
        object_key = f"upload/{name}_{timestamp}{ext}"

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
            else:
                raise e

        # Upload file
        result = client.put_object_from_file(
            bucket=bucket_name, key=object_key, file_path=file_path
        )

        logger.info("File uploaded successfully!")
        logger.info(f"ETag: {result.etag}")
        logger.info(f"Request ID: {result.request_id}")

        # Generate signed URL
        signed_url_output = client.pre_signed_url(
            http_method=HttpMethodType.Http_Method_Get,
            bucket=bucket_name,
            key=object_key,
            expires=expires,
        )

        signed_url = signed_url_output.signed_url
        logger.info(f"Signed URL generated successfully (valid for {expires} seconds)")
        logger.info(f"Access URL: {signed_url}")

        return signed_url

    except tos.exceptions.TosClientError as e:
        logger.info(f"TOS client error: {e}")
        return None
    except tos.exceptions.TosServerError as e:
        logger.info(f"TOS server error: {e}")
        logger.info(f"Status code: {e.status_code}")
        logger.info(f"Error code: {e.code}")
        logger.info(f"Error message: {e.message}")
        return None
    except Exception as e:
        logger.info(f"File upload failed: {e}")
        import traceback

        traceback.print_exc()
        return None
    finally:
        # Close client
        if client:
            client.close()
