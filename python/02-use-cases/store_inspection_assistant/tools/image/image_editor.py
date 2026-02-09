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
    Draw bounding boxes on cropped image based on detection result
    Args:
        cropped_image_path: Path to cropped image
        detection_result: String containing multiple bbox coordinates
        output_path: Path to save output image. If None, will generate automatically
    Returns:
        str: Path to output image with bounding boxes drawn
    """
    import re
    from PIL import Image, ImageDraw
    from pathlib import Path

    # Parse all bbox coordinates
    bbox_pattern = r"<bbox>(\d+)\s+(\d+)\s+(\d+)\s+(\d+)</bbox>"
    bboxes = re.findall(bbox_pattern, detection_result)

    if not bboxes:
        logger.warning(
            f"No valid bbox coordinates found in detection result: {detection_result}"
        )
        return cropped_image_path

    # Open image
    with Image.open(cropped_image_path) as img:
        # Create drawing object
        draw = ImageDraw.Draw(img)

        w, h = img.size

        # Set box selection style
        box_color = "red"
        box_width = 2

        # Draw each bbox
        for bbox in bboxes:
            x1, y1, x2, y2 = map(int, bbox)

            x1 = int(x1 * w / 1000)
            y1 = int(y1 * h / 1000)
            x2 = int(x2 * w / 1000)
            y2 = int(y2 * h / 1000)

            # Ensure coordinates are in correct order
            if x1 > x2:
                x1, x2 = x2, x1
            if y1 > y2:
                y1, y2 = y2, y1
            print(x1, y1, x2, y2)
            # Draw rectangle box
            draw.rectangle([x1, y1, x2, y2], outline=box_color, width=box_width)

            # # Add small label at top-left corner of box
            # label_y = max(0, y1 - 20)  # Ensure label doesn't go above image top
            # draw.rectangle([x1, label_y, x1 + 40, label_y + 15], fill=box_color)
            # draw.text([x1 + 2, label_y + 2], "Text", fill="white")

        # Generate output path if not provided
        if output_path is None:
            input_path = Path(cropped_image_path)
            output_path = (
                input_path.parent / f"{input_path.stem}_with_boxes{input_path.suffix}"
            )

        # Save image with bounding boxes drawn
        img.save(output_path)

        logger.info(
            f"Drawn {len(bboxes)} bounding boxes on image, saved to: {output_path}"
        )

        # Upload to tos and return url
        box_marked_url = upload_file_to_tos(output_path)
        logger.info(f"Box marked image tos url {box_marked_url}")

        return str(output_path), box_marked_url
