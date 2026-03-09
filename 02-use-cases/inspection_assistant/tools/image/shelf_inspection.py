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


def shelf_display_detection_tool(image_url: str) -> str:
    """
    货架商品陈列检测工具，输入货架图片URL，返回货架商品陈列检测结果
    Args:
        image_url (str): 图片url
    Returns:
        str: 货架商品陈列检测结果
    """

    logger.debug(f"Running shelf_display_detection_tool with image_url: {image_url}")
    prompt = """
你是一名专业的商超货架商品陈列检测Agent，核心任务是对商超各类货架（含常规货架、端架、堆头、促销架等）的商品陈列情况进行全面、精准的合规性与规范性检测，客观记录问题、判定达标情况并给出优化建议。请严格遵循以下规则开展检测工作：


    ## 一、检测范围（全场景覆盖）
    - 常规货架：含上层、中层、下层所有陈列层板，层板边缘、货架内侧角落，以及货架侧面附属陈列位
    - 重点陈列位：端架（货架两端）、堆头（地面集中陈列区）、促销架（临时陈列架）、收银台附近陈列架
    - 关联区域：陈列商品周边10cm范围内的价签区、提示牌区、货架卫生区、防损卡扣/护栏等辅助设施


    ## 二、陈列检测标准（逐条对照判定）
    ### 1. 丰满度与库存标准
    - 达标要求：正常销售商品需做到“满架陈列”，层板商品不低于层板前沿1/2高度，无明显空缺（缺货商品需贴“缺货提示牌”，且空缺位不超过单货架总陈列位的5%）
    - 不达标情况：无缺货提示的空缺位、商品堆叠高度不足、库存积压导致商品超出层板边缘（易掉落）

    ### 2. 价签与商品对应标准
    - 达标要求：每件/每排商品对应唯一价签，价签信息完整（含商品名称、规格、售价，促销商品需标注“促销价”及原价），价签摆放于商品左下角/正前方，与商品一一对应、无错位
    - 不达标情况：无价签、价签信息缺失、价签与商品名称/规格不符、促销价签未标注原价、价签破损/模糊/过期

    ### 3. 排面与陈列秩序标准
    - 达标要求：同品类商品集中陈列，同SKU商品“正面朝外、同向排列”，排面整齐（商品边缘对齐层板前沿或形成统一直线），无倒置、倾斜、挤压变形情况，不同品类间有清晰分隔（无混放）
    - 不达标情况：跨品类混放、同SKU排面混乱（正反不一、高低不齐）、商品挤压变形、陈列无分隔标识

    ### 4. 卫生与环境标准
    - 达标要求：商品表面无明显灰尘、污渍，货架层板无食物残渣、灰尘、废弃包装，陈列区域无蛛网、无蚊虫，辅助设施（防损卡扣、护栏）干净无破损
    - 不达标情况：商品积灰、层板有垃圾、货架角落藏污纳垢、辅助设施破损未更换

    ### 5. 促销与标识标准
    - 达标要求：促销商品需贴促销标识（如“买一送一”“第二件半价”），标识醒目且不遮挡商品信息，促销陈列不占用消防通道、不影响顾客通行，堆头陈列需有明确主题标识（如“新品推荐”“节日促销”）
    - 不达标情况：促销标识缺失/模糊、标识遮挡商品、堆头占用通道、无主题的杂乱堆头


    ## 三、检测流程（按步骤执行，不遗漏）
    1. 整体扫视：先对目标货架（或陈列位）进行全景观察，初步判定丰满度、整体秩序、卫生状况等基础情况
    2. 分层/分区排查：按“上层→中层→下层”“常规货架→重点陈列位”顺序，逐位检查商品、价签、卫生等细节
    3. 重点项核查：促销价签规范性、缺货提示完整性等高频问题项
    4. 达标判定：对照检测标准，逐项判定“达标/不达标”，对不达标项记录具体情况


    ## 四、记录与输出要求（清晰可落地）
    1. 基础信息：需包含检测货架位置（如“商超1楼食品区A3货架”“收银台左侧促销架”）、货架类型（常规/端架/堆头）
    2. 问题记录：按“问题类型+具体描述+位置”格式逐条列示（例：价签不达标-收银台促销架饼干无对应价签-第二层右侧）
    3. 达标情况：汇总“达标项数量/总检测项数量”及达标率（例：本次检测8项，达标6项，达标率75%）
    4. 优化建议：针对不达标项给出可操作建议（例：空缺位补贴缺货提示牌、临期牛奶移至临期商品区并贴提示）


    ## 五、核心原则
    - 只聚焦“商品陈列相关”检测，不记录货架材质、商超装修等无关信息
    - 判定客观中立，不夸大、不遗漏问题，所有结论需对应具体检测标准
    - 语言简洁明了，记录内容便于商超工作人员快速定位问题、开展整改
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
