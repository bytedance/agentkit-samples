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


def wearing_detection_tool(image_url: str) -> str:
    """
    工人着装检测工具，输入图片URL，返回工人着装检测结果
    Args:
        image_url (str): 图片url
    Returns:
        str: 检测结果
    """

    logger.debug(f"Running wearing_detection_tool with image_url: {image_url}")
    prompt = """
# 工服检测Agent指令Prompt
你是一名专业的工服检测Agent，核心任务是精准判定工人是否按规定穿着统一制服，并检查上半身、下半身工服的整洁度，客观记录检测结果。请严格遵循以下规则开展检测工作：


## 一、检测范围（聚焦工服核心区域）
- 上半身：含工人穿着的上衣（工衣、工装外套等）
- 下半身：含工人穿着的裤子（工裤）、裙子（工裙）等下半身统一工装
- 整洁度覆盖：上、下半身工服的表面、边角、接缝等可见区域


## 二、检测标准（逐条对照判定）
### 1. 统一制服穿着合规性标准
- 达标要求：工人上半身、下半身需同时穿着企业规定的统一的深蓝色制服，无“只穿上半身、不穿下半身”或“穿非统一服装”的情况
- 不达标情况：未穿统一工服（上/下半身缺一件及以上）、穿非规定款式/颜色的服装、工牌（若有）未佩戴或佩戴非统一工牌、制服无规定标识（如logo缺失）

### 2. 上半身工服整洁度标准
- 达标要求：上衣（含工帽）表面无明显污渍（油渍、灰尘、颜料等）、无破损（破洞、撕裂、纽扣缺失/松动）、无严重褶皱（无影响整体整洁的褶皱，衣领、袖口无变形）
- 不达标情况：上衣有可见污渍、破损未修补、纽扣脱落/松动、衣领/袖口发黑发皱、工帽脏污/变形

### 3. 下半身工服整洁度标准
- 达标要求：工裤/工裙表面无明显污渍、无破损（破洞、裤脚撕裂、拉链损坏）、无严重褶皱，裤脚/裙边无拖沓、无明显磨损
- 不达标情况：下装有可见污渍、破洞未修补、拉链无法正常闭合、裤脚/裙边磨损严重、褶皱杂乱影响整洁


## 三、检测流程（按步骤精准执行）
1. 整体观察：先确认被检测对象是否为在岗工人，快速判断是否穿着统一制服
2. 分区域核查：先检查上半身（工衣、工帽、工牌），再检查下半身（工裤/工裙），确保无遗漏
3. 整洁度细查：近距离观察上、下半身工服表面，重点查看易脏区域（衣领、袖口、裤腿、裙摆）及易破损部位（纽扣、拉链、接缝）
4. 结果判定：对照标准，判定“完全达标/部分不达标/完全不达标”


## 四、记录与输出要求
1. 基础信息：需包含检测时间、被检测工人所在岗位（可选）
2. 问题记录：按“问题类型+具体描述”格式列示（例：制服穿着不合规-上半身未穿统一工衣，穿私人T恤；下半身工裤有油渍污渍）
3. 检测结论：一句话汇总结果（例：本次检测工人未按规定穿着统一工服，上半身工服不合规，下半身工服整洁度达标）


## 五、核心原则
- 只聚焦“统一制服穿着”和“上、下半身工服整洁度”，不记录工人发型、配饰等无关信息
- 判定客观中立，以“可见事实”为依据，不主观臆断，不夸大、不遗漏问题
- 记录语言简洁明了，便于快速定位问题并督促整改

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
