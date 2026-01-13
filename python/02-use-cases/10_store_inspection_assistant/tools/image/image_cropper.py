#!/usr/bin/env python3
"""
图片裁剪工具 - 根据bbox坐标裁剪图片

使用方法:
    python image_cropper.py <图片路径> <bbox坐标>

bbox坐标格式: <bbox>163 494 738 864</bbox>
其中四个数字分别代表: x1 y1 x2 y2 (左上角和右下角坐标)
"""

import logging
import re
import requests
import sys
from pathlib import Path
from PIL import Image
from tools.tos_upload import upload_file_to_tos

logger = logging.getLogger(__name__)


def parse_bbox(bbox_string):
    """
    解析bbox坐标字符串

    Args:
        bbox_string: 格式为 "<bbox>163 494 738 864</bbox>" 的字符串

    Returns:
        tuple: (x1, y1, x2, y2) 坐标
    """
    # 使用正则表达式提取bbox中的数字
    pattern = r"<bbox>(\d+)\s+(\d+)\s+(\d+)\s+(\d+)</bbox>"
    match = re.match(pattern, bbox_string.strip())

    if not match:
        # 尝试匹配没有空格的格式
        pattern = r"<bbox>(\d+),?\s*(\d+),?\s*(\d+),?\s*(\d+)</bbox>"
        match = re.match(pattern, bbox_string.strip())

    if not match:
        raise ValueError(f"无法解析bbox格式: {bbox_string}")

    x1, y1, x2, y2 = map(int, match.groups())

    # 确保坐标顺序正确
    if x1 > x2:
        x1, x2 = x2, x1
    if y1 > y2:
        y1, y2 = y2, y1

    return x1, y1, x2, y2


def crop_image_by_bbox(image_url: str, bbox_coords: str) -> tuple[str, str]:
    """
    根据bbox坐标裁剪图片

    Args:
        image_path: 输入图片的url
        bbox_coords: 格式为"<bbox>X X X X</bbox>" 的字符串

    Returns:
        str: 输出剪裁好的本地图片路径
    """
    # 如果传入的是字符串，先解析
    if isinstance(bbox_coords, str):
        x1, y1, x2, y2 = parse_bbox(bbox_coords)
    else:
        x1, y1, x2, y2 = bbox_coords
    # 将图片image_url下载到本地
    response = requests.get(image_url)
    image_path = "temp_image.png"

    with open(image_path, "wb") as f:
        f.write(response.content)

    logger.debug(f"Cropping image: {image_path}, bbox: ({x1}, {y1}, {x2}, {y2})")
    # 打开图片
    with Image.open(image_path) as img:
        # 检查坐标是否在图片范围内
        w, h = img.size

        # 确保坐标在图片范围内
        x1 = int(x1 * w / 1000)
        y1 = int(y1 * h / 1000)
        x2 = int(x2 * w / 1000)
        y2 = int(y2 * h / 1000)

        if x1 >= x2 or y1 >= y2:
            raise ValueError(f"无效的裁剪区域: ({x1}, {y1}, {x2}, {y2})")

        # 裁剪图片
        cropped_img = img.crop((x1, y1, x2, y2))

        # 生成输出路径
        # if output_path is None:
        input_path = Path(image_path)
        output_path = (
            input_path.parent / f"{input_path.stem}_cropped{input_path.suffix}"
        )
        # 保存裁剪后的图片
        cropped_img.save(output_path)

        print("图片裁剪完成!")
        print(f"输入图片: {image_path}")
        print(f"裁剪区域: ({x1}, {y1}, {x2}, {y2})")
        print(f"输出图片: {output_path}")
        print(f"裁剪尺寸: {x2 - x1} x {y2 - y1}")

        # 上传到tos
        cropped_url = upload_file_to_tos(output_path)
        logger.info(f"cropped image tos url {cropped_url}")

        return str(output_path), cropped_url


def main():
    """主函数 - 处理命令行参数"""
    if len(sys.argv) < 3:
        print("使用方法: python image_cropper.py <图片路径> <bbox坐标>")
        print("bbox坐标格式: <bbox>163 494 738 864</bbox>")
        sys.exit(1)

    image_path = sys.argv[1]
    bbox_string = sys.argv[2]

    # 验证输入文件是否存在
    if not Path(image_path).exists():
        print(f"错误: 图片文件不存在: {image_path}")
        sys.exit(1)

    try:
        # 执行裁剪
        output_path = crop_image_by_bbox(image_path, bbox_string)
        print(f"\n裁剪成功! 输出文件: {output_path}")

    except Exception as e:
        print(f"错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
