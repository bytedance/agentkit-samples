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
from typing import Any, Dict, Optional

from common.logger_config import get_file_logger, get_console_logger, loggers_info, loggers_error, loggers_exception, flush_loggers
from common import job_utils

file_logger = get_file_logger("query_job")
console_logger = get_console_logger()


def main() -> None:
    parser = argparse.ArgumentParser(description="查询 Job 状态和详情")
    parser.add_argument(
        "--job_id",
        "--JobId",
        type=str,
        required=True,
        help="必填，需要查询的 JobId",
    )

    args = parser.parse_args()
    query_job(args.job_id)


def query_job(job_id: str) -> None:
    start_time = datetime.datetime.now()
    job_utils.log_execution_start(file_logger, "query_job", start_time)

    status: Optional[int] = None
    status_result: Optional[Dict[str, Any]] = None
    job_detail: Optional[Dict[str, Any]] = None
    error_info: Optional[Dict[str, Any]] = None

    try:
        status, status_result, error_info = job_utils.query_job_status_once(job_id, file_logger)

        if error_info is not None:
            file_logger.error("查询 Job 状态失败: %s", error_info)
            loggers_error([console_logger, file_logger],
                json.dumps(
                    {
                        "ErrorCode": error_info.get("code"),
                        "ErrorMessage": error_info.get("message"),
                    },
                    ensure_ascii=False,
                )
            )
        else:
            if status == 4:
                file_logger.info("Job 状态为 4（JobFinished），继续查询详情")
                job_detail, detail_error = job_utils.query_job_detail(job_id, file_logger)

                if detail_error is not None:
                    file_logger.error("查询 Job 详情失败: %s", detail_error)
                    error_info = detail_error
                    loggers_error([console_logger, file_logger],
                        json.dumps(
                            {
                                "ErrorCode": detail_error.get("code"),
                                "ErrorMessage": detail_error.get("message"),
                            },
                            ensure_ascii=False,
                        )
                    )

            formatted_result = job_utils.format_job_detail(job_id, status, job_detail)
            loggers_info([console_logger, file_logger], json.dumps(formatted_result, ensure_ascii=False))

    except Exception as exc:
        loggers_exception([console_logger, file_logger], exc)
        error_info = {"exception": str(exc)}
        flush_loggers()

    finally:
        end_time = datetime.datetime.now()
        job_utils.log_execution_end(
            file_logger,
            console_logger,
            "query_job",
            start_time,
            end_time,
            error_info,
            loggers_info,
            loggers_error
        )
    flush_loggers()

    sys.exit(0 if error_info is None else 1)


if __name__ == "__main__":
    main()
