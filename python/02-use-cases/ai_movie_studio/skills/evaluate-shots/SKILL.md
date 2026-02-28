---
name: evaluate-shots
description: 使用多模态大模型对分镜画面进行视觉质量、内容一致性和风格一致性的专业评估。
version: 1.0.0
entrypoint: python evaluate.py
args:
    project_id:
        type: string
        description: 项目ID，用于标识评估任务。
        required: true
    shots:
        type: string
        description: 分镜列表的 JSON 字符串。包含 prompt 和 media_list (url, type)。
        required: true
output:
    type: json
    description: 返回评估结果，包含总分、是否通过以及每个分镜的详细评分和建议。
---

# 视觉评估工具 (Visual Evaluation Skill)

本 Skill 利用多模态大模型（如 Doubao-Vision）对生成的图像或视频素材进行自动化审计。

## 评估维度
1.  **Visual Quality**: 构图、光影、清晰度。
2.  **Content Alignment**: 画面是否符合 Prompt 描述。
3.  **Style Consistency**: 是否符合设定的艺术风格。

## 输入格式示例 (shots)
```json
[
    {
        "shot_id": "1",
        "prompt": "一只赛博朋克风格的猫",
        "media_list": [
            {"id": "img1", "url": "https://example.com/cat.jpg", "type": "image"}
        ]
    }
]
```

## 输出示例
```json
{
    "project_id": "proj_123",
    "total_score": 85,
    "is_approved": true,
    "shots": [...]
}
```
