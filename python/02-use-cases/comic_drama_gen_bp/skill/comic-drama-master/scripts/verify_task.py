"""
Comic drama task artifact verification tool.

Automatically checks after each comic drama generation:
1. Artifact completeness (directory tree + non-empty files)
2. Duration compliance (each scene 4~30s, total duration matches)
3. Five-dimension quality scoring (plot coherence / dialogue richness / visual quality / emotional tension / audio-visual sync)
4. Overall pass/fail verdict

Usage:
    python scripts/verify_task.py <task_folder> [--scene-count N] [--durations '6,8,12,14,11,9'] [--verbose]
    python scripts/verify_task.py <task_folder> --auto        # Auto-extract scene_count and durations from plot.md
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ── Constants ─────────────────────────────────────────────

MIN_SCENE_DURATION = 4
MAX_SCENE_DURATION = 30

# Root-level files that must exist and be non-empty
_REQUIRED_ROOT_FILES = [
    "requirements.md",
    "plot.md",
    "script.md",
    "characters.md",
    "cover.jpg",
    "cover.md",
]

# Subdirectories that must exist and be non-empty (with expected file patterns)
_REQUIRED_SUBDIRS = [
    "storyboard",
    "characters",
    "videos",
    "final",
]

# Score dimensions (these strings are emitted as JSON keys in the report and
# printed in the summary, so they are written in English like every other output)
_SCORE_DIMENSIONS = [
    "Plot coherence",
    "Dialogue richness",
    "Visual quality",
    "Emotional tension",
    "Duration diversity",
]


# ── Artifact completeness check ───────────────────────────


def check_file_exists_and_nonempty(path: Path) -> Tuple[bool, str]:
    """Check that a file exists and is non-empty."""
    if not path.exists():
        return False, f"Missing: {path.name}"
    if path.stat().st_size == 0:
        return False, f"Empty file: {path.name}"
    return True, f"✅ {path.name} ({path.stat().st_size} bytes)"


def check_artifacts(task_folder: Path, scene_count: int) -> Dict:
    """
    Check artifact completeness.

    Returns:
        dict: {passed, total_checks, failures, details, directory_tree}
    """
    checks = []
    failures = []

    # 1. Root-level files
    for fname in _REQUIRED_ROOT_FILES:
        ok, msg = check_file_exists_and_nonempty(task_folder / fname)
        checks.append({"file": fname, "passed": ok, "detail": msg})
        if not ok:
            failures.append(msg)

    # 2. final_video.md (optional but recommended)
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
                "detail": "⚠️ final_video.md missing (final delivery document)",
            }
        )
        failures.append("Missing: final_video.md")

    # 3. storyboard/ directory: scene_01.jpg ~ scene_NN.jpg
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
            {
                "file": "storyboard/",
                "passed": False,
                "detail": "Missing: storyboard/ directory",
            }
        )
        failures.append("Missing: storyboard/ directory")

    # 4. characters/ directory: at least 1 character portrait
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
                    "detail": f"✅ characters/ ({len(char_files)} character portraits)",
                }
            )
        else:
            checks.append(
                {
                    "file": "characters/",
                    "passed": False,
                    "detail": "Empty directory: characters/ (no character portrait images)",
                }
            )
            failures.append("Empty directory: characters/")
    else:
        checks.append(
            {
                "file": "characters/",
                "passed": False,
                "detail": "Missing: characters/ directory",
            }
        )
        failures.append("Missing: characters/ directory")

    # 5. videos/ directory: scene_01.mp4 ~ scene_NN.mp4
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
            {"file": "videos/", "passed": False, "detail": "Missing: videos/ directory"}
        )
        failures.append("Missing: videos/ directory")

    # 6. final/ directory: at least 1 .mp4
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
                    "detail": "Empty directory: final/ (no merged video)",
                }
            )
            failures.append("Empty directory: final/ (no merged video)")
    else:
        checks.append(
            {"file": "final/", "passed": False, "detail": "Missing: final/ directory"}
        )
        failures.append("Missing: final/ directory")

    # Build the directory tree
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
    """Build a string representation of the artifact directory tree."""
    lines = [f"{task_folder.name}/"]

    def _status(path: Path) -> str:
        if not path.exists():
            return "❌ missing"
        if path.is_file() and path.stat().st_size == 0:
            return "❌ empty file"
        return "✅"

    # Root-level files
    root_files = _REQUIRED_ROOT_FILES + ["final_video.md"]
    for i, fname in enumerate(root_files):
        is_last_file = (i == len(root_files) - 1) and not _REQUIRED_SUBDIRS
        prefix = "└── " if is_last_file else "├── "
        s = _status(task_folder / fname)
        lines.append(f"    {prefix}{fname}  {s}")

    # Subdirectories
    subdirs = _REQUIRED_SUBDIRS
    for j, dname in enumerate(subdirs):
        is_last_dir = j == len(subdirs) - 1
        prefix = "└── " if is_last_dir else "├── "
        d = task_folder / dname
        if not d.exists():
            lines.append(f"    {prefix}{dname}/  ❌ missing")
            continue

        file_count = len([f for f in d.iterdir() if f.is_file()]) if d.is_dir() else 0
        s = "✅" if file_count > 0 else "❌ empty"
        lines.append(f"    {prefix}{dname}/  {s} ({file_count} files)")

    return "\n".join(lines)


# ── Duration compliance check ─────────────────────────────


def check_durations(durations: List[int], expected_total: Optional[int] = None) -> Dict:
    """
    Check whether the duration allocation is compliant.

    Args:
        durations: List of per-scene durations (e.g. [6, 8, 12, 14, 11, 9])
        expected_total: Expected total duration in seconds, e.g. 60/120/180/240

    Returns:
        dict: {passed, actual_total, issues, duration_distribution}
    """
    issues = []
    actual_total = sum(durations)

    # Check each scene's duration range
    for i, d in enumerate(durations):
        if not (MIN_SCENE_DURATION <= d <= MAX_SCENE_DURATION):
            issues.append(
                f"Scene {i + 1} duration {d}s out of range [{MIN_SCENE_DURATION}~{MAX_SCENE_DURATION}]s"
            )

    # Check total duration deviation (±10% allowed)
    if expected_total:
        deviation = abs(actual_total - expected_total) / expected_total * 100
        if deviation > 10:
            issues.append(
                f"Total duration deviation too large: actual {actual_total}s vs expected {expected_total}s (deviation {deviation:.1f}%)"
            )

    # Duration diversity check: at least 3 distinct durations
    unique_durations = len(set(durations))
    if len(durations) >= 4 and unique_durations < 3:
        issues.append(
            f"Insufficient duration diversity: only {unique_durations} distinct durations used, recommended ≥ 3"
        )

    # Distribution statistics
    short_cut = [
        d for d in durations if MIN_SCENE_DURATION <= d <= 6
    ]  # tense quick cuts
    standard = [d for d in durations if 7 <= d <= 10]  # standard narration
    climax = [d for d in durations if 11 <= d <= 15]  # climax build-up
    epic = [d for d in durations if 16 <= d <= MAX_SCENE_DURATION]  # epic long takes

    # Tier labels are emitted as JSON keys in the report and printed in the summary
    distribution = {
        "Tense quick cuts (4~6s)": {"count": len(short_cut), "values": short_cut},
        "Standard narrative (7~10s)": {"count": len(standard), "values": standard},
        "Climax build-up (11~15s)": {"count": len(climax), "values": climax},
        "Epic long takes (16~30s)": {"count": len(epic), "values": epic},
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


# ── Content quality scoring (offline static analysis) ─────


def score_content(task_folder: Path, durations: List[int]) -> Dict:
    """
    Static quality scoring based on artifact files (no LLM API needed).

    Scoring dimensions (0-10 points each):
    1. Plot coherence: check that plot.md chapter count matches scene_count and scenes have transition wording
    2. Dialogue richness: check dialogue line count/density in script.md
    3. Visual quality: check characters.md prompt quality and storyboard file completeness
    4. Emotional tension: check for climax markers and rise-and-fall in duration allocation
    5. Duration diversity: check whether the distribution of durations is rich
    """
    scores = {}

    # 1. Plot coherence
    scores["Plot coherence"] = _score_plot_coherence(task_folder, len(durations))

    # 2. Dialogue richness
    scores["Dialogue richness"] = _score_dialogue_richness(task_folder, durations)

    # 3. Visual quality
    scores["Visual quality"] = _score_visual_quality(task_folder, len(durations))

    # 4. Emotional tension
    scores["Emotional tension"] = _score_emotional_tension(task_folder, durations)

    # 5. Duration diversity
    scores["Duration diversity"] = _score_duration_diversity(durations)

    # Overall score
    total = sum(s["score"] for s in scores.values())
    avg = total / len(scores)

    return {
        "dimensions": scores,
        "total_score": round(total, 1),
        "average_score": round(avg, 1),
        "grade": _grade(avg),
    }


def _read_file_safe(path: Path, max_chars: int = 5000) -> str:
    """Safely read the first N characters of a file."""
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8")[:max_chars]
    except Exception:
        return ""


def _score_plot_coherence(task_folder: Path, scene_count: int) -> Dict:
    """Evaluate plot coherence."""
    plot = _read_file_safe(task_folder / "plot.md")
    score = 0
    comments = []

    if not plot:
        return {"score": 0, "comment": "plot.md missing or empty"}

    # Check chapter count. Artifacts are written in the working language —
    # English by default ("## Chapter 3: ..." as a heading, or "Chapter 3: ...
    # (5s)" as an outline line) or the user's language (Chinese headings such
    # as "第三章" / "## 场景 3" are also recognised; other languages fall back
    # to the numbered-heading form). Count distinct chapter markers so the
    # outline and the headings are not double-counted.
    chapter_markers = set(
        re.findall(r"(?im)^\s*(?:#{1,4}\s*)?(?:chapter|scene)\s+(\d+)\s*:", plot)
    ) | set(
        re.findall(
            r"(?m)^\s*(?:#{1,4}\s*)?(?:第\s*([一二三四五六七八九十\d]+)\s*章|场景\s*(\d+))",
            plot,
        )
    )
    if len(chapter_markers) >= scene_count:
        score += 4
        comments.append(
            f"chapter count {len(chapter_markers)} ≥ scene count {scene_count}"
        )
    elif len(chapter_markers) >= scene_count * 0.7:
        score += 2
        comments.append(
            f"chapter count {len(chapter_markers)} slightly below scene count {scene_count}"
        )
    else:
        comments.append(
            f"chapter count {len(chapter_markers)} far below scene count {scene_count}"
        )

    # Check duration markers ("6s", "6 sec", "6 seconds", "6秒")
    duration_markers = re.findall(r"(?i)\d+\s*(?:seconds?|secs?|s\b|秒)", plot)
    if len(duration_markers) >= scene_count * 0.8:
        score += 3
        comments.append("duration markers complete")
    elif duration_markers:
        score += 1
        comments.append(
            f"duration markers incomplete ({len(duration_markers)}/{scene_count})"
        )

    # Check content richness
    if len(plot) > 500:
        score += 2
        comments.append("content detailed")
    elif len(plot) > 200:
        score += 1
        comments.append("content moderate")

    # Check for story-arc markers (English and Chinese keywords matched against
    # plot.md content; the documents are written in the working language)
    arc_keywords = [
        "setup",
        "development",
        "climax",
        "resolution",
        "build-up",
        "buildup",
        "turning point",
        "ending",
        "afterglow",
        "开端",
        "发展",
        "高潮",
        "结局",
        "铺垫",
        "转折",
        "收尾",
    ]
    plot_lower = plot.lower()
    arc_found = sum(1 for kw in arc_keywords if kw in plot_lower)
    if arc_found >= 3:
        score += 1
        comments.append("story arc clear")

    return {"score": min(score, 10), "comment": "; ".join(comments)}


def _score_dialogue_richness(task_folder: Path, durations: List[int]) -> Dict:
    """Evaluate dialogue richness."""
    script = _read_file_safe(task_folder / "script.md", max_chars=10000)
    score = 0
    comments = []

    if not script:
        return {"score": 0, "comment": "script.md missing or empty"}

    # Dialogue line count (English screenplays quote lines with straight or curly
    # double quotes, e.g. `**Han Li** (grits teeth): "I will not yield."`)
    dialogue_lines = re.findall(r'"[^"\n]{2,}"|[“][^”\n]{2,}[”]', script)
    if len(dialogue_lines) >= len(durations) * 3:
        score += 4
        comments.append(f"rich dialogue ({len(dialogue_lines)} lines)")
    elif len(dialogue_lines) >= len(durations) * 2:
        score += 3
        comments.append(f"moderate dialogue ({len(dialogue_lines)} lines)")
    elif len(dialogue_lines) >= len(durations):
        score += 2
        comments.append(f"sparse dialogue ({len(dialogue_lines)} lines)")
    else:
        score += 1
        comments.append(f"insufficient dialogue ({len(dialogue_lines)} lines)")

    # Check speaker variety: names are bolded (`**Han Li** (...): "..."`) or written
    # plainly before a colon (`Han Li: "..."` / `韩立："..."`)
    speaker_patterns = re.findall(r"\*\*([^*\n]{1,30})\*\*", script)
    speaker_patterns += re.findall(
        r"(?m)^\s*([A-Z][A-Za-z .'\-]{1,30}?|[\u4e00-\u9fff·]{1,10})\s*[:：]\s*[\"“]",
        script,
    )
    unique_speakers = len({s.strip().lower() for s in speaker_patterns})
    if unique_speakers >= 2:
        score += 2
        comments.append(f"{unique_speakers} speaking characters")
    elif unique_speakers == 1:
        score += 1
        comments.append("only 1 speaking character")

    # Check timestamps ("0:04", "6s", "6 seconds", "6秒", "T=4")
    timestamps = re.findall(
        r"(?i)\d+:\d+|\d+\s*(?:seconds?|secs?|s\b|秒)|T=\d+", script
    )
    if len(timestamps) >= len(durations):
        score += 2
        comments.append("per-scene timestamps complete")
    elif timestamps:
        score += 1
        comments.append("partial timestamps")

    # Check scene ending states (the screenplay template — English by default, Chinese also recognised — writes
    # "### Scene End State")
    end_states = re.findall(
        r"(?:scene end state|ending state|end state|场景结束状态|结束状态)",
        script,
        re.IGNORECASE,
    )
    if len(end_states) >= len(durations) * 0.5:
        score += 2
        comments.append("scene ending states fully annotated")

    return {"score": min(score, 10), "comment": "; ".join(comments)}


def _score_visual_quality(task_folder: Path, scene_count: int) -> Dict:
    """Evaluate visual quality."""
    score = 0
    comments = []

    # Check characters.md prompts
    chars = _read_file_safe(task_folder / "characters.md")
    if chars:
        # Check English prompt words
        eng_prompts = re.findall(r"[a-zA-Z]{3,}", chars)
        if len(eng_prompts) >= 20:
            score += 3
            comments.append("character prompts detailed")
        elif len(eng_prompts) >= 10:
            score += 2
            comments.append("character prompts basic")
        else:
            score += 1
            comments.append("character prompts minimal")

        # Check STYLE_ANCHOR
        if "STYLE_ANCHOR" in chars or "style_anchor" in chars.lower():
            score += 1
            comments.append("STYLE_ANCHOR defined")
    else:
        comments.append("characters.md missing")

    # Check storyboard image completeness
    sb_dir = task_folder / "storyboard"
    if sb_dir.is_dir():
        sb_files = [
            f for f in sb_dir.iterdir() if f.suffix in (".jpg", ".png", ".webp")
        ]
        if len(sb_files) >= scene_count:
            score += 3
            comments.append(
                f"storyboard images complete ({len(sb_files)}/{scene_count})"
            )
        elif len(sb_files) >= scene_count * 0.7:
            score += 2
            comments.append(
                f"storyboard images mostly complete ({len(sb_files)}/{scene_count})"
            )
        else:
            score += 1
            comments.append(
                f"storyboard images insufficient ({len(sb_files)}/{scene_count})"
            )
    else:
        comments.append("storyboard/ missing")

    # Check cover
    cover = task_folder / "cover.jpg"
    if cover.exists() and cover.stat().st_size > 0:
        score += 2
        comments.append("cover image present")
    else:
        comments.append("cover image missing")

    # Check character portraits
    char_dir = task_folder / "characters"
    if char_dir.is_dir():
        char_imgs = [
            f for f in char_dir.iterdir() if f.suffix in (".jpg", ".png", ".webp")
        ]
        if char_imgs:
            score += 1
            comments.append(f"{len(char_imgs)} character portraits")

    return {"score": min(score, 10), "comment": "; ".join(comments)}


def _score_emotional_tension(task_folder: Path, durations: List[int]) -> Dict:
    """Evaluate emotional tension."""
    score = 0
    comments = []

    plot = _read_file_safe(task_folder / "plot.md")
    script = _read_file_safe(task_folder / "script.md", max_chars=10000)
    combined = plot + script

    # Check emotion keywords (English and Chinese keywords matched against
    # plot/script content; the documents are written in the working language)
    tension_keywords = [
        "climax",
        "turning point",
        "showdown",
        "eruption",
        "outburst",
        "fury",
        "furious",
        "tense",
        "tension",
        "fierce",
        "roar",
        "desperate",
        "despair",
        "hope",
        "sacrifice",
        "awaken",
        "defiant",
        "grief",
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
    combined_lower = combined.lower()
    found_keywords = [kw for kw in tension_keywords if kw in combined_lower]
    if len(found_keywords) >= 5:
        score += 3
        comments.append(f"rich emotional keywords ({len(found_keywords)})")
    elif len(found_keywords) >= 3:
        score += 2
        comments.append(f"moderate emotional keywords ({len(found_keywords)})")
    elif found_keywords:
        score += 1
        comments.append(f"few emotional keywords ({len(found_keywords)})")

    # Check for rise-and-fall in duration allocation (standard deviation)
    if len(durations) >= 3:
        avg = sum(durations) / len(durations)
        variance = sum((d - avg) ** 2 for d in durations) / len(durations)
        std_dev = variance**0.5
        if std_dev >= 3:
            score += 3
            comments.append(
                f"large duration variation (σ={std_dev:.1f}s), strong pacing"
            )
        elif std_dev >= 2:
            score += 2
            comments.append(f"some duration variation (σ={std_dev:.1f}s)")
        elif std_dev >= 1:
            score += 1
            comments.append(f"durations fairly uniform (σ={std_dev:.1f}s), flat pacing")
        else:
            comments.append(
                f"no duration variation (σ={std_dev:.1f}s), monotonous pacing"
            )

    # Check that the climax is in the latter half (longer scenes should cluster in the middle/late part)
    if len(durations) >= 4:
        # If the latter half is not all short (a short wrap-up is allowed), check whether the maximum is in the middle/late part
        max_idx = durations.index(max(durations))
        if max_idx >= len(durations) * 0.3:
            score += 2
            comments.append("climax scene in the middle/late section")
        else:
            score += 1
            comments.append("climax scene too early")

    # Camera-work keywords (English and Chinese terms matched against
    # plot/script content; the documents are written in the working language)
    camera_keywords = [
        "close-up",
        "medium shot",
        "wide shot",
        "low angle",
        "high angle",
        "bird's-eye",
        "worm's-eye",
        "tracking shot",
        "slow motion",
        "quick cut",
        "fast cut",
        "push-in",
        "pull-back",
        "whip pan",
        "dolly",
        "orbit",
        "zoom",
        "特写",
        "近景",
        "远景",
        "仰角",
        "俯瞰",
        "追踪",
        "慢动作",
        "快切",
        "推镜",
        "环绕",
    ]
    cam_found = [kw for kw in camera_keywords if kw in combined.lower()]
    if len(cam_found) >= 3:
        score += 2
        comments.append(f"rich camera language ({len(cam_found)} types)")
    elif cam_found:
        score += 1
        comments.append(f"basic camera language ({len(cam_found)} types)")

    return {"score": min(score, 10), "comment": "; ".join(comments)}


def _score_duration_diversity(durations: List[int]) -> Dict:
    """Evaluate duration diversity."""
    score = 0
    comments = []

    unique = set(durations)

    # Variety of distinct durations
    if len(unique) >= 5:
        score += 4
        comments.append(f"{len(unique)} distinct durations, very rich")
    elif len(unique) >= 4:
        score += 3
        comments.append(f"{len(unique)} distinct durations")
    elif len(unique) >= 3:
        score += 2
        comments.append(f"{len(unique)} distinct durations")
    elif len(unique) >= 2:
        score += 1
        comments.append(f"only {len(unique)} distinct durations, rather monotonous")
    else:
        comments.append(f"only 1 duration ({durations[0]}s), completely monotonous")

    # Coverage of the three tiers
    has_short = any(MIN_SCENE_DURATION <= d <= 6 for d in durations)
    has_mid = any(7 <= d <= 10 for d in durations)
    has_long = any(11 <= d <= MAX_SCENE_DURATION for d in durations)
    coverage = sum([has_short, has_mid, has_long])

    if coverage == 3:
        score += 3
        comments.append("all three duration tiers covered (quick-cut/standard/climax)")
    elif coverage == 2:
        score += 2
        comments.append(f"covers {coverage}/3 duration tiers")
    else:
        score += 1
        comments.append(f"covers only {coverage}/3 duration tiers")

    # Range span
    span = max(durations) - min(durations)
    if span >= 8:
        score += 3
        comments.append(
            f"duration span {span}s ({min(durations)}s ~ {max(durations)}s), rich pacing"
        )
    elif span >= 5:
        score += 2
        comments.append(f"duration span {span}s")
    elif span >= 2:
        score += 1
        comments.append(f"duration span only {span}s, rather narrow")
    else:
        comments.append(f"duration span only {span}s, too monotonous")

    return {"score": min(score, 10), "comment": "; ".join(comments)}


def _grade(avg_score: float) -> str:
    """Assign a grade based on the average score."""
    if avg_score >= 9:
        return "S (Outstanding)"
    elif avg_score >= 8:
        return "A (Excellent)"
    elif avg_score >= 7:
        return "B (Good)"
    elif avg_score >= 6:
        return "C (Pass)"
    elif avg_score >= 5:
        return "D (Needs Improvement)"
    else:
        return "F (Fail)"


# ── Auto-extract scene_count and durations ────────────────


def auto_detect_from_plot(
    task_folder: Path,
) -> Tuple[Optional[int], Optional[List[int]]]:
    """Auto-extract scene_count and durations from plot.md or script.md."""
    for fname in ("plot.md", "script.md"):
        content = _read_file_safe(task_folder / fname, max_chars=10000)
        if not content:
            continue

        # Try to match scene_durations = [6, 8, 12, 14, 11, 9]
        m = re.search(r"scene_durations\s*=\s*\[([0-9,\s]+)\]", content)
        if m:
            durations = [int(x.strip()) for x in m.group(1).split(",") if x.strip()]
            return len(durations), durations

        # Try to match the "Chapter N: xxx (Ns)" / "## Chapter N: ... (Duration: Ns)"
        # format used by plot.md and script.md (English by default), or the
        # Chinese equivalent "第N章 ... (N秒)" / "场景N ... N秒"
        chapters = re.findall(
            r"(?i)(?:chapter|scene)\s+\d+\s*:.*?(\d+)\s*(?:seconds?|secs?|s\b|秒)",
            content,
        )
        if not chapters:
            chapters = re.findall(
                r"(?:第[一二三四五六七八九十\d]+章|场景\s*\d+).*?(\d+)\s*(?:秒|s\b)",
                content,
            )
        if chapters:
            durations = [int(x) for x in chapters]
            return len(durations), durations

    return None, None


# ── Main verification flow ────────────────────────────────


def verify_task(
    task_folder: str,
    scene_count: Optional[int] = None,
    durations: Optional[List[int]] = None,
    expected_total: Optional[int] = None,
    verbose: bool = False,
) -> Dict:
    """
    Run the full verification.

    Args:
        task_folder: Path to the task directory
        scene_count: Number of scenes (auto-detected if not provided)
        durations: List of durations (auto-detected if not provided)
        expected_total: Expected total duration in seconds
        verbose: Whether to output detailed information

    Returns:
        dict: Full verification report
    """
    folder = Path(task_folder)
    if not folder.is_dir():
        return {
            "task_folder": task_folder,
            "overall_passed": False,
            "error": f"Task directory does not exist: {task_folder}",
        }

    # Auto-detect
    if scene_count is None or durations is None:
        auto_sc, auto_dur = auto_detect_from_plot(folder)
        if auto_sc and auto_dur:
            scene_count = scene_count or auto_sc
            durations = durations or auto_dur

    if scene_count is None:
        # Infer from the videos/ directory
        vid_dir = folder / "videos"
        if vid_dir.is_dir():
            vid_files = sorted(
                [f for f in vid_dir.iterdir() if re.match(r"scene_\d{2}\.mp4$", f.name)]
            )
            scene_count = len(vid_files) if vid_files else 6
        else:
            scene_count = 6  # default

    if durations is None:
        durations = [10] * scene_count  # default: uniform

    # 1. Artifact completeness
    artifact_result = check_artifacts(folder, scene_count)

    # 2. Duration compliance
    duration_result = check_durations(durations, expected_total)

    # 3. Content quality scoring
    score_result = score_content(folder, durations)

    # Overall verdict
    overall_passed = artifact_result["passed"] and duration_result["passed"]

    report = {
        "task_folder": str(folder.absolute()),
        "task_name": folder.name,
        "verified_at": datetime.now().isoformat(),
        "overall_passed": overall_passed,
        "overall_verdict": "✅ PASSED" if overall_passed else "❌ FAILED",
        "artifact_check": artifact_result,
        "duration_check": duration_result,
        "quality_score": score_result,
        "summary": _build_summary(
            artifact_result, duration_result, score_result, overall_passed
        ),
    }

    return report


def _build_summary(artifacts: Dict, durations: Dict, scores: Dict, passed: bool) -> str:
    """Build a human-readable summary."""
    lines = []
    lines.append("=" * 60)
    lines.append("📋 Comic Drama Artifact Verification Report")
    lines.append("=" * 60)
    lines.append("")

    # Artifact completeness
    lines.append(
        f"📁 Artifact completeness: {'✅ PASSED' if artifacts['passed'] else '❌ FAILED'} ({artifacts['passed_count']}/{artifacts['total_checks']})"
    )
    if artifacts["failures"]:
        for f in artifacts["failures"]:
            lines.append(f"   ⛔ {f}")
    lines.append("")

    # Directory tree
    lines.append("📂 Directory structure:")
    lines.append(artifacts["directory_tree"])
    lines.append("")

    # Duration compliance
    lines.append(
        f"⏱️  Duration compliance: {'✅ PASSED' if durations['passed'] else '❌ FAILED'}"
    )
    lines.append(f"   Scene count: {durations['scene_count']}")
    lines.append(f"   Durations: {durations['durations']}")
    lines.append(f"   Total duration: {durations['actual_total_seconds']}s")
    lines.append(f"   Distinct durations: {durations['unique_duration_count']}")
    for tier, info in durations["distribution"].items():
        lines.append(f"   {tier}: {info['count']} scenes {info['values']}")
    if durations["issues"]:
        for issue in durations["issues"]:
            lines.append(f"   ⚠️ {issue}")
    lines.append("")

    # Quality score
    lines.append(f"🎯 Quality score: {scores['average_score']}/10 ({scores['grade']})")
    for dim, info in scores["dimensions"].items():
        bar = "█" * info["score"] + "░" * (10 - info["score"])
        lines.append(f"   {dim}: {bar} {info['score']}/10")
        lines.append(f"     └ {info['comment']}")
    lines.append(f"   Total score: {scores['total_score']}/50")
    lines.append("")

    # Overall verdict
    lines.append("=" * 60)
    lines.append(
        f"{'✅ Verification passed — artifacts complete, durations compliant' if passed else '❌ Verification failed — please review the issues above'}"
    )
    lines.append("=" * 60)

    return "\n".join(lines)


# ── CLI ───────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Comic drama task artifact verification tool"
    )
    parser.add_argument("task_folder", help="Path to the task directory")
    parser.add_argument(
        "--scene-count", type=int, default=None, help="Number of scenes"
    )
    parser.add_argument(
        "--durations",
        type=str,
        default=None,
        help="List of durations (comma-separated), e.g.: 6,8,12,14,11,9",
    )
    parser.add_argument(
        "--expected-total",
        type=int,
        default=None,
        help="Expected total duration in seconds, e.g.: 60",
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Auto-extract scene_count and durations from plot.md/script.md",
    )
    parser.add_argument(
        "--verbose", action="store_true", help="Output detailed information"
    )
    parser.add_argument(
        "--json", action="store_true", help="Output JSON only (no summary)"
    )

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
        # Print human-readable summary
        print(report["summary"])
        print()
        # Also output JSON to stderr for programmatic parsing
        print(json.dumps(report, ensure_ascii=False, indent=2), file=sys.stderr)

    sys.exit(0 if report["overall_passed"] else 1)
