"""
Comic drama quality scoring tool.

Usage:
    python scripts/video_scorer.py <task_folder>
"""

import json
import os
import sys

import requests

_CHAT_URL = (
    os.environ.get(
        "MODEL_AGENT_API_BASE", "https://ark.ap-southeast.bytepluses.com/api/v3"
    ).rstrip("/")
    + "/chat/completions"
)
_EVAL_MODEL = os.environ.get("EVAL_MODEL_NAME", "deepseek-v4-pro-260425")

_RUBRIC = """You are a professional comic drama quality reviewer. Please score the following comic drama video on 5 dimensions (0-10 points each) and give overall suggestions.

Write your entire response in the same language as the script excerpt below (English by default; if the excerpt is written in another language, respond in that language).

Scoring dimensions:
1. Plot coherence (are transitions between scenes smooth, is there any sense of disjointedness)
2. Dialogue richness (are there enough character lines, is the tone varied, is there a sense of conflict)
3. Visual quality (consistency of visual style, quality of effects, camera work)
4. Emotional tension (are there dramatic ups and downs, is the climax impactful)
5. Audio-visual sync (does the music fit the mood, is the voiceover clear)

Task directory structure:
{task_structure}

Script excerpt (first 500 characters):
{script_preview}

Please output in the following format:
```
Plot coherence: X/10 - [one-sentence comment]
Dialogue richness: X/10 - [one-sentence comment]
Visual quality:   X/10 - [one-sentence comment]
Emotional tension:   X/10 - [one-sentence comment]
Audio-visual sync:   X/10 - [one-sentence comment]
Overall score:   X.X/10
Improvement suggestions:   [2-3 specific, actionable suggestions]
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
- script.md: {"present" if script_preview else "missing"}
- storyboard/: {storyboard_count} storyboard images
- videos/: {video_count} video segments
- final/: {"merged video present" if has_final else "no merged video"}
"""

    prompt = _RUBRIC.format(
        task_structure=task_structure,
        script_preview=script_preview or "(script not found)",
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
        return {
            "task_folder": task_folder,
            "evaluation": f"Scoring failed: {e}",
            "stats": {},
        }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/video_scorer.py <task_folder>")
        sys.exit(1)

    result = score_video(sys.argv[1])
    print(json.dumps(result, ensure_ascii=False, indent=2))
