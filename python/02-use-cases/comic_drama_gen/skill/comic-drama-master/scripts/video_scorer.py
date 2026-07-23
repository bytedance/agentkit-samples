"""
漫剧质量评分工具。

用法:
    python scripts/video_scorer.py <task_folder>
"""

import json
import os
import sys

import requests

_CHAT_URL = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
_EVAL_MODEL = os.environ.get("EVAL_MODEL_NAME", "deepseek-v3-2-251201")

_RUBRIC = """你是专业漫剧质量评审员。请对以下漫剧视频按5个维度评分（每项0-10分），并给出总体建议。

评分维度：
1. 剧情连贯性（场景间衔接是否流畅，是否有割裂感）
2. 对白丰富度（人物台词是否足够，语气是否多样，是否有冲突感）
3. 视觉质感（画面风格统一性，特效质量，镜头运用）
4. 情感张力（是否有戏剧性起伏，高潮是否震撼）
5. 音画同步（配乐是否贴合情绪，配音是否清晰）

任务目录结构：
{task_structure}

剧本摘要（前500字）：
{script_preview}

请按以下格式输出：
```
剧情连贯性: X/10 - [1句点评]
对白丰富度: X/10 - [1句点评]
视觉质感:   X/10 - [1句点评]
情感张力:   X/10 - [1句点评]
音画同步:   X/10 - [1句点评]
综合评分:   X.X/10
改进建议:   [2-3条具体可操作的建议]
```"""


def _get_auth() -> str:
    api_key = os.environ.get("ARK_API_KEY", "") or os.environ.get(
        "MODEL_AGENT_API_KEY", ""
    )
    return f"Bearer {api_key}"


def score_video(task_folder: str) -> dict:
    task_folder = task_folder.rstrip("/")

    script_path = os.path.join(task_folder, "script.md")
    script_preview = ""
    if os.path.exists(script_path):
        with open(script_path, encoding="utf-8") as f:
            script_preview = f.read()[:500]

    videos_dir = os.path.join(task_folder, "videos")
    storyboard_dir = os.path.join(task_folder, "storyboard")
    final_dir = os.path.join(task_folder, "final")

    video_count = (
        len([f for f in os.listdir(videos_dir) if f.endswith(".mp4")])
        if os.path.isdir(videos_dir)
        else 0
    )
    storyboard_count = (
        len([f for f in os.listdir(storyboard_dir) if f.endswith(".jpg")])
        if os.path.isdir(storyboard_dir)
        else 0
    )
    has_final = os.path.exists(os.path.join(final_dir, "final_video.mp4")) or any(
        f.endswith(".mp4")
        for f in (os.listdir(final_dir) if os.path.isdir(final_dir) else [])
    )

    task_structure = f"""
- script.md: {"存在" if script_preview else "缺失"}
- storyboard/: {storyboard_count} 张分镜图
- videos/: {video_count} 段视频
- final/: {"有合成视频" if has_final else "无合成视频"}
"""

    prompt = _RUBRIC.format(
        task_structure=task_structure, script_preview=script_preview or "（未找到剧本）"
    )

    try:
        resp = requests.post(
            _CHAT_URL,
            json={
                "model": _EVAL_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
            },
            headers={"Content-Type": "application/json", "Authorization": _get_auth()},
            timeout=60,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        return {
            "task_folder": task_folder,
            "evaluation": content,
            "stats": {
                "video_count": video_count,
                "storyboard_count": storyboard_count,
                "has_final": has_final,
            },
        }
    except Exception as e:
        return {"task_folder": task_folder, "evaluation": f"评分失败: {e}", "stats": {}}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python scripts/video_scorer.py <task_folder>")
        sys.exit(1)

    result = score_video(sys.argv[1])
    print(json.dumps(result, ensure_ascii=False, indent=2))
