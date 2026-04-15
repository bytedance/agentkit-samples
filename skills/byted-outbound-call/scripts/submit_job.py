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
import sys
from typing import Any, Dict

from common.logger_config import get_file_logger, get_console_logger, loggers_info, loggers_error, loggers_exception, flush_loggers
from common.api_response import parse_api_response
import common.http_request as http_request
from common.utils import print_openclaw_session_env
from schemas.script.submit_job_schema import *
from schemas.service.submit_job_data import *
import message.notify as notify
import subprocess
import time
import os
import json


file_logger = get_file_logger("submit_job")
console_logger = get_console_logger("submit_job_console")
current_dir = os.path.dirname(os.path.abspath(__file__))



def parse_request_body(request_body: str) -> Dict[str, Any]:
    """解析 --request-body 参数中的 JSON 字符串。"""
    if not request_body:
        return {}

    try:
        parsed_data: Dict[str, Any] = json.loads(request_body)
        if not isinstance(parsed_data, dict):
            raise ValueError("request_body 必须是 JSON 对象（顶层为 {}）")
        return parsed_data
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON 解析失败: {e}") from e


def build_submit_job_body_from_args(args: argparse.Namespace) -> Dict[str, Any]:
    """根据命令行参数构造 SubmitJob 的请求体。"""
    if not args.phone:
        raise ValueError("当未提供 --request-body 时，--phone 为必填参数")

    body: Dict[str, Any] = {"Phone": args.phone}

    if args.script_name:
        body["ScriptName"] = args.script_name

    if args.params:
        try:
            variable_params = json.loads(args.params)
        except json.JSONDecodeError as e:
            raise ValueError(f"--params 解析失败，应为 JSON 字符串: {e}") from e

        if not isinstance(variable_params, dict):
            raise ValueError("--params 必须为 JSON 对象（键值对）")

        body["VariableParams"] = variable_params

    return body

def _convert_submit_outer_to_request(submit_job_outer: SubmitJobOuter) -> SubmitJobRequest:
    """将 SubmitJobOuter 对象转换为 SubmitJobRequest 对象。"""

    # submit_job_outer中的params 是 SubmitJobParams 类型，需要转换为 dict
    variable_params = submit_job_outer.params.__dict__

    return SubmitJobRequest(
        Phone=variable_params['shop_phone_number'],
        ScriptName=submit_job_outer.script_id,
        VariableParams=variable_params,
    )

def call_submit_job_api(
        request_body: Dict[str, Any],
) -> Dict[str, Any]:
    """调用 SubmitJob 接口。"""

    # 从请求体创建 SubmitJobOuter 对象
    try:
        submit_job_outer = SubmitJobOuter.from_json(request_body)
    except ValueError as e:
        file_logger.error("请求体转换为 OutboundJob 对象失败: %s", e)
        raise

    # 验证必填字段是否完整
    is_valid, error_msg = submit_job_outer.validate()
    if not is_valid:
        file_logger.error("外呼任务数据验证失败: %s", error_msg)
        raise ValueError(error_msg)

    # 将 SubmitJobOuter 对象转换为 SubmitJobRequest 对象
    submit_job_request = _convert_submit_outer_to_request(submit_job_outer)

    response = http_request.run_submit_job(submit_job_request)
    return response


def main() -> None:
    parser = argparse.ArgumentParser(description="提交外呼 Job")
    parser.add_argument(
        "--request-body",
        type=str,
        default="",
        help="完整的请求体 JSON 字符串，若提供则优先使用并忽略其他参数",
    )
    parser.add_argument(
        "--phone",
        type=str,
        help="必填，需呼叫的电话号码（当未提供 --request-body 时）",
    )
    parser.add_argument(
        "--script-name",
        type=str,
        help="可选，剧本名称 ScriptName",
    )
    parser.add_argument(
        "--params",
        type=str,
        help="可选，VariableParams，JSON 字符串，形如 '{\"key\": \"value\"}'",
    )

    args = parser.parse_args()
    submit(args.request_body)


def submit(request_body: Dict[str, Any]) -> str:
    start_time = datetime.datetime.now()
    file_logger.info("=" * 60)
    file_logger.info("submit_job 程序开始执行 - %s", start_time.strftime("%Y-%m-%d %H:%M:%S"))
    file_logger.info("=" * 60)

    try:
        file_logger.info("最终 SubmitJob 请求体: %s", json.dumps(request_body, ensure_ascii=False))
        # 调用接口
        response_body = call_submit_job_api(request_body)

        # 记录完整响应
        file_logger.info("SubmitJob 接口响应: %s", json.dumps(response_body, ensure_ascii=False))

        # 解析统一响应结构
        is_ok, error_code, error_message, result, _ = parse_api_response(response_body)

        if not is_ok:
            loggers_error([file_logger, console_logger],
                "SubmitJob 调用异常，Error.Code=%s, Error.Message=%s",
                error_code,
                error_message,
            )
            sys.exit(1)

        # response_body是一个json字符串，解析成SubmitJobResponse对象
        submit_job_response = SubmitJobResponse.from_dict(response_body)

        job_id = submit_job_response.Result.JobId
        if not job_id:
            file_logger.error("SubmitJob 返回成功但未包含 JobId 字段")
            loggers_error([file_logger, console_logger],
                json.dumps(
                    {
                        "ErrorCode": "MissingJobId",
                        "ErrorMessage": "Result 中未包含 JobId 字段",
                    },
                    ensure_ascii=False,
                )
            )
            sys.exit(1)

        end_time = datetime.datetime.now()
        duration = (end_time - start_time).total_seconds()
        file_logger.info("=" * 60)
        file_logger.info(
            "submit_job 程序执行成功 - %s", end_time.strftime("%Y-%m-%d %H:%M:%S")
        )
        file_logger.info("执行耗时: %.2f 秒", duration)
        file_logger.info("=" * 60)
        loggers_info([file_logger, console_logger], "SubmitJob 调用成功，JobId=%s", job_id)
        process =subprocess.Popen(
            ["python3", os.path.join(current_dir, "wait_job_result.py"), "--JobId", job_id],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
            close_fds=True,
        )
        time.sleep(1)
        status = process.poll()
        if status is not None:
            loggers_error([file_logger, console_logger], "wait_job_result.py 子进程执行失败，状态码=%s，JobId=%s", status, job_id)
        return job_id

    except Exception as exc:  # pragma: no cover - 兜底异常日志
        end_time = datetime.datetime.now()
        duration = (end_time - start_time).total_seconds()
        loggers_exception([file_logger, console_logger], exc)
        file_logger.error("执行耗时: %.2f 秒", duration)
        file_logger.error("=" * 60)
        flush_loggers()
        raise
    flush_loggers()

if __name__ == "__main__":
    print_openclaw_session_env(file_logger)
    # 跳过环境变量校验，直接执行
    if not notify.validate_env_variables(file_logger):
        file_logger.error("环境变量校验失败，请参考错误输出，检查哪些变量没有传递，重新提交命令")
        sys.exit(1)

    main()