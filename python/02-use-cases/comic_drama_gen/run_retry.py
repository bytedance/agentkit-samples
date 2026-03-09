#!/usr/bin/env python3
import json
import os
import subprocess
import sys
import time
from pathlib import Path

BASE_URL = "http://localhost:8000"
APP = "comic_drama_gen_opencode"
PROJECT_ROOT = Path(__file__).parent
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
LOG_DIR = Path("/tmp/comic_drama_retry")
LOG_DIR.mkdir(parents=True, exist_ok=True)

REMAINING = [
    {"name": "绘本童话：小狐狸寻找星星碎片", "minutes": 1, "style": "温暖水彩绘本"},
    {"name": "历史武侠：荆轲刺秦王最后一夜", "minutes": 2, "style": "水墨古风写实"},
    {
        "name": "水墨古风：白蛇传·许仙与白娘子初遇",
        "minutes": 1,
        "style": "水墨晕染国风",
    },
    {"name": "科幻惊悚：克隆人觉醒反抗实验室", "minutes": 1, "style": "冷峻科幻写实"},
    {"name": "奇幻冒险：小镇女孩误入精灵王国", "minutes": 1, "style": "欧洲奇幻插画风"},
    {"name": "热血修仙：天才少年逆天改命", "minutes": 2, "style": "国漫3D玄幻风"},
    {"name": "国风神话：哪吒闹海斗龙王", "minutes": 1, "style": "敦煌壁画国风"},
]

ENV_BASE = {
    "VOLCENGINE_ACCESS_KEY": os.getenv("VOLCENGINE_ACCESS_KEY", ""),
    "VOLCENGINE_SECRET_KEY": os.getenv("VOLCENGINE_SECRET_KEY", ""),
    "MODEL_AGENT_API_KEY": os.getenv(
        "MODEL_AGENT_API_KEY", os.getenv("ARK_API_KEY", "")
    ),
    "DATABASE_TOS_BUCKET": os.getenv("DATABASE_TOS_BUCKET", ""),
}


def send_sse(uid, sid, message, log_path):
    payload = {
        "appName": APP,
        "userId": uid,
        "sessionId": sid,
        "newMessage": {"role": "user", "parts": [{"text": message}]},
        "streaming": True,
    }
    with open(log_path, "ab") as f:
        return subprocess.Popen(
            [
                "curl",
                "-s",
                "-N",
                f"{BASE_URL}/run_sse",
                "-H",
                "Content-Type: application/json",
                "-d",
                json.dumps(payload, ensure_ascii=False),
            ],
            stdout=f,
            stderr=subprocess.DEVNULL,
        )


def create_session(uid, sid):
    subprocess.run(
        [
            "curl",
            "-s",
            "-X",
            "POST",
            f"{BASE_URL}/apps/{APP}/users/{uid}/sessions/{sid}",
            "-H",
            "Content-Type: application/json",
            "-d",
            "",
        ],
        capture_output=True,
    )


def get_newest_task():
    dirs = sorted(
        OUTPUTS_DIR.glob("task_*"), key=lambda d: d.stat().st_ctime, reverse=True
    )
    return dirs[0] if dirs else None


def has_final_video(task_folder):
    if task_folder is None:
        return False
    return len(list(task_folder.glob("final/*.mp4"))) > 0


def continuation_message(task_folder):
    if task_folder is None:
        return "请继续完成漫剧生成全流程"
    has_script = (task_folder / "script.md").exists()
    has_chars = (task_folder / "characters.md").exists()
    sb = len(list(task_folder.glob("storyboard/scene_*.jpg")))
    vid = len(list(task_folder.glob("videos/scene_[0-9][0-9].mp4")))
    if not has_script:
        return "请继续创作完整对白剧本script.md（含逐秒时间戳和空间方位），然后继续角色设计、场景美术、分镜视频、视频合成全流程"
    if not has_chars:
        return "剧本已完成，请继续角色设计、场景美术、分镜视频生成、视频合成"
    if sb == 0:
        return (
            "角色设计完成，请继续场景美术（storyboard分镜图）、分镜视频生成、视频合成"
        )
    if vid == 0:
        return "分镜图完成，请用submit_video_tasks并行提交所有视频任务，轮询完成后下载，最后合成final视频"
    return f"视频已下载({vid}个)，请合成最终视频（mergeVideos严格只用scene_01.mp4格式文件），上传TOS并返回链接"


def restart_server(minutes):
    subprocess.run(["pkill", "-f", "veadk web"], capture_output=True)
    time.sleep(3)
    env = {**os.environ, **ENV_BASE, "VIDEO_DURATION_MINUTES": str(minutes)}
    log = open(f"/tmp/veadk_retry_{minutes}min.log", "w")
    subprocess.Popen(
        ["veadk", "web"], cwd=str(PROJECT_ROOT.parent), env=env, stdout=log, stderr=log
    )
    for _ in range(20):
        time.sleep(2)
        try:
            r = subprocess.run(
                ["curl", "-s", f"{BASE_URL}/list-apps"],
                capture_output=True,
                text=True,
                timeout=3,
            )
            if APP in r.stdout:
                return True
        except Exception:
            pass
    return False


def wait_sse(proc, timeout_s):
    deadline = time.time() + timeout_s
    while proc.poll() is None and time.time() < deadline:
        time.sleep(5)
    if proc.poll() is None:
        proc.terminate()
        proc.wait(timeout=5)


def run_one(idx, test):
    name, minutes, style = test["name"], test["minutes"], test["style"]
    uid, sid = f"u_r{idx}", f"s_r{idx}"

    print(f"\n{'═' * 56}")
    print(f"▶ Retry {idx + 1}/7: {name}")
    print(f"  {minutes}min ({minutes * 6} scenes) | {style}")
    print(f"{'═' * 56}", flush=True)

    if not restart_server(minutes):
        print("  ❌ Server failed to start", flush=True)
        return False

    create_session(uid, sid)

    prompt = f"请生成漫剧：{name}，视觉风格：{style}"
    print(f"[{time.strftime('%H:%M:%S')}] Round 1", flush=True)
    proc = send_sse(uid, sid, prompt, LOG_DIR / f"r{idx}_1.bin")
    wait_sse(proc, 180)

    for rnd in range(2, 30):
        task = get_newest_task()
        if task and has_final_video(task):
            sz = next(task.glob("final/*.mp4")).stat().st_size / 1_000_000
            print(f"[{time.strftime('%H:%M:%S')}] ✅ DONE ({sz:.1f}MB)", flush=True)
            return True

        msg = continuation_message(task)
        print(f"[{time.strftime('%H:%M:%S')}] Round {rnd}: {msg[:70]}...", flush=True)
        proc = send_sse(uid, sid, msg, LOG_DIR / f"r{idx}_{rnd}.bin")

        deadline = time.time() + 360
        while proc.poll() is None and time.time() < deadline:
            time.sleep(15)
            t = get_newest_task()
            if t and has_final_video(t):
                proc.terminate()
                sz = next(t.glob("final/*.mp4")).stat().st_size / 1_000_000
                print(f"[{time.strftime('%H:%M:%S')}] ✅ DONE ({sz:.1f}MB)", flush=True)
                return True
        if proc.poll() is None:
            proc.terminate()
        time.sleep(5)

    print(f"[{time.strftime('%H:%M:%S')}] ⚠️ Did not complete", flush=True)
    return False


def main():
    start = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    results = []
    for i in range(start, len(REMAINING)):
        ok = run_one(i, REMAINING[i])
        results.append((REMAINING[i]["name"], ok))
        p = sum(1 for _, o in results if o)
        print(
            f"Progress: {len(results)}/7 | ✅ {p} | ❌ {len(results) - p}", flush=True
        )

    print(f"\n{'═' * 56}")
    for name, ok in results:
        print(f"  {'✅' if ok else '❌'} {name}")
    print(f"Total: {sum(1 for _, o in results if o)}/{len(results)}")
    print(f"{'═' * 56}")


if __name__ == "__main__":
    main()
