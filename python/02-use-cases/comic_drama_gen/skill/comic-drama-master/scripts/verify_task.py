"""
漫剧任务产物验证工具。

在每次漫剧生成后自动检查：
1. 产物完整性（目录树 + 文件非空）
2. 时长合规性（每段 4~15s，总时长匹配）
3. 五维效果评分（剧情连贯/对白丰富/视觉质感/情感张力/音画同步）
4. 综合通过/失败判定

用法:
    python scripts/verify_task.py <task_folder> [--scene-count N] [--durations '6,8,12,14,11,9'] [--verbose]
    python scripts/verify_task.py <task_folder> --auto        # 从 plot.md 自动提取 scene_count 和 durations
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ── 常量 ──────────────────────────────────────────────────

MIN_SCENE_DURATION = 4
MAX_SCENE_DURATION = 15

# 必须存在且非空的根级文件
_REQUIRED_ROOT_FILES = [
    "requirements.md",
    "plot.md",
    "script.md",
    "characters.md",
    "cover.jpg",
    "cover.md",
]

# 必须存在且非空的子目录（及其期望文件模式）
_REQUIRED_SUBDIRS = [
    "storyboard",
    "characters",
    "videos",
    "final",
]

# 评分维度
_SCORE_DIMENSIONS = [
    "剧情连贯性",
    "对白丰富度",
    "视觉质感",
    "情感张力",
    "时长多样性",
]


# ── 产物完整性检查 ─────────────────────────────────────────


def check_file_exists_and_nonempty(path: Path) -> Tuple[bool, str]:
    """检查文件是否存在且非空。"""
    if not path.exists():
        return False, f"缺失: {path.name}"
    if path.stat().st_size == 0:
        return False, f"空文件: {path.name}"
    return True, f"✅ {path.name} ({path.stat().st_size} bytes)"


def check_artifacts(task_folder: Path, scene_count: int) -> Dict:
    """
    检查产物完整性。

    Returns:
        dict: {passed, total_checks, failures, details, directory_tree}
    """
    checks = []
    failures = []

    # 1. 根级文件
    for fname in _REQUIRED_ROOT_FILES:
        ok, msg = check_file_exists_and_nonempty(task_folder / fname)
        checks.append({"file": fname, "passed": ok, "detail": msg})
        if not ok:
            failures.append(msg)

    # 2. final_video.md（可选但推荐）
    fv = task_folder / "final_video.md"
    if fv.exists() and fv.stat().st_size > 0:
        checks.append(
            {"file": "final_video.md", "passed": True, "detail": "✅ final_video.md"}
        )
    else:
        checks.append(
            {
                "file": "final_video.md",
                "passed": False,
                "detail": "⚠️ final_video.md 缺失（最终交付文档）",
            }
        )
        failures.append("缺失: final_video.md")

    # 3. storyboard/ 目录：scene_01.jpg ~ scene_NN.jpg
    sb_dir = task_folder / "storyboard"
    if sb_dir.is_dir():
        for i in range(1, scene_count + 1):
            fname = f"scene_{i:02d}.jpg"
            ok, msg = check_file_exists_and_nonempty(sb_dir / fname)
            checks.append({"file": f"storyboard/{fname}", "passed": ok, "detail": msg})
            if not ok:
                failures.append(f"storyboard/{msg}")
    else:
        checks.append(
            {"file": "storyboard/", "passed": False, "detail": "缺失: storyboard/ 目录"}
        )
        failures.append("缺失: storyboard/ 目录")

    # 4. characters/ 目录：至少 1 张立绘
    char_dir = task_folder / "characters"
    if char_dir.is_dir():
        char_files = [
            f
            for f in char_dir.iterdir()
            if f.is_file() and f.suffix in (".jpg", ".png", ".webp")
        ]
        if char_files:
            checks.append(
                {
                    "file": "characters/",
                    "passed": True,
                    "detail": f"✅ characters/ ({len(char_files)} 张立绘)",
                }
            )
        else:
            checks.append(
                {
                    "file": "characters/",
                    "passed": False,
                    "detail": "空目录: characters/ (无立绘图片)",
                }
            )
            failures.append("空目录: characters/")
    else:
        checks.append(
            {"file": "characters/", "passed": False, "detail": "缺失: characters/ 目录"}
        )
        failures.append("缺失: characters/ 目录")

    # 5. videos/ 目录：scene_01.mp4 ~ scene_NN.mp4
    vid_dir = task_folder / "videos"
    if vid_dir.is_dir():
        for i in range(1, scene_count + 1):
            fname = f"scene_{i:02d}.mp4"
            ok, msg = check_file_exists_and_nonempty(vid_dir / fname)
            checks.append({"file": f"videos/{fname}", "passed": ok, "detail": msg})
            if not ok:
                failures.append(f"videos/{msg}")
    else:
        checks.append(
            {"file": "videos/", "passed": False, "detail": "缺失: videos/ 目录"}
        )
        failures.append("缺失: videos/ 目录")

    # 6. final/ 目录：至少 1 个 .mp4
    final_dir = task_folder / "final"
    if final_dir.is_dir():
        final_mp4 = [
            f
            for f in final_dir.iterdir()
            if f.is_file() and f.suffix == ".mp4" and f.stat().st_size > 0
        ]
        if final_mp4:
            checks.append(
                {
                    "file": "final/",
                    "passed": True,
                    "detail": f"✅ final/ ({final_mp4[0].name}, {final_mp4[0].stat().st_size / 1024 / 1024:.1f} MB)",
                }
            )
        else:
            checks.append(
                {
                    "file": "final/",
                    "passed": False,
                    "detail": "空目录: final/ (无合成视频)",
                }
            )
            failures.append("空目录: final/ (无合成视频)")
    else:
        checks.append(
            {"file": "final/", "passed": False, "detail": "缺失: final/ 目录"}
        )
        failures.append("缺失: final/ 目录")

    # 构建目录树
    tree = _build_directory_tree(task_folder, scene_count)

    passed_count = sum(1 for c in checks if c["passed"])
    return {
        "passed": len(failures) == 0,
        "passed_count": passed_count,
        "total_checks": len(checks),
        "failures": failures,
        "checks": checks,
        "directory_tree": tree,
    }


def _build_directory_tree(task_folder: Path, scene_count: int) -> str:
    """构建产物目录树字符串。"""
    lines = [f"{task_folder.name}/"]

    def _status(path: Path) -> str:
        if not path.exists():
            return "❌ 缺失"
        if path.is_file() and path.stat().st_size == 0:
            return "❌ 空文件"
        return "✅"

    # 根级文件
    root_files = _REQUIRED_ROOT_FILES + ["final_video.md"]
    for i, fname in enumerate(root_files):
        is_last_file = (i == len(root_files) - 1) and not _REQUIRED_SUBDIRS
        prefix = "└── " if is_last_file else "├── "
        s = _status(task_folder / fname)
        lines.append(f"    {prefix}{fname}  {s}")

    # 子目录
    subdirs = _REQUIRED_SUBDIRS
    for j, dname in enumerate(subdirs):
        is_last_dir = j == len(subdirs) - 1
        prefix = "└── " if is_last_dir else "├── "
        d = task_folder / dname
        if not d.exists():
            lines.append(f"    {prefix}{dname}/  ❌ 缺失")
            continue

        file_count = len([f for f in d.iterdir() if f.is_file()]) if d.is_dir() else 0
        s = "✅" if file_count > 0 else "❌ 空"
        lines.append(f"    {prefix}{dname}/  {s} ({file_count} 个文件)")

    return "\n".join(lines)


# ── 时长合规性检查 ─────────────────────────────────────────


def check_durations(durations: List[int], expected_total: Optional[int] = None) -> Dict:
    """
    检查时长分配是否合规。

    Args:
        durations: 每段时长列表 (如 [6, 8, 12, 14, 11, 9])
        expected_total: 期望总时长（秒），如 60/120/180/240

    Returns:
        dict: {passed, actual_total, issues, duration_distribution}
    """
    issues = []
    actual_total = sum(durations)

    # 检查每段时长范围
    for i, d in enumerate(durations):
        if not (MIN_SCENE_DURATION <= d <= MAX_SCENE_DURATION):
            issues.append(
                f"场景{i + 1} 时长 {d}s 超出范围 [{MIN_SCENE_DURATION}~{MAX_SCENE_DURATION}]s"
            )

    # 检查总时长偏差（允许 ±10%）
    if expected_total:
        deviation = abs(actual_total - expected_total) / expected_total * 100
        if deviation > 10:
            issues.append(
                f"总时长偏差过大: 实际 {actual_total}s vs 期望 {expected_total}s (偏差 {deviation:.1f}%)"
            )

    # 时长多样性检查：至少使用 3 种不同时长
    unique_durations = len(set(durations))
    if len(durations) >= 4 and unique_durations < 3:
        issues.append(
            f"时长多样性不足: 仅使用了 {unique_durations} 种不同时长，建议 ≥ 3 种"
        )

    # 分布统计
    short_cut = [d for d in durations if MIN_SCENE_DURATION <= d <= 6]  # 紧张快切
    standard = [d for d in durations if 7 <= d <= 10]  # 标准叙事
    climax = [d for d in durations if 11 <= d <= MAX_SCENE_DURATION]  # 高潮铺垫

    distribution = {
        "紧张快切(4~6s)": {"count": len(short_cut), "values": short_cut},
        "标准叙事(7~10s)": {"count": len(standard), "values": standard},
        "高潮铺垫(11~15s)": {"count": len(climax), "values": climax},
    }

    return {
        "passed": len(issues) == 0,
        "durations": durations,
        "actual_total_seconds": actual_total,
        "expected_total_seconds": expected_total,
        "unique_duration_count": unique_durations,
        "scene_count": len(durations),
        "distribution": distribution,
        "issues": issues,
    }


# ── 内容质量评分（离线静态分析） ───────────────────────────


def score_content(task_folder: Path, durations: List[int]) -> Dict:
    """
    基于产物文件进行静态质量评分（不依赖 LLM API）。

    评分维度（每项 0-10 分）：
    1. 剧情连贯性：检查 plot.md 章节数与 scene_count 匹配，场景间有衔接词
    2. 对白丰富度：检查 script.md 对白行数/密度
    3. 视觉质感：检查 characters.md 提示词质量、storyboard 文件完整性
    4. 情感张力：检查是否有高潮标记、时长分配是否有起伏
    5. 时长多样性：检查 durations 分布是否丰富
    """
    scores = {}

    # 1. 剧情连贯性
    scores["剧情连贯性"] = _score_plot_coherence(task_folder, len(durations))

    # 2. 对白丰富度
    scores["对白丰富度"] = _score_dialogue_richness(task_folder, durations)

    # 3. 视觉质感
    scores["视觉质感"] = _score_visual_quality(task_folder, len(durations))

    # 4. 情感张力
    scores["情感张力"] = _score_emotional_tension(task_folder, durations)

    # 5. 时长多样性
    scores["时长多样性"] = _score_duration_diversity(durations)

    # 综合评分
    total = sum(s["score"] for s in scores.values())
    avg = total / len(scores)

    return {
        "dimensions": scores,
        "total_score": round(total, 1),
        "average_score": round(avg, 1),
        "grade": _grade(avg),
    }


def _read_file_safe(path: Path, max_chars: int = 5000) -> str:
    """安全读取文件前 N 个字符。"""
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8")[:max_chars]
    except Exception:
        return ""


def _score_plot_coherence(task_folder: Path, scene_count: int) -> Dict:
    """评估剧情连贯性。"""
    plot = _read_file_safe(task_folder / "plot.md")
    score = 0
    comments = []

    if not plot:
        return {"score": 0, "comment": "plot.md 缺失或为空"}

    # 检查章节数量
    chapter_markers = re.findall(
        r"(?:第[一二三四五六七八九十\d]+章|##\s+场景|##\s+第)", plot
    )
    if len(chapter_markers) >= scene_count:
        score += 4
        comments.append(f"章节数 {len(chapter_markers)} ≥ 场景数 {scene_count}")
    elif len(chapter_markers) >= scene_count * 0.7:
        score += 2
        comments.append(f"章节数 {len(chapter_markers)} 略少于场景数 {scene_count}")
    else:
        comments.append(f"章节数 {len(chapter_markers)} 远少于场景数 {scene_count}")

    # 检查时长标记
    duration_markers = re.findall(r"\d+\s*[秒s]", plot)
    if len(duration_markers) >= scene_count * 0.8:
        score += 3
        comments.append("时长标记完整")
    elif duration_markers:
        score += 1
        comments.append(f"时长标记不完整 ({len(duration_markers)}/{scene_count})")

    # 检查内容丰富度
    if len(plot) > 500:
        score += 2
        comments.append("内容详实")
    elif len(plot) > 200:
        score += 1
        comments.append("内容适中")

    # 检查是否有故事弧线标记
    arc_keywords = ["开端", "发展", "高潮", "结局", "铺垫", "转折", "收尾"]
    arc_found = sum(1 for kw in arc_keywords if kw in plot)
    if arc_found >= 3:
        score += 1
        comments.append("故事弧线清晰")

    return {"score": min(score, 10), "comment": "; ".join(comments)}


def _score_dialogue_richness(task_folder: Path, durations: List[int]) -> Dict:
    """评估对白丰富度。"""
    script = _read_file_safe(task_folder / "script.md", max_chars=10000)
    score = 0
    comments = []

    if not script:
        return {"score": 0, "comment": "script.md 缺失或为空"}

    # 对白行数（匹配中文引号或冒号后内容）
    dialogue_lines = re.findall(
        r'[""「].*?[""」]|：\s*[""「].*?[""」]|:\s*".*?"', script
    )
    if len(dialogue_lines) >= len(durations) * 3:
        score += 4
        comments.append(f"对白丰富 ({len(dialogue_lines)} 句)")
    elif len(dialogue_lines) >= len(durations) * 2:
        score += 3
        comments.append(f"对白适中 ({len(dialogue_lines)} 句)")
    elif len(dialogue_lines) >= len(durations):
        score += 2
        comments.append(f"对白偏少 ({len(dialogue_lines)} 句)")
    else:
        score += 1
        comments.append(f"对白不足 ({len(dialogue_lines)} 句)")

    # 检查角色区分
    speaker_patterns = re.findall(r"([\u4e00-\u9fff]{2,6})\s*[：:]", script)
    unique_speakers = len(set(speaker_patterns))
    if unique_speakers >= 2:
        score += 2
        comments.append(f"{unique_speakers} 个说话角色")
    elif unique_speakers == 1:
        score += 1
        comments.append("仅 1 个说话角色")

    # 检查时间戳
    timestamps = re.findall(r"\d+:\d+|\d+[秒s]|T=\d+", script)
    if len(timestamps) >= len(durations):
        score += 2
        comments.append("逐场时间戳完整")
    elif timestamps:
        score += 1
        comments.append("部分时间戳")

    # 检查场景结束状态
    end_states = re.findall(
        r"(?:场景结束状态|结束状态|ending state)", script, re.IGNORECASE
    )
    if len(end_states) >= len(durations) * 0.5:
        score += 2
        comments.append("场景结束状态标注完整")

    return {"score": min(score, 10), "comment": "; ".join(comments)}


def _score_visual_quality(task_folder: Path, scene_count: int) -> Dict:
    """评估视觉质感。"""
    score = 0
    comments = []

    # 检查 characters.md 提示词
    chars = _read_file_safe(task_folder / "characters.md")
    if chars:
        # 检查英文提示词
        eng_prompts = re.findall(r"[a-zA-Z]{3,}", chars)
        if len(eng_prompts) >= 20:
            score += 3
            comments.append("角色提示词详细")
        elif len(eng_prompts) >= 10:
            score += 2
            comments.append("角色提示词基本")
        else:
            score += 1
            comments.append("角色提示词简略")

        # 检查 STYLE_ANCHOR
        if "STYLE_ANCHOR" in chars or "style_anchor" in chars.lower():
            score += 1
            comments.append("STYLE_ANCHOR 已定义")
    else:
        comments.append("characters.md 缺失")

    # 检查分镜图完整性
    sb_dir = task_folder / "storyboard"
    if sb_dir.is_dir():
        sb_files = [
            f for f in sb_dir.iterdir() if f.suffix in (".jpg", ".png", ".webp")
        ]
        if len(sb_files) >= scene_count:
            score += 3
            comments.append(f"分镜图完整 ({len(sb_files)}/{scene_count})")
        elif len(sb_files) >= scene_count * 0.7:
            score += 2
            comments.append(f"分镜图基本完整 ({len(sb_files)}/{scene_count})")
        else:
            score += 1
            comments.append(f"分镜图不足 ({len(sb_files)}/{scene_count})")
    else:
        comments.append("storyboard/ 缺失")

    # 检查封面
    cover = task_folder / "cover.jpg"
    if cover.exists() and cover.stat().st_size > 0:
        score += 2
        comments.append("封面图存在")
    else:
        comments.append("封面图缺失")

    # 检查角色立绘
    char_dir = task_folder / "characters"
    if char_dir.is_dir():
        char_imgs = [
            f for f in char_dir.iterdir() if f.suffix in (".jpg", ".png", ".webp")
        ]
        if char_imgs:
            score += 1
            comments.append(f"{len(char_imgs)} 张角色立绘")

    return {"score": min(score, 10), "comment": "; ".join(comments)}


def _score_emotional_tension(task_folder: Path, durations: List[int]) -> Dict:
    """评估情感张力。"""
    score = 0
    comments = []

    plot = _read_file_safe(task_folder / "plot.md")
    script = _read_file_safe(task_folder / "script.md", max_chars=10000)
    combined = plot + script

    # 检查情绪关键词
    tension_keywords = [
        "高潮",
        "转折",
        "对决",
        "爆发",
        "震怒",
        "紧张",
        "激烈",
        "悲壮",
        "怒吼",
        "嘶吼",
        "震撼",
        "绝望",
        "希望",
        "牺牲",
        "觉醒",
    ]
    found_keywords = [kw for kw in tension_keywords if kw in combined]
    if len(found_keywords) >= 5:
        score += 3
        comments.append(f"情感关键词丰富 ({len(found_keywords)} 个)")
    elif len(found_keywords) >= 3:
        score += 2
        comments.append(f"情感关键词适中 ({len(found_keywords)} 个)")
    elif found_keywords:
        score += 1
        comments.append(f"情感关键词偏少 ({len(found_keywords)} 个)")

    # 检查时长分配是否有起伏（标准差）
    if len(durations) >= 3:
        avg = sum(durations) / len(durations)
        variance = sum((d - avg) ** 2 for d in durations) / len(durations)
        std_dev = variance**0.5
        if std_dev >= 3:
            score += 3
            comments.append(f"时长起伏大 (σ={std_dev:.1f}s)，节奏感强")
        elif std_dev >= 2:
            score += 2
            comments.append(f"时长有一定起伏 (σ={std_dev:.1f}s)")
        elif std_dev >= 1:
            score += 1
            comments.append(f"时长较平均 (σ={std_dev:.1f}s)，节奏偏平")
        else:
            comments.append(f"时长无起伏 (σ={std_dev:.1f}s)，节奏单调")

    # 检查高潮段是否在后半段（时长较长的段落应集中在中后部）
    if len(durations) >= 4:
        # 如果后半段不全是短的（允许收尾变短），检查最大值是否在中后段
        max_idx = durations.index(max(durations))
        if max_idx >= len(durations) * 0.3:
            score += 2
            comments.append("高潮段位于中后部")
        else:
            score += 1
            comments.append("高潮段偏前")

    # 音效/运镜关键词
    camera_keywords = [
        "特写",
        "近景",
        "仰角",
        "俯瞰",
        "追踪",
        "慢动作",
        "快切",
        "close-up",
        "tracking shot",
        "slow motion",
        "zoom",
    ]
    cam_found = [kw for kw in camera_keywords if kw in combined.lower()]
    if len(cam_found) >= 3:
        score += 2
        comments.append(f"镜头语言丰富 ({len(cam_found)} 种)")
    elif cam_found:
        score += 1
        comments.append(f"镜头语言基本 ({len(cam_found)} 种)")

    return {"score": min(score, 10), "comment": "; ".join(comments)}


def _score_duration_diversity(durations: List[int]) -> Dict:
    """评估时长多样性。"""
    score = 0
    comments = []

    unique = set(durations)

    # 种类多样性
    if len(unique) >= 5:
        score += 4
        comments.append(f"{len(unique)} 种不同时长，非常丰富")
    elif len(unique) >= 4:
        score += 3
        comments.append(f"{len(unique)} 种不同时长")
    elif len(unique) >= 3:
        score += 2
        comments.append(f"{len(unique)} 种不同时长")
    elif len(unique) >= 2:
        score += 1
        comments.append(f"仅 {len(unique)} 种时长，较单调")
    else:
        comments.append(f"仅 1 种时长 ({durations[0]}s)，完全单调")

    # 三档覆盖度
    has_short = any(MIN_SCENE_DURATION <= d <= 6 for d in durations)
    has_mid = any(7 <= d <= 10 for d in durations)
    has_long = any(11 <= d <= MAX_SCENE_DURATION for d in durations)
    coverage = sum([has_short, has_mid, has_long])

    if coverage == 3:
        score += 3
        comments.append("三档时长全覆盖（快切/标准/高潮）")
    elif coverage == 2:
        score += 2
        comments.append(f"覆盖 {coverage}/3 档时长")
    else:
        score += 1
        comments.append(f"仅覆盖 {coverage}/3 档时长")

    # 范围跨度
    span = max(durations) - min(durations)
    if span >= 8:
        score += 3
        comments.append(
            f"时长跨度 {span}s（{min(durations)}s ~ {max(durations)}s），节奏丰富"
        )
    elif span >= 5:
        score += 2
        comments.append(f"时长跨度 {span}s")
    elif span >= 2:
        score += 1
        comments.append(f"时长跨度仅 {span}s，偏窄")
    else:
        comments.append(f"时长跨度仅 {span}s，过于单调")

    return {"score": min(score, 10), "comment": "; ".join(comments)}


def _grade(avg_score: float) -> str:
    """根据平均分给等级。"""
    if avg_score >= 9:
        return "S（卓越）"
    elif avg_score >= 8:
        return "A（优秀）"
    elif avg_score >= 7:
        return "B（良好）"
    elif avg_score >= 6:
        return "C（合格）"
    elif avg_score >= 5:
        return "D（待改进）"
    else:
        return "F（不合格）"


# ── 自动提取 scene_count 和 durations ──────────────────────


def auto_detect_from_plot(
    task_folder: Path,
) -> Tuple[Optional[int], Optional[List[int]]]:
    """从 plot.md 或 script.md 自动提取 scene_count 和 durations。"""
    for fname in ("plot.md", "script.md"):
        content = _read_file_safe(task_folder / fname, max_chars=10000)
        if not content:
            continue

        # 尝试匹配 scene_durations = [6, 8, 12, 14, 11, 9]
        m = re.search(r"scene_durations\s*=\s*\[([0-9,\s]+)\]", content)
        if m:
            durations = [int(x.strip()) for x in m.group(1).split(",") if x.strip()]
            return len(durations), durations

        # 尝试匹配 "第X章：xxx（Ns）" 格式
        chapters = re.findall(
            r"(?:第[一二三四五六七八九十\d]+章|场景\s*\d+).*?(\d+)\s*[秒s]", content
        )
        if chapters:
            durations = [int(x) for x in chapters]
            return len(durations), durations

    return None, None


# ── 主验证流程 ─────────────────────────────────────────────


def verify_task(
    task_folder: str,
    scene_count: Optional[int] = None,
    durations: Optional[List[int]] = None,
    expected_total: Optional[int] = None,
    verbose: bool = False,
) -> Dict:
    """
    执行完整验证。

    Args:
        task_folder: 任务目录路径
        scene_count: 场景数（不提供则自动检测）
        durations: 时长列表（不提供则自动检测）
        expected_total: 期望总时长（秒）
        verbose: 是否输出详细信息

    Returns:
        dict: 完整验证报告
    """
    folder = Path(task_folder)
    if not folder.is_dir():
        return {
            "task_folder": task_folder,
            "overall_passed": False,
            "error": f"任务目录不存在: {task_folder}",
        }

    # 自动检测
    if scene_count is None or durations is None:
        auto_sc, auto_dur = auto_detect_from_plot(folder)
        if auto_sc and auto_dur:
            scene_count = scene_count or auto_sc
            durations = durations or auto_dur

    if scene_count is None:
        # 从 videos/ 目录推断
        vid_dir = folder / "videos"
        if vid_dir.is_dir():
            vid_files = sorted(
                [f for f in vid_dir.iterdir() if re.match(r"scene_\d{2}\.mp4$", f.name)]
            )
            scene_count = len(vid_files) if vid_files else 6
        else:
            scene_count = 6  # 默认

    if durations is None:
        durations = [10] * scene_count  # 默认均匀

    # 1. 产物完整性
    artifact_result = check_artifacts(folder, scene_count)

    # 2. 时长合规性
    duration_result = check_durations(durations, expected_total)

    # 3. 内容质量评分
    score_result = score_content(folder, durations)

    # 综合判定
    overall_passed = artifact_result["passed"] and duration_result["passed"]

    report = {
        "task_folder": str(folder.absolute()),
        "task_name": folder.name,
        "verified_at": datetime.now().isoformat(),
        "overall_passed": overall_passed,
        "overall_verdict": "✅ 通过" if overall_passed else "❌ 失败",
        "artifact_check": artifact_result,
        "duration_check": duration_result,
        "quality_score": score_result,
        "summary": _build_summary(
            artifact_result, duration_result, score_result, overall_passed
        ),
    }

    return report


def _build_summary(artifacts: Dict, durations: Dict, scores: Dict, passed: bool) -> str:
    """构建人类可读的摘要。"""
    lines = []
    lines.append("=" * 60)
    lines.append("📋 漫剧产物验证报告")
    lines.append("=" * 60)
    lines.append("")

    # 产物完整性
    lines.append(
        f"📁 产物完整性: {'✅ 通过' if artifacts['passed'] else '❌ 失败'} ({artifacts['passed_count']}/{artifacts['total_checks']})"
    )
    if artifacts["failures"]:
        for f in artifacts["failures"]:
            lines.append(f"   ⛔ {f}")
    lines.append("")

    # 目录树
    lines.append("📂 目录结构:")
    lines.append(artifacts["directory_tree"])
    lines.append("")

    # 时长合规
    lines.append(f"⏱️  时长合规性: {'✅ 通过' if durations['passed'] else '❌ 失败'}")
    lines.append(f"   场景数: {durations['scene_count']}")
    lines.append(f"   时长列表: {durations['durations']}")
    lines.append(f"   总时长: {durations['actual_total_seconds']}s")
    lines.append(f"   时长种类: {durations['unique_duration_count']}")
    for tier, info in durations["distribution"].items():
        lines.append(f"   {tier}: {info['count']}段 {info['values']}")
    if durations["issues"]:
        for issue in durations["issues"]:
            lines.append(f"   ⚠️ {issue}")
    lines.append("")

    # 质量评分
    lines.append(f"🎯 效果评分: {scores['average_score']}/10 ({scores['grade']})")
    for dim, info in scores["dimensions"].items():
        bar = "█" * info["score"] + "░" * (10 - info["score"])
        lines.append(f"   {dim}: {bar} {info['score']}/10")
        lines.append(f"     └ {info['comment']}")
    lines.append(f"   总分: {scores['total_score']}/50")
    lines.append("")

    # 综合判定
    lines.append("=" * 60)
    lines.append(
        f"{'✅ 验证通过 — 产物完整，时长合规' if passed else '❌ 验证失败 — 请检查上述问题'}"
    )
    lines.append("=" * 60)

    return "\n".join(lines)


# ── CLI ───────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="漫剧任务产物验证工具")
    parser.add_argument("task_folder", help="任务目录路径")
    parser.add_argument("--scene-count", type=int, default=None, help="场景数")
    parser.add_argument(
        "--durations",
        type=str,
        default=None,
        help="时长列表（逗号分隔），如: 6,8,12,14,11,9",
    )
    parser.add_argument(
        "--expected-total", type=int, default=None, help="期望总时长（秒），如: 60"
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="自动从 plot.md/script.md 提取 scene_count 和 durations",
    )
    parser.add_argument("--verbose", action="store_true", help="输出详细信息")
    parser.add_argument("--json", action="store_true", help="仅输出 JSON（不输出摘要）")

    args = parser.parse_args()

    durations_list = None
    if args.durations:
        durations_list = [int(x.strip()) for x in args.durations.split(",")]

    report = verify_task(
        task_folder=args.task_folder,
        scene_count=args.scene_count,
        durations=durations_list,
        expected_total=args.expected_total,
        verbose=args.verbose,
    )

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        # 打印人类可读摘要
        print(report["summary"])
        print()
        # 也输出 JSON 到 stderr 便于程序解析
        print(json.dumps(report, ensure_ascii=False, indent=2), file=sys.stderr)

    sys.exit(0 if report["overall_passed"] else 1)
