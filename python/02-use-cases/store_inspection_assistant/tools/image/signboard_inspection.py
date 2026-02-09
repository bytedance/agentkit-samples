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

from tools.model_auth import get_ark_api_key, get_base_url
from tools.image.image_editor import draw_bboxes_on_image
from volcenginesdkarkruntime import Ark

logger = logging.getLogger(__name__)


client = Ark(
    api_key=get_ark_api_key(),
    base_url=get_base_url(),
    timeout=1800,
)


def signboard_detection_tool(picture_url: str) -> str:
    """
    Signboard detection tool, input signboard image URL, return signboard detection result, including bbox information
    Args:
        picture_url (str): Signboard image URL
    Returns:
        str: Signboard detection result, including bbox information, format such as: <bbox>x1 y1 x2 y2</bbox>
    """

    logger.debug(f"Running signboard_detection_tool with picture_url: {picture_url}")

    response = client.chat.completions.create(
        model="seed-1-6-250915",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"Please select the complete signboard area in the image, including the logo and the English and Chinese name. Try to remove any irrelevant areas as much as possible. Represent the selected area in the form of <bbox>x1 y1 x2 y2</bbox>. Note to ensure the integrity of the logo and text. url: {picture_url}",
                    },
                ],
            }
        ],
    )
    return response.choices[0].message.content


def signboard_char_detection_tool(cropped_image_path: str) -> str:
    """
    Signboard character detection tool, input signboard image path, return signboard character detection result, including bbox information
    Args:
        cropped_image_path (str): Signboard image path
    Returns:
        str: Signboard character detection result, including bbox information, format such as: <bbox>x1 y1 x2 y2</bbox>
    """

    import base64

    with open(cropped_image_path, "rb") as image_file:
        base64_image = base64.b64encode(image_file.read()).decode("utf-8")

    response = client.chat.completions.create(
        model="seed-1-6-250915",
        temperature=0.1,
        top_p=0.1,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{base64_image}",
                            "detail": "high",
                        },
                    },
                    {
                        "type": "text",
                        "text": "Please select each character in the image and output it using a bounding box. Each Chinese and English character should be selected separately and represented in the form of <bbox>x1 y1 x2 y2</bbox>.",
                    },
                ],
            }
        ],
    )

    char_crop_result = response.choices[0].message.content
    # For each character, draw a bounding box on the cropped image and save the result
    try:
        output_path = draw_bboxes_on_image(cropped_image_path, char_crop_result, None)
        logger.info(f"Signboard character bbox image saved to: {output_path}")
    except Exception as e:
        logger.error(f"Error drawing signboard character bboxes: {e}")

    return output_path


def led_status_analysis_tool(cropped_image_path: str) -> str:
    """
    LED light status analysis tool, input cropped signboard image path, return LED light status analysis result
    Args:
        cropped_image_path (str): Cropped signboard image path
    Returns:
        str: LED light status analysis result, describing whether LED is normal, whether there are any exceptions, etc.
    """

    logger.debug(
        f"Running led_status_analysis_tool with cropped_image_path: {cropped_image_path}"
    )

    # cropped_image_path转base64
    import base64

    with open(cropped_image_path, "rb") as image_file:
        base64_image = base64.b64encode(image_file.read()).decode("utf-8")

    response = client.chat.completions.create(
        model="seed-1-6-250915",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{base64_image}",
                            "detail": "high",
                        },
                    },
                    # {"type": "text", "text": "You are a professional LED light status analysis agent. Please carefully check the cropped image, step by step, to check whether there are any problems with the LED light status in the signboard. Please check carefully and output the parts with problems."},
                    {
                        "type": "text",
                        "text": "You are a professional signboard image analysis expert, specializing in text detection and LED illumination status analysis of store signboard images. Based on the information in the given image URL, please perform the following analysis: 1. Detect all text and logo in the image. 2. Strictly determine if the four Chinese characters for '火', '山', '咖' and '啡' the four English characters for 'VOLC,' and all elements of the logo are present. If any text is missing, output the missing content directly. 3. If every character and logo is present, determine if each character is normally illuminated without obvious dark areas.",
                    },
                ],
            }
        ],
        thinking={"typed": "enabled"},
        reasoning_effort="high",
    )
    return response.choices[0].message.content
