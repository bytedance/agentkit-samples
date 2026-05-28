from __future__ import annotations
import tos
import os
from config import config

def _normalize_endpoint(endpoint: str) -> str:
    endpoint = endpoint.strip()
    if endpoint.startswith("https://"):
        endpoint = endpoint[len("https://") :]
    if endpoint.startswith("http://"):
        endpoint = endpoint[len("http://") :]
    return endpoint.strip("/")

class TOSClient:
    def __init__(
        self,
        ak: str | None = None,
        sk: str | None = None,
        endpoint: str | None = None,
        region: str | None = None,
        bucket: str | None = None,
    ):
        self.ak = ak or config.VOLC_AK
        self.sk = sk or config.VOLC_SK
        self.endpoint = _normalize_endpoint(endpoint or (config.TOS_ENDPOINT or ""))
        self.region = region or config.TOS_REGION
        self.bucket = bucket or config.TOS_BUCKET

        if not self.ak or not self.sk:
            raise ValueError("缺少 VOLC_AK 或 VOLC_SK")
        if not self.endpoint:
            raise ValueError("缺少 TOS_ENDPOINT")
        if not self.region:
            raise ValueError("缺少 TOS_REGION")
        if not self.bucket:
            raise ValueError("缺少 TOS_BUCKET")

        self.client = tos.TosClientV2(self.ak, self.sk, self.endpoint, self.region)

    def public_url(self, key: str) -> str:
        key = key.lstrip("/")
        return f"https://{self.bucket}.{self.endpoint}/{key}"

    def upload_file(self, file_path: str, object_key: str | None = None, public: bool = False) -> str:
        """上传本地文件并返回公网访问地址"""
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")
        
        key = object_key or os.path.basename(file_path)
        acl = tos.ACLType.ACL_Public_Read if public else None
        with open(file_path, "rb") as f:
            self.client.put_object(
                bucket=self.bucket,
                key=key,
                content=f,
                acl=acl
            )
        return self.public_url(key)

    def upload_content(self, content: bytes, object_key: str, public: bool = False) -> str:
        """上传二进制内容并返回公网访问地址"""
        acl = tos.ACLType.ACL_Public_Read if public else None
        self.client.put_object(
            bucket=self.bucket,
            key=object_key,
            content=content,
            acl=acl
        )
        return self.public_url(object_key)

    def upload_stream(self, stream, object_key: str, public: bool = False) -> str:
        acl = tos.ACLType.ACL_Public_Read if public else None
        self.client.put_object(
            bucket=self.bucket,
            key=object_key,
            content=stream,
            acl=acl
        )
        return self.public_url(object_key)
