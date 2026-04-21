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
"""SDK Provider 实现。

通过官方 `volcengine-python-sdk` 调用市场洞察三大接口：
- ListCustomSubsTask
- PullPost
- QueryClueInfo

本模块：
- 依赖 `volcengine-python-sdk>=5.0.22`；
- 不负责自动安装 SDK（由 auth_resolver.ensure_sdk_available 统一处理）；
- 将统一 PascalCase 参数映射到 SDK 的 snake_case 请求体；
- 返回与 Gateway Provider 一致的顶层结构；
- 对 QueryClueInfo 的 ClueText 做 json.loads 解析，并提供 `ClueText` 字段。
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from auth_resolver import AuthError, NetworkError


def _init_sdk_config(access_key_id: str, secret_access_key: str, region: str) -> None:
    """初始化 SDK 全局配置（每次调用按给定 AK/SK/Region 覆盖）。"""

    try:
        import volcenginesdkcore  # type: ignore[import]
    except ImportError as exc:  # noqa: BLE001
        raise NetworkError(f"导入 volcenginesdkcore 失败: {exc}") from exc

    configuration = volcenginesdkcore.Configuration()
    configuration.ak = access_key_id
    configuration.sk = secret_access_key
    configuration.region = region

    # 重试与超时配置，与便携版示例保持一致
    configuration.auto_retry = True
    configuration.num_max_retries = 5
    configuration.retry_error_codes = {"Throttling", "RequestLimitExceeded"}
    configuration.connect_timeout = 10
    configuration.read_timeout = 30

    volcenginesdkcore.Configuration.set_default(configuration)


def _get_insight_api():
    try:
        from volcenginesdkinsight import INSIGHTApi  # type: ignore[import]
    except ImportError as exc:  # noqa: BLE001
        raise NetworkError(f"导入 volcenginesdkinsight 失败: {exc}") from exc

    return INSIGHTApi()


def _model_to_plain(value: Any) -> Any:
    """将 SDK 返回的模型对象递归转换为基础类型（dict/list/标量）。"""

    if isinstance(value, list):
        return [_model_to_plain(v) for v in value]
    if isinstance(value, dict):
        return {k: _model_to_plain(v) for k, v in value.items()}

    # 优先使用 SDK 模型自带的 to_dict
    if hasattr(value, "to_dict") and callable(getattr(value, "to_dict")):
        try:
            return _model_to_plain(value.to_dict())
        except Exception:  # noqa: BLE001
            return str(value)

    # 回退到 __dict__
    if hasattr(value, "__dict__") and not isinstance(value, type):
        try:
            return _model_to_plain(vars(value))
        except Exception:  # noqa: BLE001
            return str(value)

    return value


def _handle_api_exception(action: str, exc: Exception) -> None:
    """统一将 SDK 异常转换为 AuthError 或 NetworkError。"""

    try:
        from volcenginesdkcore.rest import ApiException  # type: ignore[import]
    except Exception:  # noqa: BLE001
        # 未能导入 ApiException，则一律视为网络错误
        raise NetworkError(f"{action} 调用异常: {exc}") from exc

    if isinstance(exc, ApiException):
        status = getattr(exc, "status", None)
        if status in (401, 403):
            raise AuthError(f"SDK {action} 鉴权失败（HTTP {status}）") from exc
        if status == 429 or (isinstance(status, int) and status >= 500):
            raise NetworkError(f"SDK {action} 请求失败（HTTP {status}）") from exc
        raise NetworkError(f"SDK {action} 调用失败: {exc}") from exc

    raise NetworkError(f"SDK {action} 调用异常: {exc}") from exc


# ------------------------ 统一封装的三个接口 ------------------------


def list_custom_subs_task(
    *,
    access_key_id: str,
    secret_access_key: str,
    region: str,
    Status: int = 2,
    TaskName: Optional[str] = None,
    PageNum: int = 1,
    PageSize: int = 30,
) -> Dict[str, Any]:
    """通过 SDK 调用 ListCustomSubsTask，返回统一结构：

    {"InsightSaasTaskList": [...], "Total": int}
    """

    _init_sdk_config(access_key_id, secret_access_key, region)

    try:
        from volcenginesdkinsight import (  # type: ignore[import]
            INSIGHTApi,
            ListCustomSubsTaskRequest,
        )
    except ImportError as exc:  # noqa: BLE001
        raise NetworkError(f"导入 volcenginesdkinsight 失败: {exc}") from exc

    api = INSIGHTApi()

    # SDK 使用 snake_case 参数
    request = ListCustomSubsTaskRequest(
        status=Status,
        page_num=PageNum,
        page_size=PageSize,
    )
    if TaskName:
        request.task_name = TaskName

    try:
        response = api.list_custom_subs_task(request)
    except Exception as exc:  # noqa: BLE001
        _handle_api_exception("ListCustomSubsTask", exc)
        raise  # for type checker

    tasks = getattr(response, "insight_saas_task_list", None) or []
    total_raw = getattr(response, "total", 0)
    try:
        total = int(total_raw)
    except Exception:  # noqa: BLE001
        total = 0

    tasks_plain = _model_to_plain(tasks)

    return {
        "InsightSaasTaskList": tasks_plain,
        "Total": total,
    }


def pull_post(
    *,
    access_key_id: str,
    secret_access_key: str,
    region: str,
    TaskID: int,
    StartTime: str,
    EndTime: str,
    Size: int = 50,
    PageToken: Optional[str] = None,
) -> Dict[str, Any]:
    """通过 SDK 调用 PullPost，返回统一结构：

    {"ItemDocs": [...], "HasMore": bool, "NextPageToken": str | None}
    """

    _init_sdk_config(access_key_id, secret_access_key, region)

    try:
        from volcenginesdkinsight import (  # type: ignore[import]
            INSIGHTApi,
            PullPostRequest,
        )
    except ImportError as exc:  # noqa: BLE001
        raise NetworkError(f"导入 volcenginesdkinsight 失败: {exc}") from exc

    api = INSIGHTApi()

    request = PullPostRequest(
        task_id=TaskID,
        start_time=StartTime,
        end_time=EndTime,
        size=Size,
    )
    if PageToken:
        request.page_token = PageToken

    try:
        response = api.pull_post(request)
    except Exception as exc:  # noqa: BLE001
        _handle_api_exception("PullPost", exc)
        raise

    docs = getattr(response, "item_docs", None) or []
    has_more = bool(getattr(response, "has_more", False))
    next_page_token = getattr(response, "next_page_token", None)

    docs_plain = _model_to_plain(docs)

    return {
        "ItemDocs": docs_plain,
        "HasMore": has_more,
        "NextPageToken": next_page_token,
    }


def query_clue_info(
    *,
    access_key_id: str,
    secret_access_key: str,
    region: str,
    StartTime: str,
    EndTime: str,
    MaxResults: int = 10,
    NextToken: Optional[str] = None,
) -> Dict[str, Any]:
    """通过 SDK 调用 QueryClueInfo，返回统一结构：

    {"ClueList": [...], "NextToken": str | None, "ResultCnt": int}

    其中每个元素的 ClueText 字段为解析后的对象（若解析成功），并保留原始字段。"""

    _init_sdk_config(access_key_id, secret_access_key, region)

    try:
        from volcenginesdkinsight import (  # type: ignore[import]
            INSIGHTApi,
            QueryClueInfoRequest,
        )
    except ImportError as exc:  # noqa: BLE001
        raise NetworkError(f"导入 volcenginesdkinsight 失败: {exc}") from exc

    api = INSIGHTApi()

    request = QueryClueInfoRequest(
        start_time=StartTime,
        end_time=EndTime,
    )
    if MaxResults:
        request.max_results = MaxResults
    if NextToken:
        request.next_token = NextToken

    try:
        response = api.query_clue_info(request)
    except Exception as exc:  # noqa: BLE001
        _handle_api_exception("QueryClueInfo", exc)
        raise

    clues = getattr(response, "clue_list", None) or []
    next_token = getattr(response, "next_token", None)
    result_cnt_raw = getattr(response, "result_cnt", None)

    clues_plain = _model_to_plain(clues)  # 期望为 List[dict]
    parsed_clues = []
    for item in clues_plain:
        if not isinstance(item, dict):
            continue
        parsed = dict(item)
        raw_text = parsed.get("ClueText") or parsed.get("clue_text")
        if isinstance(raw_text, str) and raw_text:
            try:
                import json

                parsed["ClueText"] = json.loads(raw_text)
            except Exception:  # noqa: BLE001
                # 保留原始字符串
                parsed.setdefault("ClueText", raw_text)
        parsed_clues.append(parsed)

    try:
        result_cnt = int(result_cnt_raw) if result_cnt_raw is not None else len(parsed_clues)
    except Exception:  # noqa: BLE001
        result_cnt = len(parsed_clues)

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
