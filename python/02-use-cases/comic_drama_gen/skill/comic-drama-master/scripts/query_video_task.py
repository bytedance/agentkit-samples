"""
查询视频生成任务状态。

用法:
    python scripts/query_video_task.py <task_id>
"""

import logging
import sys
import os
import requests


logger = logging.getLogger(__name__)


def _get_auth() -> str:
    api_key = os.environ.get("ARK_API_KEY", "")
    return f"Bearer {api_key}"


def query_video_status(task_id: str) -> str:
    """
    查询视频生成任务状态。

    Returns:
        str: 状态描述（含视频链接或错误信息）
    """
    url = (
        f"https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks/{task_id}"
    )
    headers = {"Content-Type": "application/json", "Authorization": _get_auth()}

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()

        data = response.json()
        status = data.get("status")

        if status in ["success", "succeeded"]:
            content = data.get("content", {})
            video_url = None

            if isinstance(content, dict):
                video_url = (
                    content.get("video_url")
                    or content.get("url")
                    or content.get("url_main")
                )
                if not video_url:
                    for key, val in content.items():
                        if (
                            isinstance(val, str)
                            and "http" in val
                            and (".mp4" in val or "video" in val.lower())
                        ):
                            video_url = val
                            break
            elif isinstance(content, list):
                for c in content:
                    if isinstance(c, dict):
                        if c.get("type") == "video":
                            video_url = (
                                c.get("video_url") or c.get("url") or c.get("url_main")
                            )
                        else:
                            for key, val in c.items():
                                if (
                                    isinstance(val, str)
                                    and "http" in val
                                    and (".mp4" in val or "video" in val.lower())
                                ):
                                    video_url = val
                                    break
                    if video_url:
                        break

            if not video_url:
                video_url = data.get("video_url") or data.get("url")

            if video_url:
                result = f"视频生成成功！视频链接: {video_url}"
            else:
                result = f"视频生成成功！返回数据: {data}"

            return result

        elif status == "failed":
            error = data.get("error", "未知错误")
            # 结构化输出错误信息
            if isinstance(error, dict):
                error_code = error.get("code", "")
                error_msg = error.get("message", str(error))
            else:
                error_code = ""
                error_msg = str(error)

            # 对内容审核错误给出明确提示，引导 Agent 调整提示词重试
            if "SensitiveContent" in error_code or "Sensitive" in error_code:
                return (
                    f"任务失败（内容审核不通过）: {error_msg}\n"
                    f"错误码: {error_code}\n"
                    f"建议: 请修改视频提示词，避免含有打斗、武器、暴力等可能触发审核的描述，"
                    f"改用更温和的场景叙述后重新提交任务。"
                )
            return f"任务失败，错误码: {error_code}，原因: {error_msg}"

        else:
            return f"任务状态: {status}，请稍候再查"

    except requests.exceptions.RequestException as e:
        raise Exception(f"查询生成任务状态失败: {e}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        result = query_video_status(sys.argv[1])
        print(result)
    else:
        print("用法: python scripts/query_video_task.py <task_id>")
        sys.exit(1)
