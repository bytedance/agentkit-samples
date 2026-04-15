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
import subprocess
from typing import Any, Dict, Optional, Tuple
import sys
import os
import shlex

# 添加scripts目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.logger_config import get_file_logger, get_console_logger, loggers_error, loggers_exception
from common.utils import print_openclaw_session_env
from schemas.service.job_status import JobStatus
from schemas.service.call_result import CallResult

file_logger = get_file_logger("notify")
console_logger = get_console_logger()


def execute_local_shell_command(logger, command) -> Tuple[bool, str]:
    """执行本地shell命令并记录相关日志

    Args:
        logger: 日志记录器
        command: 要执行的shell命令

    Returns:
        Tuple[bool, str]: (执行是否成功, 命令输出或错误信息)
    """
    logger.info(f"开始执行本地shell命令: {command}")

    try:
        # 执行shell命令
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30  # 30秒超时
        )

        # 记录命令执行结果
        if result.returncode == 0:
            logger.info(f"命令执行成功，返回码: {result.returncode}")
            logger.info(f"命令输出: {result.stdout}")

            # 如果输出内容较长，只记录前500个字符
            if len(result.stdout) > 500:
                logger.info(f"命令输出(截断): {result.stdout[:500]}...")

            return True, result.stdout
        else:
            logger.error(f"命令执行失败，返回码: {result.returncode}")
            logger.error(f"错误输出: {result.stderr}")
            return False, result.stderr

    except subprocess.TimeoutExpired:
        logger.error(f"命令执行超时: {command}")
        return False, "命令执行超时"
    except Exception as e:
        logger.error(f"命令执行异常: {str(e)}")
        return False, str(e)

# 校验环境变量
def validate_env_variables(logger) -> bool:
    """校验必要的环境变量是否存在

    Args:
        logger: 日志记录器

    Returns:
        bool: 如果所有必要变量都存在则返回True，否则返回False
    """
    # 获取当前消息通道
    current_channel = os.getenv("OPENCLAW_CHANNEL", "unknown")
    # 当前请求的用户唯一ID
    user_id = os.getenv("OPENCLAW_USER_ID", "unknown")
    # 当前请求的会话id
    session_id = os.getenv("OPENCLAW_SESSION_ID", "unknown")

    print_openclaw_session_env(logger)

    if current_channel == "unknown" or current_channel is None or current_channel.strip() == "":
        loggers_error([console_logger, logger], "通道未知，无法发送消息, OPENCLAW_CHANNEL={current_channel}有问题，请检查，否则消息会发送失败")
        return False
    elif current_channel == "webchat":
        if session_id == "unknown":
            loggers_error([console_logger, logger], "会话id未知，环境变量OPENCLAW_SESSION_ID未获取到值，无法发送消息")
            return False
        if session_id == "no_need":
            loggers_error([console_logger, logger], "当前渠道是webchat，必须获取到会话id，将其赋给环境变量OPENCLAW_SESSION_ID，否则无法发送消息")
            return False
        if session_id.startswith("agent:"):
            loggers_error([console_logger, logger], "会话id格式错误，必须从sessions_list命令中获取当前会话的session_id")
            return False
        if user_id == "unknown":
            loggers_error([console_logger, logger], "用户唯一ID未知，环境变量OPENCLAW_USER_ID未获取到值，无法发送消息")
            return False
    return True

def send_message(
        job_id: str,
        status: Optional[int],
        detail: Optional[Dict[str, Any]],
        error: Optional[Dict[str, Any]],
) -> None:
    """发送消息的占位方法。

    由业务方实现具体的消息发送逻辑，例如推送到 IM 或内部通知系统。
    当前方法留空，仅保留参数签名。
    """

    file_logger.info(
        "准备发送消息，JobId=%s, Status=%s, Detail=%s, Error=%s",
        job_id, status, detail, error
    )

    if not validate_env_variables(file_logger):
        loggers_error([console_logger, file_logger], "环境变量校验失败，无法发送消息")
        sys.exit(1)

    # 获取当前消息通道
    current_channel = os.getenv("OPENCLAW_CHANNEL", "unknown")
    # 当前请求的用户唯一ID
    user_id = os.getenv("OPENCLAW_USER_ID", "unknown")
    # 当前请求的会话id
    session_id = os.getenv("OPENCLAW_SESSION_ID", "unknown")

    print_openclaw_session_env(file_logger)

    call_result_desc = None
    summary = None
    if status == JobStatus.JobFinished:
        call_result_desc = CallResult.get_call_result_description(detail['CallResult'])
        if detail['CallResult'] == CallResult.Connected:
            summary = detail['Summary']

    info = ""
    if call_result_desc is not None:
        info += f'接通状态: {call_result_desc}\n'
    if summary is not None:
        info += f'\n\n\n{summary}\n'
    
    message = ""
    if error is not None:
        message = f'等待外呼任务(JobId: {job_id})完成的过程出现异常，请手动查询外呼任务执行结果。错误信息: {error}'
    else:
        message = f'任务ID: {job_id}\n任务状态: {JobStatus.get_job_status_description(status)}\n'
        message += info
    
    if current_channel == "unknown" or current_channel is None or current_channel.strip() == "":
        loggers_error([console_logger, file_logger], "通道未知，无法发送消息, OPENCLAW_CHANNEL={current_channel}有问题，请检查，否则消息会发送失败")
        return
    elif current_channel == "webchat":
        if session_id == "unknown":
            loggers_error([console_logger, file_logger], "会话Key未知，无法发送消息")
            return
        command_format = "openclaw agent --session-id %s --message %s --deliver"
        command = command_format % (shlex.quote(session_id), shlex.quote(message))
        execute_local_shell_command(file_logger, command)
    else:
        if user_id == "unknown":
            loggers_error([console_logger, file_logger], "用户ID未知，无法发送消息")
            return

        command_format = "openclaw message send --channel %s --target user:%s --message %s"
        command = command_format % (shlex.quote(current_channel), shlex.quote(user_id), shlex.quote(message))
        execute_local_shell_command(file_logger, command)

    file_logger.info(f"消息已发送: {message}")
    return

