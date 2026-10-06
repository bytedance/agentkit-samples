"""
Query the status of a video generation task.

Usage:
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
    Query the status of a video generation task.

    Returns:
        str: Status description (including the video link or error information)
    """
    api_base = os.environ.get(
        "MODEL_VIDEO_API_BASE", "https://ark.ap-southeast.bytepluses.com/api/v3"
    ).rstrip("/")
    url = f"{api_base}/contents/generations/tasks/{task_id}"
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
                result = f"Video generated successfully! Video link: {video_url}"
            else:
                result = f"Video generated successfully! Returned data: {data}"

            return result

        elif status == "failed":
            error = data.get("error", "unknown error")
            # Output error information in structured form
            if isinstance(error, dict):
                error_code = error.get("code", "")
                error_msg = error.get("message", str(error))
            else:
                error_code = ""
                error_msg = str(error)

            # Give a clear hint for content-moderation errors, guiding the Agent to adjust the prompt and retry
            if "SensitiveContent" in error_code or "Sensitive" in error_code:
                return (
                    f"Task failed (content moderation rejected): {error_msg}\n"
                    f"Error code: {error_code}\n"
                    f"Suggestion: Please revise the video prompt to avoid descriptions of fighting, weapons, violence, "
                    f"or other content that may trigger moderation, then resubmit the task with a milder scene description."
                )
            return f"Task failed, error code: {error_code}, reason: {error_msg}"

        else:
            return f"Task status: {status}, please check again later"

    except requests.exceptions.RequestException as e:
        raise Exception(f"Failed to query generation task status: {e}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        result = query_video_status(sys.argv[1])
        print(result)
    else:
        print("Usage: python scripts/query_video_task.py <task_id>")
        sys.exit(1)
