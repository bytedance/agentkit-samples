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

import os
import asyncio
import aiohttp
import logging
from abc import ABC, abstractmethod
from typing import List, Callable, Optional


class FilenameGenerator(ABC):
    """
    文件名生成策略接口（策略模式）
    """

    @abstractmethod
    def generate(self, url: str) -> str:
        """
        根据URL生成文件名

        Args:
            url: 文件URL

        Returns:
            生成的文件名
        """
        pass

    def modify(self, file_path: str) -> str:
        """
        修改文件路径（模板方法）

        默认直接返回原始文件路径，子类可以重写此方法实现文件修改逻辑

        Args:
            file_path: 原始文件路径

        Returns:
            修改后的文件路径
        """
        return file_path


class DefaultFilenameGenerator(FilenameGenerator):
    """
    默认文件名生成策略：从URL提取文件名
    """

    def generate(self, url: str) -> str:
        filename = os.path.basename(url).split("?")[0]
        if not filename or filename == ".":
            filename = f"download_{hash(url) % 10000}.tmp"
        return filename


class MagicFilenameGenerator(FilenameGenerator):
    """
    魔法文件名生成策略：根据文件内容生成文件名
    """

    # MIME类型到文件扩展名的映射
    MIME_TYPE_MAP = {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/gif": ".gif",
        "image/webp": ".webp",
        "image/bmp": ".bmp",
        "image/tiff": ".tiff",
        "image/svg+xml": ".svg",
        "video/mp4": ".mp4",
        "video/mov": ".mov",
        "video/avi": ".avi",
        "video/mkv": ".mkv",
        "video/flv": ".flv",
        "video/webm": ".webm",
        "video/wmv": ".wmv",
        "video/mpeg": ".mpeg",
        "application/pdf": ".pdf",
        "application/json": ".json",
        "text/plain": ".txt",
        "application/octet-stream": ".bin",
    }

    def generate(self, url: str) -> str:
        filename = os.path.basename(url).split("?")[0]
        if not filename or filename == ".":
            filename = f"download_{hash(url) % 10000}"
        return filename

    def modify(self, file_path: str) -> str:
        """
        修改文件路径：使用magic库检测文件类型并添加正确的文件后缀

        Args:
            file_path: 原始文件路径

        Returns:
            添加正确后缀后的文件路径
        """
        import magic

        # 检查文件是否存在
        if not os.path.exists(file_path):
            return file_path

        # 使用magic库检测文件类型
        with open(file_path, "rb") as f:
            file_data = f.read(2048)
        mime_type = magic.from_buffer(file_data, mime=True)

        # 根据MIME类型获取扩展名
        ext = self.MIME_TYPE_MAP.get(mime_type, ".tmp")
        new_file_path = f"{file_path}{ext}"
        os.rename(file_path, new_file_path)
        return new_file_path


class SequentialFilenameGenerator(FilenameGenerator):
    """
    顺序文件名生成策略：按下载顺序生成文件名
    """

    def __init__(self, prefix: str = "file"):
        self.prefix = prefix
        self.counter = 0

    def generate(self, url: str) -> str:
        self.counter += 1
        ext = os.path.splitext(url.split("?")[0])[1] or ".tmp"
        return f"{self.prefix}_{self.counter}{ext}"


class DownloadResult:
    """
    下载结果数据类
    """

    def __init__(
        self,
        url: str,
        success: bool,
        file_path: Optional[str] = None,
        error: Optional[str] = None,
    ):
        self.url = url
        self.success = success
        self.file_path = file_path
        self.error = error


class BaseDownloader(ABC):
    """
    下载器抽象基类（模板方法模式）
    """

    def __init__(
        self, output: str, filename_generator: Optional[FilenameGenerator] = None
    ):
        """
        初始化下载器

        Args:
            output: 输出目录路径
            filename_generator: 文件名生成策略，默认为DefaultFilenameGenerator
        """
        self.output = output
        self.filename_generator = filename_generator or DefaultFilenameGenerator()
        self._ensure_output_dir()

    def _ensure_output_dir(self):
        """确保输出目录存在"""
        os.makedirs(self.output, exist_ok=True)

    @abstractmethod
    def download(self, urls: List[str]) -> int:
        """
        同步下载接口

        Args:
            urls: URL数组

        Returns:
            下载成功的文件数量
        """
        pass


class ParallelDownloader(BaseDownloader):
    """
    并行异步下载器（组合模式 + 策略模式）
    """

    def __init__(
        self,
        output: str,
        max_concurrent: int = 5,
        timeout: int = 30,
        filename_generator: Optional[FilenameGenerator] = None,
        on_progress: Optional[Callable[[int, int], None]] = None,
    ):
        """
        初始化并行下载器

        Args:
            output: 输出目录路径
            max_concurrent: 最大并发下载数，默认为5
            timeout: 单个请求超时时间（秒），默认为30
            filename_generator: 文件名生成策略
            on_progress: 进度回调函数 (current, total)
        """
        super().__init__(output, filename_generator)
        self.max_concurrent = max_concurrent
        self.timeout = timeout
        self.on_progress = on_progress
        self._downloaded_count = 0
        self._total_count = 0

    async def _download_single(
        self, session: aiohttp.ClientSession, url: str
    ) -> DownloadResult:
        """
        下载单个文件（私有方法）

        Args:
            session: aiohttp客户端会话
            url: 文件URL

        Returns:
            下载结果
        """
        try:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            async with session.get(url, timeout=timeout) as response:
                if response.status != 200:
                    return DownloadResult(
                        url=url, success=False, error=f"HTTP {response.status}"
                    )

                filename = self.filename_generator.generate(url)
                file_path = os.path.join(self.output, filename)

                with open(file_path, "wb") as f:
                    async for chunk in response.content.iter_chunked(8192):
                        f.write(chunk)
                file_path = self.filename_generator.modify(file_path)
                logging.info(f"下载成功: {url} -> {file_path}")
                return DownloadResult(url=url, success=True, file_path=file_path)
        except Exception as e:
            logging.error(f"下载失败 {url}: {str(e)}")
            return DownloadResult(url=url, success=False, error=str(e))

    async def _download_with_semaphore(
        self, session: aiohttp.ClientSession, url: str, semaphore: asyncio.Semaphore
    ) -> DownloadResult:
        """
        使用信号量控制并发的下载任务

        Args:
            session: aiohttp客户端会话
            url: 文件URL
            semaphore: 信号量对象

        Returns:
            下载结果
        """
        async with semaphore:
            result = await self._download_single(session, url)
            self._downloaded_count += 1
            if self.on_progress:
                self.on_progress(self._downloaded_count, self._total_count)
            return result

    async def _async_download(self, urls: List[str]) -> int:
        """
        异步下载核心方法

        Args:
            urls: URL数组

        Returns:
            下载成功的文件数量
        """
        if not urls:
            logging.warning("URL列表为空")
            return 0

        self._downloaded_count = 0
        self._total_count = len(urls)

        semaphore = asyncio.Semaphore(self.max_concurrent)

        async with aiohttp.ClientSession() as session:
            tasks = [
                self._download_with_semaphore(session, url, semaphore) for url in urls
            ]
            results = await asyncio.gather(*tasks)

        success_count = sum(1 for r in results if r.success)
        logging.info(f"下载完成: {success_count}/{len(urls)} 成功")
        return success_count

    def download(self, urls: List[str]) -> int:
        """
        同步下载接口（模板方法）

        Args:
            urls: URL数组

        Returns:
            下载成功的文件数量
        """
        return asyncio.run(self._async_download(urls))
