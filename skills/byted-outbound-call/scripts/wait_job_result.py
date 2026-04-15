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
import argparse
import datetime
import json
import sys
import time
from typing import Any, Dict, Optional, Tuple

from common.logger_config import get_file_logger, get_console_logger, loggers_info, loggers_error, flush_loggers
from common.api_response import parse_api_response
from common import http_request
from common import job_utils
from message.notify import send_message, validate_env_variables

file_logger = get_file_logger("wait_job_result")
console_logger = get_console_logger()

def poll_job_status(
        job_id: str,
        interval_sec: int,
        max_polls: int,
) -> Tuple[Optional[int], Optional[Dict[str, Any]]]:
    """轮询 QueryJobStatus，返回最终状态及错误信息。

    返回：(final_status, error_info)
    - final_status: 最后一次获取到的 Status 值（可能为 None）。
    - error_info: 若发生异常或达到退出条件，返回 {code, message}，否则为 None。
    """

    final_status: Optional[int] = None
    error_info: Optional[Dict[str, Any]] = None

    for attempt in range(1, max_polls + 1):
        
        file_logger.info("第 %d 次轮询 Job 状态，JobId=%s", attempt, job_id)

        status, _, error_info = job_utils.query_job_status_once(job_id, file_logger)
        if error_info is not None:
            break

        final_status = status

        if status == -1:
            # 业务定义的异常状态
            file_logger.error("Job 状态为 -1，视为执行异常，停止轮询。")
            error_info = {
                "code": "-1",
                "message": "Job 执行异常（Status=-1）",
            }
            break

        if status == 4:
            # JobFinished，轮询成功结束
            file_logger.info("Job 状态为 4（JobFinished），轮询结束。")
            break

        if status in (1, 2, 3):
            # Waiting / Running / CallFinished，继续轮询
            if attempt >= max_polls:
                file_logger.warning(
                    "已达到最大轮询次数 %d，Job 仍未结束，停止轮询。", max_polls
                )
                error_info = {
                    "code": "MaxPollsExceeded",
                    "message": f"在最大轮询次数 {max_polls} 内未达到结束状态",
                }
                break

            file_logger.info(
                "Job 未结束，%d 秒后进行下一次轮询……", interval_sec
            )
            time.sleep(interval_sec)
            continue

        # 未知状态，视为异常
        file_logger.error("收到未知 Job 状态: %s，停止轮询。", status)
        error_info = {
            "code": "UnknownStatus",
            "message": f"未知的 Job 状态: {status}",
        }
        break

    return final_status, error_info


def main() -> None:
    parser = argparse.ArgumentParser(description="轮询等待 Job 结果并查询详情")
    parser.add_argument(
        "--job_id",
        "--JobId",
        type=str,
        required=True,
        help="必填，需要轮询的 JobId",
    )
    parser.add_argument(
        "--interval-sec",
        type=int,
        default=30,
        help="轮询间隔秒数，默认 30",
    )
    parser.add_argument(
        "--max-polls",
        type=int,
        default=120,
        help="最大轮询次数，默认 120，2个小时",
    )

    args = parser.parse_args()
    # 等待10秒，确保云端数据同步完成
    time.sleep(10)
    wait_job(args.job_id, args.interval_sec, args.max_polls)


def wait_job(job_id: str, interval_sec: int=30, max_polls: int=120) -> None:
    start_time = datetime.datetime.now()
    job_utils.log_execution_start(
        file_logger,
        "wait_job_result",
        start_time,
        f"轮询配置：interval_sec={interval_sec}, max_polls={max_polls}"
    )

    final_status: Optional[int] = None
    job_detail: Optional[Dict[str, Any]] = None
    error_info: Optional[Dict[str, Any]] = None

    try:
        final_status, error_info = poll_job_status(job_id, interval_sec, max_polls)

        if error_info is not None:
            file_logger.error("轮询 Job 状态失败或异常结束: %s", error_info)
        else:
            file_logger.info("轮询 Job 状态结束，最终 Status=%s", final_status)

        if error_info is None and final_status == 4:
            job_detail, detail_error = job_utils.query_job_detail(job_id, file_logger)

            if detail_error is not None:
                file_logger.error("查询 Job 详情失败: %s", detail_error)
                error_info = detail_error
            else:
                assert job_detail is not None
                pretty_detail = json.dumps(job_detail, ensure_ascii=False, indent=2)
                file_logger.info("Job 详情: %s", pretty_detail)
        elif error_info is None and final_status != 4:
            file_logger.warning(
                "轮询结束但 Job 未进入结束状态，最终 Status=%s", final_status
            )
            error_info = {
                "code": "UnexpectedFinalStatus",
                "message": f"轮询结束但 Job 最终状态为 {final_status}",
            }

    except Exception as exc:
        loggers_error([console_logger, file_logger], "wait_job_result 程序执行过程中发生异常: %s", exc)
        error_info = {"exception": str(exc)}
        flush_loggers()

    finally:
        try:
            send_message(job_id, final_status, job_detail, error_info)
        except Exception as exc:
            loggers_error([console_logger, file_logger], "send_message 调用异常: %s", exc)

        end_time = datetime.datetime.now()
        job_utils.log_execution_end(
            file_logger,
            console_logger,
            "wait_job_result",
            start_time,
            end_time,
            error_info,
            loggers_info,
            loggers_error
        )
    flush_loggers()
    
    sys.exit(0 if error_info is None else 1)

if __name__ == "__main__":
    if not validate_env_variables(file_logger):
        file_logger.error("环境变量校验失败，程序退出")
        sys.exit(1)

    main()