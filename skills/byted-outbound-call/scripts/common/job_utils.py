# Copyright (c) 2025 Beijing Volcano Engine Technology Co., Ltd. and/or its affiliates. 
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
import json
import sys
import os
from typing import Any, Dict, Optional, Tuple, Callable

from .logger_config import get_file_logger
from .api_response import parse_api_response
from . import http_request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from schemas.service.job_status import JobStatus
from schemas.service.call_result import CallResult


def query_job_status_once(
        job_id: str,
        file_logger: Any,
) -> Tuple[Optional[int], Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """查询 Job 状态一次。

    返回：(status, status_result, error_info)
    - status: Job 状态值。
    - status_result: QueryJobStatus 接口的 Result 字段内容。
    - error_info: 异常时为 {code, message}，否则为 None。
    """

    response = http_request.query_job_status(job_id)
    file_logger.info("QueryJobStatus 响应: %s", json.dumps(response, ensure_ascii=False))

    is_ok, error_code, error_message, result, _ = parse_api_response(response)

    if not is_ok:
        file_logger.error(
            "QueryJobStatus 接口异常，Error.Code=%s, Error.Message=%s",
            error_code,
            error_message,
        )
        return None, None, {"code": error_code, "message": error_message}

    if not isinstance(result, dict) or "Status" not in result:
        file_logger.error("QueryJobStatus 返回成功但 Result 中缺少 Status 字段：%s", result)
        return None, None, {
            "code": "MissingStatus",
            "message": "Result 中未包含 Status 字段",
        }

    status = result.get("Status")
    file_logger.info("当前 Job 状态 Status=%s", status)

    return status, result, None


def query_job_detail(
        job_id: str,
        file_logger: Any,
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """查询 Job 详情。

    返回：(detail_result, error_info)
    - detail_result: 正常时为 Result 字段内容（详情数据）。
    - error_info: 异常时为 {code, message}，否则为 None。
    """

    response = http_request.query_job_detail(job_id)
    file_logger.info("QueryJobDetail 响应: %s", json.dumps(response, ensure_ascii=False))

    is_ok, error_code, error_message, result, _ = parse_api_response(response)

    if not is_ok:
        file_logger.error(
            "QueryJobDetail 接口异常，Error.Code=%s, Error.Message=%s",
            error_code,
            error_message,
        )
        return None, {"code": error_code, "message": error_message}

    if not isinstance(result, dict):
        file_logger.error("QueryJobDetail 返回成功但 Result 非对象类型：%s", result)
        return None, {
            "code": "InvalidResult",
            "message": "Result 不是 JSON 对象",
        }

    return result, None


def log_execution_start(
        file_logger: Any,
        program_name: str,
        start_time: Any,
        extra_info: Optional[str] = None,
) -> None:
    """记录程序开始执行日志。"""
    file_logger.info("=" * 60)
    file_logger.info("%s 程序开始执行 - %s", program_name, start_time.strftime("%Y-%m-%d %H:%M:%S"))
    if extra_info:
        file_logger.info(extra_info)
    file_logger.info("=" * 60)


def log_execution_end(
        file_logger: Any,
        console_logger: Any,
        program_name: str,
        start_time: Any,
        end_time: Any,
        error_info: Optional[Dict[str, Any]] = None,
        loggers_info_func: Optional[Callable] = None,
        loggers_error_func: Optional[Callable] = None,
) -> None:
    """记录程序结束执行日志。"""
    duration = (end_time - start_time).total_seconds()
    file_logger.info("=" * 60)
    if error_info is None:
        if loggers_info_func:
            loggers_info_func([console_logger, file_logger],
                "%s 程序执行成功 - %s",
                program_name,
                end_time.strftime("%Y-%m-%d %H:%M:%S"),
            )
    else:
        if loggers_error_func:
            loggers_error_func([console_logger, file_logger],
                "%s 程序执行结束（存在异常） - %s",
                program_name,
                end_time.strftime("%Y-%m-%d %H:%M:%S"),
            )
            loggers_error_func([console_logger, file_logger], "错误信息: %s", error_info)
    file_logger.info("执行耗时: %.2f 秒", duration)
    file_logger.info("=" * 60)


def format_job_detail(
        job_id: str,
        status: Optional[int],
        job_detail: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """整理 JobDetail 信息，包括任务状态、接通情况和 summary。

    返回：整理后的字典，包含以下字段：
    - JobId: 任务ID
    - StatusDescription: 状态描述
    - CallResult: 接通结果值（仅当状态为 JobFinished 时）
    - CallResultDescription: 接通结果描述（仅当状态为 JobFinished 时）
    - Summary: 信息汇总（仅当接通且有摘要时）
    """

    result: Dict[str, Any] = {
        "JobId": job_id,
    }

    if status is not None:
        status_desc = JobStatus.get_job_status_description(status)
        result["StatusDescription"] = status_desc

    if status == JobStatus.JobFinished and job_detail is not None:
        call_result = job_detail.get("CallResult")
        if call_result is not None:
            result["CallResult"] = call_result
            call_result_desc = CallResult.get_call_result_description(call_result)
            result["CallResultDescription"] = call_result_desc

            if call_result == CallResult.Connected:
                summary = job_detail.get("Summary")
                if summary is not None:
                    result["Summary"] = summary

    return result
