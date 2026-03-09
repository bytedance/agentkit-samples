#!/usr/bin/env python3
"""
Batch Comic Drama Generator
Generates 30 comic dramas in 3 groups with reports after each group.
Usage:
  python batch_generate.py               # Run all 3 groups
  python batch_generate.py --group 2     # Run only group 2
"""

import argparse
import json
import signal
import sys
import time
from datetime import datetime

from config import PROJECT_ROOT, LOG_DIR
from runner_utils import (
    create_session,
    send_sse,
    get_newest_task,
    has_final_video,
    continuation_message,
    restart_server,
    pull_sse_until_completion,
)

LOG_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR = PROJECT_ROOT / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
PROMPTS_FILE = PROJECT_ROOT / "comic_prompts_30.json"


def load_prompts():
    with open(PROMPTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def get_prompts_by_group(prompts, group):
    return [p for p in prompts if p["group"] == group]


def generate_single_drama(prompt_info, idx):
    name = prompt_info["name"]
    prompt_text = prompt_info["prompt"]
    style = prompt_info["style"]
    minutes = prompt_info["minutes"]

    uid = f"u_batch_{idx}"
    sid = f"s_batch_{idx}"
    log_file = LOG_DIR / f"drama_{idx:02d}_{name}.log"

    print(f"\n{'=' * 60}")
    print(f">>> [{idx + 1}] Generating: {name}")
    print(f"    Style: {style} | Duration: {minutes}min")
    print(f"{'=' * 60}")

    if not restart_server(minutes, outputs_dir=OUTPUT_DIR):
        return {"success": False, "error": "Server failed to start"}

    create_session(uid, sid)

    initial_msg = f"请生成漫剧：{prompt_text}，视觉风格：{style}"
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Round 1: Initial prompt")

    proc = send_sse(uid, sid, initial_msg, log_file)
    pull_sse_until_completion(proc, check_interval=5, timeout=180)

    for rnd in range(2, 30):
        task = get_newest_task(OUTPUT_DIR)

        if has_final_video(task):
            finals = list(task.glob("final/*.mp4"))
            size_mb = finals[0].stat().st_size / 1_000_000
            print(
                f"[{datetime.now().strftime('%H:%M:%S')}] SUCCESS: {task.name} ({size_mb:.1f}MB)"
            )
            return {
                "success": True,
                "task_name": task.name,
                "task_path": str(task),
                "final_video": str(finals[0]),
                "size_mb": size_mb,
            }

        msg = continuation_message(task)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Round {rnd}: {msg[:50]}...")

        rnd_log = LOG_DIR / f"drama_{idx:02d}_{name}_r{rnd}.log"
        proc = send_sse(uid, sid, msg, rnd_log)
        pull_sse_until_completion(
            proc, check_interval=10, timeout=300, task_check_interval=10
        )

        task = get_newest_task(OUTPUT_DIR)
        if has_final_video(task):
            finals = list(task.glob("final/*.mp4"))
            size_mb = finals[0].stat().st_size / 1_000_000
            print(
                f"[{datetime.now().strftime('%H:%M:%S')}] SUCCESS: {task.name} ({size_mb:.1f}MB)"
            )
            return {
                "success": True,
                "task_name": task.name,
                "task_path": str(task),
                "final_video": str(finals[0]),
                "size_mb": size_mb,
            }

        time.sleep(5)

    print(
        f"[{datetime.now().strftime('%H:%M:%S')}] FAILED: {name} - Max rounds reached"
    )
    newest = get_newest_task(OUTPUT_DIR)
    return {
        "success": False,
        "error": "Max rounds reached",
        "task_name": newest.name if newest else None,
    }


def generate_group(group_num, prompts):
    group_prompts = get_prompts_by_group(prompts, group_num)
    results = []

    print(f"\n{'#' * 60}")
    print(f"# GROUP {group_num}: Generating {len(group_prompts)} dramas")
    print(f"{'#' * 60}")

    for prompt_info in group_prompts:
        idx = prompt_info["id"] - 1
        result = generate_single_drama(prompt_info, idx)
        result["prompt_info"] = prompt_info
        results.append(result)

        # Save progress
        progress_file = PROJECT_ROOT / f"group_{group_num}_progress.json"
        with open(progress_file, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        print("\n  Waiting 30 seconds before next generation...")
        time.sleep(30)

    return results


def generate_report(group_num, results):
    report_file = PROJECT_ROOT / f"report_group_{group_num}.md"

    successful = [r for r in results if r.get("success")]
    failed = [r for r in results if not r.get("success")]

    report = f"""# 漫剧生成报告 - 第{group_num}组

生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## 概览

| 指标 | 数值 |
|------|------|
| 总数 | {len(results)} |
| 成功 | {len(successful)} |
| 失败 | {len(failed)} |
| 成功率 | {len(successful) / len(results) * 100:.1f}% |

## 成功生成的漫剧

| # | 名称 | 风格 | 时长 | 文件大小 |
|---|------|------|------|---------|
"""

    for i, r in enumerate(successful):
        p = r["prompt_info"]
        report += f"| {i + 1} | {p['name']} | {p['style']} | {p['minutes']}min | {r.get('size_mb', 0):.1f}MB |\n"

    if failed:
        report += "\n## 失败的漫剧\n\n"
        for r in failed:
            p = r.get("prompt_info", {})
            report += (
                f"- **{p.get('name', 'Unknown')}**: {r.get('error', 'Unknown error')}\n"
            )

    report += "\n## 详细评分\n\n_评分将在视频分析后生成_\n"

    with open(report_file, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"\n  Report saved: {report_file}")


def main():
    parser = argparse.ArgumentParser(description="Batch Comic Drama Generator")
    parser.add_argument(
        "--group", type=int, default=0, help="Group number (1-3), 0 for all"
    )
    args = parser.parse_args()

    prompts = load_prompts()

    print(f"\n{'=' * 60}")
    print("  BATCH COMIC DRAMA GENERATOR")
    print(f"  Total prompts: {len(prompts)}")
    print(f"  Output directory: {OUTPUT_DIR}")
    print(f"{'=' * 60}")

    def signal_handler(sig, frame):
        print("\n\nShutting down...")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    if args.group > 0:
        results = generate_group(args.group, prompts)
        generate_report(args.group, results)
    else:
        all_results = {}
        for group_num in [1, 2, 3]:
            results = generate_group(group_num, prompts)
            all_results[f"group_{group_num}"] = results
            generate_report(group_num, results)

        final_file = PROJECT_ROOT / "all_results.json"
        with open(final_file, "w", encoding="utf-8") as f:
            json.dump(all_results, f, ensure_ascii=False, indent=2)

    print("\n\nGeneration complete!")


if __name__ == "__main__":
    main()
