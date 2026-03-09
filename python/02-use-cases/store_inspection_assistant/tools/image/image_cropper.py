#!/usr/bin/env python3
"""
Image Cropper Tool - crop image by bbox coordinates

Usage:
    python image_cropper.py <input_image_path> <bbox_coords>

bbox coordinates format: <bbox>163 494 738 864</bbox>
where the four numbers represent: x1 y1 x2 y2 (top-left and bottom-right coordinates)
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
    Parse bbox coordinates string

    Args:
        bbox_string: String in format "<bbox>163 494 738 864</bbox>"

    Returns:
        tuple: (x1, y1, x2, y2) coordinates
    """
    # Extract coordinates using regex
    pattern = r"<bbox>(\d+)\s+(\d+)\s+(\d+)\s+(\d+)</bbox>"
    match = re.match(pattern, bbox_string.strip())

    if not match:
        # Try matching without spaces
        pattern = r"<bbox>(\d+),?\s*(\d+),?\s*(\d+),?\s*(\d+)</bbox>"
        match = re.match(pattern, bbox_string.strip())

    if not match:
        raise ValueError(f"Cannot parse bbox format: {bbox_string}")

    x1, y1, x2, y2 = map(int, match.groups())

    # 确保坐标顺序正确
    if x1 > x2:
        x1, x2 = x2, x1
    if y1 > y2:
        y1, y2 = y2, y1

    return x1, y1, x2, y2


def crop_image_by_bbox(image_url: str, bbox_coords: str) -> tuple[str, str]:
    """
    Crop image by bbox coordinates

    Args:
        image_url: URL of input image
        bbox_coords: String in format "<bbox>X X X X</bbox>"

    Returns:
        str: Output path of cropped image
    """
    # If bbox_coords is a string, parse it first
    if isinstance(bbox_coords, str):
        x1, y1, x2, y2 = parse_bbox(bbox_coords)
    else:
        x1, y1, x2, y2 = bbox_coords
    # Download image from URL
    response = requests.get(image_url)
    image_path = "temp_image.png"

    with open(image_path, "wb") as f:
        f.write(response.content)

    logger.debug(f"Cropping image: {image_path}, bbox: ({x1}, {y1}, {x2}, {y2})")
    # Open image
    with Image.open(image_path) as img:
        # Check if coordinates are within image bounds
        w, h = img.size

        # Check if coordinates are within image bounds
        x1 = int(x1 * w / 1000)
        y1 = int(y1 * h / 1000)
        x2 = int(x2 * w / 1000)
        y2 = int(y2 * h / 1000)

        if x1 >= x2 or y1 >= y2:
            raise ValueError(f"Invalid crop area: ({x1}, {y1}, {x2}, {y2})")

        # Crop image
        cropped_img = img.crop((x1, y1, x2, y2))

        # Generate output path
        # if output_path is None:
        input_path = Path(image_path)
        output_path = (
            input_path.parent / f"{input_path.stem}_cropped{input_path.suffix}"
        )
        # Save cropped image
        cropped_img.save(output_path)

        print("Image cropping completed!")
        print(f"Input image: {image_path}")
        print(f"Crop area: ({x1}, {y1}, {x2}, {y2})")
        print(f"Output image: {output_path}")
        print(f"Crop size: {x2 - x1} x {y2 - y1}")

        # Upload cropped image to TOS
        cropped_url = upload_file_to_tos(output_path)
        logger.info(f"cropped image tos url {cropped_url}")

        return str(output_path), cropped_url


def main():
    """Main function - handle command line arguments"""
    if len(sys.argv) < 3:
        print("Usage: python image_cropper.py <image_path> <bbox_coords>")
        print("bbox coordinates format: <bbox>163 494 738 864</bbox>")
        sys.exit(1)

    image_path = sys.argv[1]
    bbox_string = sys.argv[2]

    # Check if image file exists
    if not Path(image_path).exists():
        print(f"Error: Image file does not exist: {image_path}")
        sys.exit(1)

    try:
        # Execute cropping
        output_path = crop_image_by_bbox(image_path, bbox_string)
        print(f"\nImage cropping completed successfully! Output file: {output_path}")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
