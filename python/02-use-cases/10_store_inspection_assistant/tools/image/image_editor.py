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

import logging
from tools.tos_upload import upload_file_to_tos

logger = logging.getLogger(__name__)


def draw_bboxes_on_image(
    cropped_image_path: str, detection_result: str, output_path: str
) -> tuple[str, str]:
    """
    针对返回的文字框选结果，对cropped_image_path图片进行框选并保存
    Args:
        cropped_image_path: 裁剪后的图片路径
        detection_result: 包含多个bbox的检测结果字符串
        output_path: 输出图片路径，如果为None则自动生成
    Returns:
        str: 输出图片路径
    """
    import re
    from PIL import Image, ImageDraw
    from pathlib import Path

    # 解析所有bbox坐标
    bbox_pattern = r"<bbox>(\d+)\s+(\d+)\s+(\d+)\s+(\d+)</bbox>"
    bboxes = re.findall(bbox_pattern, detection_result)

    if not bboxes:
        logger.warning(f"未在检测结果中找到有效的bbox坐标: {detection_result}")
        return cropped_image_path

    # 打开图片
    with Image.open(cropped_image_path) as img:
        # 创建绘图对象
        draw = ImageDraw.Draw(img)

        w, h = img.size

        # 设置框选样式
        box_color = "red"
        box_width = 2

        # 绘制每个bbox
        for bbox in bboxes:
            x1, y1, x2, y2 = map(int, bbox)

            x1 = int(x1 * w / 1000)
            y1 = int(y1 * h / 1000)
            x2 = int(x2 * w / 1000)
            y2 = int(y2 * h / 1000)

            # 确保坐标顺序正确
            if x1 > x2:
                x1, x2 = x2, x1
            if y1 > y2:
                y1, y2 = y2, y1
            print(x1, y1, x2, y2)
            # 绘制矩形框
            draw.rectangle([x1, y1, x2, y2], outline=box_color, width=box_width)

            # # 在框的左上角添加小标签
            # label_y = max(0, y1 - 20)  # 确保标签不会超出图片顶部
            # draw.rectangle([x1, label_y, x1 + 40, label_y + 15], fill=box_color)
            # draw.text([x1 + 2, label_y + 2], "文字", fill="white")

        # 生成输出路径
        if output_path is None:
            input_path = Path(cropped_image_path)
            output_path = (
                input_path.parent / f"{input_path.stem}_with_boxes{input_path.suffix}"
            )

        # 保存带框选的图片
        img.save(output_path)

        logger.info(f"已在图片上绘制 {len(bboxes)} 个文字框选，保存至: {output_path}")

        # 上传到tos
        box_marked_url = upload_file_to_tos(output_path)
        logger.info(f"box marked image tos url {box_marked_url}")

        return str(output_path), box_marked_url
