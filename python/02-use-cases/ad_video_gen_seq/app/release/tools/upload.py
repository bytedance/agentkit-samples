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
TOS file upload utility
Provides functionality to upload files to Volcano Engine TOS object storage and returns a signed access URL
Implemented using the tos library directly
"""

from typing import Optional

from veadk.utils.logger import get_logger

logger = get_logger(__name__)


def upload_file_to_tos(
    file_path: str,
    object_key: Optional[str] = None,
    region: str = "cn-beijing",
    expires: int = 604800,  # 7-day validity
) -> Optional[str]:
    """
    Upload a file to TOS object storage and return a signed accessible URL

    Args:
        file_path: Local file path
        bucket_name: TOS bucket name, defaults to "aaa-bbb-ccc-ddd"
        object_key: Object storage key name; if empty, uses the filename
        region: TOS region, defaults to cn-beijing
        ak: Access Key; if empty, reads from environment variables
        sk: Secret Key; if empty, reads from environment variables
        expires: Signed URL validity period (seconds), defaults to 7 days (604800 seconds)

    Returns:
        str: Signed TOS URL that can be accessed directly
        None: Returns None if upload fails

    Environment variables required:
        VOLCENGINE_ACCESS_KEY: Volcano Engine access key
        VOLCENGINE_SECRET_KEY: Volcano Engine secret key

    Usage example:
        >>> url = upload_file_to_tos("./video.mp4")
        >>> print(url)
        https://bucket.tos-cn-beijing.volces.com/video.mp4?X-Tos-Signature=...
    """
    from app.utils import upload_file_to_tos as upload_file

    return upload_file(file_path, object_key, region, expires)
