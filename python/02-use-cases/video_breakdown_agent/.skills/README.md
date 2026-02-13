# Video Breakdown Agent - VeADK Skills

基于 VeADK 原生 Skills 格式的视频分镜拆解技能集。自包含模式，无需外部后端服务。

## Skills 列表

| Skill | 目录 | 描述 |
|-------|------|------|
| **video-breakdown** | `video-breakdown-skill/` | 视频分镜拆解：FFmpeg 预处理 → 分段 → 帧提取 |
| **hook-analyzer** | `hook-analyzer-skill/` | 前三秒钩子分析：从分镜数据中提取前3秒，构造多模态分析上下文 |
| **report-generator** | `report-generator-skill/` | 分析报告生成：整合分镜+钩子数据，输出 Markdown 报告 |

## 目录结构

```
skills/
├── README.md
├── video-breakdown-skill/
│   ├── SKILL.md
│   └── scripts/
│       ├── process_video.py           # 视频预处理（FFmpeg，自包含）
│       └── video_upload.py            # 上传本地视频到 TOS
├── hook-analyzer-skill/
│   ├── SKILL.md
│   └── scripts/
│       └── analyze_hook_segments.py   # 提取前三秒分镜数据
└── report-generator-skill/
    ├── SKILL.md
    └── scripts/
        └── generate_report.py         # 生成 Markdown 分析报告
```

## 典型工作流

```bash
# 1. 视频预处理
python video-breakdown-skill/scripts/process_video.py "https://example.com/video.mp4" > breakdown.json

# 2. 提取前三秒钩子数据
python hook-analyzer-skill/scripts/analyze_hook_segments.py breakdown.json > hook_context.json

# 3. (LLM 评分后得到 hook_analysis.json)

# 4. 生成完整报告
python report-generator-skill/scripts/generate_report.py breakdown.json hook_analysis.json > report.md
```

## 前置要求

- FFmpeg：`brew install ffmpeg`
- Python 3.12+
- httpx：`pip install httpx`

## 环境变量

| 变量 | 用途 | 必需 |
|------|------|------|
| `FFMPEG_BIN` | FFmpeg 路径 | 否（默认 `ffmpeg`） |
| `FFPROBE_BIN` | FFprobe 路径 | 否（默认 `ffprobe`） |
| `VOLCENGINE_ACCESS_KEY` | 火山引擎 AK | 上传视频时 |
| `VOLCENGINE_SECRET_KEY` | 火山引擎 SK | 上传视频时 |
| `DATABASE_TOS_BUCKET` | TOS 存储桶 | 上传时（可选） |
| `DATABASE_TOS_REGION` | TOS 区域 | 上传时（可选） |

## 参考

- [VeADK 内置工具文档](https://volcengine.github.io/veadk-python/tools/builtin/)
- [AgentKit Skills 示例](https://github.com/volcengine/agentkit-samples/tree/main/02-use-cases/agent_skills)
