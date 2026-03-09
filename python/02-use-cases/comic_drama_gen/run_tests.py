#!/usr/bin/env python3
import sys
import time

from config import LOG_DIR
from runner_utils import (
    create_session,
    send_sse,
    get_newest_task,
    has_final_video,
    continuation_message,
    restart_server,
    pull_sse_until_completion,
)

TESTS = [
    {"name": "霓虹都市：黑客女神破解AI帝国", "minutes": 1, "style": "赛博朋克霓虹风"},
    {"name": "水墨玄幻：剑仙凌霄怒斩天命", "minutes": 1, "style": "中国水墨画风"},
    {
        "name": "言情穿越：现代CEO穿越成战国质子",
        "minutes": 1,
        "style": "唯美国漫3D写实",
    },
    {"name": "赛博朋克：废土猎人追杀机械龙", "minutes": 1, "style": "赛博朋克废土风"},
    {"name": "职场风云：实习生逆袭大厂CEO", "minutes": 1, "style": "现代都市写实"},
    {"name": "国风神话：嫦娥奔月的真相", "minutes": 1, "style": "敦煌壁画国风"},
    {"name": "科幻冒险：星际特工拯救地球", "minutes": 1, "style": "科幻硬核写实"},
    {"name": "喜剧奇幻：厨神穿越成宫廷御厨", "minutes": 1, "style": "Q版2D绘本"},
    {"name": "热血修仙：天才少年逆天改命", "minutes": 2, "style": "国漫3D玄幻风"},
    {"name": "悬疑都市：侦探女王破解连环密案", "minutes": 1, "style": "黑色电影诺瓦尔"},
    {"name": "绘本童话：小狐狸寻找星星碎片", "minutes": 1, "style": "温暖水彩绘本"},
    {"name": "历史武侠：荆轲刺秦王最后一夜", "minutes": 2, "style": "水墨古风写实"},
    {"name": "青春校园：篮球少年的冠军之路", "minutes": 1, "style": "青春活力漫画风"},
    {
        "name": "水墨古风：白蛇传·许仙与白娘子初遇",
        "minutes": 1,
        "style": "水墨晕染国风",
    },
    {"name": "科幻惊悚：克隆人觉醒反抗实验室", "minutes": 1, "style": "冷峻科幻写实"},
    {"name": "奇幻冒险：小镇女孩误入精灵王国", "minutes": 1, "style": "欧洲奇幻插画风"},
]


def run_test(idx, test):
    name = test["name"]
    minutes = test["minutes"]
    style = test["style"]
    uid = f"u_t{idx}"
    sid = f"s_t{idx}"
    log = LOG_DIR / f"test_{idx:02d}.bin"

    print(f"\n{'═' * 56}")
    print(f"▶ Test {idx + 1}/16: {name}")
    print(f"  Duration: {minutes}min ({minutes * 6} scenes) | Style: {style}")
    print(f"{'═' * 56}")

    if not restart_server(minutes):
        return False

    create_session(uid, sid)

    initial_msg = f"请生成漫剧：{name}，视觉风格：{style}"
    print(f"[{time.strftime('%H:%M:%S')}] Round 1: initial prompt")

    proc = send_sse(uid, sid, initial_msg, log)
    pull_sse_until_completion(proc, check_interval=5, timeout=180)

    for rnd in range(2, 25):
        task = get_newest_task()
        if has_final_video(task):
            finals = list(task.glob("final/*.mp4"))
            size_mb = finals[0].stat().st_size / 1_000_000
            print(
                f"[{time.strftime('%H:%M:%S')}] ✅ DONE: {task.name} ({size_mb:.1f}MB)"
            )
            return True

        msg = continuation_message(task)
        print(f"[{time.strftime('%H:%M:%S')}] Round {rnd}: {msg[:60]}...")
        rnd_log = LOG_DIR / f"test_{idx:02d}_r{rnd}.bin"

        proc = send_sse(uid, sid, msg, rnd_log)
        pull_sse_until_completion(
            proc, check_interval=10, timeout=300, task_check_interval=10
        )

        task = get_newest_task()
        if has_final_video(task):
            finals = list(task.glob("final/*.mp4"))
            size_mb = finals[0].stat().st_size / 1_000_000
            print(
                f"[{time.strftime('%H:%M:%S')}] ✅ DONE: {task.name} ({size_mb:.1f}MB)"
            )
            return True

        # 显示当前任务进度
        if task:
            st = {
                "storyboards": len(list(task.glob("storyboard/scene_*.jpg"))),
                "videos": len(list(task.glob("videos/scene_[0-9][0-9].mp4")))
                + len(list(task.glob("videos/*.mp4"))),
                "script": (task / "script.md").exists(),
                "chars": (task / "characters.md").exists(),
            }
            print(
                f"   📊 Task status: script={'✅' if st['script'] else '⏳'} chars={'✅' if st['chars'] else '⏳'} storyboard={st['storyboards']}张 video={st['videos']}个"
            )

        time.sleep(5)

    print(f"[{time.strftime('%H:%M:%S')}] ⚠️  Test {idx + 1} incomplete after 24 rounds")
    return False


def main():
    start = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    print(f"Starting 16-test suite from test {start + 1}")
    print(f"📁 Log directory: {LOG_DIR}")
    print(f"   Tip: tail -f {LOG_DIR}/test_NN.bin  to watch agent output")
    results = []

    for i in range(start, len(TESTS)):
        ok = run_test(i, TESTS[i])
        results.append((TESTS[i]["name"], ok))
        passed = sum(1 for _, ok in results if ok)
        total = len(results)
        print(
            f"\nProgress: {start + total}/{len(TESTS)} | ✅ {passed} | ❌ {total - passed}"
        )

    print(f"\n{'═' * 56}")
    print("FINAL RESULTS:")
    for name, ok in results:
        print(f"  {'✅' if ok else '❌'} {name}")
    passed = sum(1 for _, ok in results if ok)
    print(f"\nTotal: {passed}/{len(results)} passed")
    print(f"{'═' * 56}")


if __name__ == "__main__":
    main()
