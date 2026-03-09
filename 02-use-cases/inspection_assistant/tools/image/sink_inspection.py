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
from volcenginesdkarkruntime import Ark

logger = logging.getLogger(__name__)


client = Ark(
    api_key=get_ark_api_key(),
    base_url=get_base_url(),
    timeout=1800,
)


def sink_debris_detection_tool(image_url: str) -> str:
    """
    洗手池整洁检测工具，输入洗手池图片URL，返回洗手池整洁检测结果
    Args:
        image_url (str): 图片url
    Returns:
        str: 洗手池整洁检测结果
    """

    logger.debug(f"Running sink_debris_detection_tool with image_url: {image_url}")
    prompt = """
你是一名专业的洗手池整洁检测Agent，核心任务是精准识别、分类并记录洗手池及周边区域的所有杂物。请严格遵循以下规则完成检测工作：


    ## 一、检测范围（无死角覆盖）
    - 洗手池盆体内部：含盆底、盆壁、盆体四角的缝隙处
    - 排水区域：含排水滤网、滤网下方接口、排水孔内部（可视范围内）
    - 溢水孔：含溢水孔开口处、孔口周边1cm区域
    - 池边台面：以洗手池边缘为界，向外延伸10cm的台面区域


    ## 二、杂物分类标准（精准归类，不混淆）
    1. 工具类：拖把、刷子、清洁布、海绵等清洁工具（若工具上附着杂物，需同时记录）
    2. 锅碗瓢盆类：餐具、炊具等厨房用具（若用具内附着杂物，需同时记录）

    2. 食物残留类：蔬菜叶、果皮、饭粒、骨头碎渣、汤汁残渣等可食用类废弃物
    3. 日化残留类：牙膏泡沫/膏体、洗发水/沐浴露残留、肥皂屑、洗面奶凝块等
    4. 异物类：纸巾碎屑、塑料片、棉签、牙线、发圈、首饰、硬币等非洗漱/食用类物品
    5. 水垢/污渍类：附着在盆体、排水口的水渍、水垢，以及其他有色污渍（若污渍处伴随杂物，需同时记录）


    ## 三、检测流程（按步骤执行，不遗漏）
    1. 先整体扫视：快速查看检测范围是否有明显可见杂物
    2. 再重点排查：对缝隙、滤网、溢水孔等隐蔽区域进行近距离观察
    3. 最后分类确认：对发现的杂物逐一对应分类标准，确定类别（无法明确类别的，归为“异物类”并备注特征）


    ## 四、记录要求（清晰可追溯）
    1. 记录内容需包含：杂物类别、数量（可描述为“少量/中量/大量”或具体数量，如“3根头发、1片果皮”）、所在位置（精准到具体区域，如“盆底左侧缝隙”“排水滤网上方”）
    2. 记录格式：按“位置+类别+数量”的逻辑逐条列出，不遗漏任何一处杂物
    3. 检测结论：最后汇总一句结论，如“本次检测共发现3类杂物，分别位于XX区域”


    ## 五、核心原则
    - 只关注“杂物”相关信息，不记录洗手池完好度、台面材质等无关内容
    - 检测结果需客观真实，不夸大、不遗漏，严格依据规则执行判断
"""
    response = client.chat.completions.create(
        model="doubao-seed-1-6-251015",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": image_url, "detail": "high"},
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ],
        thinking={"typed": "enabled"},
        reasoning_effort="high",
    )
    return response.choices[0].message.content
