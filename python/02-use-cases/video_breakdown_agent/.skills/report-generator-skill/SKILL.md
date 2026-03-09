---
name: report-generator
description: 视频分析报告生成技能。整合分镜拆解数据和钩子分析结果，生成 Markdown 格式的专业视频分析报告。运行脚本 `python scripts/generate_report.py <breakdown_json> [hook_analysis_json]`，输出完整的 Markdown 报告，包含基本信息、前三秒钩子分析、分镜概览、BGM分析、场景分析等章节。
---

# 视频分析报告生成 (Report Generator)

## 概述

视频分析报告生成技能将分镜拆解数据和（可选的）钩子分析结果整合为一份专业的 Markdown 格式分析报告。报告包含视频基本信息、前三秒钩子评分、分镜概览表格、BGM 分析、场景分析和平台推荐等章节。

## 适用场景

1. **视频分析交付**：为客户或团队生成完整的视频分析文档
2. **创意复盘**：生成结构化的视频内容复盘报告
3. **竞品报告**：批量生成竞品视频分析报告

## 使用步骤

### 完整报告（分镜 + 钩子分析）

```bash
# 1. 准备分镜拆解数据和钩子分析数据（JSON 文件）
# 2. 生成报告
python scripts/generate_report.py breakdown.json hook_analysis.json

# 3. 保存到文件
python scripts/generate_report.py breakdown.json hook_analysis.json > report.md
```

### 仅分镜报告（无钩子分析）

```bash
python scripts/generate_report.py breakdown.json
```

## 报告结构

生成的报告包含以下章节：

```markdown
# 视频分析报告

## 基本信息
- 视频时长、分镜数量、分辨率

## 前三秒钩子分析（核心）
- 综合评分
- 5维度评分表格
- 钩子类型
- 优势/不足/优化建议
- 留存预测

## 分镜概览
- 前10个分镜的概览表格

## BGM 分析
- 音乐风格、情绪基调、节拍

## 场景分析
- 主要场景、视频风格、目标受众
- 平台推荐

报告生成时间
```

## 输入格式

### breakdown.json（必需）

```json
{
  "duration": 30.5,
  "segment_count": 12,
  "resolution": "1920x1080",
  "segments": [...],
  "bgm_analysis": {
    "music_style": {"primary": "流行"},
    "emotion": {"primary": "欢快"},
    "tempo": {"bpm_estimate": 120, "pace": "中速"}
  },
  "scene_analysis": {
    "primary_scene": "室内",
    "video_style": {"overall": "生活方式", "target_audience": ["年轻人"]},
    "platform_recommendations": [...]
  }
}
```

### hook_analysis.json（可选）

```json
{
  "overall_score": 7.5,
  "visual_impact": 8.0,
  "visual_comment": "评价...",
  "language_hook": 7.0,
  "language_comment": "评价...",
  "emotion_trigger": 7.5,
  "emotion_comment": "评价...",
  "information_density": 7.0,
  "info_comment": "评价...",
  "rhythm_control": 8.0,
  "rhythm_comment": "评价...",
  "hook_type": "好奇型",
  "strengths": ["优点1", "优点2"],
  "weaknesses": ["不足1"],
  "suggestions": ["建议1", "建议2"],
  "retention_prediction": "中：50-70%，因为..."
}
```

## 输出格式

Markdown 格式的完整报告文本，直接输出到 stdout。

## 示例

```bash
# 完整流程
python ../video-breakdown-skill/scripts/process_video.py "https://example.com/video.mp4" > breakdown.json
cat breakdown.json | python ../hook-analyzer-skill/scripts/analyze_hook_segments.py - > hooks.json
# (hooks.json 需经 LLM 评分后得到 hook_analysis.json)
python scripts/generate_report.py breakdown.json hook_analysis.json > report.md
```

## 注意事项

1. 如果缺少 hook_analysis 数据，报告中钩子分析章节将显示"暂无数据"
2. 分镜概览最多展示前 10 个分镜
3. 报告自动添加生成时间戳
4. 画面内容描述超过 40 字符会自动截断

## 故障排除

| 问题 | 解决方案 |
|------|----------|
| 钩子分析为空 | 确认传入了 hook_analysis.json 文件 |
| 分镜表格为空 | 确认 breakdown.json 包含 segments 字段 |
| BGM/场景显示 N/A | 分镜拆解服务可能未返回此数据 |
