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

import json
import os
import sys
import time

from abc import ABC, abstractmethod
from typing import Dict, Any, List
from pathlib import Path
import pandas as pd

# 动态加载项目根目录，以便于引入 core.Result
sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
from auth.strategy import AuthStrategyFactory
from utils.hash import HashUtils
from utils.validator import Validator
from utils.extractor import MetadataExtractor
from api.meida.chunks import (
    AppConfig,
    ApiClientFactory,
    MaterialUploader,
    MediaFormatter,
    IamService,
    KickartMuseService,
)
from core import MediaConfig


class RemoteUploader(ABC):
    """远程上传器接口 (策略模式)"""

    @abstractmethod
    def upload(self, file: str) -> Any:
        pass


class MuseRemoteUploader(RemoteUploader):
    """基于 Muse 的远程上传器具体实现"""

    def __init__(self):  # type: ignore
        strategy = AuthStrategyFactory.create()
        client = ApiClientFactory.create(strategy)
        self.uploader = MaterialUploader(client)

    def upload(self, file: str) -> Any:
        owner_id = self.uploader.iam.get_admin_user_id()
        file_md5, file_crc32, file_size = HashUtils.file_hash(file)

        file_name = os.path.splitext(os.path.basename(file))[0]
        file_ext = os.path.splitext(file)[1].lstrip(".")

        cat = "image" if file_ext.lower() in AppConfig.IMAGE_EXTENSIONS else "video"
        title = f"artclaw-material-{int(time.time())}"
        owner_type = "user"

        state = self.uploader.muse.get_upload_state(
            file_md5, file_size, file_crc32, owner_id
        )
        state = self.uploader.stream_upload(
            file, file_md5, file_size, file_crc32, owner_id, state
        )

        media_id = self.uploader.muse.create_material(
            file_md5,
            file_size,
            file_name,
            file_ext,
            state["SkipDataComplete"],
            owner_id,
            owner_type,
            title,
            cat,
        )

        media_info = self.uploader.muse.poll_media_info(media_id, owner_id, owner_type)
        return MediaFormatter.format(MediaFormatter.simplify(media_info))


class KickartUploader(RemoteUploader):
    def __init__(self, source: str):
        self.strategy = AuthStrategyFactory.create()
        self.client = ApiClientFactory.create(self.strategy)
        self.iam = IamService(self.client)
        self.muse = KickartMuseService(self.client)
        self.source = source

    def upload(self, file: str) -> Any:
        """通过文件 上传媒资"""

        owner_id = self.iam.get_admin_user_id()
        owner_type = "user"
        title = f"artclaw-material-{int(time.time())}"

        body = {
            "Owner": {"Id": owner_id, "Type": "PERSON"},
            "CreateUrlFilmInfo": {
                "Title": title,
                "SourceFrom": self.source,
                "MediaFirstCategory": "video",
                "MaterialUrl": file,
                "Description": title,
            },
        }

        result = self.client.request(
            action="CreateUrlFilm", service=AppConfig.SERVICE_MUSE, body=body
        )
        media_id = result.get("Result", {}).get("MediaId")
        if not media_id:
            raise ValueError("CreateUrlFilm 未返回 MediaId")

        media_info = self.muse.poll_media_info(media_id, owner_id, owner_type)
        return MediaFormatter.format(MediaFormatter.simplify(media_info))


class MediaRepository:
    """仓储层：处理底层 CSV 数据的读写"""

    def __init__(self, base_dir: str = MediaConfig.STORAGE_BASE_DIR):
        self.base_dir = Path(base_dir)

    def _get_path(self, group: str) -> Path:
        return self.base_dir / f"{group}.csv"

    def load(self, group: str) -> pd.DataFrame:
        path = self._get_path(group)
        if not path.exists():
            return pd.DataFrame(columns=MediaConfig.CSV_COLUMNS)
        return pd.read_csv(path, header=None, names=MediaConfig.CSV_COLUMNS)

    def save(self, group: str, df: pd.DataFrame):
        path = self._get_path(group)
        os.makedirs(path.parent, exist_ok=True)
        df.to_csv(path, index=False, header=False)

    def clear(self, group: str):
        path = self._get_path(group)
        if path.exists():
            os.remove(path)


class SimpleMediaRepository:
    """媒体缓存仓储层：处理底层 JSON 文件的读写（仿照 MediaRepository 设计）"""

    def __init__(self, base_dir: str = None):  # type: ignore
        self.base_dir = Path(base_dir or MediaConfig.STORAGE_BASE_DIR)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _get_path(self, media_id: str) -> Path:
        """获取媒体缓存文件路径"""
        return self.base_dir / f"{media_id}.json"

    def load(self, media_id: str) -> dict | None:
        """加载指定媒体ID的缓存数据"""
        path = self._get_path(media_id)
        if not path.exists():
            raise FileNotFoundError(f"文件不存在: {path}")
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def save(self, media_id: str, data: dict):
        """保存媒体数据到缓存"""
        path = self._get_path(media_id)
        os.makedirs(path.parent, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def clear(self, media_id: str):
        """清除指定媒体ID的缓存"""
        path = self._get_path(media_id)
        if path.exists():
            os.remove(path)

    def clear_all(self):
        """清除所有缓存"""
        for file in self.base_dir.glob("*.json"):
            file.unlink()


class MediaService:
    """业务服务层：协调校验、提取、上传与存储 (依赖注入)"""

    def __init__(
        self, repository: MediaRepository = None, uploader: RemoteUploader = None
    ):  # type: ignore
        self.repository = repository or MediaRepository()
        self.uploader = uploader or MuseRemoteUploader()

    def add_media(
        self,
        file: str,
        group: str,
        metadata: dict,
        extractor: MetadataExtractor,
        validator: Validator,
    ) -> Any:  # type: ignore
        metadata_result = extractor.extract(file)
        validation_result = validator.validate(metadata_result)

        if not validation_result.get("valid", False):
            return validation_result

        # 上传文件到远程服务器
        matriel = self.uploader.upload(file)

        # 补全缺失的媒体信息
        if hasattr(matriel, "type") and matriel.type == "":
            matriel.type = validation_result.get("file_type", "")

        # 构造存储记录
        row = {
            "group": group,
            "channel": metadata.get("channel", ""),
            "account": metadata.get("chat_id", ""),
            "path": file,
            "id": matriel.id,
            "material": matriel.model_dump_json(),
            "timestamp": str(time.time()),
        }

        # 持久化到仓储
        df = self.repository.load(group)
        df.loc[len(df)] = row
        self.repository.save(group, df)

        return matriel

    def list_media(self, group: str) -> List[Dict]:
        df = self.repository.load(group)
        if df.empty:
            return []
        return df["material"].map(lambda x: json.loads(x)).to_list()  # type: ignore

    def remove_media(self, media_id: str, group: str):
        df = self.repository.load(group)
        df.drop(df[df["id"].eq(media_id)].index, inplace=True)
        self.repository.save(group, df)

    def clear_media(self, group: str):
        self.repository.clear(group)


class SimpleMediaService:
    """简化版媒体服务：仅负责文件上传，不需要group参数，支持本地缓存"""

    def __init__(
        self, repository: SimpleMediaRepository = None, uploader: RemoteUploader = None
    ):  # type: ignore
        self.repository = repository or SimpleMediaRepository()
        self.uploader = uploader or MuseRemoteUploader()

    def add_media(
        self, file: str, extractor: MetadataExtractor, validator: Validator
    ) -> Any:  # type: ignore
        """
        上传单个文件到远程服务器，并将信息存储到本地缓存

        Args:
            file: 本地文件绝对路径
            extractor: 元数据提取器（可选）
            validator: 校验器（可选）

        Returns:
            Matriel 对象，包含上传后的媒体信息（id、url等）
        """
        metadata_result = extractor.extract(file)
        validation_result = validator.validate(metadata_result)

        if not validation_result.get("valid", False):
            return validation_result

        # 上传文件到远程服务器
        matriel = self.uploader.upload(file)

        # 补全缺失的媒体信息
        matriel.width = getattr(metadata_result, "width", 0)
        matriel.height = getattr(metadata_result, "height", 0)
        if hasattr(metadata_result, "duration"):
            matriel.duration = getattr(metadata_result, "duration", 0)
        if hasattr(metadata_result, "closest_ratio"):
            matriel.closest_ratio = getattr(metadata_result, "closest_ratio", "")
        matriel.size = getattr(metadata_result, "size", 0)

        # 将媒体信息保存到本地缓存
        media_info = {
            "id": matriel.id,
            "url": matriel.url,
            "type": matriel.type,
            "width": matriel.width,
            "height": matriel.height,
            "size": matriel.size,
            "timestamp": time.time(),
        }
        if hasattr(matriel, "duration"):
            media_info["duration"] = matriel.duration
        if hasattr(matriel, "closest_ratio"):
            media_info["closest_ratio"] = matriel.closest_ratio
        self.repository.save(matriel.id, media_info)
        return matriel

    def get_media(self, media_id: str) -> dict:
        """
        通过媒资ID获取媒体详细信息（优先从本地缓存读取）

        Args:
            media_id: 媒资ID

        Returns:
            媒体信息字典
        """
        return self.repository.load(media_id)  # type: ignore
