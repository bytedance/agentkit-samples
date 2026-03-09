"""
漫剧应用配置工具
读取环境变量 VIDEO_DURATION_MINUTES，输出 JSON 配置。
智能时长模式：每个分镜根据场景复杂度动态分配 4s ~ 15s 时长。

用法:
    python scripts/app_config.py
"""

import json
import os

SUPPORTED_DURATIONS = (0.5, 1, 2, 3, 4)

# 动态时长范围：每个分镜可分配 4s ~ 15s
MIN_SCENE_DURATION = 4
MAX_SCENE_DURATION = 15


def get_app_config() -> dict:
    raw = os.environ.get("VIDEO_DURATION_MINUTES", "0.5").strip()
    try:
        minutes = float(raw)
    except ValueError:
        minutes = 0.5

    if minutes not in SUPPORTED_DURATIONS:
        minutes = 0.5

    # 智能时长模式：总时长 = minutes * 60 秒
    # 每个分镜可动态分配 4s ~ 15s，节奏更丰富多变
    total_seconds = int(minutes * 60)
    # 场景数参考范围：全用最长时长为下限，全用最短时长为上限
    min_scenes = total_seconds // MAX_SCENE_DURATION  # 全用15s时的场景数
    max_scenes = total_seconds // MIN_SCENE_DURATION  # 全用4s时的场景数
    # 推荐场景数：以平均8s估算，兼顾节奏多样性
    avg_duration = (MIN_SCENE_DURATION + MAX_SCENE_DURATION) / 2
    recommended_scenes = round(total_seconds / avg_duration)

    return {
        "video_duration_minutes": minutes,
        "total_seconds": total_seconds,
        "smart_duration": True,
        "duration_range": {"min": MIN_SCENE_DURATION, "max": MAX_SCENE_DURATION},
        "duration_options": "4s ~ 15s 动态分配（4/5/6/7/8/9/10/11/12/13/14/15）",
        "scene_count_range": {"min": min_scenes, "max": max_scenes},
        "recommended_scene_count": recommended_scenes,
        "note": "每个分镜时长根据剧情节奏动态决定：紧张快切4-6s，标准叙事7-10s，高潮铺垫11-15s",
        "config_source": f"VIDEO_DURATION_MINUTES={raw}",
    }


if __name__ == "__main__":
    config = get_app_config()
    print(json.dumps(config, ensure_ascii=False, indent=2))
