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
"""市场洞察 Agent 统一客户端入口。

对外暴露三个函数：
- list_custom_subs_task
- pull_post
- query_clue_info

内部通过 auth_resolver 自动选择 Gateway 或 SDK Provider：
- 默认优先 Gateway，按会话状态实现粘性；
- 在需要 SDK 时自动安装依赖；
- 统一返回结构；
- 提供 CLI 入口便于本地调试。
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, Optional, Set

from auth_resolver import (
    AuthError,
    NetworkError,
    MissingCredentialsError,
    MINIMAL_ASK_HINT,
    get_provider,
    mark_degraded,
    record_success,
)


# ------------------------ 内部调度封装 ------------------------


def _invoke_with_fallback(method_name: str, **params: Any) -> Dict[str, Any]:
    """统一的调度封装：

    - 首次按照会话粘性 + 默认优先级选择 Provider；
    - 若发生 AuthError，则将当前 Provider 标记为降级并尝试另一条链路；
    - 若所有 Provider 均不可用，则抛出 MissingCredentialsError，交由 Agent 层进行最小化询问；
    - NetworkError 直接向上抛出（内部已做退避重试）。
    """

    exclude: Set[str] = set()
    last_error: Optional[Exception] = None

    # 最多尝试两条 Provider 链路（gateway + sdk）
    for _ in range(2):
        provider = get_provider(exclude)
        try:
            func = getattr(provider, method_name)
        except AttributeError as exc:  # noqa: BLE001
            raise RuntimeError(
                f"Provider {provider.name} 不支持方法 {method_name}"
            ) from exc

        try:
            result = func(**params)
            record_success(provider.name)
            return result
        except AuthError as exc:
            # 鉴权错误：标记当前 Provider 降级，尝试其他链路
            mark_degraded(provider.name, exc)
            exclude.add(provider.name)
            last_error = exc
        except NetworkError as exc:
            # 网络错误：不切换链路，直接抛出
            last_error = exc
            raise

    # 所有 Provider 均不可用：触发最小化询问
    if isinstance(last_error, AuthError) or last_error is None:
        raise MissingCredentialsError()

    # 兜底：返回最后一个错误
    raise last_error


# ------------------------ 对外函数（Python 调用） ------------------------


def list_custom_subs_task(
    *,
    Status: int = 2,
    TaskName: Optional[str] = None,
    PageNum: int = 1,
    PageSize: int = 30,
) -> Dict[str, Any]:
    """查询订阅/监控任务列表（ListCustomSubsTask）。

    返回结构：{"InsightSaasTaskList": [...], "Total": int}
    """

    return _invoke_with_fallback(
        "list_custom_subs_task",
        Status=Status,
        TaskName=TaskName,
        PageNum=PageNum,
        PageSize=PageSize,
    )


def pull_post(
    *,
    TaskID: int,
    StartTime: str,
    EndTime: str,
    Size: int = 50,
    PageToken: Optional[str] = None,
) -> Dict[str, Any]:
    """拉取监测任务的 AI 精筛数据（PullPost）。

    返回结构：{"ItemDocs": [...], "HasMore": bool, "NextPageToken": str | None}
    """

    return _invoke_with_fallback(
        "pull_post",
        TaskID=TaskID,
        StartTime=StartTime,
        EndTime=EndTime,
        Size=Size,
        PageToken=PageToken,
    )


def query_clue_info(
    *,
    StartTime: str,
    EndTime: str,
    MaxResults: int = 10,
    NextToken: Optional[str] = None,
) -> Dict[str, Any]:
    """查询商机信息（QueryClueInfo）。

    返回结构：{"ClueList": [...], "NextToken": str | None, "ResultCnt": int}
    其中 ClueText 字段若存在，将被解析为结构化对象。
    """

    return _invoke_with_fallback(
        "query_clue_info",
        StartTime=StartTime,
        EndTime=EndTime,
        MaxResults=MaxResults,
        NextToken=NextToken,
    )


# ------------------------ CLI 入口 ------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="市场洞察 Agent 统一客户端（Gateway + SDK 无感切换）",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # list_custom_subs_task
    p_list = subparsers.add_parser(
        "list_custom_subs_task",
        help="查询订阅/监控任务列表 (ListCustomSubsTask)",
    )
    p_list.add_argument("--Status", type=int, default=2, choices=[1, 2], help="任务状态过滤：1=运行中, 2=全部（默认 2）")
    p_list.add_argument("--TaskName", type=str, default=None, help="按任务名称模糊搜索（可选）")
    p_list.add_argument("--PageNum", type=int, default=1, help="页码，从 1 开始（默认 1）")
    p_list.add_argument("--PageSize", type=int, default=30, help="每页条数（默认 30）")

    # pull_post
    p_pull = subparsers.add_parser(
        "pull_post",
        help="拉取监测任务 AI 精筛数据 (PullPost)",
    )
    p_pull.add_argument("--TaskID", type=int, required=True, help="监测任务 ID")
    p_pull.add_argument("--StartTime", type=str, required=True, help='数据起始时间，格式 "YYYY-MM-DD HH:MM:SS"')
    p_pull.add_argument("--EndTime", type=str, required=True, help='数据结束时间，格式 "YYYY-MM-DD HH:MM:SS"')
    p_pull.add_argument("--Size", type=int, default=50, help="每页条数（默认 50）")
    p_pull.add_argument("--PageToken", type=str, default=None, help="分页游标（可选）")

    # query_clue_info
    p_clue = subparsers.add_parser(
        "query_clue_info",
        help="查询商机信息 (QueryClueInfo)",
    )
    p_clue.add_argument("--StartTime", type=str, required=True, help='数据起始时间，格式 "YYYY-MM-DD HH:MM:SS"')
    p_clue.add_argument("--EndTime", type=str, required=True, help='数据结束时间，格式 "YYYY-MM-DD HH:MM:SS"')
    p_clue.add_argument("--MaxResults", type=int, default=10, help="每页最大返回条数（默认 10）")
    p_clue.add_argument("--NextToken", type=str, default=None, help="分页游标（可选）")

    return parser


def _run_cli(argv: Optional[list[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "list_custom_subs_task":
            result = list_custom_subs_task(
                Status=args.Status,
                TaskName=args.TaskName,
                PageNum=args.PageNum,
                PageSize=args.PageSize,
            )
        elif args.command == "pull_post":
            result = pull_post(
                TaskID=args.TaskID,
                StartTime=args.StartTime,
                EndTime=args.EndTime,
                Size=args.Size,
                PageToken=args.PageToken,
            )
        elif args.command == "query_clue_info":
            result = query_clue_info(
                StartTime=args.StartTime,
                EndTime=args.EndTime,
                MaxResults=args.MaxResults,
                NextToken=args.NextToken,
            )
        else:  # 理论上不会触达
            parser.print_help()
            return 1

        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    except MissingCredentialsError as exc:
        # 提示 Agent 层应进行最小化询问
        print(str(exc or MINIMAL_ASK_HINT), file=sys.stderr)
        return 2
    except AuthError as exc:
        print(f"鉴权错误：{exc}", file=sys.stderr)
        return 3
    except NetworkError as exc:
        print(f"网络/网关错误：{exc}", file=sys.stderr)
        return 4
    except KeyboardInterrupt:
        print("已中断", file=sys.stderr)
        return 130


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_run_cli())
