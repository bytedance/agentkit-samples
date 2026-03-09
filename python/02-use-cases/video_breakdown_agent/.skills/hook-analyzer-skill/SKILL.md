---
name: hook-analyzer
description: 视频前三秒钩子分析技能。从分镜拆解结果中提取前三秒分镜数据，为钩子吸引力评估提供结构化上下文。运行脚本 `python scripts/analyze_hook_segments.py "<breakdown_json_file>"` 或通过 stdin 传入 JSON。输出包含前三秒分镜数量、总时长和每个分镜的详细信息（含关键帧 URL）。
---

# 视频前三秒钩子分析 (Hook Analyzer)

## 概述

视频前三秒钩子分析技能从分镜拆解结果中提取前三秒的分镜数据，并构造结构化的分析上下文，包含视觉内容描述、关键帧图片 URL、运镜方式等信息，为后续的 LLM 多维度评分分析提供输入。

## 适用场景

1. **短视频优化**：评估视频开头的吸引力，提升 3 秒留存率
2. **创意评审**：从5个维度量化分析钩子质量
3. **竞品对标**：对比不同视频开头的钩子策略

## 分析维度

本技能提取的数据供以下 5 个维度评分（由 LLM 完成评分）：

| 维度 | 权重 | 评估要点 |
|------|------|----------|
| 视觉冲击力 | 30% | 画面构图、色彩、光影、运镜动感 |
| 语言钩子 | 25% | 文案与画面配合度、悬念制造 |
| 情绪唤起 | 15% | 画面情绪、人物表情、氛围营造 |
| 信息密度 | 15% | 有效信息量、核心价值传达 |
| 节奏掌控 | 15% | 分镜切换节奏、平台特性适配 |

## 使用步骤

### 方式一：从文件读取分镜数据

```bash
# 1. 先使用 video-breakdown skill 处理视频并获取分镜结果
python ../video-breakdown-skill/scripts/process_video.py "https://example.com/video.mp4" > breakdown.json

# 2. 提取前三秒分镜数据
python scripts/analyze_hook_segments.py breakdown.json
```

### 方式二：通过 stdin 管道传入

```bash
cat breakdown.json | python scripts/analyze_hook_segments.py -
```

## 输出格式

```json
{
  "segment_count": 3,
  "total_duration": 2.8,
  "total_video_segments": 15,
  "analysis_mode": "multimodal",
  "segments": [
    {
      "index": 0,
      "start_time": 0.0,
      "end_time": 1.0,
      "duration": 1.0,
      "visual_content": "画面描述",
      "speech_text": "语音文字",
      "shot_type": "特写",
      "camera_movement": "推镜头",
      "function_tag": "开场",
      "frame_images": [
        {"type": "image_url", "image_url": {"url": "https://..."}}
      ],
      "frame_count": 3
    }
  ]
}
```

## 钩子类型分类

分析结果可用于识别以下钩子类型：

- **痛点型**：直击用户痛点，引发共鸣
- **好奇型**：设置悬念，引发好奇
- **冲突型**：制造对比或冲突吸引注意
- **价值型**：直接展示价值承诺
- **情感型**：以情感共鸣打动用户
- **视觉冲击型**：通过强烈视觉效果吸引
- **悬念型**：留下悬念引导继续观看

## 评分标准

| 分数段 | 等级 | 描述 |
|--------|------|------|
| 9-10 | 顶级 | 极强的吸引力和创意 |
| 7-8 | 优秀 | 具备良好的吸引力 |
| 5-6 | 一般 | 有改进空间 |
| 3-4 | 较弱 | 需要重大改进 |
| 1-2 | 很差 | 基本没有吸引力 |

## 注意事项

1. 此脚本只做**数据提取**，不做 LLM 评分（评分由 Agent 的 LLM 完成）
2. 提取的 `frame_images` 字段中包含关键帧 URL，可供 Vision 模型直接分析
3. 每个分镜最多取前 3 帧关键帧，避免 token 超限
4. 输入必须是 `process_video` 返回的完整 JSON 数据

## 故障排除

| 问题 | 解决方案 |
|------|----------|
| 输出为空 segments | 确认输入 JSON 包含 `segments` 字段且不为空 |
| 前三秒无分镜 | 视频可能从静止画面开始，检查原始数据 |
| 关键帧 URL 失效 | TOS 签名 URL 可能已过期，重新拆解获取 |
