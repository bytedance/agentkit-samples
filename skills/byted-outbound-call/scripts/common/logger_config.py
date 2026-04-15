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
"""公共日志配置模块。

日志目录：位于当前文件父目录的父目录下的 logs 目录，即：
<项目根目录>/logs/

使用 TimedRotatingFileHandler 按天切分日志文件，并同时输出到控制台。
"""

import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Optional

_LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def _get_logs_dir() -> Path:
    """获取 logs 目录路径并确保其存在。

    日志目录相对当前脚本文件的父级目录上一级：
    common/logger_config.py 的上一级目录为项目根目录，日志目录为 <项目根目录>/../logs。
    """
    base_dir = Path(__file__).resolve().parent.parent.parent
    logs_dir = base_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir


def get_file_logger(name: str, *, level: int = logging.INFO) -> logging.Logger:
    """获取带有按天切分文件 handler 的 logger。

    日志文件路径为：<项目根目录>/logs/{name}.log。
    多次调用同名 logger 时不会重复添加 handlers。
    """
    logger = logging.getLogger(name)

    # 避免重复添加 handler
    if logger.handlers:
        return logger

    logger.setLevel(level)

    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    # 文件输出，按天切分
    logs_dir = _get_logs_dir()
    log_file = logs_dir / f"{name}.log"

    file_handler = TimedRotatingFileHandler(
        filename=log_file,
        when="midnight",
        interval=1,
        backupCount=7,
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # 防止日志向 root logger 传播导致重复输出
    logger.propagate = False

    return logger


def get_console_logger(level: int = logging.INFO) -> logging.Logger:
    """获取仅输出到控制台的 logger。"""
    logger = logging.getLogger("console")
    # 避免重复添加 handler
    if logger.handlers:
        return logger

    logger.setLevel(level)

    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    # 控制台输出
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    # 防止日志向 root logger 传播导致重复输出
    logger.propagate = False

    return logger

def loggers_info(logs: list[logging.Logger], msg: str, *args, **kwargs) -> None:
    """日志记录器，同时记录到多个 logger。"""
    for logger in logs:
        logger.info(msg, *args, **kwargs)

def loggers_error(logs: list[logging.Logger], msg: str, *args, **kwargs) -> None:
    """日志记录器，同时记录到多个 logger。"""
    for logger in logs:
        logger.error(msg, *args, **kwargs)

def loggers_exception(logs: list[logging.Logger], exc: Exception) -> None:
    """日志记录器，同时记录到多个 logger。"""
    for logger in logs:
        logger.exception(exc)
       

def flush_loggers() -> None:
    """刷新所有 logger 的 handlers。"""
    for handler in logging.root.handlers:
        handler.flush()