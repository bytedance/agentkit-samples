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


import click
import logging
import sys
import os

from core import Result
from core.api.meida.media import SimpleMediaService
from core.utils.extractor import ImageMetadataExtractor
from core.utils.validator import ImageValidator


@click.command()
@click.option("--file", required=True, type=str, help="数字形象图片绝对路径")
def main(file):
    """本地图片文件上传工具，上传图片并获取媒资ID"""
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
