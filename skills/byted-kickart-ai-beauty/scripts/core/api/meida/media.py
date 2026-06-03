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
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from auth.strategy import AuthStrategyFactory
from utils.hash import HashUtils
from core.api.meida.chunks import (
    AppConfig, ApiClientFactory, 
    MaterialUploader, MediaFormatter
)

from utils.validator import Validator, DefaultValidator
from utils.extractor import MetadataExtractor

class MediaConfig:
    """媒体相关配置与常量"""
    IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
    VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov"}
    
    IMAGE_MAX_SIZE = 8 * 1024 * 1024
    VIDEO_MAX_SIZE = 50 * 1024 * 1024
    
    IMAGE_MIN_WIDTH = 300
    IMAGE_MIN_HEIGHT = 300
    IMAGE_MAX_PIXELS = 36_000_000
    
    CSV_COLUMNS = ["group", "channel", "account", "path", "id", "material", "timestamp"]
    STORAGE_BASE_DIR = "/tmp/openclaw/replicator/media"


class RemoteUploader(ABC):
    """远程上传器接口 (策略模式)"""
    @abstractmethod
    def upload(self, file_path: str) -> Any:
        pass

class MuseRemoteUploader(RemoteUploader):
    """基于 Muse 的远程上传器具体实现"""
    def __init__(self): # type: ignore
        strategy = AuthStrategyFactory.create()
        client = ApiClientFactory.create(strategy)
        self.uploader = MaterialUploader(client)
        
    def upload(self, file_path: str) -> Any:
        owner_id = self.uploader.iam.get_admin_user_id()
        file_md5, file_crc32, file_size = HashUtils.file_hash(file_path)
        
        file_name = os.path.splitext(os.path.basename(file_path))[0]
        file_ext = os.path.splitext(file_path)[1].lstrip(".")
        
        cat = "image" if file_ext.lower() in AppConfig.IMAGE_EXTENSIONS else "video"
        title = f"artclaw-material-{int(time.time())}"
        owner_type = "user"

        state = self.uploader.muse.get_upload_state(file_md5, file_size, file_crc32, owner_id)
        state = self.uploader.stream_upload(file_path, file_md5, file_size, file_crc32, owner_id, state)
        
        media_id = self.uploader.muse.create_material(
            file_md5, file_size, file_name, file_ext, 
            state["SkipDataComplete"], owner_id, owner_type, title, cat
        )
        
        media_info = self.uploader.muse.poll_media_info(media_id, owner_id, owner_type)
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


class MediaService:
    """业务服务层：协调校验、提取、上传与存储 (依赖注入)"""
    
    def __init__(self, repository: MediaRepository, uploader: RemoteUploader = None): # type: ignore
        self.repository = repository
        self.uploader = uploader or MuseRemoteUploader()

    def add_media(self, file: str, group: str, metadata: dict, extractor: MetadataExtractor = None, validator: Validator = None) -> Any: # type: ignore
        if extractor and validator:
            metadata_result = extractor.extract(file)
            validation_result = validator.validate(metadata_result)
        else:
            validation_result = DefaultValidator.validate(file)
            
        if not validation_result.get('valid', False):
            return validation_result

        # 上传文件到远程服务器
        matriel = self.uploader.upload(file)

        # 补全缺失的媒体信息
        if hasattr(matriel, 'type') and matriel.type == "":
            matriel.type = validation_result.get('file_type', '')
        
        # 构造存储记录
        row = {
            'group': group,
            'channel': metadata.get('channel', ''),
            'account': metadata.get('chat_id', ''),
            'path': file,
            'id': matriel.id,
            'material': matriel.model_dump_json(),
            'timestamp': str(time.time())
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
        return df["material"].map(lambda x: json.loads(x)).to_list() # type: ignore

    def remove_media(self, media_id: str, group: str):
        df = self.repository.load(group)
        df.drop(df[df["id"].eq(media_id)].index, inplace=True)
        self.repository.save(group, df)

    def clear_media(self, group: str):
        self.repository.clear(group)