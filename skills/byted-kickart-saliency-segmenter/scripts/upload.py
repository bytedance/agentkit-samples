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

import click
import logging
import sys
import os

from core import Result
from core.api.meida.media import SimpleMediaService
from core.utils.extractor import ImageMetadataExtractor
from core.utils.validator import Validator
from typing import Dict, Any
from core.utils.matriel import ImageMatriel


class ImageValidator(Validator):
    """图片校验器 (具体策略)"""

    def validate(self, metadata: ImageMatriel) -> Dict[str, Any]:  # type: ignore
        result = {"valid": False, "file_type": "image", "errors": [], "warnings": []}
        if metadata.size > 8 * 1024 * 1024:
            result["errors"].append(
                f"图片大小过大，当前为 {metadata.size / 1048576}MB，要求≤8MB"
            )
            return result

        if metadata.width > 8000 or metadata.height > 6000:
            result["errors"].append(
                f"图片分辨率超限，当前为 {metadata.width}x{metadata.height}，要求≤8000x6000"
            )

        if not result["errors"]:
            result["valid"] = True
        return result


@click.command()
@click.option("--file", required=True, type=str, help="本地视频文件绝对路径")
def main(file):
    """本地视频文件上传工具，上传视频并获取媒资ID"""
    logging.info(f"[tool] >>> python3 {' '.join(sys.argv)}")

    # 检查文件是否存在
    if not os.path.isfile(file):
        click.echo(
            Result(code="-1", message=f"文件不存在: {file}").model_dump_json(), err=True
        )
        exit(1)

    try:
        # 创建媒体服务实例
        media_service = SimpleMediaService()

        # 创建元数据提取器和校验器
        extractor = ImageMetadataExtractor()
        validator = ImageValidator()

        # 上传图片文件
        click.echo(f"正在上传图片文件: {file}")
        matriel = media_service.add_media(file, extractor, validator)
        click.echo(Result(code="0", message="success", data=matriel).model_dump_json())
    except Exception as e:
        click.echo(Result(code="-1", message=str(e)).model_dump_json(), err=True)
        exit(1)


if __name__ == "__main__":
    main()
