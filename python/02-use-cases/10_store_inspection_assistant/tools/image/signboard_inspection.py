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
    门店招牌检测工具，输入门店招牌图片URL，返回检测结果，包括招牌位置的bbox信息
    Args:
        picture_url (str): 门店招牌图片URL
    Returns:
        str: 检测结果，包含bbox信息，格式如：<bbox>x1 y1 x2 y2</bbox>
    """

    logger.debug(f"Running signboard_detection_tool with picture_url: {picture_url}")

    response = client.chat.completions.create(
        model="doubao-seed-1-6-vision-250815",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"帮我框选图片里，火山咖啡招牌完整区域。要完整包含logo和中英文名称的主要区域，并且尽可能的剔除掉不相关的区域，以<bbox>x1 y1 x2 y2</bbox>的形式表示，注意保障logo和文字的完整性。url: {picture_url}",
                    },
                ],
            }
        ],
    )
    return response.choices[0].message.content


def signboard_char_detection_tool(cropped_image_path: str) -> str:
    """
    图片招牌文字检测工具，用于检测图片中招牌文字，并将检测的结果在图片上画框，返回画上文字框以后的图片路径
    Args:
        picture_url (str): 门店招牌图片URL
    Returns:
        str: 返回画上文字框以后得图片路径
    """

    import base64

    with open(cropped_image_path, "rb") as image_file:
        base64_image = base64.b64encode(image_file.read()).decode("utf-8")

    response = client.chat.completions.create(
        model="doubao-seed-1-6-vision-250815",
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
                        "text": "请框选图片中的每个文字，并用bounding box输出，每个中文、英文字符都单独框选出来，以<bbox>x1 y1 x2 y2</bbox>的形式表示。",
                    },
                ],
            }
        ],
    )

    char_crop_result = response.choices[0].message.content
    # 针对返回的文字框选结果，对cropped_image_path 图片进行框选并保存
    try:
        output_path = draw_bboxes_on_image(cropped_image_path, char_crop_result, None)
        logger.info(f"文字框选图片已保存至: {output_path}")
    except Exception as e:
        logger.error(f"绘制文字框选时出错: {e}")

    return output_path


def led_status_analysis_tool(cropped_image_path: str) -> str:
    """
    LED发光状态分析工具，输入剪裁后的门店招牌图片URL，返回LED发光状态分析结果
    Args:
        cropped_image_url (str): 剪裁后的门店招牌图片URL
    Returns:
        str: LED发光状态分析结果，描述LED是否正常发光，有无异常等
    """

    logger.debug(
        f"Running led_status_analysis_tool with cropped_image_url: {cropped_image_path}"
    )

    # cropped_image_path转base64
    import base64

    with open(cropped_image_path, "rb") as image_file:
        base64_image = base64.b64encode(image_file.read()).decode("utf-8")

    response = client.chat.completions.create(
        model="doubao-seed-1-6-251015",
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
                    # {"type": "text", "text": "你是专业的照片LED发光检测员。请仔细检查框选出来的照片图片，逐步检查招牌中的log、文字，是否存在LED不亮的问题。请仔细检查，输出有问题的部分。"},
                    {
                        "type": "text",
                        "text": "你是一个专业的招牌图片分析专家，擅长对门店招牌图片进行文字检测和LED发光状态分析。 请根据给定的图片url中的信息，做如下分析： 1. 检测图片中的所有文字和logo 2. 严格判断火、山、咖、啡四中文个字符、VOLC四个英文字符、logo各个元素是否都存在，如果有文字不存在，则直接输出缺失的内容。 3. 如果每个文字、logo都存在，判断每个字是否都正常发光，没有明显暗区。",
                    },
                ],
            }
        ],
        thinking={"typed": "enabled"},
        reasoning_effort="high",
    )
    return response.choices[0].message.content
