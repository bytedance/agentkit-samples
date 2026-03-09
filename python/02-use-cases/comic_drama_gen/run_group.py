#!/usr/bin/env python3
import json
import sys
import time
import subprocess

from config import PROJECT_ROOT, LOG_DIR
from runner_utils import (
    create_session,
    send_sse,
    get_newest_task,
    has_final_video,
    continuation_message,
    restart_server,
)

with open(PROJECT_ROOT / "comic_prompts_30.json", "r", encoding="utf-8") as f:
    ALL_PROMPTS = json.load(f)


def run_single_test(idx, test):
    name = test["name"]
    minutes = test["minutes"]
    style = test["style"]
    desc = test["prompt"]
    uid = f"u_grp_{idx}"
    sid = f"s_grp_{idx}_{int(time.time())}"
    log = LOG_DIR / f"test_{idx:02d}.bin"

    print(f"\n{'═' * 56}")
    print(f"▶ Generating: {name}")
    print(f"  Duration: {minutes}min | Style: {style}")
    print(f"{'═' * 56}")

    if not restart_server(minutes):
        return False, None
    create_session(uid, sid)

    initial_msg = f"请生成漫剧：{name}，视觉风格：{style}。故事内容：{desc}"
    print(f"[{time.strftime('%H:%M:%S')}] Round 1: initial prompt")

    proc = send_sse(uid, sid, initial_msg, log)
    deadline = time.time() + 180
    while proc.poll() is None and time.time() < deadline:
        time.sleep(5)
    if proc.poll() is None:
        proc.kill()

    for rnd in range(2, 40):
        task = get_newest_task()
        if has_final_video(task):
            finals = list(task.glob("final/*.mp4"))
            size_mb = finals[0].stat().st_size / 1_000_000
            print(
                f"[{time.strftime('%H:%M:%S')}] ✅ DONE: {task.name} ({size_mb:.1f}MB)"
            )
            return True, task

        msg = continuation_message(task)
        print(f"[{time.strftime('%H:%M:%S')}] Round {rnd}: {msg[:60]}...")
        rnd_log = LOG_DIR / f"test_{idx:02d}_r{rnd}.bin"
        proc = send_sse(uid, sid, msg, rnd_log)
        deadline = time.time() + 300
        while proc.poll() is None and time.time() < deadline:
            time.sleep(10)
            task = get_newest_task()
            if has_final_video(task):
                break
        if proc.poll() is None:
            proc.kill()

        task = get_newest_task()
        if has_final_video(task):
            finals = list(task.glob("final/*.mp4"))
            size_mb = finals[0].stat().st_size / 1_000_000
            print(
                f"[{time.strftime('%H:%M:%S')}] ✅ DONE: {task.name} ({size_mb:.1f}MB)"
            )
            return True, task

        time.sleep(5)

    # 失败尝试清理
    print(f"[{time.strftime('%H:%M:%S')}] ⚠️ Failed to complete after 40 rounds")
    return False, None


def score_task(task_folder):
    if not task_folder:
        return ""
    try:
        proc = subprocess.run(
            [
                "python",
                "skill/comic-drama-master/scripts/video_scorer.py",
                str(task_folder),
            ],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
        )
        return proc.stdout
    except Exception as e:
        return f"Scoring error: {str(e)}"


def main():
    if len(sys.argv) < 2:
        print("Usage: python run_group.py <group_id>")
        sys.exit(1)

    group_id = int(sys.argv[1])
    group_prompts = [p for p in ALL_PROMPTS if p["group"] == group_id]

    print(f"Starting execution for Group {group_id} ({len(group_prompts)} prompts)")

    results = []

    for item in group_prompts:
        success = False
        retry_count = 0
        max_retries = 3
        task_folder = None

        while not success and retry_count < max_retries:
            if retry_count > 0:
                print(f"Retrying {item['name']}, attempt {retry_count + 1}...")
            success, task_folder = run_single_test(item["id"], item)
            if not success:
                retry_count += 1
                time.sleep(5)

        if success and task_folder:
            score_out = score_task(task_folder)
            results.append(
                {
                    "id": item["id"],
                    "name": item["name"],
                    "folder": str(task_folder),
                    "score_output": score_out,
                    "success": True,
                }
            )
        else:
            results.append({"id": item["id"], "name": item["name"], "success": False})

    # 将包含分数的结果保存下来供 Agent 写报告
    out_file = PROJECT_ROOT / f"group_{group_id}_results.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"Group {group_id} complete. Results saved to {out_file}")


if __name__ == "__main__":
    main()
