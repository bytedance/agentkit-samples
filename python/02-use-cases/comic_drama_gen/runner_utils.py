import json
import os
import subprocess
import time

from config import APP, BASE_URL, ENV_BASE, LOG_DIR, OUTPUTS_DIR, PROJECT_ROOT, load_env

LOG_DIR.mkdir(parents=True, exist_ok=True)
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)


def send_sse(uid, sid, message, log_path, base_url=BASE_URL):
    """Sends a Server-Sent Event request with the given message."""
    payload = {
        "appName": APP,
        "userId": uid,
        "sessionId": sid,
        "newMessage": {"role": "user", "parts": [{"text": message}]},
        "streaming": True,
    }
    with open(log_path, "ab") as f:
        proc = subprocess.Popen(
            [
                "curl",
                "-s",
                "-N",
                f"{base_url}/run_sse",
                "-H",
                "Content-Type: application/json",
                "-d",
                json.dumps(payload, ensure_ascii=False),
            ],
            stdout=f,
            stderr=subprocess.DEVNULL,
        )
    return proc


def create_session(uid, sid, base_url=BASE_URL):
    """Creates a new session for the given user ID and session ID."""
    subprocess.run(
        [
            "curl",
            "-s",
            "-X",
            "POST",
            f"{base_url}/apps/{APP}/users/{uid}/sessions/{sid}",
            "-H",
            "Content-Type: application/json",
            "-d",
            "",
        ],
        capture_output=True,
    )


def get_newest_task(outputs_dir=OUTPUTS_DIR):
    """Finds the most recently created task folder."""
    dirs = sorted(
        outputs_dir.glob("task_*"), key=lambda d: d.stat().st_ctime, reverse=True
    )
    return dirs[0] if dirs else None


def has_final_video(task_folder):
    """Checks if the task folder has a generated final video."""
    if task_folder is None:
        return False
    finals = list(task_folder.glob("final/*.mp4"))
    return len(finals) > 0


def task_status(task_folder):
    """Returns the current status of artifacts in a task folder."""
    if task_folder is None:
        return {}
    return {
        "has_script": (task_folder / "script.md").exists(),
        "has_chars": (task_folder / "characters.md").exists(),
        "storyboards": len(list(task_folder.glob("storyboard/scene_*.jpg"))),
        "videos": len(list(task_folder.glob("videos/scene_[0-9][0-9].mp4")))
        + len(list(task_folder.glob("videos/*.mp4"))),
    }


def continuation_message(task_folder):
    """Determines the correct prompt message to nudge the agent based on missing artifacts."""
    st = task_status(task_folder)
    # 在所有续接消息中明确当前任务目录，防止 Agent 重新 init 创建新目录
    folder_hint = (
        f"【当前任务目录：{task_folder}，请在此目录继续，不要重新初始化新目录】\n"
        if task_folder
        else ""
    )
    if not st.get("has_script"):
        return (
            folder_hint
            + "请继续创作完整对白剧本script.md（含逐秒时间戳和空间方位小节），然后继续角色设计、场景美术、分镜视频、视频合成全流程"
        )
    if not st.get("has_chars"):
        return (
            folder_hint
            + "剧本已完成，请继续角色设计、场景美术（storyboard）、分镜视频生成、视频合成"
        )
    if st.get("storyboards", 0) == 0:
        return (
            folder_hint
            + "角色设计完成，请继续场景美术（storyboard）、分镜视频生成、视频合成"
        )
    if st.get("videos", 0) == 0:
        return (
            folder_hint
            + "分镜图完成，请用submit_video_tasks并行提交所有视频任务，轮询完成后下载，最后合成final视频"
        )
    return (
        folder_hint
        + f"视频已下载({st['videos']}个)，请合成最终视频（mergeVideos严格只使用scene_01.mp4...格式文件，不含_1后缀），上传TOS并返回链接"
    )


def restart_server(minutes, base_url=BASE_URL, outputs_dir=OUTPUTS_DIR, port=None):
    """Terminates existing server and starts a new instance with the specified configuration."""
    subprocess.run(["pkill", "-f", "veadk web"], capture_output=True)
    time.sleep(3)

    custom_env = load_env()
    env = {
        **os.environ,
        **ENV_BASE,
        **custom_env,
        "VIDEO_DURATION_MINUTES": str(minutes),
        "COMIC_DRAMA_OUTPUT_DIR": str(outputs_dir),
    }

    log = open(f"/tmp/veadk_server_{minutes}min.log", "w")
    cmd = ["veadk", "web"]
    if port:
        cmd.extend(["--port", str(port)])

    subprocess.Popen(
        cmd,
        cwd=str(PROJECT_ROOT.parent),
        env=env,
        stdout=log,
        stderr=log,
    )

    for _ in range(30):
        time.sleep(2)
        try:
            result = subprocess.run(
                ["curl", "-s", f"{base_url}/list-apps"],
                capture_output=True,
                text=True,
                timeout=3,
            )
            if APP in result.stdout:
                print(f"  Server ready ({minutes}min config)")
                return True
        except Exception:
            pass
    print("  Server failed to start!")
    return False


def pull_sse_until_completion(
    proc, check_interval=5, timeout=180, task_check_interval=0
):
    """Wait for the SSE process to complete or timeout."""
    deadline = time.time() + timeout
    last_task_check = time.time()
    start_time = time.time()
    last_heartbeat = time.time()
    heartbeat_interval = 60  # 每60秒打印一次心跳

    while proc.poll() is None and time.time() < deadline:
        time.sleep(check_interval)
        now = time.time()
        elapsed = int(now - start_time)
        remaining = int(deadline - now)

        # 心跳输出，避免用户以为脚本挂死
        if now - last_heartbeat >= heartbeat_interval:
            print(
                f"   ⏳ Agent still running... elapsed={elapsed}s remaining={remaining}s"
            )
            last_heartbeat = now

        if task_check_interval > 0 and now - last_task_check >= task_check_interval:
            task = get_newest_task()
            if has_final_video(task):
                break
            last_task_check = now

    if proc.poll() is None:
        proc.terminate()
        proc.wait(timeout=5)
