# Copyright 2026 ByteDance
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


import hashlib
import hmac
import zlib


class HashUtils:
    """哈希计算工具"""

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
