#!/usr/bin/env python3
"""
Video Breakdown Agent — 最小联调/冒烟测试脚本

用法（从项目根目录运行）：
    # 交互式对话（默认）
    uv run python .scripts/smoke_test.py

    # 直接发送一条消息
    uv run python .scripts/smoke_test.py "你好，介绍一下你的功能"

    # 运行 pipeline 回归用例
    uv run python .scripts/smoke_test.py --pipeline-cases

依赖：需要在项目根目录下已有 config.yaml 或 .env 配置。
"""

import asyncio
import sys
import os
from pathlib import Path

# 确保项目根目录在 Python 路径中
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


async def run_single(message: str) -> str:
    """发送单条消息并返回 Agent 最终输出"""
    # 延迟导入，让 sys.path 先生效
    from agent import runner  # noqa: E402

    print(f"\n{'=' * 60}")
    print(f"📤 发送: {message}")
    print(f"{'=' * 60}")

    result = await runner.run(
        messages=message,
        user_id="smoke_test_user",
        session_id="smoke_test_session",
    )

    print(f"\n{'=' * 60}")
    print("📥 回复:")
    print(f"{'=' * 60}")
    print(result)
    return result


async def run_interactive() -> None:
    """交互式多轮对话"""
    from agent import runner  # noqa: E402

    session_id = f"smoke_test_{os.getpid()}"
    user_id = "smoke_test_user"
    turn = 0

    print("=" * 60)
    print("Video Breakdown Agent — 交互式测试")
    print("输入消息后回车发送，输入 q/quit/exit 退出")
    print("=" * 60)

    while True:
        try:
            message = input("\n🧑 你: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n👋 再见！")
            break

        if not message:
            continue
        if message.lower() in ("q", "quit", "exit"):
            print("👋 再见！")
            break

        turn += 1
        print(f"\n⏳ 正在处理（第 {turn} 轮）...")

        try:
            result = await runner.run(
                messages=message,
                user_id=user_id,
                session_id=session_id,
            )
            print(f"\n🤖 小视: {result}")
        except Exception as e:
            print(f"\n❌ 出错: {e}")


def _looks_like_raw_json(text: str) -> bool:
    stripped = (text or "").strip()
    return (stripped.startswith("{") and stripped.endswith("}")) or (
        stripped.startswith("[") and stripped.endswith("]")
    )


def _assert_case_output(
    case_name: str, output: str, expected_keywords: list[str]
) -> None:
    lowered = (output or "").lower()
    if "<[plhd" in lowered or "transfer_to_agent" in lowered:
        raise AssertionError(f"{case_name}: 检测到内部占位/转移片段泄露")
    if _looks_like_raw_json(output):
        raise AssertionError(f"{case_name}: 输出仍是原始 JSON")
    if "我是search_agent" in (output or ""):
        raise AssertionError(f"{case_name}: 对话未切回 root，仍由 search_agent 输出")
    for keyword in expected_keywords:
        if keyword not in output:
            raise AssertionError(f"{case_name}: 未命中预期关键词 `{keyword}`")


async def run_pipeline_cases() -> None:
    """本地/云端一致性回归用例（需要真实视频 URL 或本地测试视频）。"""
    from agent import runner  # noqa: E402

    session_id = f"pipeline_case_{os.getpid()}"
    user_id = "smoke_test_user"

    # 使用实际测试视频（如果项目内有 .media-uploads 中的测试样本）
    test_video = os.getenv(
        "TEST_VIDEO_URL", "https://tos-cn-beijing.volces.com/obj/video-demo/sample.mp4"
    )

    # 检查本地测试视频
    local_test_videos = list(Path(PROJECT_ROOT / ".media-uploads").glob("*.mp4"))
    if local_test_videos:
        test_video = str(local_test_videos[0])
        print(f"Using local test video: {test_video}")

    cases = [
        (
            "case1_full_pipeline",
            f"请对这个视频做完整分析并给出报告：{test_video}",
            ["钩子分析", "报告"],
        ),
        (
            "case2_hook_only",
            f"请分析这个视频前三秒钩子：{test_video}",
            ["前三秒钩子分析", "综合评分"],
        ),
        (
            "case3_greeting",
            "你好，介绍一下你的功能",
            ["分镜", "钩子", "报告"],
        ),
        (
            "case4_search_then_identity",
            "搜一下杭州这两天天气，然后回答：你是谁？",
            ["小视"],
        ),
    ]

    print("=" * 60)
    print("Video Breakdown Agent — Pipeline Cases")
    print("=" * 60)
    print(f"Test video: {test_video}")
    print(f"Session: {session_id}")

    passed = 0
    failed = 0

    for case_name, message, expected_keywords in cases:
        print(f"\n[RUN] {case_name}")
        print(f"Input: {message[:80]}...")
        try:
            output = await runner.run(
                messages=message,
                user_id=user_id,
                session_id=session_id,
            )
            output_str = str(output)
            print(f"Output preview: {output_str[:300]}...")
            _assert_case_output(case_name, output_str, expected_keywords)
            print(f"✅ [PASS] {case_name}")
            passed += 1
        except Exception as e:
            print(f"❌ [FAIL] {case_name}: {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    if failed > 0:
        sys.exit(1)


async def main() -> None:
    # 切换到项目根目录，确保 config.yaml 能被 VeADK 读取
    os.chdir(PROJECT_ROOT)

    if len(sys.argv) > 1 and sys.argv[1] == "--pipeline-cases":
        await run_pipeline_cases()
    elif len(sys.argv) > 1:
        # 单条消息模式
        message = " ".join(sys.argv[1:])
        await run_single(message)
    else:
        # 交互模式
        await run_interactive()


if __name__ == "__main__":
    asyncio.run(main())
