#!/usr/bin/env python3
# Copyright 2024 ByteDance, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Gateway Provider 实现。

使用 urllib 通过 API Gateway 调用市场洞察三大接口：
- ListCustomSubsTask（GET + JSON Body）
- PullPost（POST + JSON Body）
- QueryClueInfo（GET + JSON Body）

本模块：
- 仅依赖标准库；
- 统一解析网关返回的 Result；
- 对 QueryClueInfo 的 ClueText 做 json.loads 解析；
- 对网络错误和 429 做退避重试；
- 不打印密钥或完整网关地址，仅输出非敏感 Debug 摘要。
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

from auth_resolver import AuthError, NetworkError

API_VERSION = "2025-09-05"
DEFAULT_TIMEOUT = 30
MAX_RETRIES = 3
BACKOFF_BASE_SECONDS = 0.5


def _sanitize_host(url: str) -> str:
    """去掉 scheme 和查询参数，只保留主机部分并做简单截断。"""

    # 形如 https://host/path?query
    without_scheme = url.split("://", 1)[-1]
    host = without_scheme.split("/", 1)[0]
    if len(host) > 40:
        return host[:37] + "..."
    return host


def _debug_request_summary(action: str, method: str, url: str, payload: Dict[str, Any]) -> None:
    host = _sanitize_host(url)
    page_num = payload.get("PageNum")
    page_size = payload.get("PageSize") or payload.get("Size") or payload.get("MaxResults")
    print(
        f"[DEBUG][gateway] Action={action} method={method} host={host} "
        f"PageNum={page_num} PageSize/Size/MaxResults={page_size}"
    )


def _debug_response_summary(action: str, body: bytes) -> None:
    try:
        text = body.decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        return
    snippet = text[:500]
    print(
        f"[DEBUG][gateway] Action={action} 响应体前 500 字符:" f" {snippet!r}"
    )


def _build_url(api_base: str, action: str) -> str:
    return f"{api_base.rstrip('/')}/?Action={action}&Version={API_VERSION}"


def _do_request(
    *,
    method: str,
    url: str,
    api_key: str,
    payload: Dict[str, Any],
    action: str,
) -> Dict[str, Any]:
    """执行单次 HTTP 请求并解析 JSON 响应，包含重试与错误分类。"""

    data = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json; charset=UTF-8",
        "Authorization": f"Bearer {api_key}",
        "ServiceName": "insight",
    }

    for attempt in range(MAX_RETRIES):
        try:
            _debug_request_summary(action, method, url, payload)

            if method == "GET":
                req = urllib.request.Request(url, data=data, headers=headers)
                # 有 body 时 urllib 默认 POST，这里强制改为 GET
                req.get_method = lambda: "GET"  # type: ignore[assignment]
            else:
                req = urllib.request.Request(
                    url, data=data, headers=headers, method="POST"
                )

            with urllib.request.urlopen(req, timeout=DEFAULT_TIMEOUT) as resp:
                body = resp.read()
                _debug_response_summary(action, body)
                try:
                    parsed = json.loads(body.decode("utf-8"))
                except Exception as exc:  # noqa: BLE001
                    raise NetworkError(
                        f"Gateway 响应不是合法 JSON（Action={action}）: {exc}"
                    ) from exc

                if not isinstance(parsed, dict):
                    raise NetworkError(
                        f"Gateway 响应 JSON 顶层不是对象（Action={action}）"
                    )
                return parsed

        except urllib.error.HTTPError as e:  # HTTP 层错误
            status = e.code
            # 读出错误体但不打印，以避免泄漏敏感信息
            try:
                _ = e.read()
            except Exception:  # noqa: BLE001
                _ = b""

            if status in (401, 403):
                raise AuthError(f"Gateway 鉴权失败（HTTP {status}）") from e

            if status == 429 or 500 <= status < 600:
                # 限流或服务器错误：退避重试
                if attempt < MAX_RETRIES - 1:
                    delay = BACKOFF_BASE_SECONDS * (2 ** attempt)
                    print(
                        f"[WARN][gateway] Action={action} HTTP {status}，" f"{delay:.2f}s 后重试..."
                    )
                    time.sleep(delay)
                    continue
                raise NetworkError(
                    f"Gateway 请求失败（HTTP {status}，已重试 {MAX_RETRIES} 次）"
                ) from e

            # 其它 HTTP 视为一次性错误，不再重试
            raise NetworkError(f"Gateway 请求异常（HTTP {status}）") from e

        except urllib.error.URLError as e:
            # 网络错误（DNS/连接超时等）
            if attempt < MAX_RETRIES - 1:
                delay = BACKOFF_BASE_SECONDS * (2 ** attempt)
                print(
                    f"[WARN][gateway] Action={action} 网络错误 {e.reason}，" f"{delay:.2f}s 后重试..."
                )
                time.sleep(delay)
                continue
            raise NetworkError(
                f"Gateway 网络错误（Action={action}）：{e.reason}"
            ) from e

    # 理论上不会到达这里
    raise NetworkError(f"Gateway 请求失败（Action={action}）：重试耗尽")


# ------------------------ 统一封装的三个接口 ------------------------


def list_custom_subs_task(
    *,
    api_base: str,
    api_key: str,
    Status: int = 2,
    TaskName: Optional[str] = None,
    PageNum: int = 1,
    PageSize: int = 30,
) -> Dict[str, Any]:
    """调用 ListCustomSubsTask，返回统一结构：

    {"InsightSaasTaskList": [...], "Total": int}
    """

    url = _build_url(api_base, "ListCustomSubsTask")

    payload: Dict[str, Any] = {
        "Status": Status,
        "PageNum": PageNum,
        "PageSize": PageSize,
    }
    if TaskName:
        payload["TaskName"] = TaskName

    raw = _do_request(method="GET", url=url, api_key=api_key, payload=payload, action="ListCustomSubsTask")

    result = raw.get("Result") or {}
    if not isinstance(result, dict):
        raise NetworkError("ListCustomSubsTask 响应缺少 Result 字段或类型错误")

    tasks = result.get("InsightSaasTaskList") or []
    total_raw = result.get("Total", 0)
    try:
        total = int(total_raw)
    except Exception:  # noqa: BLE001
        total = 0

    # 业务为空：返回空列表和 0 即可
    return {
        "InsightSaasTaskList": tasks,
        "Total": total,
    }


def pull_post(
    *,
    api_base: str,
    api_key: str,
    TaskID: int,
    StartTime: str,
    EndTime: str,
    Size: int = 50,
    PageToken: Optional[str] = None,
) -> Dict[str, Any]:
    """调用 PullPost，返回统一结构：

    {"ItemDocs": [...], "HasMore": bool, "NextPageToken": str | None}
    """

    url = _build_url(api_base, "PullPost")

    payload: Dict[str, Any] = {
        "TaskID": TaskID,
        "StartTime": StartTime,
        "EndTime": EndTime,
        "Size": Size,
    }
    if PageToken:
        payload["PageToken"] = PageToken

    raw = _do_request(method="POST", url=url, api_key=api_key, payload=payload, action="PullPost")

    result = raw.get("Result") or {}
    if not isinstance(result, dict):
        raise NetworkError("PullPost 响应缺少 Result 字段或类型错误")

    docs = result.get("ItemDocs") or []
    has_more = bool(result.get("HasMore", False))
    next_token = result.get("NextPageToken")

    return {
        "ItemDocs": docs,
        "HasMore": has_more,
        "NextPageToken": next_token,
    }


def query_clue_info(
    *,
    api_base: str,
    api_key: str,
    StartTime: str,
    EndTime: str,
    MaxResults: int = 10,
    NextToken: Optional[str] = None,
) -> Dict[str, Any]:
    """调用 QueryClueInfo，返回统一结构：

    {"ClueList": [...], "NextToken": str | None, "ResultCnt": int}

    其中每个元素的 ClueText 字段若为 JSON 字符串，将被解析为对象。
    """

    url = _build_url(api_base, "QueryClueInfo")

    payload: Dict[str, Any] = {
        "StartTime": StartTime,
        "EndTime": EndTime,
        "MaxResults": MaxResults,
    }
    if NextToken:
        payload["NextToken"] = NextToken

    raw = _do_request(method="GET", url=url, api_key=api_key, payload=payload, action="QueryClueInfo")

    result = raw.get("Result") or {}
    if not isinstance(result, dict):
        raise NetworkError("QueryClueInfo 响应缺少 Result 字段或类型错误")

    clues = result.get("ClueList") or []
    parsed_clues = []
    for item in clues:
        if isinstance(item, dict):
            parsed = dict(item)
        else:
            # 非 dict 的异常数据直接跳过
            continue

        raw_text = parsed.get("ClueText")
        if isinstance(raw_text, str) and raw_text:
            try:
                parsed["ClueText"] = json.loads(raw_text)
            except Exception:  # noqa: BLE001
                # 保留原始字符串，避免因单条解析失败影响整体
                pass

        parsed_clues.append(parsed)

    result_cnt_raw = result.get("ResultCnt")
    try:
        result_cnt = int(result_cnt_raw) if result_cnt_raw is not None else len(parsed_clues)
    except Exception:  # noqa: BLE001
        result_cnt = len(parsed_clues)

    next_token = result.get("NextToken")

    return {
        "ClueList": parsed_clues,
        "NextToken": next_token,
        "ResultCnt": result_cnt,
    }


__all__ = [
    "list_custom_subs_task",
    "pull_post",
    "query_clue_info",
]
