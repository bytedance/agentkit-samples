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
import logging
from functools import wraps
from typing import Any, Callable

from .common import to_json

logger = logging.getLogger(__name__)


def format_error(e: Exception) -> str:
    error_msg = str(e) if str(e) else f"{type(e).__name__}"
    return error_msg


def handle_errors(func: Callable) -> Callable:
    @wraps(func)
    async def wrapper(*args, **kwargs) -> str:
        try:
            result = await func(*args, **kwargs)
            if isinstance(result, str):
                return result
            if isinstance(result, list):
                if result and hasattr(result[0], 'model_dump'):
                    result = [item.model_dump() for item in result]
            elif hasattr(result, 'model_dump'):
                result = result.model_dump()
            return to_json(result)
        except Exception as e:
            error_msg = format_error(e)
            logger.error(f"Error in {func.__name__}: {error_msg}")
            return to_json({"error": error_msg})
    return wrapper


def read_only_check(func: Callable) -> Callable:
    @wraps(func)
    async def wrapper(*args, **kwargs) -> Any:
        from ..config import READ_ONLY
        if READ_ONLY:
            return to_json({"error": f"Cannot execute {func.__name__} in read-only mode"})
        return await func(*args, **kwargs)
    return wrapper
