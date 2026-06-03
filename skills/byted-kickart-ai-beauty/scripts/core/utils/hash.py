# MIT License
# 
# Copyright (c) 2026 ByteDance
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

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