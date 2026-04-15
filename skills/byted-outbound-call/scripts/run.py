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
import sys

from common.logger_config import get_file_logger
from common.utils import print_openclaw_session_env
from submit_job import submit
from wait_job_result import wait_job

def main() -> None:

    parser = argparse.ArgumentParser(description="提交外呼 Job")
    parser.add_argument(
        "--request-body",
        type=str,
        default="",
        help="完整的请求体 JSON 字符串，若提供则优先使用并忽略其他参数",
    )

    args = parser.parse_args()
    job_id = submit(args.request_body)
    if job_id is None:
        logger.error("SubmitJob 调用失败，未返回 JobId")
        sys.exit(1)
    else:
        logger.info("SubmitJob 调用成功，JobId=%s", job_id)

    logger.info("wait_job 开始调用，JobId=%s", job_id)
    wait_job(job_id)

if __name__ == "__main__":
    logger = get_file_logger("run")
    print_openclaw_session_env(logger)

    logger.info("开始提交外呼任务，run.py")

    main()