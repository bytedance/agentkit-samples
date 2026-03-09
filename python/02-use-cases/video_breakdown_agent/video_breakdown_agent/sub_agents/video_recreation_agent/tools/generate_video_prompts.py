"""
提示词生成工具 - 将分镜数据转换为视频生成提示词
参考: multimedia项目的prompt工程和Plan中的电影级提示词标准范式

Skill方案：三阶段工作流（知识库作为可选参考）
1. 特征提取（LLM）：从脚本提取运镜、氛围、音频等特征
2. 知识检索（函数）：从知识库匹配相关提示词片段（可选，允许空）
3. 组装生成（LLM）：100%基于原始脚本，参考知识片段风格补充细节

核心原则：
- 完全忠于原始视频脚本，不偏离脚本内容
- 知识库仅作为表达风格参考，不强制套用
- 如果知识库无匹配项，完全基于脚本自主生成
"""

from __future__ import annotations

import json
import logging
import os
import random
from typing import Dict, List, Optional

from google.adk.tools import ToolContext

logger = logging.getLogger(__name__)

# ==================== Skill方案知识库 ====================

PROMPT_KNOWLEDGE_BASE = {
    # 运镜描述库（基于阿里云指南 + 用户案例 + 搜索结果）
    "camera_movements": {
        "推进": [
            "镜头从{起点}匀速推进至{焦点}，运动丝滑流畅，焦点精准跟随",
            "推进镜头从{前景}过渡到{主体}，焦点从浅景深逐渐收缩，背景渐进式虚化",
            "镜头缓慢向前推进，逐渐聚焦于{主体}细节，景深控制突出主体",
        ],
        "拉远": [
            "镜头从{特写}匀速拉远至{全景}，展现完整空间关系和环境层次",
            "缓慢拉开镜头，从局部过渡到全景，层次感清晰，视野逐渐开阔",
        ],
        "环绕": [
            "镜头360度环绕{主体}旋转，展现全方位细节和质感",
            "镜头从左侧缓慢环绕至右侧，角度从45度到135度匀速变化，流畅展示{主体}全貌",
        ],
        "跟拍": [
            "镜头流畅跟随{主体}运动，保持画面稳定构图，动态节奏感强",
            "手持跟拍，略带晃动增强真实感，视角贴近{主体}，代入感强",
        ],
        "固定": [
            "固定机位，镜头稳定对准{主体}，构图居中，展现稳定画面",
            "静态构图，{主体}位于画面{位置}，稳定展现细节，氛围克制",
        ],
        "一镜到底": [
            "10秒一镜到底运镜，全程无剪辑断点，镜头从{起点}自然衔接慢拉，匀速穿过{过渡物}，顺滑过渡到{终点}，运镜丝滑连贯、速度均匀不卡顿",
            "一镜到底长镜头，镜头从{场景A}流畅移动至{场景B}，中间经过{过渡元素}，全程运动连贯无停顿，氛围感拉满",
        ],
        "穿越": [
            "镜头穿过{障碍物}（如门/窗/缝隙），自然衔接前后空间，过渡流畅无断点",
            "镜头从{前景物}缝隙穿出，视角从封闭空间过渡到开阔场景，空间感递进",
        ],
        "摇移": [
            "镜头无缝摇移至{目标}处，运动平稳流畅，视角自然切换",
            "镜头从{起点}摇移到{终点}，速度均匀，画面连贯衔接",
        ],
        "升降": [
            "镜头缓慢升降拍摄，视角从{低角度}过渡到{高角度}，展现空间纵深",
            "升降镜头展现场景全貌，从近处升至远景，层次感丰富",
        ],
    },
    # 打光描述库（按场景类型分类）
    "lighting_setups": {
        "产品展示_高端": [
            "三点布光：主光源（左侧柔光箱，色温5500K），辅光（右侧反光板），轮廓光（顶部LED灯带），突出产品质感和高级感",
            "侧光从45度照射，勾勒出{主体}轮廓和质感，柔光箱补光消除阴影，高光反射细腻精致",
        ],
        "产品展示_简约": [
            "均匀顶光漫射，白色无缝背景，柔和自然光，无明显阴影，呈现简约高级感",
            "环形光源包围{主体}，光线柔和均匀，呈现极简风格，画面干净纯粹",
        ],
        "生活场景_温馨": [
            "自然光从窗户洒入，暖色调环境光（色温3200K），营造温馨亲切氛围",
            "顶光柔和漫射，暖黄色调，光线柔和不刺眼，氛围温暖治愈，家的感觉",
        ],
        "生活场景_真实": [
            "自然环境光，明暗对比自然，符合真实生活场景光线分布，质感真实",
            "混合光源（自然光+室内灯光），光影层次丰富，真实感强，生活化气息浓厚",
        ],
        "动态场景": [
            "侧逆光强化边缘轮廓，动态光影随运动变化，层次感强，视觉冲击力强",
            "顶光+侧光组合，光影对比明显，突出动作冲击力和力量感",
        ],
        "节日喜庆": [
            "暖色调主光（色温3000K），红色金色光效点缀，营造喜庆氛围，节日感拉满",
            "环境光融入节日元素（灯笼、彩灯），暖光包裹画面，烘托浓厚节日氛围",
        ],
    },
    # 景深与色调控制
    "visual_aesthetics": {
        "景深_浅": "浅景深虚化背景，焦点精准锁定{主体}，突出主体细节，层次分明",
        "景深_深": "深景深保持前后景清晰，展现完整空间层次，环境信息丰富",
        "色调_暖": "暖色调主导（橙黄色系），色温3000-3500K，营造温馨亲切感，情感温暖",
        "色调_冷": "冷色调主导（蓝灰色系），色温5500-6500K，呈现高级质感，专业商务感",
        "色调_高饱和": "高饱和度色彩，色彩鲜明跳跃，视觉冲击力强，活力四射",
        "色调_低饱和": "低饱和度色彩，柔和淡雅，文艺质感，情绪克制",
        "色调_新年": "红色金色主导，高饱和度，喜庆氛围，新年元素（红灯笼、福字）点缀",
    },
    # 音频描述模板
    "audio_templates": {
        "女声旁白": "女性旁白说道：「{content}」，语气{mood}，语速{speed}，声音{tone}",
        "男声旁白": "男性旁白说道：「{content}」，语气{mood}，语速{speed}，声音{tone}",
        "对话": "{角色}说道：「{content}」，{emotion}地说，语速{speed}，情绪真挚",
        "BGM_轻快": "背景音乐为{style}，BPM {tempo}，{instruments}，节奏明快，烘托{atmosphere}氛围",
        "BGM_舒缓": "背景音乐为{style}，节奏舒缓，{instruments}，营造{atmosphere}氛围，情绪沉浸",
        "BGM_喜庆": "背景音乐为{style}，节奏欢快，传统乐器（锣鼓、唢呐），烘托喜庆节日氛围",
        "环境音": "{environment}环境音，{specific_sounds}，增强场景真实感和代入感",
        "音效": "{action}的音效，{sound_quality}，细节清晰，增强画面感染力",
    },
    # 阿里云典型案例片段（拆解为可复用的模式）
    "aliyun_patterns": {
        "新年一镜到底": {
            "运镜": "10秒一镜到底运镜，全程无剪辑断点，新年喜庆氛围感拉满；镜头慢拉匀速穿过厨房门，顺滑过渡到客厅，无缝摇移至窗户处，紧接着慢推镜头从窗户向外穿出",
            "氛围": "画面融入红灯笼、福字等新年元素，烘托浓厚过年氛围，节日感拉满",
            "音频": "背景音乐喜庆欢快，背景语音为：「新春快乐，阖家幸福，马年吉祥」",
        },
        "产品特写递进": {
            "运镜": "特写镜头从产品侧面匀速推进至正面，焦距从f/2.8逐渐收缩至f/1.4",
            "景深": "景深控制使背景渐进式虚化，突出产品主体，细节清晰可见",
        },
        "场景穿梭": {
            "运镜": "镜头从{场景A}穿梭至{场景B}，中间经过{过渡点}，运动连贯流畅",
            "过渡": "自然衔接，无断点，速度均匀，空间感递进",
        },
    },
    # 营销视频模板精华（从现有10个模板提取）
    "marketing_essentials": {
        "产品展示": {
            "关键词": ["特写镜头", "环绕旋转", "侧光勾勒", "高级感", "产品质感"],
            "运镜": "镜头缓慢环绕产品旋转，展现360度细节，突出质感和工艺",
        },
        "痛点场景": {
            "关键词": ["快节奏切换", "功能特写", "生活化", "实用性"],
            "运镜": "镜头快速推进到细节，突出功能亮点，节奏明快",
        },
        "情感共鸣": {
            "关键词": ["暖光", "胶片质感", "虚化背景", "治愈系"],
            "氛围": "暖色调柔光，营造温馨治愈氛围，情感共鸣",
        },
        "对比冲击": {
            "关键词": ["分屏对比", "强对比光影", "快节奏", "视觉冲击"],
            "运镜": "快速切换前后对比，视觉冲击力强，转化效果明显",
        },
    },
}

# 保留原有的电影级提示词模板库（作为降级方案）
CINEMATIC_TEMPLATES = {
    # 通用模板（模板①-④）
    "epic_scifi": {
        "name": "史诗级科幻风",
        "keywords": ["史诗级", "写实风格", "光影对比", "逆光", "烟雾漂浮", "深蓝调"],
        "适用": "品牌大片、科技产品",
    },
    "thriller": {
        "name": "心理惊悚风",
        "keywords": [
            "写实风格",
            "冷白光",
            "手持镜头",
            "悬疑氛围",
            "声音细节",
            "静谧张力",
        ],
        "适用": "悬疑剧情、情绪类内容",
    },
    "dreamy": {
        "name": "文艺梦境风",
        "keywords": [
            "清晨",
            "雾气",
            "柔光",
            "梦境感",
            "延时镜头",
            "慢节奏",
            "光线穿透",
        ],
        "适用": "文艺内容、治愈系视频",
    },
    "action": {
        "name": "动作大片风",
        "keywords": [
            "动作大片",
            "手持镜头",
            "爆炸",
            "高速切换",
            "火光",
            "残骸",
            "压迫感",
        ],
        "适用": "动作场景、冲击力内容",
    },
    # 营销视频模板（模板⑤-⑩）
    "product_premium": {
        "name": "产品展示-高端质感型",
        "keywords": [
            "特写镜头",
            "环绕旋转",
            "侧光勾勒",
            "焦点切换",
            "高级感",
            "产品质感",
            "虚化背景",
        ],
        "适用": "3C、美妆、轻奢、珠宝",
        "hook_strategy": "产品环绕旋转",
    },
    "pain_point": {
        "name": "痛点场景-问题解决型",
        "keywords": [
            "痛点场景",
            "功能特写",
            "快节奏切换",
            "暖色调",
            "生活化",
            "实用性",
        ],
        "适用": "工具、生活用品、家电、厨具",
        "hook_strategy": "痛点场景展示",
    },
    "comparison": {
        "name": "对比冲击-前后反差型",
        "keywords": [
            "分屏对比",
            "动作爆发",
            "强对比光影",
            "快节奏",
            "视觉冲击",
            "转化导向",
        ],
        "适用": "清洁、美妆、改造、健身",
        "hook_strategy": "脏污对比",
    },
    "lifestyle": {
        "name": "场景植入-生活方式型",
        "keywords": [
            "场景植入",
            "生活方式",
            "情感共鸣",
            "暖光",
            "胶片质感",
            "虚化背景",
            "治愈系",
        ],
        "适用": "家居、美食、母婴、宠物",
        "hook_strategy": "温馨场景",
    },
    "info_dense": {
        "name": "卖点罗列-信息密集型",
        "keywords": [
            "信息密集",
            "快速切换",
            "卖点罗列",
            "动态字幕",
            "强节奏",
            "电商风格",
        ],
        "适用": "课程、软件、工具、知识付费",
        "hook_strategy": "卖点弹出",
    },
    "ugc": {
        "name": "UGC真实感-素人种草型",
        "keywords": [
            "UGC风格",
            "手持晃动",
            "开箱仪式",
            "真实感",
            "生活滤镜",
            "降低戒备",
        ],
        "适用": "口碑营销、测评",
        "hook_strategy": "开箱展示",
    },
}


def detect_video_type(segments: List[Dict]) -> str:
    """
    智能识别视频类型（营销视频 vs 通用创意）

    根据分镜数据的特征信号判断视频类型，优先识别为营销视频
    """
    if not segments:
        return "lifestyle"  # 默认生活方式型

    signals = {
        "product_focus": 0,  # 产品特写占比
        "text_overlay": 0,  # 文字标签数量
        "pace": 0,  # 节奏快慢（分镜切换频率）
        "human_presence": 0,  # 人物出现占比
        "hand_gesture": 0,  # 手部动作（产品展示典型信号）
    }

    # 分析每个分镜
    for segment in segments:
        content = segment.get("visual_content", "").lower()
        tags = segment.get("functional_tags", [])

        # 产品焦点检测
        if any(
            keyword in content for keyword in ["产品", "展示", "特写", "拿起", "手持"]
        ):
            signals["product_focus"] += 1

        # 文字标签检测
        if "产品介绍" in tags or "价值输出" in tags:
            signals["text_overlay"] += 1

        # 节奏检测（短分镜=快节奏）
        if segment.get("duration", 5.0) < 2.5:
            signals["pace"] += 1

        # 人物检测
        if any(keyword in content for keyword in ["人物", "女性", "男性", "手", "脸"]):
            signals["human_presence"] += 1

        # 手部动作检测（产品展示的强信号）
        if any(
            keyword in content for keyword in ["手", "拿起", "握持", "触摸", "打开"]
        ):
            signals["hand_gesture"] += 1

    total_segments = len(segments)

    # 判断逻辑（优先识别为营销视频）
    if signals["product_focus"] > total_segments * 0.5:
        return "product_premium"  # 产品展示型
    elif signals["hand_gesture"] >= 2:
        return "product_premium"  # 产品展示型
    elif signals["text_overlay"] >= 3:
        return "info_dense"  # 信息密集型
    elif signals["pace"] > total_segments * 0.7:
        return "pain_point"  # 快节奏带货型
    elif signals["human_presence"] > signals["product_focus"] * 1.5:
        return "lifestyle"  # 生活方式型
    else:
        return "lifestyle"  # 默认通用


# ==================== Skill方案：辅助函数 ====================


def format_bgm_info(bgm_info: Dict) -> str:
    """将BGM分析结果格式化为可读字符串"""
    if not bgm_info or not bgm_info.get("has_bgm"):
        return "无背景音乐"

    parts = []
    if bgm_info.get("style"):
        parts.append(f"风格: {bgm_info['style']}")
    if bgm_info.get("mood"):
        parts.append(f"情绪: {bgm_info['mood']}")
    if bgm_info.get("tempo"):
        parts.append(f"节奏: {bgm_info['tempo']}")
    if bgm_info.get("instruments"):
        parts.append(f"乐器: {', '.join(bgm_info['instruments'])}")

    return "；".join(parts) if parts else "有背景音乐"


# ==================== Skill方案：阶段1 - 特征提取 ====================


async def extract_script_features(segment: Dict, bgm_info: Optional[Dict]) -> Dict:
    """
    阶段1：LLM提取脚本关键特征

    Args:
        segment: 单个分镜数据
        bgm_info: BGM分析结果

    Returns:
        结构化特征Dict
    """
    system_prompt = """
你是视频分析专家。分析脚本并提取关键特征，输出严格JSON格式。

输出格式示例：
{
  "运镜类型": ["推进", "固定"],
  "场景氛围": "简约",
  "光影特点": ["柔光", "侧光"],
  "色调风格": {"主色调": "暖白", "饱和度": "中等", "氛围": "暖色调"},
  "景深控制": {"虚化程度": "弱虚化", "焦点": "产品"},
  "构图方式": {"主体位置": "画面中心", "法则": "中心构图"},
  "运动特征": {"速度": "慢速", "节奏": "流畅", "特效": "无"},
  "音频要素": ["女声旁白"],
  "营销重点": "产品展示",
  "视觉风格": "高饱和度"
}

运镜类型可选：推进、拉远、环绕、跟拍、固定、一镜到底、穿越、摇移、升降
场景氛围可选：简约、温馨、高级、真实、动感、文艺、喜庆
光影特点可选：柔光、侧光、顶光、自然光、环形光、逆光、暖色调、冷色调、混合光
音频要素可选：女声旁白、男声旁白、对话、轻快BGM、舒缓BGM、喜庆BGM、环境音、音效
营销重点可选：产品展示、场景植入、情感共鸣、痛点解决、对比冲击
视觉风格可选：高饱和度、低饱和度、自然、胶片质感、简约、新年喜庆
"""

    # 从 Vision 分析结果中提取增强的视觉信息
    visual = segment.get("视觉表现", {})
    lighting = visual.get("光影", {})
    color = visual.get("色调", {})
    depth = visual.get("景深", {})
    composition = visual.get("构图", {})
    motion = visual.get("运动", {})

    user_message = f"""
分析以下视频脚本，提取关键特征（仅输出JSON）：

脚本信息：
- 画面：{segment.get("visual_content", "") or visual.get("画面内容", "无")}
- 镜头：{segment.get("shot_type", "") or visual.get("景别", "中景")}，{segment.get("camera_movement", "") or visual.get("运镜", "固定")}
- 场景：{segment.get("scene", "室内")}
- 功能标签：{", ".join(segment.get("functional_tags", []) or segment.get("内容标签", []))}
- 语音：{segment.get("speech_text") or "无"}
- BGM：{format_bgm_info(bgm_info) if bgm_info else "无"}

视觉增强信息：
- 光影：{lighting.get("光源类型", "未知")} / {lighting.get("光源方向", "未知")} / {lighting.get("明暗对比", "中等")}
- 色调：{color.get("主色调", "未知")} / {color.get("饱和度", "中等")} / {color.get("色彩氛围", "中性")}
- 景深：{depth.get("虚化程度", "未知")} / 焦点：{depth.get("焦点主体", "未知")}
- 构图：{composition.get("主体位置", "未知")} / {composition.get("构图法则", "未知")}
- 运动：{motion.get("速度", "未知")} / {motion.get("节奏感", "未知")}
"""

    try:
        from video_breakdown_agent.utils.doubao_client import call_doubao_text

        response = await call_doubao_text(
            model=os.getenv("MODEL_AGENT_NAME", "doubao-seed-1-6-251015"),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=0.3,  # 低温度保证稳定
            max_tokens=300,
        )

        content = response["choices"][0]["message"]["content"].strip()
        # 尝试解析JSON
        features = json.loads(content)
        logger.info(f"特征提取成功: {features}")
        return features

    except Exception as e:
        logger.error(f"特征提取失败: {e}")
        raise


# ==================== Skill方案：阶段2 - 知识检索 ====================


def retrieve_relevant_knowledge(
    features: Dict, knowledge_base: Dict = PROMPT_KNOWLEDGE_BASE
) -> List[str]:
    """
    阶段2：根据特征检索知识库片段（纯函数，无LLM）

    注意：知识库仅作为可选参考，不强制匹配。如果没有匹配项，返回空列表。

    Args:
        features: 提取的特征
        knowledge_base: 知识库

    Returns:
        相关知识片段列表（可能为空）
    """
    knowledge_pieces = []

    # 1. 检索运镜描述（宽松匹配）
    for movement in features.get("运镜类型", []):
        if movement in knowledge_base["camera_movements"]:
            # 随机选择一个描述（避免重复）
            desc = random.choice(knowledge_base["camera_movements"][movement])
            knowledge_pieces.append(f"【运镜参考】{desc}")

    # 2. 检索打光描述（宽松匹配，允许不匹配）
    scene_type = features.get("场景氛围", "")
    marketing_focus = features.get("营销重点", "")

    # 尝试精确匹配
    lighting_key = (
        f"{marketing_focus}_{scene_type}" if marketing_focus and scene_type else None
    )
    if lighting_key and lighting_key in knowledge_base["lighting_setups"]:
        desc = random.choice(knowledge_base["lighting_setups"][lighting_key])
        knowledge_pieces.append(f"【打光参考】{desc}")
    # 尝试场景类型匹配
    elif scene_type in ["温馨", "真实", "喜庆"]:
        key = f"生活场景_{scene_type}"
        if key in knowledge_base["lighting_setups"]:
            desc = random.choice(knowledge_base["lighting_setups"][key])
            knowledge_pieces.append(f"【打光参考】{desc}")
    # 尝试营销重点匹配（但不强制）
    elif marketing_focus == "产品展示":
        key = "产品展示_高端"
        if key in knowledge_base["lighting_setups"]:
            desc = random.choice(knowledge_base["lighting_setups"][key])
            knowledge_pieces.append(f"【打光参考】{desc}")

    # 3. 检索视觉美学（仅在明确匹配时添加）
    visual_style = features.get("视觉风格", "")
    if visual_style:
        for key, desc in knowledge_base["visual_aesthetics"].items():
            if visual_style in key or (scene_type and scene_type in key):
                knowledge_pieces.append(f"【视觉参考】{desc}")
                break

    # 4. 检索音频模板（宽松匹配）
    for audio_element in features.get("音频要素", []):
        for template_key, template in knowledge_base["audio_templates"].items():
            if audio_element in template_key:
                knowledge_pieces.append(f"【音频参考】{template}")
                break

    # 5. 检索营销模板精华（仅在明确匹配时添加）
    if marketing_focus and marketing_focus in knowledge_base["marketing_essentials"]:
        essentials = knowledge_base["marketing_essentials"][marketing_focus]
        if "运镜" in essentials:
            knowledge_pieces.append(f"【营销参考】{essentials['运镜']}")

    if knowledge_pieces:
        logger.info(f"检索到{len(knowledge_pieces)}个相关知识片段作为参考")
    else:
        logger.info("未找到匹配的知识片段，将完全基于原始脚本生成")

    return knowledge_pieces


# ==================== Skill方案：阶段3 - 组装生成 ====================


async def generate_final_prompt(
    segment: Dict, bgm_info: Optional[Dict], features: Dict, knowledge_pieces: List[str]
) -> str:
    """
    阶段3：基于原始脚本 + 知识片段生成最终提示词

    Args:
        segment: 原始分镜数据
        bgm_info: BGM信息
        features: 提取的特征
        knowledge_pieces: 检索到的知识片段

    Returns:
        最终视频生成提示词
    """
    system_prompt = """
你是专业的视频生成提示词工程师。

任务：基于原始脚本生成用于AI视频生成的专业提示词。

核心原则（优先级从高到低）：
1. **画面内容是灵魂**：提示词必须以「画面内容」为核心展开，所有具体的人物、产品、动作、背景元素都必须体现在提示词中，不能省略或替换为笼统词汇
2. **主体与动线必须清晰**（新增，最关键）：
   - 开篇明确镜头主体（人/手/产品/物体），禁止用"画面中"等模糊开头
   - 凡涉及动作、位移、场景变化，必须从**摄像机视角**说明：
     主体从哪里 → 做了什么动作 → 移动到哪里 / 状态如何变化
   - 示例写法："一只手从右侧入画，缓慢将水杯推向画面中央，镜头固定追随手部特写"
   - 多个主体共存时，说明空间位置关系（前景/背景/左侧/右侧/画面外）
   - 物体运动时说明运动方向、速度、是否连续（慢推 / 快速掠过 / 静止出现）
3. **完全忠于原始脚本**：不编造、不偏离脚本，所有信息来自提供的数据
4. **专业视觉补充**：在忠实描述画面内容的基础上，自然融入运镜、光影、色调等专业描述
5. **知识库仅作参考**：知识片段仅在与脚本相关时参考表达风格，不相关则忽略

重要：**画面内容字段的每一个具体描述都必须出现在生成的提示词中**。

输出格式：
- 单段落，以镜头主体+初始状态开头，按顺序描述：动作/变化过程 → 摄像机跟随方式 → 光影/色调/氛围
- 使用顿号、逗号连接，句号结束
- 长度：100-200字（描述越丰富越好，但不堆砌重复词）
"""

    # 提取增强的视觉信息
    visual = segment.get("视觉表现", {})
    lighting = visual.get("光影", {})
    color = visual.get("色调", {})
    depth = visual.get("景深", {})

    # 兼容两种数据格式（旧版字段名 / 新版视觉表现）
    visual_content = segment.get("visual_content", "") or visual.get("画面内容", "无")
    shot_type = segment.get("shot_type", "") or visual.get("景别", "中景")
    camera_movement = segment.get("camera_movement", "") or visual.get("运镜", "固定")
    start_time = segment.get("start_time", segment.get("start", 0))
    end_time = segment.get("end_time", segment.get("end", 3))
    duration = segment.get("duration", end_time - start_time)

    # 仅在非默认值时输出视觉参数，避免默认值干扰 LLM
    lighting_summary_parts = []
    if lighting.get("光源类型") not in ("", "自然光", "未知", None):
        lighting_summary_parts.append(lighting["光源类型"])
    if lighting.get("光源方向") not in ("", "正面光", "未知", None):
        lighting_summary_parts.append(lighting["光源方向"])
    if lighting.get("明暗对比") not in ("", "中等", "未知", None):
        lighting_summary_parts.append(lighting["明暗对比"])
    lighting_summary = (
        "、".join(lighting_summary_parts)
        if lighting_summary_parts
        else "（无特殊光影）"
    )

    color_summary_parts = []
    if color.get("主色调") not in ("", "自然", "中性", "未知", None):
        color_summary_parts.append(color["主色调"])
    if color.get("色彩氛围") not in ("", "中性", "未知", None):
        color_summary_parts.append(color["色彩氛围"])
    if color.get("滤镜效果") not in ("", "无", "未知", None):
        color_summary_parts.append(f"滤镜:{color['滤镜效果']}")
    color_summary = (
        "、".join(color_summary_parts) if color_summary_parts else "（自然色调）"
    )

    depth_summary_parts = []
    if depth.get("虚化程度") not in ("", "中等虚化", "未知", None):
        depth_summary_parts.append(depth["虚化程度"])
    if depth.get("焦点主体") not in ("", "主体", "未知", None):
        depth_summary_parts.append(f"焦点:{depth['焦点主体']}")
    depth_summary = (
        "、".join(depth_summary_parts) if depth_summary_parts else "（标准景深）"
    )

    user_message = f"""
## 原始脚本（画面内容必须完整体现，不得省略）

**【画面内容 - 最高优先级】**：{visual_content}

**镜头**：{shot_type}，{camera_movement}
**场景**：{segment.get("scene", "室内")}，时长 {duration:.1f}s
**音频**：语音={segment.get("speech_text") or "无"}；BGM={format_bgm_info(bgm_info) if bgm_info else "无"}
**视觉参数（仅非默认值）**：光影={lighting_summary}，色调={color_summary}，景深={depth_summary}

## 参考知识片段（可选）

{chr(10).join(knowledge_pieces) if knowledge_pieces else "（无，请完全基于原始脚本自主生成）"}

## 生成要求

1. 提示词必须以镜头主体（人物/手/产品/物体）+初始状态开头，禁止以"画面中"/"镜头内"等虚词开头
2. 画面内容中的每个具体元素（人物、产品、背景道具、文字等）都必须出现在提示词中
3. **动作/位移描述规范**：凡涉及动作或运动，必须说明：
   - 主体身份（谁/什么在动）
   - 起始位置（从画面哪个位置/从哪里入画）
   - 运动轨迹和方向（向左/向前/从近到远/由下至上等）
   - 运动结果（到达哪里/状态如何变化）
   - 摄像机配合方式（固定机位/跟随推进/切至特写等）
4. 在描述完画面内容和动线后，自然加入镜头语言（{shot_type}，{camera_movement}）和光影/色调补充
5. 音频信息（语音/BGM）放在提示词末尾

生成提示词：
"""

    try:
        from video_breakdown_agent.utils.doubao_client import call_doubao_text

        response = await call_doubao_text(
            model=os.getenv("MODEL_AGENT_NAME", "doubao-seed-1-6-251015"),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=0.7,  # 适度创意
            max_tokens=600,
        )

        prompt = response["choices"][0]["message"]["content"].strip()
        logger.info(f"最终提示词生成成功（{len(prompt)}字）")
        return prompt

    except Exception as e:
        logger.error(f"最终提示词生成失败: {e}")
        raise


# ==================== 降级方案：单阶段LLM ====================


async def generate_single_stage_llm_prompt(
    segment: Dict, bgm_info: Optional[Dict]
) -> str:
    """单阶段LLM直接生成（降级方案1）"""
    system_prompt = """
你是视频提示词专家。基于原始脚本，生成专业视频生成提示词。

核心要求：
1. 以镜头主体（人/手/产品/物体）+初始状态开头，禁止用"画面中"/"镜头内"等虚词开头
2. 凡有动作或位移，必须说明：主体身份 → 起始位置 → 运动方向/轨迹 → 终点/结果状态 → 摄像机配合方式
3. 多主体共存时，说明其空间位置关系（前景/背景/左右）

输出格式：单段落，150-250字，按顺序：主体+动线描述 → 镜头语言（运镜/景别）→ 光影/色调 → 音频。
"""

    # 提取增强的视觉信息
    visual = segment.get("视觉表现", {})
    lighting = visual.get("光影", {})
    color = visual.get("色调", {})
    depth = visual.get("景深", {})
    composition = visual.get("构图", {})
    motion = visual.get("运动", {})

    # 兼容两种数据格式
    visual_content = segment.get("visual_content", "") or visual.get("画面内容", "无")
    shot_type = segment.get("shot_type", "") or visual.get("景别", "中景")
    camera_movement = segment.get("camera_movement", "") or visual.get("运镜", "固定")

    user_message = f"""
脚本：
- 画面：{visual_content}
- 镜头：{shot_type}，{camera_movement}
- 场景：{segment.get("scene", "室内")}
- 光影：{lighting.get("光源类型", "未知")}/{lighting.get("光源方向", "未知")}/{lighting.get("明暗对比", "中等")}
- 色调：{color.get("主色调", "未知")}/{color.get("饱和度", "中等")}/{color.get("色彩氛围", "中性")}
- 景深：{depth.get("虚化程度", "未知")}/焦点：{depth.get("焦点主体", "未知")}
- 构图：{composition.get("主体位置", "未知")}/{composition.get("构图法则", "未知")}
- 运动：{motion.get("速度", "未知")}/{motion.get("节奏感", "未知")}
- 语音：{segment.get("speech_text") or "无"}
- BGM：{format_bgm_info(bgm_info) if bgm_info else "无"}

生成专业提示词：
"""

    from video_breakdown_agent.utils.doubao_client import call_doubao_text

    response = await call_doubao_text(
        model=os.getenv("MODEL_AGENT_NAME", "doubao-seed-1-6-251015"),
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        temperature=0.7,
        max_tokens=500,
    )
    return response["choices"][0]["message"]["content"].strip()


# ==================== 保留原有函数（降级方案） ====================


def build_cinematic_prompt(
    segment: Dict, template_key: str, style_config: Optional[Dict] = None
) -> str:
    """
    基于电影级标准范式构建提示词

    黄金结构公式：
    [时间] + [场景空间] + [人物与动作] + [镜头语言] + [光影氛围] + [风格关键词] + [节奏描述]

    Args:
        segment: 分镜数据
        template_key: 模板key
        style_config: 风格配置（可选）

    Returns:
        电影级提示词字符串
    """
    # 提取分镜数据，兼容新版（视觉表现.画面内容）和旧版（顶层 visual_content）两种格式
    visual_info = segment.get("视觉表现", {})
    visual_content = segment.get("visual_content", "") or visual_info.get(
        "画面内容", ""
    )
    shot_type = (
        segment.get("shot_type", "") or visual_info.get("景别", "中景") or "中景"
    )
    camera_movement = (
        segment.get("camera_movement", "") or visual_info.get("运镜", "固定") or "固定"
    )
    scene = segment.get("scene", "室内场景")
    duration = segment.get("duration", 3.0)

    # 获取模板
    template = CINEMATIC_TEMPLATES.get(template_key, CINEMATIC_TEMPLATES["lifestyle"])

    # 从视觉内容中提取关键元素
    # 1. 时间（默认推断）
    time_of_day = "午后" if "阳光" in visual_content else "室内光线下"

    # 2. 场景空间
    scene_space = scene if scene else "简约背景"

    # 3. 人物与动作
    subject_action = visual_content if visual_content else "产品静态展示"

    # 4. 镜头语言
    camera_desc = f"{shot_type}镜头"
    if camera_movement and camera_movement != "固定":
        camera_desc += f"，{camera_movement}"

    # 根据模板类型添加镜头运动
    if template_key in ["product_premium", "comparison"]:
        camera_desc += "，镜头缓慢环绕产品旋转"
    elif template_key == "ugc":
        camera_desc += "，手持跟拍（略带晃动）"
    elif template_key == "pain_point":
        camera_desc += "，镜头快速推进到细节"

    # 5. 光影氛围
    lighting = (
        "柔和自然光"
        if "柔和" in visual_content or "自然" in visual_content
        else "均匀打光"
    )
    if template_key == "product_premium":
        lighting += "，侧光勾勒产品轮廓，高光反射细腻质感"
    elif template_key == "thriller":
        lighting = "冷白光下墙壁反射出微光"
    elif template_key == "epic_scifi":
        lighting = "逆光照亮边缘，烟雾与光线交织"

    # 6. 风格关键词
    style_keywords = "、".join(template["keywords"][:3])

    # 7. 节奏描述
    if duration < 2.0:
        pace = "节奏极快，信息密度高"
    elif duration < 3.5:
        pace = "节奏明快，干净利落"
    elif duration < 5.0:
        pace = "节奏舒缓，呼吸感强"
    else:
        pace = "节奏缓慢克制，沉浸感强"

    # 组合提示词
    prompt_parts = [
        f"{time_of_day}，{scene_space}，",
        f"{subject_action}，",
        f"{camera_desc}，",
        f"{lighting}，",
        f"{style_keywords}，",
        f"{pace}。",
    ]

    cinematic_prompt = "".join(prompt_parts)

    # 清理多余逗号和空格
    cinematic_prompt = cinematic_prompt.replace("，，", "，").replace("  ", " ").strip()

    return cinematic_prompt


async def generate_video_prompts(
    tool_context: ToolContext,
    segment_indexes: str = "",  # 逗号分隔的分镜序号，如 "1" 或 "1,3"；空字符串=全部
    use_skill_mode: bool = True,  # 默认启用Skill模式
    user_product_type: Optional[str] = None,
    force_template: Optional[str] = None,
    style_transfer_config: Optional[Dict] = None,
) -> Dict:
    """
    生成视频提示词工具（Skill模式主导，三级降级）

    工作模式：
    1. Skill模式（默认）：特征提取 → 知识检索 → 组装生成
    2. 单阶段LLM（降级1）：直接LLM生成
    3. 函数模板（降级2）：纯函数生成

    Args:
        tool_context: 工具上下文（包含session state）
        segment_indexes: 逗号分隔的分镜序号（如 "1" 或 "1,3"），空字符串表示生成全部分镜
        use_skill_mode: 是否启用Skill模式（默认True）
        user_product_type: 用户指定的产品类型（可选）
        force_template: 强制使用指定模板（可选）
        style_transfer_config: 风格迁移配置（可选）

    Returns:
        {
            "status": "success" | "error",
            "prompts": List[Dict],  # 提示词列表（仅含展示字段，调试字段存入 state）
            "total_count": int,  # 本次生成的分镜数
            "message": str  # 状态消息
        }
    """
    try:
        # 读取分镜数据
        vision_result = tool_context.state.get("vision_analysis_result")
        bgm_result = tool_context.state.get("bgm_analysis_result")

        if not vision_result:
            return {
                "status": "error",
                "message": "未找到分镜数据，请先执行视频拆解（breakdown_agent）",
                "prompts": [],
                "total_count": 0,
            }

        # vision_analysis_result 由 analyze_segments_vision 以 list 形式存储；
        # 兼容旧格式（dict 包裹 segments 字段）
        if isinstance(vision_result, list):
            segments = vision_result
        elif isinstance(vision_result, dict):
            segments = vision_result.get("segments", [])
        else:
            segments = []

        if not segments:
            return {
                "status": "error",
                "message": "分镜数据为空",
                "prompts": [],
                "total_count": 0,
            }

        # 解析 segment_indexes 过滤：空字符串=全部，否则只处理指定序号（从1开始）
        filter_indexes: Optional[set] = None
        if segment_indexes and segment_indexes.strip():
            try:
                filter_indexes = {
                    int(x.strip()) for x in segment_indexes.split(",") if x.strip()
                }
            except ValueError:
                logger.warning(
                    f"segment_indexes 格式无效，忽略过滤: {segment_indexes!r}"
                )

        logger.info(
            f"开始生成提示词，共{len(segments)}个分镜，模式: {'Skill' if use_skill_mode else '函数'}"
            + (f"，仅生成分镜: {filter_indexes}" if filter_indexes else "，生成全部")
        )

        prompts = []
        prompts_debug = []  # 内部调试数据，不回传给 LLM

        for idx, segment in enumerate(segments, start=1):
            # 跳过未被指定的分镜
            if filter_indexes and idx not in filter_indexes:
                continue
            # 向后兼容：为旧版数据（缺少增强视觉维度）补充默认值
            visual = segment.get("视觉表现", {})
            if "光影" not in visual:
                visual["光影"] = {
                    "光源类型": "自然光",
                    "光源方向": "正面光",
                    "明暗对比": "中等",
                    "阴影风格": "柔和阴影",
                }
            if "色调" not in visual:
                visual["色调"] = {
                    "主色调": "自然",
                    "饱和度": "中等",
                    "色彩氛围": "中性",
                    "滤镜效果": "无",
                }
            if "景深" not in visual:
                visual["景深"] = {
                    "虚化程度": "中等虚化",
                    "焦点主体": "主体",
                    "景深范围": "中景深",
                }
            if "构图" not in visual:
                visual["构图"] = {
                    "主体位置": "画面中心",
                    "构图法则": "中心构图",
                    "画面平衡": "对称",
                }
            if "运动" not in visual:
                visual["运动"] = {"速度": "中速", "节奏感": "流畅", "特殊效果": "无"}
            segment["视觉表现"] = visual

            prompt_text = None
            generation_method = "unknown"
            features = None
            knowledge_pieces = []

            # 模式1：Skill三阶段
            if use_skill_mode:
                try:
                    # 阶段1：特征提取
                    features = await extract_script_features(segment, bgm_result)

                    # 阶段2：知识检索
                    knowledge_pieces = retrieve_relevant_knowledge(features)

                    # 阶段3：组装生成
                    prompt_text = await generate_final_prompt(
                        segment, bgm_result, features, knowledge_pieces
                    )
                    generation_method = "skill"
                    logger.info(f"分镜{idx}: Skill模式生成成功")

                except Exception as e:
                    logger.warning(f"分镜{idx}: Skill模式失败，尝试降级 - {e}")
                    prompt_text = None

            # 降级1：单阶段LLM（如果Skill失败）
            if prompt_text is None and use_skill_mode:
                try:
                    prompt_text = await generate_single_stage_llm_prompt(
                        segment, bgm_result
                    )
                    generation_method = "llm_single"
                    logger.info(f"分镜{idx}: 单阶段LLM降级成功")
                except Exception as e:
                    logger.warning(f"分镜{idx}: LLM降级失败 - {e}")
                    prompt_text = None

            # 降级2：函数模板（最终兜底）
            if prompt_text is None:
                template_key = force_template or detect_video_type(segments)
                prompt_text = build_cinematic_prompt(
                    segment=segment,
                    template_key=template_key,
                    style_config=style_transfer_config,
                )
                generation_method = "function"
                logger.info(f"分镜{idx}: 函数模板生成")

            # 负向提示词（通用）
            negative_prompt = "模糊，扭曲，低质量，失焦，噪点，水印"

            # 参考首帧
            first_frame = None
            frame_urls = segment.get("frame_urls", [])
            if frame_urls:
                first_frame = frame_urls[0]

            # 预估费用（基于时长）
            duration = segment.get("duration", 3.0)
            estimated_cost = round(duration * 1.5, 2)  # 假设每秒1.5元

            # 构建对外返回的精简结构（LLM 可见，禁止含调试大字段）
            prompt_data = {
                "segment_index": idx,
                "segment_name": f"segment_{idx}",
                "start_time": segment.get("start_time", 0.0),
                "end_time": segment.get("end_time", duration),
                "duration": duration,
                "positive_prompt": prompt_text,
                "negative_prompt": negative_prompt,
                "first_frame": first_frame,
                "resolution": "720p",
                "ratio": "9:16",
                "selected": (idx == 1)
                if not filter_indexes
                else (idx in filter_indexes),
                "estimated_cost": estimated_cost,
                "generation_method": generation_method,
            }

            # 调试字段仅写入 state 的内部 key，不回传给 LLM
            prompt_data_debug = dict(prompt_data)
            prompt_data_debug["extracted_features"] = features
            prompt_data_debug["knowledge_used"] = len(knowledge_pieces)
            prompt_data_debug["original_segment_data"] = segment

            prompts.append(prompt_data)
            prompts_debug.append(prompt_data_debug)

        # 统计生成方式
        method_counts = {}
        for p in prompts:
            method = p["generation_method"]
            method_counts[method] = method_counts.get(method, 0) + 1

        # 计算总费用（仅选中的）
        total_cost = sum(p["estimated_cost"] for p in prompts if p["selected"])

        # 存入 session state：
        # - pending_prompts：精简结构（供 review_prompts / video_generate 使用）
        # - pending_prompts_debug：含调试字段，仅内部工具（如 evaluator）使用
        tool_context.state["pending_prompts"] = {
            "prompts": prompts,
            "total_count": len(prompts),
            "total_selected": sum(1 for p in prompts if p["selected"]),
            "total_duration": sum(p["duration"] for p in prompts if p["selected"]),
            "total_cost": total_cost,
            "generation_stats": method_counts,
        }
        tool_context.state["pending_prompts_debug"] = {
            "prompts": prompts_debug,
        }

        logger.info(f"✅ 提示词生成完成，统计: {method_counts}")

        selected_indexes = [p["segment_index"] for p in prompts if p["selected"]]
        return {
            "status": "success",
            "prompts": prompts,
            "total_count": len(prompts),
            "total_selected": len(selected_indexes),
            "total_cost": total_cost,
            "message": f"成功生成{len(prompts)}个分镜的提示词",
        }

    except Exception as e:
        logger.error(f"生成提示词失败: {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"生成提示词失败: {str(e)}",
            "prompts": [],
            "total_count": 0,
        }
